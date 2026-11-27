"""Shared, decimal-safe rules for every transaction entry point."""
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from .models import InventoryMovement, OrderAllocation

CENT = Decimal('.01')
PURPOSES = {'fresh': '门店鲜销', 'kitchen': '厨房加工', 'juice': '榨汁采购'}
FLEXIBLE = {'size', 'grade', 'packaging', 'budget', 'deadline'}


def hard_quality_reason(batch):
    if batch.removal_date and batch.removal_date<timezone.localdate():return '超过已录入的移出日期，需重新核实'
    for record in reversed(batch.inspections):
        metrics=record.get('metrics',{})
        if 'rot' in metrics:
            if int(metrics['rot'])>0:return '最近腐坏专项记录未解除，需隔离复核'
            break
    return ''


def price_for(product, quantity, override=None, batch=None):
    q = Decimal(str(quantity))
    step = Decimal(str(product.quantity_step))
    if q <= 0 or q < product.min_order or (step and q % step):
        raise ValidationError(f'起订 {product.min_order}{product.unit}，增量为 {step}{product.unit}')
    batch_price = batch.sale_price if batch is not None else None
    unit = Decimal(str(override if override is not None else batch_price if batch_price is not None else product.retail_price))
    if override is None and batch_price is None:
        for t in sorted(product.price_tiers.all(),key=lambda t:t.min_quantity):
            if q >= t.min_quantity:
                unit = Decimal(str(t.wholesale_price))
    goods = (q * unit).quantize(CENT)
    packaging = (q * Decimal(str(product.packaging_fee))).quantize(CENT)
    freight = Decimal(str(product.freight_fee)).quantize(CENT)
    return {'unit_price': unit, 'goods': goods, 'packaging': packaging, 'freight': freight,
            'total': goods+packaging+freight, 'quantity': q,
            'expires_at': (timezone.now()+timedelta(minutes=15)).isoformat()}


def json_price(value):
    return {k: float(v) if isinstance(v, Decimal) else v for k, v in value.items()}


def assess(batch, demand, quantity=None, unit_price=None, robust=False):
    from .commerce import wilson
    p = batch.product
    issues = []
    def add(key, reason):
        issues.append({'field': key, 'reason': reason,
                       'negotiable': key in FLEXIBLE and key in demand.flexible_fields})
    if demand.keyword.lower() not in (p.name+' '+p.variety).lower(): add('keyword', '采购品种不符')
    if p.unit != demand.unit: add('unit', '计量单位不同，未自动换算')
    if getattr(demand, 'required_usable', None):
        from .coordination import yield_data
        evidence = yield_data(batch, demand.purpose, getattr(demand, 'process', ''))
        if not evidence or evidence['rate'] <= 0:
            add('yield', '缺少对应用途与加工方式的称重依据')
    if batch.size_mm < demand.min_size: add('size', f'尺寸低于 {demand.min_size}mm')
    if demand.grade and batch.grade != demand.grade: add('grade', '等级不符')
    if demand.packaging and batch.packaging != demand.packaging: add('packaging', '包装不符')
    q = quantity or max(Decimal(p.min_order), min(demand.quantity, max(Decimal(0), batch.quantity-batch.reserved)))
    try:
        cost = price_for(p, q, unit_price, batch=batch)
        if cost['unit_price'] > demand.budget: add('budget', '商品单价超预算')
    except ValidationError:
        add('quantity', '数量不满足起订量或包装增量')
    arrival = max(batch.available_date or timezone.localdate(), timezone.localdate())+timedelta(days=p.delivery_days)
    if arrival > demand.deadline: add('deadline', '预计到货晚于约定日期')
    if batch.status != 'released': add('quality', '批次未放行')
    if p.status != 'on_sale' or p.is_deleted: add('product', '商品已下架')
    if batch.removal_date and arrival > batch.removal_date: add('quality', '到货已晚于已录入移出日期')
    # Corruption is never a negotiable cosmetic grade.
    if hard_quality_reason(batch):add('quality', hard_quality_reason(batch))
    if robust:
        if not batch.sample_size: add('evidence', '缺少代表性抽样记录')
        elif wilson(batch.sample_size, batch.defect_count)[1] > demand.tolerance:
            add('quality', '外观抽检区间上界超过约定阈值')
    elif batch.sample_size and batch.defect_count/batch.sample_size*100 > demand.tolerance:
        add('quality', '观察外观缺陷率超过约定阈值')
    return issues


def allocations_for(order, lock=False):
    qs = order.allocations.select_related('batch__product')
    if lock: qs = qs.select_for_update()
    rows = list(qs.order_by('id'))
    if not rows and order.batch_id and order.quantity is not None:
        dispatched = order.quantity if order.status in ['shipped', 'completed', 'issue', 'refunded'] else Decimal(0)
        rows = [OrderAllocation.objects.create(order=order, batch=order.batch, quantity=order.quantity,
                    dispatched=dispatched, unit_price=order.unit_price_at_purchase,
                    terms=order.snapshot.get('pricing',{}))]
    return rows


def movement(batch, actor, kind, quantity=0, reserved=0, order=None, note=''):
    """Record a change that has already been applied under a transaction lock."""
    if batch.quantity < 0 or batch.reserved < 0 or batch.reserved > batch.quantity:
        raise ValidationError('库存守恒校验失败，请核对实称和预留记录')
    batch.version += 1
    batch.save(update_fields=['version', 'updated_at'])
    InventoryMovement.objects.create(batch=batch, actor=actor, kind=kind,
        quantity=quantity, reserved_delta=reserved, balance=batch.quantity,
        reserved_balance=batch.reserved, order=order, note=note[:300])


def reopen_demand(order):
    from .models import DemandQuote
    from .commerce import notice
    for quote in DemandQuote.objects.select_for_update().filter(order=order, status='accepted').select_related('demand'):
        quote.status = 'cancelled'
        quote.save(update_fields=['status'])
        d = quote.demand
        if d.deadline >= timezone.localdate():
            d.status = 'open'
            d.version += 1
            d.save(update_fields=['status', 'version'])
        notice(d.buyer, f'采购需求「{d.title}」已恢复缺口',
               '关联订单取消，已恢复对应采购量，请重新比较报价', f'/demands?demand={d.id}')


def restore_refunded_quantity(order, quantity):
    from .models import DemandQuote
    from .commerce import notice
    for q in DemandQuote.objects.select_for_update().filter(order=order,status='accepted').select_related('demand'):
        restore=min(quantity,q.quantity-q.released_quantity)
        if restore<=0:continue
        q.released_quantity+=restore;q.save(update_fields=['released_quantity'])
        d=q.demand
        if d.deadline>=timezone.localdate():d.status='open'
        d.version+=1;d.save(update_fields=['status','version'])
        notice(d.buyer,f'需求「{d.title}」恢复待采购数量',f'处理单确认后恢复 {restore}{d.unit}',f'/demands?demand={d.id}')


def public_weight(batch):
    measured = bool(batch.input_weight and batch.usable_weight is not None)
    return {'input_weight': float(batch.input_weight) if batch.input_weight is not None else None,
        'usable_weight': float(batch.usable_weight) if batch.usable_weight is not None else None,
        'yield_rate': round(float(batch.usable_weight/batch.input_weight)*100, 2) if measured else None,
        'weight_note': batch.weight_note, 'storage_condition': batch.storage_condition,
        'removal_date': batch.removal_date, 'version': batch.version}
