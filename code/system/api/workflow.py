"""Shipment, acceptance and manual settlement with explicit state transitions."""
from decimal import Decimal
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied
from .models import StockBatch, Product, DeliveryRecord, SettlementCase
from .commerce_rules import allocations_for, movement, reopen_demand, restore_refunded_quantity, hard_quality_reason
from .access import supplier_ids


def order_workflow(request, pk, action):
    from .commerce import visible_orders, number, event, notice, order_data, stock_sync
    with transaction.atomic():
        o = visible_orders(request.user).select_for_update().filter(pk=pk).first()
        if not o: raise PermissionDenied('订单不属于当前工作区')
        u = request.user
        seller = u.role == 'admin' or o.product.owner_id in supplier_ids(u,'dispatch' if action=='ship' else 'manage')
        buyer = o.user_id == u.id
        if action == 'ship':
            if not seller or o.status != 'paid': raise ValidationError('只能发运已收款的待发运数量')
            if o.cases.filter(kind='supplement', status__in=['proposed', 'accepted', 'executed']).exists():
                raise ValidationError('补充款项尚未完成核对，暂不能发运')
            carrier, tracking = str(request.data.get('carrier', '')).strip(), str(request.data.get('tracking_number', '')).strip()
            if not carrier or not tracking: raise ValidationError('请填写承运方和运单号')
            rows = allocations_for(o, True)
            remaining = sum(a.quantity-a.dispatched for a in rows)
            qty = number(request.data.get('quantity', remaining), Decimal('.01'), remaining)
            batches = {b.id: b for b in StockBatch.objects.select_for_update().filter(
                pk__in=[a.batch_id for a in rows]).order_by('id')}
            parts, todo = [], qty
            for a in rows:
                if not todo: break
                take = min(todo, a.quantity-a.dispatched)
                if not take: continue
                b = batches[a.batch_id]
                if b.status != 'released' or hard_quality_reason(b) or b.quantity < take or b.reserved < take:
                    raise ValidationError(f'{b.code} 尚未放行或预留不足，请先补配')
                if b.available_date and b.available_date > timezone.localdate():
                    raise ValidationError(f'{b.code} 尚未到可发货日期')
                if b.removal_date and b.removal_date < timezone.localdate():
                    raise ValidationError(f'{b.code} 已超过录入的移出日期')
                b.quantity -= take; b.reserved -= take; b.save()
                movement(b, u, 'dispatch', -take, -take, o, tracking)
                stock_sync(b.product)
                a.dispatched += take; a.save(update_fields=['dispatched'])
                parts.append({'batch_id': b.id, 'code': b.code, 'quantity': float(take)})
                todo -= take
            delivery = DeliveryRecord.objects.create(order=o, actor=u, quantity=qty,
                allocations=parts, carrier=carrier[:100], tracking_number=tracking[:120])
            o.carrier, o.tracking_number = carrier[:100], tracking[:100]
            o.status = 'shipped' if qty == remaining else 'paid'
            event(o, u, '分批发运已登记', f'{qty}{o.snapshot.get("unit", "")} · {carrier} · {tracking}')
            notice(o.user, f'订单 #{o.id} 有新发运', f'{qty}{o.snapshot.get("unit", "")}', f'/orders?order={o.id}')
        elif action == 'receive':
            if not buyer or o.status not in ['paid', 'shipped', 'issue']:
                raise ValidationError('只有采购方可验收已发运货物')
            if o.quantity is None: raise ValidationError('历史数量未知，请先与供应方核对')
            deliveries = o.deliveries.select_for_update().filter(status='shipped')
            delivery = deliveries.filter(pk=request.data.get('delivery_id')).first() if request.data.get('delivery_id') else deliveries.first()
            if o.deliveries.exists() and not delivery: raise ValidationError('请选择尚未验收的发运单')
            if not delivery and o.status != 'shipped': raise ValidationError('尚无可验收的发运记录')
            maximum = delivery.quantity if delivery else o.quantity
            good = number(request.data.get('accepted_quantity'), Decimal(0), maximum)
            received = number(request.data.get('received_quantity', maximum), good, maximum)
            note = str(request.data.get('note', '')).strip()
            quality = str(request.data.get('quality_issue', '')).strip()[:1000]
            packaging = str(request.data.get('packaging_issue', '')).strip()[:500]
            issue = good < maximum or bool(quality or packaging)
            if issue and not (note or quality or packaging): raise ValidationError('请填写短重、拒收或品质差异原因')
            receipt = {'received': float(received), 'accepted': float(good), 'rejected': float(received-good),
                'shortage': float(maximum-received), 'quality_issue': quality, 'packaging_issue': packaging,
                'note': note[:2000], 'actor': u.username, 'time': timezone.now().isoformat()}
            if delivery:
                delivery.receipt, delivery.status, delivery.received_at = receipt, 'received', timezone.now()
                delivery.save()
                all_receipts = list(o.deliveries.filter(status='received').values_list('receipt', flat=True))
                accepted = sum(Decimal(str(x.get('accepted', 0))) for x in all_receipts)
                received_total = sum(Decimal(str(x.get('received', 0))) for x in all_receipts)
                shipped = sum(a.dispatched for a in allocations_for(o))
                done = shipped == o.quantity and not o.deliveries.filter(status='shipped').exists()
            else:
                accepted, received_total, done = good, received, True
            o.accepted_quantity = accepted
            o.receipt = {'received': float(received_total), 'accepted': float(accepted), 'latest': receipt}
            o.issue = '\n'.join(x for x in [o.issue, quality, packaging, note if issue else ''] if x)[:4000]
            o.status = 'issue' if issue or o.issue else ('completed' if done else 'paid' if shipped < o.quantity else 'shipped')
            event(o, u, '到货验收存在差异' if issue else '到货验收已记录',
                f'实收 {received}，合格 {good}，拒收 {received-good}；{quality or note}')
            notice(o.product.owner, f'订单 #{o.id} 验收已更新', o.issue, f'/orders?order={o.id}')
            if o.product and good:
                Product.objects.filter(pk=o.product_id).update(sales_count=F('sales_count')+int(good))
        elif action == 'resolve':
            if not seller or o.status != 'issue': raise ValidationError('当前无可处理的验收差异')
            kind = request.data.get('kind', 'discount')
            if kind not in ['discount', 'refund', 'replacement', 'return']: raise ValidationError('请选择处理方式')
            note = str(request.data.get('note', '')).strip()
            if not note: raise ValidationError('请说明处理依据')
            if o.cases.exclude(status__in=['confirmed', 'rejected']).exists(): raise ValidationError('已有处理方案待确认')
            supplements=sum(c.amount for c in o.cases.filter(kind='supplement',status='confirmed'))
            refunds=sum(c.amount for c in o.cases.filter(kind__in=['refund','discount'],status='confirmed'))
            refundable=max(Decimal(0),o.total_amount+supplements-refunds)
            amount = number(request.data.get('amount', 0), Decimal(0), refundable)
            qty = number(request.data.get('quantity', 0), Decimal(0), o.quantity or 0)
            if kind == 'replacement' and qty <= 0: raise ValidationError('请填写补发数量')
            if kind in ['discount', 'refund'] and amount <= 0: raise ValidationError('请填写实际退款或折让金额')
            case = SettlementCase.objects.create(order=o, creator=u, kind=kind, quantity=qty, amount=amount,
                note=note[:2000], events=[{'action': 'proposed', 'actor': u.username, 'time': timezone.now().isoformat()}])
            o.resolution = f'{kind} · {note}'
            event(o, u, '提出结构化处理方案', f'处理单 #{case.id} · 数量 {qty} · 金额 {amount}')
            notice(o.user, f'订单 #{o.id} 处理方案待确认', note[:300], f'/orders?order={o.id}')
        else:
            raise ValidationError('请在处理单中确认方案、执行凭证及最终结果，不能只凭文字结案')
        o.version += 1
        o.save()
        return Response(order_data(o))


def case_action(request, pk):
    from .commerce import visible_orders, notice, event, order_data, stock_sync
    from .models import Order
    with transaction.atomic():
        c = SettlementCase.objects.select_for_update().select_related('order__product__owner').filter(pk=pk,
            order_id__in=visible_orders(request.user).values('id')).first()
        if not c: raise PermissionDenied('处理单不存在或不属于当前账号')
        o = Order.objects.select_for_update().get(pk=c.order_id)
        buyer, seller = o.user_id == request.user.id, request.user.role == 'admin' or o.product.owner_id in supplier_ids(request.user,'manage')
        action = request.data.get('action')
        if action in ['accept', 'reject']:
            if c.status != 'proposed' or not buyer or c.kind == 'supplement':
                raise ValidationError('当前不可确认此方案')
            c.status = 'accepted' if action == 'accept' else 'rejected'
        elif action == 'execute':
            payer = buyer if c.kind == 'supplement' else seller
            if c.status != 'accepted' or not payer: raise ValidationError('请由执行方在方案确认后登记凭证')
            reference = str(request.data.get('reference', '')).strip()
            if len(reference) < 4: raise ValidationError('请填写实际流水号、退货交接或补发单号')
            if c.kind == 'replacement':
                b = StockBatch.objects.select_for_update().select_related('product').get(pk=request.data.get('batch_id'))
                if b.product.owner_id != o.product.owner_id or b.product_id != o.product_id or b.status != 'released' or hard_quality_reason(b) or b.quantity-b.reserved < c.quantity:
                    raise ValidationError('补发批次必须为原供应方同商品的可售库存')
                b.quantity -= c.quantity; b.save()
                movement(b, request.user, 'replacement', -c.quantity, order=o, note=reference)
                stock_sync(b.product)
            c.reference, c.status = reference[:200], 'executed'
        elif action == 'confirm':
            recipient = seller if c.kind == 'supplement' else buyer
            if c.status != 'executed' or not recipient: raise ValidationError('请由接收方核对执行结果后确认')
            if c.kind in ['discount', 'refund']:
                previous = sum(x.amount for x in o.cases.filter(kind__in=['discount','refund'], status='confirmed'))
                supplements=sum(x.amount for x in o.cases.filter(kind='supplement',status='confirmed'))
                if previous+c.amount > o.total_amount+supplements: raise ValidationError('累计退款不能超过已核对的订单与补款金额')
            c.status = 'confirmed'
            if c.kind == 'replacement':
                o.accepted_quantity = min(o.quantity, (o.accepted_quantity or 0)+c.quantity)
            remaining_cases = o.cases.exclude(pk=c.pk).exclude(status__in=['confirmed', 'rejected']).exists()
            if o.status == 'issue' and not remaining_cases:
                shipped = sum(a.dispatched for a in allocations_for(o))
                o.issue=''
                o.status='paid' if shipped<(o.quantity or 0) else 'shipped' if o.deliveries.filter(status='shipped').exists() else 'completed'
            if c.kind=='refund' and c.quantity>0:restore_refunded_quantity(o,c.quantity)
            if c.kind == 'refund' and c.amount == o.total_amount:
                o.status = 'refunded'
                # Reopen only the quantity that was not fulfilled; do not erase delivered history.
                if not o.accepted_quantity: reopen_demand(o)
        else: raise ValidationError('不支持的处理动作')
        c.events = [*c.events, {'action': action, 'actor': request.user.username, 'time': timezone.now().isoformat()}]
        c.save()
        event(o, request.user, f'处理单 #{c.id} 已更新', f'{c.kind} · {c.status} · {c.reference}')
        o.version += 1; o.save()
        for uid in {o.user_id, o.product.owner_id}-{request.user.id}:
            from .models import User
            notice(User.objects.get(pk=uid), f'订单 #{o.id} 处理进度更新', c.note[:200], f'/orders?order={o.id}')
        return Response(order_data(o))
