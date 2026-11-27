"""Shared objects joining procurement, physical work and financial confirmation."""
from datetime import datetime, time
from decimal import Decimal, ROUND_CEILING
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from .access import buyer_ids, supplier_ids
from .models import (BusinessEvent, Company, ProcurementSheet, PurposeYieldRecord,
    FulfilmentTask, WorkspaceNotification, OrderAllocation, WeightReconciliation,
    SupplierSettlement, SettlementCase)

TASK_NAMES = {'pick': '分拣备货', 'dispatch': '装车发运', 'receive': '到货验收',
              'replacement': '补发验收', 'return': '退货交接'}


def visible_sheets(user, action='read'):
    qs = ProcurementSheet.objects.select_related('buyer', 'company', 'creator')
    if user.role == 'admin':
        return qs
    if user.role == 'supplier':
        return qs.filter(Q(orders__product__owner_id__in=supplier_ids(user)) |
            Q(orders__allocations__batch__product__owner_id__in=supplier_ids(user))).distinct()
    return qs.filter(buyer_id__in=buyer_ids(user, action))


def visible_tasks(user):
    qs = FulfilmentTask.objects.select_related('order__product__owner', 'order__user',
        'batch__product', 'supplier', 'assignee', 'site', 'delivery')
    if user.role == 'admin':
        return qs
    if user.role == 'supplier':
        return qs.filter(Q(supplier_id__in=supplier_ids(user)) | Q(assignee=user))
    return qs.filter(order__user_id__in=buyer_ids(user), kind__in=['receive', 'replacement', 'return'])


def order_due(order):
    date = order.promised_date
    if date:
        return timezone.make_aware(datetime.combine(date, time(23, 59)))
    return None


def close_task(task, actor, note='', status='done'):
    if task.status in ['done', 'cancelled']:
        return
    task.status = status
    task.version += 1
    task.events = [*task.events, {'action': status, 'actor': actor.username,
        'note': note, 'time': timezone.now().isoformat()}]
    task.save()
    task.notifications.update(read=True, resolved=True)


def sync_order_tasks(order, actor):
    """Call after business writes; task completion never fabricates shipment / receipt."""
    if order.status in ['cancelled', 'refunded']:
        for task in order.tasks.exclude(status__in=['done', 'cancelled']):
            close_task(task, actor, '关联订单已关闭', 'cancelled')
        return
    if order.payment_status == 'confirmed':
        for allocation in order.allocations.select_related('batch__product'):
            remaining = allocation.quantity-allocation.dispatched
            for kind in ['pick', 'dispatch']:
                key = f'{kind}:{order.id}:{allocation.id}'
                if remaining <= 0:
                    for task in order.tasks.filter(source_key=key).exclude(status__in=['done', 'cancelled']):
                        close_task(task, actor, '本项发运已登记')
                    continue
                task, created = FulfilmentTask.objects.get_or_create(source_key=key, defaults={
                    'order': order, 'batch': allocation.batch, 'supplier': allocation.batch.product.owner,
                    'kind': kind, 'quantity': remaining, 'site': order.site, 'due_at': order_due(order),
                    'note': '按约定批次分拣与交接；发运仍须填写实际数量和单号。'})
                if created:
                    WorkspaceNotification.objects.create(recipient=task.supplier, task=task,
                        title=f'{order.id}号订单 · {TASK_NAMES[kind]}', content=allocation.batch.code,
                        route=f'/workboard?task={task.id}')
                elif task.status not in ['done', 'cancelled'] and task.quantity != remaining:
                    task.quantity = remaining
                    task.version += 1
                    task.save(update_fields=['quantity', 'version', 'updated_at'])
    valid_batches = order.allocations.values_list('batch_id', flat=True)
    for task in order.tasks.filter(kind__in=['pick', 'dispatch']).exclude(batch_id__in=valid_batches).exclude(status__in=['done', 'cancelled']):
        close_task(task, actor, '履约批次已由确认方案替换', 'cancelled')
    for delivery in order.deliveries.all():
        kind = 'replacement' if delivery.kind == 'replacement' else 'receive'
        task, created = FulfilmentTask.objects.get_or_create(source_key=f'receive:{delivery.id}', defaults={
            'order': order, 'delivery': delivery, 'supplier': delivery.supplier,
            'site': order.site, 'kind': kind, 'quantity': delivery.physical_quantity or delivery.quantity,
            'due_at': order_due(order), 'note': f'{delivery.carrier} / {delivery.tracking_number}'})
        if created:
            WorkspaceNotification.objects.create(recipient=order.user, task=task,
                title=f'{order.id}号订单 · {TASK_NAMES[kind]}', content=task.note,
                route=f'/workboard?task={task.id}')
        if delivery.status == 'received':
            close_task(task, actor, '实际验收记录已保存')


def yield_data(batch, purpose, process=''):
    qs = batch.yield_records.filter(purpose=purpose)
    if process:
        qs = qs.filter(process=process)
    record = qs.order_by('-created_at', '-id').first()
    if not record:
        return None
    return {'id': record.id, 'purpose': record.purpose, 'process': record.process,
        'input_weight': float(record.input_weight), 'usable_weight': float(record.usable_weight),
        'rate': float(record.usable_weight/record.input_weight), 'scope': record.scope,
        'note': record.note, 'created_at': record.created_at,
        'source': '演示称重参数' if batch.product.is_demo else '整批实称' if record.scope == 'whole' else '样本实称估算'}


def net_options(user, data):
    from types import SimpleNamespace
    from datetime import timedelta
    from .commerce import number, day, integer, batch_data
    from .commerce_rules import assess, price_for, json_price, hard_quality_reason
    from .models import StockBatch
    target = number(data.get('required_usable'), Decimal('.01'))
    purpose = data.get('purpose', 'kitchen')
    keyword = str(data.get('keyword', '')).strip()
    unit = data.get('unit', 'kg')
    if unit not in ['kg', '斤']:
        raise ValidationError('净用量采购需使用 kg 或斤；箱和件请使用已确认的商品数量')
    rows = []
    batches = StockBatch.objects.select_related('product__owner').prefetch_related('product__price_tiers', 'yield_records').filter(
        product__is_deleted=False, product__status='on_sale').order_by('id')
    for b in batches[:300]:
        p = b.product
        if keyword and keyword.lower() not in (p.name+' '+p.variety).lower():
            continue
        if p.unit != unit:
            continue
        evidence = yield_data(b, purpose, str(data.get('process', '')).strip())
        available = max(Decimal(0), b.quantity-b.reserved) if b.status == 'released' and not hard_quality_reason(b) else Decimal(0)
        row = {'batch': batch_data(b), 'evidence': evidence, 'required_usable': float(target)}
        if not evidence or evidence['rate'] <= 0:
            rows.append({**row, 'gross': None, 'usable': None, 'net_cost': None, 'compatible': False,
                         'issues': ['缺少该用途、加工方式的可用重量记录']})
            continue
        rate = Decimal(str(evidence['rate']))
        step = Decimal(str(p.quantity_step))
        required = (max(Decimal(p.min_order),target/rate)/step).to_integral_value(rounding=ROUND_CEILING)*step
        proxy = SimpleNamespace(keyword=keyword, unit=unit, min_size=integer(data.get('min_size', 0), 0, 2000),
            grade=data.get('grade', ''), packaging=data.get('packaging', ''), quantity=required,
            budget=number(data.get('budget', 100), Decimal('.01')), deadline=day(data.get('deadline'), timezone.localdate()+timedelta(days=7)),
            tolerance=float(number(data.get('tolerance', 10), maximum=100)), flexible_fields=[], purpose=purpose)
        issues = [x['reason'] for x in assess(b, proxy, required)]
        if required > available:
            issues.append('按当前净得率不能覆盖本次净用量')
        costs = price_for(p, required, batch=b)
        usable = required*rate
        rows.append({**row, 'gross': float(required), 'usable': float(usable), 'overage': float(max(Decimal(0), usable-target)),
            'pricing': json_price(costs), 'net_cost': round(float(costs['total']/usable), 2),
            'compatible': not issues, 'issues': issues})
    rows.sort(key=lambda r: (not r['compatible'], r.get('net_cost') if r.get('net_cost') is not None else float('inf')))
    return {'rows': rows, 'purpose': purpose, 'required_usable': float(target), 'unit': unit,
        'note': '按对应加工方式的实称比率反算；样本估算与演示参数分别标识，实际交付仍以验收为准。'}


def task_data(task):
    o = task.order
    return {'id': task.id, 'order_id': o.id, 'number': f'HL{o.created_at:%y%m%d}{o.id:05d}',
        'product': o.snapshot.get('name', o.product.name if o.product else '历史商品'),
        'batch_id': task.batch_id, 'batch_code': task.batch.code if task.batch else '',
        'supplier_id': task.supplier_id, 'supplier': task.supplier.username if task.supplier else '',
        'buyer_id': o.user_id, 'buyer': o.user.username, 'assignee_id': task.assignee_id,
        'assignee': task.assignee.username if task.assignee else '', 'kind': task.kind,
        'kind_label': TASK_NAMES.get(task.kind, task.kind), 'status': task.status, 'quantity': float(task.quantity),
        'unit': o.snapshot.get('unit', ''), 'due_at': task.due_at, 'overdue': bool(task.due_at and task.due_at < timezone.now() and task.status not in ['done', 'cancelled']),
        'site_id': task.site_id, 'site': task.site.name if task.site else '', 'address': o.address_info,
        'delivery_id': task.delivery_id, 'note': task.note, 'evidence': task.evidence,
        'events': task.events, 'version': task.version, 'is_demo': o.is_demo, 'updated_at': task.updated_at}


def reconcile_delivery(order, delivery, actor, receipt):
    if order.settlement_basis != 'accepted_weight' or delivery.kind != 'normal':
        return
    expected = delivery.quantity
    accepted = Decimal(str(receipt['accepted']))
    difference = ((accepted-expected)*order.unit_price_at_purchase).quantize(Decimal('.01'))
    WeightReconciliation.objects.create(order=order, delivery=delivery, creator=actor,
        expected_quantity=expected, received_quantity=Decimal(str(receipt['received'])),
        accepted_quantity=accepted, difference_amount=difference,
        note='按成交单价核对本次合格实收量；包装、运费依原约定，需供应方确认重量后再处理尾差。')


def settlement_data(record):
    return {'id': record.id, 'order_id': record.order_id, 'payer_id': record.payer_id,
        'payer': record.payer.username, 'supplier_id': record.supplier_id, 'supplier': record.supplier.username,
        'quantity': float(record.quantity), 'amount': float(record.amount), 'status': record.status,
        'reference': record.reference, 'events': record.events, 'created_at': record.created_at}
