"""Physical shipment and acceptance. Invoked under the order transaction lock."""
from decimal import Decimal
from django.db.models import F
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied
from .models import StockBatch, Product, DeliveryRecord
from .access import supplier_ids, buyer_ids
from .commerce_rules import allocations_for, movement, hard_quality_reason
from .coordination import reconcile_delivery


def finish_order_if_clear(order, resolved=False):
    if order.status in ['cancelled', 'refunded']:
        return
    if order.cases.exclude(status__in=['confirmed', 'rejected']).exists() or order.reconciliations.exclude(status='confirmed').exists():
        order.status = 'issue'
        return
    if order.issue and not resolved:
        order.status = 'issue'
        return
    if resolved:
        order.issue = ''
    shipped = sum(a.dispatched for a in allocations_for(order))
    order.status = 'paid' if shipped < (order.quantity or 0) else 'shipped' if order.deliveries.filter(status='shipped').exists() else 'completed'


def weighing(data, unit):
    from .commerce import number
    if data.get('gross_weight') is None and data.get('tare_weight') is None:
        return None
    if unit not in ['kg', '斤']:
        raise ValidationError('箱和件不能隐含换算重量，请按约定计量单位操作')
    gross = number(data.get('gross_weight'), Decimal('.01'))
    tare = number(data.get('tare_weight'), maximum=gross)
    return {'gross': float(gross), 'tare': float(tare), 'net': float(gross-tare), 'unit': unit}


def transport_action(request, o, action):
    from .commerce import number, event, notice, order_data, stock_sync
    u = request.user
    if action == 'ship':
        if o.status != 'paid':
            raise ValidationError('只能发运已核对收款的待发运订单')
        if o.cases.filter(kind='supplement', status__in=['proposed', 'accepted', 'executed']).exists():
            raise ValidationError('补充款项尚未完成核对，请先处理')
        carrier, tracking = str(request.data.get('carrier', '')).strip(), str(request.data.get('tracking_number', '')).strip()
        if not carrier or not tracking:
            raise ValidationError('请填写实际承运方和配送单号')
        all_rows = allocations_for(o, True)
        allowed = [a for a in all_rows if u.role == 'admin' or a.batch.product.owner_id in supplier_ids(u, 'dispatch')]
        owners = {a.batch.product.owner_id for a in allowed if a.quantity > a.dispatched}
        try:
            chosen = int(request.data.get('supplier_id') or (next(iter(owners)) if len(owners) == 1 else 0))
        except (TypeError, ValueError):
            raise ValidationError('履约供货方不正确')
        if chosen not in owners:
            raise PermissionDenied('请选择本次实际履约的供货方')
        if o.supplier_settlements.filter(supplier_id=chosen).exclude(status__in=['confirmed', 'cancelled']).exists():
            raise ValidationError('替代供货款项尚未完成双方核对，请先在对账中心处理')
        rows = [a for a in allowed if a.batch.product.owner_id == chosen]
        remaining = sum(a.quantity-a.dispatched for a in rows)
        qty = number(request.data.get('quantity', remaining), Decimal('.01'), remaining)
        measured = weighing(request.data, o.snapshot.get('unit'))
        physical = Decimal(str(measured['net'])) if measured else qty
        if physical <= 0 or abs(physical-qty) > qty*o.weight_tolerance_pct/100+Decimal('.005'):
            raise ValidationError('装车净重须大于0且在买方确认的数量允差内，请调整分装或重新协商')
        batches = {b.id: b for b in StockBatch.objects.select_for_update().filter(pk__in=[a.batch_id for a in rows]).order_by('id')}
        parts, todo, actual_left = [], qty, physical
        for a in rows:
            if not todo:
                break
            take = min(todo, a.quantity-a.dispatched)
            if not take:
                continue
            actual = actual_left if take == todo else (physical*take/qty).quantize(Decimal('.01'))
            b = batches[a.batch_id]
            if b.status != 'released' or hard_quality_reason(b) or b.reserved < take or b.quantity-actual < b.reserved-take:
                raise ValidationError(f'{b.code} 未放行、实际库存或预留不足，请先核实或补配')
            if b.available_date and b.available_date > timezone.localdate():
                raise ValidationError(f'{b.code} 尚未到可发运日期')
            b.quantity -= actual
            b.reserved -= take
            b.save()
            movement(b, u, 'dispatch', -actual, -take, o, tracking)
            stock_sync(b.product)
            a.dispatched += take
            a.save(update_fields=['dispatched'])
            parts.append({'batch_id': b.id, 'code': b.code, 'quantity': float(take), 'physical_quantity': float(actual)})
            todo -= take
            actual_left -= actual
        DeliveryRecord.objects.create(order=o, actor=u, supplier_id=chosen, quantity=qty, physical_quantity=physical,
            weighing=measured or {}, allocations=parts, carrier=carrier[:100], tracking_number=tracking[:120])
        o.carrier, o.tracking_number = carrier[:100], tracking[:100]
        o.status = 'shipped' if sum(a.quantity-a.dispatched for a in allocations_for(o)) <= 0 else 'paid'
        event(o, u, '实际发运已登记', f'约定 {qty}，实际 {physical}{o.snapshot.get("unit", "")} · {tracking}')
        notice(o.user, f'订单 #{o.id} 有新发运', tracking, f'/orders?order={o.id}')
    else:
        if o.user_id not in buyer_ids(u, 'receive') or o.status not in ['paid', 'shipped', 'issue']:
            raise PermissionDenied('请由收货岗位验收已发运货物')
        ds = o.deliveries.select_for_update().filter(status='shipped')
        d = ds.filter(pk=request.data.get('delivery_id')).first() if request.data.get('delivery_id') else ds.order_by('id').first()
        if not d:
            raise ValidationError('请选择尚未验收的发运单；历史订单请先补齐发运记录')
        measured = weighing(request.data, o.snapshot.get('unit'))
        received = Decimal(str(measured['net'])) if measured else number(request.data.get('received_quantity'), Decimal(0))
        good = number(request.data.get('accepted_quantity'), maximum=received)
        note = str(request.data.get('note', '')).strip()[:2000]
        quality = str(request.data.get('quality_issue', '')).strip()[:1000]
        packaging = str(request.data.get('packaging_issue', '')).strip()[:500]
        outside = abs(received-d.quantity) > d.quantity*o.weight_tolerance_pct/100+Decimal('.005')
        issue = good < received or bool(quality or packaging) or outside or (o.settlement_basis == 'contract' and good < d.quantity)
        if issue and not (note or quality or packaging):
            raise ValidationError('请记录超出允差、拒收或品质差异的依据')
        receipt = {'expected': float(d.quantity), 'received': float(received), 'accepted': float(good),
            'rejected': float(received-good), 'shortage': float(max(Decimal(0), d.quantity-received)),
            'overage': float(max(Decimal(0), received-d.quantity)), 'outside_tolerance': outside,
            'quality_issue': quality, 'packaging_issue': packaging, 'weighing': measured or {},
            'note': note, 'actor': u.username, 'time': timezone.now().isoformat()}
        d.receipt, d.status, d.received_at = receipt, 'received', timezone.now()
        d.save()
        all_receipts = list(o.deliveries.filter(status='received').values_list('receipt', flat=True))
        o.accepted_quantity = sum(Decimal(str(x.get('accepted', 0))) for x in all_receipts)
        o.receipt = {'received': float(sum(Decimal(str(x.get('received', 0))) for x in all_receipts)),
            'accepted': float(o.accepted_quantity), 'latest': receipt}
        if issue:
            o.issue = '\n'.join(x for x in [o.issue, quality, packaging, note or '实际数量与约定存在差异'] if x)[:4000]
        reconcile_delivery(o, d, u, receipt)
        finish_order_if_clear(o)
        event(o, u, '实际验收已记录', f'实收 {received}，合格 {good}，拒收 {received-good}{o.snapshot.get("unit", "")}')
        notice(o.product.owner, f'订单 #{o.id} 验收待核对', note or quality or '验收记录已更新', f'/orders?order={o.id}')
        if o.product and good:
            Product.objects.filter(pk=o.product_id).update(sales_count=F('sales_count')+int(good))
    o.version += 1
    o.save()
    return Response(order_data(o, u))
