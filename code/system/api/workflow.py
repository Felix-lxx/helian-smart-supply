"""Shipment, acceptance and manual settlement with explicit state transitions."""
from decimal import Decimal
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied
from .models import StockBatch, Product, DeliveryRecord, SettlementCase
from .commerce_rules import allocations_for, movement, reopen_demand, restore_refunded_quantity, hard_quality_reason
from .access import supplier_ids, buyer_ids
from .transport import finish_order_if_clear


def order_workflow(request, pk, action):
    from .commerce import visible_orders, number, event, notice, order_data, stock_sync
    with transaction.atomic():
        o = visible_orders(request.user).select_for_update().filter(pk=pk).first()
        if not o: raise PermissionDenied('订单不属于当前工作区')
        u = request.user
        seller = u.role == 'admin' or o.product.owner_id in supplier_ids(u,'dispatch' if action=='ship' else 'manage')
        buyer = o.user_id in buyer_ids(u, 'receive')
        if action in ['ship', 'receive']:
            from .transport import transport_action
            return transport_action(request, o, action)
        if action == 'resolve':
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
            if kind in ['replacement','return'] and qty <= 0: raise ValidationError('请填写实际补发或退货数量')
            if kind=='replacement' and qty>max(Decimal(0),(o.quantity or 0)-(o.accepted_quantity or 0)):
                raise ValidationError('补发量超过尚未合格验收数量，已合格收货请先协调退货')
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
        return Response(order_data(o, request.user))


def case_action(request, pk):
    from .commerce import visible_orders, notice, event, order_data, stock_sync
    from .models import Order
    with transaction.atomic():
        c = SettlementCase.objects.select_for_update().select_related('order__product__owner').filter(pk=pk,
            order_id__in=visible_orders(request.user).values('id')).first()
        if not c: raise PermissionDenied('处理单不存在或不属于当前账号')
        o = Order.objects.select_for_update().get(pk=c.order_id)
        buyer, seller = o.user_id in buyer_ids(request.user, 'manage'), request.user.role == 'admin' or o.product.owner_id in supplier_ids(request.user,'manage')
        action = request.data.get('action')
        if action in ['accept', 'reject']:
            if c.status != 'proposed' or not buyer or c.kind == 'supplement':
                raise ValidationError('当前不可确认此方案')
            c.status = 'accepted' if action == 'accept' else 'rejected'
        elif action == 'execute':
            payer = buyer if c.kind in ['supplement', 'return'] else seller
            if c.status != 'accepted' or not payer: raise ValidationError('请由执行方在方案确认后登记凭证')
            reference = str(request.data.get('reference', '')).strip()
            if len(reference) < 4: raise ValidationError('请填写实际流水号、退货交接或补发单号')
            if c.kind == 'replacement':
                b = StockBatch.objects.select_for_update().select_related('product').get(pk=request.data.get('batch_id'))
                if b.product.owner_id != o.product.owner_id or b.product_id != o.product_id or b.status != 'released' or hard_quality_reason(b) or b.quantity-b.reserved < c.quantity or (b.available_date and b.available_date > timezone.localdate()):
                    raise ValidationError('补发批次必须为原供应方同商品的可售库存')
                b.quantity -= c.quantity; b.save()
                movement(b, request.user, 'replacement', -c.quantity, order=o, note=reference)
                stock_sync(b.product)
                DeliveryRecord.objects.create(order=o, actor=request.user, supplier=b.product.owner,
                    quantity=c.quantity, physical_quantity=c.quantity, kind='replacement', case=c,
                    allocations=[{'batch_id': b.id, 'code': b.code, 'quantity': float(c.quantity)}],
                    carrier=str(request.data.get('carrier') or '补发交接')[:100], tracking_number=reference[:120])
            c.reference, c.status = reference[:200], 'executed'
        elif action == 'confirm':
            recipient = seller if c.kind in ['supplement', 'return'] else buyer
            if c.status != 'executed' or not recipient: raise ValidationError('请由接收方核对执行结果后确认')
            if c.kind == 'replacement':
                deliveries = list(c.deliveries.all())
                if not deliveries or any(d.status != 'received' or Decimal(str(d.receipt.get('accepted', 0))) < d.quantity for d in deliveries):
                    raise ValidationError('请先对补发配送单完成实际验收，不以单号代替收货')
            if c.kind == 'return':
                if c.quantity <= 0:raise ValidationError('退货需明确实际接收数量')
                returned = StockBatch.objects.create(product=o.product,parent=o.batch,
                    code=f'RETURN-{c.id}-{timezone.now():%m%d%H%M%S}',quantity=c.quantity,status='quarantine',
                    grade=o.snapshot.get('grade',''),packaging=o.snapshot.get('packaging',''),
                    note=f'退货单 #{c.id} · {c.reference}；接收后隔离待复核。')
                movement(returned,request.user,'return_in',c.quantity,order=o,note=c.reference)
                c.evidence=[*c.evidence,{'return_batch_id':returned.id,'code':returned.code}]
                stock_sync(o.product)
            if c.kind in ['discount', 'refund']:
                previous = sum(x.amount for x in o.cases.filter(kind__in=['discount','refund'], status='confirmed'))
                supplements=sum(x.amount for x in o.cases.filter(kind='supplement',status='confirmed'))
                if previous+c.amount > o.total_amount+supplements: raise ValidationError('累计退款不能超过已核对的订单与补款金额')
            c.status = 'confirmed'
            remaining_cases = o.cases.exclude(pk=c.pk).exclude(status__in=['confirmed', 'rejected']).exists()
            if o.status == 'issue' and not remaining_cases:
                c.save()
                finish_order_if_clear(o,resolved=True)
            if c.kind=='refund' and c.quantity>0:restore_refunded_quantity(o,c.quantity)
            if c.kind == 'refund' and c.amount == o.total_amount:
                o.status = 'refunded'
                # Release only undelivered reservations; preserve delivered allocation history.
                for allocation in allocations_for(o,True):
                    left=allocation.quantity-allocation.dispatched
                    if left<=0:continue
                    batch=StockBatch.objects.select_for_update().get(pk=allocation.batch_id)
                    if batch.reserved<left:raise ValidationError('预留记录不一致，请先核对库存流水')
                    batch.reserved-=left;batch.save()
                    movement(batch,request.user,'refund_release',reserved=-left,order=o,note=f'全额退款 #{c.id}')
                    allocation.quantity=allocation.dispatched;allocation.save(update_fields=['quantity'])
                    stock_sync(batch.product)
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
        return Response(order_data(o, request.user))
