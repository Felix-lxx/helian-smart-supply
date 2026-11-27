"""Transactional workspace API. All calculations are server-side and all writes are scoped."""
import math
import uuid
import json
import hashlib
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.db.models import F
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone
from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied, NotFound
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (Product, Order, User, StockBatch, PurchaseDemand, DemandQuote,
                     AllocationPlan, WorkspaceNotification, ShippingAddress, DeviceNode, CheckoutSubmission)
from .commerce_rules import (price_for, json_price, assess, allocations_for, movement,
                             reopen_demand, public_weight, PURPOSES, FLEXIBLE, hard_quality_reason)
from .access import supplier_ids, buyer_ids, participant_ids


def number(value, minimum=Decimal('0'), maximum=Decimal('10000000')):
    try:
        result = Decimal(str(value))
        if not result.is_finite() or result < minimum or result > maximum:
            raise ValueError()
        return result.quantize(Decimal('.01'))
    except (ValueError, TypeError, InvalidOperation):
        raise ValidationError('请输入有效范围内的数量或金额')


def integer(value, low=0, high=100000):
    value = number(value, Decimal(low), Decimal(high))
    if value != int(value):
        raise ValidationError('此项必须为整数')
    return int(value)


def day(value, default=None):
    try:
        return date.fromisoformat(str(value)) if value else default
    except ValueError:
        raise ValidationError('日期格式应为 YYYY-MM-DD')


def role(user, *allowed):
    if user.role not in allowed:
        raise PermissionDenied('当前身份没有此操作权限')


def coordinates(value):
    try:
        lng, lat = [float(v.strip()) for v in str(value).split(',')]
        if math.isfinite(lng) and math.isfinite(lat) and -180 <= lng <= 180 and -90 <= lat <= 90:
            return [lng, lat]
    except (ValueError, TypeError):
        pass
    return None


def wilson(n, k):
    if not n:
        return [0, 100]
    p, z = k / n, 1.95996398454
    center = (p + z*z/(2*n)) / (1+z*z/n)
    delta = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / (1+z*z/n)
    return [round(max(0, center-delta)*100, 2), round(min(1, center+delta)*100, 2)]


def notice(user, title, content='', route='/orders'):
    WorkspaceNotification.objects.create(recipient=user, title=title, content=content, route=route)


def event(order, user, title, note=''):
    order.events = [*(order.events or []), {'title': title, 'note': note,
                    'actor': user.username, 'time': timezone.now().isoformat()}]
    from .models import BusinessEvent
    from .coordination import sync_order_tasks
    BusinessEvent.objects.create(order=order, actor=user, title=title[:160], note=note)
    sync_order_tasks(order, user)


def batch_data(b):
    available = max(Decimal(0), b.quantity-b.reserved) if b.status == 'released' and not hard_quality_reason(b) else Decimal(0)
    return {'id': b.id, 'product_id': b.product_id, 'product_name': b.product.name,
            'supplier': b.product.owner.username, 'supplier_id': b.product.owner_id,
            'code': b.code, 'quantity': float(b.quantity), 'reserved': float(b.reserved),
            'available': float(available), 'unit': b.product.unit, 'price': float(b.sale_price if b.sale_price is not None else b.product.retail_price),
            'sale_price': float(b.sale_price) if b.sale_price is not None else None,
            'intended_purpose': b.intended_purpose, 'parent_id': b.parent_id,
            'grade': b.grade, 'packaging': b.packaging, 'size_mm': b.size_mm,
            'harvest_date': b.harvest_date, 'available_date': b.available_date,
            'status': b.status, 'sample_size': b.sample_size, 'defect_count': b.defect_count,
            'interval': wilson(b.sample_size, b.defect_count),
            'note': b.note, 'inspections': b.inspections, 'origin': b.product.origin, 'coords': coordinates(b.product.location),
            'is_demo': b.product.is_demo, 'updated_at': b.updated_at, **public_weight(b)}


def product_data(p, full=False):
    batches = list(p.batches.all())
    available = sum(max(Decimal(0), b.quantity-b.reserved) for b in batches if b.status == 'released' and not hard_quality_reason(b))
    data = {'id': p.id, 'name': p.name, 'category': p.category, 'owner': p.owner_id,
            'supplier': p.owner.username, 'retail_price': float(p.retail_price),
            'stock': float(available), 'legacy_stock': p.stock, 'unit': p.unit,
            'variety': p.variety, 'grade': p.grade, 'packaging': p.packaging,
            'min_order': p.min_order, 'delivery_days': p.delivery_days,
            'description': p.description, 'image_url': p.image_url, 'origin': p.origin,
            'coords': coordinates(p.location), 'location': p.location,
            'status': p.status, 'is_demo': p.is_demo, 'sales_count': p.sales_count,
            'rating_score': p.rating_score if p.comments.filter(rating__isnull=False).exists() else None,
            'packaging_fee': float(p.packaging_fee), 'freight_fee': float(p.freight_fee),
            'quantity_step': float(p.quantity_step), 'created_at': p.created_at,
            'price_tiers': [{'min_quantity': t.min_quantity, 'price': float(t.wholesale_price)}
                            for t in p.price_tiers.all()]}
    if full:
        data['batches'] = [batch_data(b) for b in batches]
    return data


def order_data(o, user=None):
    snap = o.snapshot or {}
    data = {'id': o.id, 'number': f'HL{o.created_at:%y%m%d}{o.id:05d}',
            'product_id': o.product_id, 'name': snap.get('name', o.product.name if o.product else '历史货品'),
            'image_url': snap.get('image_url', ''), 'supplier': snap.get('supplier', o.product.owner.username if o.product else ''),
            'buyer': o.user.username, 'buyer_id': o.user_id, 'quantity': float(o.quantity) if o.quantity is not None else None,
            'unit': snap.get('unit', o.product.unit if o.product else ''), 'snapshot': snap,
            'unit_price': float(o.unit_price_at_purchase), 'total_amount': float(o.total_amount),
            'status': o.status, 'payment_status': o.payment_status,
            'payment_reference': o.payment_reference, 'batch_id': o.batch_id,
            'batch_code': o.batch.code if o.batch else '', 'receiver_name': o.receiver_name,
            'receiver_phone': o.receiver_phone, 'address': o.address_info,
            'carrier': o.carrier, 'tracking_number': o.tracking_number,
            'accepted_quantity': float(o.accepted_quantity) if o.accepted_quantity is not None else None,
            'issue': o.issue, 'resolution': o.resolution, 'events': o.events,
            'is_demo': o.is_demo, 'created_at': o.created_at, 'receipt': o.receipt,
            'version': o.version, 'promised_date': o.promised_date,
            'dispatched_quantity': float(sum(a.dispatched for a in o.allocations.all())) if o.allocations.exists() else
                (float(o.quantity or 0) if o.status in ['shipped','completed','issue'] else 0),
            'sheet_id': o.sheet_id, 'site_id': o.site_id, 'site': o.site.name if o.site else '',
            'settlement_basis': o.settlement_basis, 'weight_tolerance_pct': float(o.weight_tolerance_pct),
            'deliveries': list(o.deliveries.order_by('id').values('id','quantity','carrier','tracking_number','status','receipt','created_at','received_at','supplier_id','kind','physical_quantity','weighing','case_id')),
            'allocations': [{'id': a.id, 'batch_id': a.batch_id, 'batch_code': a.batch.code,
                             'supplier_id': a.batch.product.owner_id, 'supplier': a.batch.product.owner.username,
                             'quantity': float(a.quantity), 'dispatched': float(a.dispatched),
                             'unit_price':float(a.unit_price),'pricing':a.terms}
                            for a in o.allocations.select_related('batch')],
            'cases': list(o.cases.order_by('-id').values()),
            'reconciliations': list(o.reconciliations.order_by('-id').values()),
            'tasks': list(o.tasks.order_by('id').values('id', 'kind', 'status', 'supplier_id', 'assignee_id', 'version'))}
    if user:
        trade = user.role == 'admin' or (o.product and o.product.owner_id in supplier_ids(user, 'manage'))
        dispatch_ids = supplier_ids(user, 'dispatch')
        data['can_manage_trade'] = trade
        data['can_receive'] = o.user_id in buyer_ids(user, 'receive')
        available = [a for a in o.allocations.select_related('batch__product') if user.role == 'admin' or a.batch.product.owner_id in dispatch_ids]
        data['fulfillable_quantity'] = float(sum(a.quantity-a.dispatched for a in available))
        data['can_ship'] = bool(available) and not data['can_receive']
        if user.role == 'supplier' and o.product.owner_id not in supplier_ids(user):
            own = {a.id for a in available}
            data['allocations'] = [a for a in data['allocations'] if a['id'] in own]
            data['total_amount'] = float(sum(Decimal(str(a.terms.get('total', a.quantity*a.unit_price))) for a in available))
            data['payment_reference'] = ''
            data['cases'], data['reconciliations'] = [], []
            data['quantity']=float(sum(a.quantity for a in available))
            data['dispatched_quantity']=float(sum(a.dispatched for a in available))
            data['unit_price']=float(sum(a.quantity*a.unit_price for a in available)/sum(a.quantity for a in available)) if any(a.quantity for a in available) else 0
            data['snapshot']={k:v for k,v in snap.items() if k not in ['pricing','contract','recovery_delta']}
            data['deliveries']=[d for d in data['deliveries'] if d['supplier_id'] in supplier_ids(user)]
            data['tasks']=[t for t in data['tasks'] if t['supplier_id'] in supplier_ids(user)]
            data['events'] = [e for e in data['events'] if '款' not in e['title'] and '对账' not in e['title']]
    return data


def demand_data(d, user):
    from .decisions import remaining_demand, remaining_usable
    quotes = d.quotes.select_related('batch__product', 'supplier').all()
    if user.role == 'supplier':
        quotes = quotes.filter(supplier_id__in=supplier_ids(user))
    accepted = sum(q.quantity-q.released_quantity for q in d.quotes.filter(status='accepted').exclude(order__status='cancelled'))
    return {'id': d.id, 'buyer': d.buyer.username, 'buyer_id': d.buyer_id, 'title': d.title,
            'remaining': float(remaining_demand(d)),
            'remaining_usable': float(remaining_usable(d)) if d.required_usable else None,
            'keyword': d.keyword, 'quantity': float(d.quantity), 'unit': d.unit, 'budget': float(d.budget),
            'min_size': d.min_size, 'grade': d.grade, 'packaging': d.packaging,
            'tolerance': d.tolerance, 'deadline': d.deadline, 'destination': d.destination,
            'coords': coordinates(d.location), 'note': d.note, 'status': d.status,
            'is_demo': d.is_demo, 'created_at': d.created_at, 'purpose': d.purpose,
            'flexible_fields': d.flexible_fields, 'priority': d.priority,
            'arrival_window': d.arrival_window, 'version': d.version,
            'sheet_id': d.sheet_id, 'site_id': d.site_id, 'site': d.site.name if d.site else '',
            'required_usable': float(d.required_usable) if d.required_usable is not None else None,
            'process': d.process,
            'quotes': [{'id': q.id, 'supplier': q.supplier.username, 'batch_code': q.batch.code,
                        'price': float(q.price), 'quantity': float(q.quantity), 'note': q.note,
                        'status': q.status, 'order_id': q.order_id, 'expires_at': q.expires_at,
                        'deviations': q.deviations, 'terms': q.terms} for q in quotes]}


def visible_orders(user):
    qs = Order.objects.select_related('product__owner', 'user', 'batch', 'site', 'sheet')
    if user.role != 'admin':
        qs = qs.filter(Q(product__owner_id__in=supplier_ids(user)) | Q(allocations__batch__product__owner_id__in=supplier_ids(user))).distinct() if user.role == 'supplier' else qs.filter(user_id__in=buyer_ids(user))
    return qs.order_by('-created_at')


def stock_sync(p):
    p.stock = int(sum(max(Decimal(0), b.quantity-b.reserved) for b in p.batches.all() if b.status == 'released' and not hard_quality_reason(b)))
    p.save(update_fields=['stock', 'updated_at'])


def create_order(user, batch, qty, price=None, address=None, site=None, sheet=None, settlement_basis='contract', weight_tolerance=0, promised_date=None):
    if hard_quality_reason(batch):raise ValidationError(hard_quality_reason(batch))
    if batch.status != 'released' or batch.product.status != 'on_sale' or batch.product.is_deleted:
        raise ValidationError('该批次尚未放行或商品已下架')
    if qty > batch.quantity-batch.reserved:
        raise ValidationError('可用库存已变化，请重新确认数量')
    p = batch.product
    if qty < p.min_order:
        raise ValidationError(f'起订量为 {p.min_order}{p.unit}')
    costs = price_for(p, qty, price, batch=batch)
    unit_price = costs['unit_price']
    snap = {'name': p.name, 'unit': p.unit, 'grade': batch.grade, 'packaging': batch.packaging,
            'size_mm': batch.size_mm, 'origin': p.origin, 'supplier': p.owner.username,
            'supplier_id': p.owner_id, 'image_url': p.image_url, 'delivery_days': p.delivery_days,
            'pricing': json_price(costs), 'inspection': {'n': batch.sample_size, 'k': batch.defect_count,
            'version': batch.version}, 'original_unit_price': float(unit_price)}
    addr = address or {}
    o = Order.objects.create(user=user, product=p, batch=batch, quantity=qty,
        unit_price_at_purchase=unit_price, total_amount=costs['total'],
        snapshot=snap, status='pending', receiver_name=str(addr.get('receiver_name', ''))[:50],
        receiver_phone=str(addr.get('receiver_phone', ''))[:20], address_info=str(addr.get('address', ''))[:1000],
        is_demo=p.is_demo, site=site, sheet=sheet, promised_date=promised_date,
        settlement_basis=settlement_basis, weight_tolerance_pct=weight_tolerance)
    event(o, user, '订单已创建', '库存已预留，待确认收款；24小时未付款自动释放')
    o.save(update_fields=['events'])
    batch.reserved += qty
    batch.save(update_fields=['reserved', 'updated_at'])
    allocations_for(o)
    movement(batch, user, 'reserve', reserved=qty, order=o, note='下单预留')
    stock_sync(p)
    notice(p.owner, f'收到采购订单 #{o.id}', f'{p.name} {qty}{p.unit}')
    return o


def release_order(o, user):
    for a in allocations_for(o, lock=True):
        b = StockBatch.objects.select_for_update().get(pk=a.batch_id)
        remaining = a.quantity-a.dispatched
        if b.reserved < remaining: raise ValidationError('预留记录不一致，请联系运营核对')
        b.reserved -= remaining
        b.save(update_fields=['reserved', 'updated_at'])
        movement(b, user, 'release', reserved=-remaining, order=o, note='订单取消')
        stock_sync(b.product)
    o.status = 'cancelled'
    o.version += 1
    event(o, user, '订单已取消', '预留库存已释放')
    o.save()
    reopen_demand(o)


def expire_pending():
    # Both parties see consistent release; no background scheduler required for local deployment.
    for pk in Order.objects.filter(status='pending', payment_status='unpaid',
                                  created_at__lt=timezone.now()-timedelta(hours=24)).values_list('pk', flat=True):
        with transaction.atomic():
            o = Order.objects.select_for_update().get(pk=pk)
            if o.status == 'pending' and o.payment_status == 'unpaid':
                release_order(o, o.user)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def bootstrap(request):
    u = request.user
    products_qs = Product.objects.filter(is_deleted=False).select_related('owner').prefetch_related('batches', 'price_tiers')
    if u.role == 'supplier':
        products_qs = products_qs.filter(owner_id__in=supplier_ids(u))
    elif u.role != 'admin':
        products_qs = products_qs.filter(status='on_sale')
    orders = list(visible_orders(u)[:500])
    batches = StockBatch.objects.select_related('product__owner').filter(product__is_deleted=False)
    if u.role == 'supplier':
        batches = batches.filter(product__owner_id__in=supplier_ids(u))
    elif u.role != 'admin':
        batches = batches.filter(product__status='on_sale', status='released')
    demands = PurchaseDemand.objects.select_related('buyer').order_by('-created_at')
    if u.role == 'retail':
        demands = demands.filter(buyer_id__in=buyer_ids(u))
    notifications = list(u.workspace_notifications.order_by('-created_at')[:30].values())
    from .reporting import report_counts
    summary=report_counts(u,weekly=True)
    buckets={x['created_at__date']:x for x in summary['daily']}
    trend=[]
    for i in range(6,-1,-1):
        target=(timezone.localdate()-timedelta(days=i)).isoformat()
        row=buckets.get(target,{})
        trend.append({'date':target,'orders':row.get('count',0),'amount':row.get('confirmed_amount',0)})
    plans = AllocationPlan.objects.all() if u.role == 'admin' else AllocationPlan.objects.filter(owner=u)
    return Response({'user': {'id': u.id, 'username': u.username, 'role': u.role,
                     'phone': u.phone, 'avatar': request.build_absolute_uri(u.avatar.url) if u.avatar else None,
                     'managed_supplier_ids':list(participant_ids(u,'manage')),
                     'managed_buyer_ids':list(buyer_ids(u,'manage')),
                     'dispatch_supplier_ids':list(supplier_ids(u,'dispatch')),
                     'inspect_supplier_ids':list(supplier_ids(u,'inspect'))},
        'products': [product_data(p, True) for p in products_qs],
        'batches': [batch_data(b) for b in batches], 'orders': [order_data(o,u) for o in orders],
        'demands': [demand_data(d, u) for d in demands[:200]],
        'notifications': notifications,
        'plans': [{'id':p.id,'name':p.name,'mode':p.mode,'status':p.status,
                   'result':{'summary':p.result.get('summary',{})},'created_at':p.created_at}
                  for p in plans.order_by('-created_at')[:30]],
        'stats': {'orders':summary['orders'],'amount':summary['confirmed_receipts'],
                  **{k:summary[k] for k in ['pending','shipping','transit','issues','completed']},
                  'trend':trend,'scope':summary['scope'],'limited':summary['orders']>500},
        'demo_enabled':settings.DEBUG})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def market(request):
    ps = Product.objects.filter(is_deleted=False, status='on_sale').select_related('owner').prefetch_related('batches', 'price_tiers')
    keyword = request.query_params.get('q', '')[:100]
    if keyword:
        ps = ps.filter(Q(name__icontains=keyword) | Q(origin__icontains=keyword) | Q(variety__icontains=keyword))
    return Response([product_data(p, True) for p in ps])


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def checkout(request):
    role(request.user, 'retail')
    items = request.data.get('items', [])
    if not isinstance(items, list) or not 1 <= len(items) <= 30:
        raise ValidationError('请选择1到30项采购货源')
    addr = request.data.get('address', {})
    if not isinstance(addr, dict) or not all(str(addr.get(k, '')).strip() for k in ['receiver_name', 'receiver_phone', 'address']):
        raise ValidationError('请填写完整收货信息')
    created = []
    from .fulfilment_api import site_for
    site = site_for(request.user, request.data.get('site_id'), 'manage')
    buyer = site.company.owner if site else request.user
    basis = request.data.get('settlement_basis', 'contract')
    if basis not in ['contract', 'accepted_weight']:
        raise ValidationError('结算方式不正确')
    tolerance = number(request.data.get('weight_tolerance_pct', 0), maximum=10)
    promised = day(request.data.get('promised_date'))
    if promised and promised < timezone.localdate():
        raise ValidationError('到货日期不能早于今天')
    with transaction.atomic():
        key = str(request.data.get('idempotency_key', ''))[:80]
        if len(key) < 12: raise ValidationError('缺少采购提交标识，请刷新清单后重试')
        digest = hashlib.sha256(json.dumps({'items': items, 'address': addr, 'site': site.id if site else None,
            'basis': basis, 'tolerance': str(tolerance), 'date': str(promised)}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        receipt, new = CheckoutSubmission.objects.get_or_create(user=request.user, key=key, defaults={'payload_hash': digest})
        receipt = CheckoutSubmission.objects.select_for_update().get(pk=receipt.pk)
        if not new:
            if receipt.payload_hash != digest: raise ValidationError('清单内容已变化，请刷新后重新提交')
            return Response({'orders': [order_data(o,request.user) for o in visible_orders(request.user).filter(pk__in=receipt.orders)]})
        # Validate the same server-generated pricing the buyer just reviewed.
        if request.data.get('pricing_signature'):
            from .collaboration_api import pricing_signature
            if pricing_signature(items) != request.data['pricing_signature']:
                raise ValidationError('价格或费用已变化，请重新核价并确认')
        # Stable lock order prevents opposite cart orders from causing lock inversions.
        try:
            items = sorted(items, key=lambda x: int(x.get('batch_id', 0)))
        except (ValueError, TypeError, AttributeError):
            raise ValidationError('采购货源格式不正确')
        for item in items:
            batch = StockBatch.objects.select_for_update().select_related('product__owner').filter(pk=item.get('batch_id')).first()
            if not batch:
                raise ValidationError('批次不存在')
            qty = number(item.get('quantity'), Decimal('.01'))
            earliest = max(batch.available_date or timezone.localdate(),timezone.localdate())+timedelta(days=batch.product.delivery_days)
            if promised and promised < earliest:
                raise ValidationError(f'{batch.code} 最早预计 {earliest} 到货，请调整约定日期')
            if basis == 'accepted_weight' and batch.product.unit not in ['kg', '斤']:
                raise ValidationError('按合格实重结算需选择重量单位商品')
            order=create_order(buyer, batch, qty, address=addr, site=site,
                settlement_basis=basis, weight_tolerance=tolerance, promised_date=promised or earliest)
            if item.get('required_usable'):
                from .coordination import yield_data
                evidence=yield_data(batch,item.get('purpose','kitchen'),str(item.get('process','')))
                target=number(item['required_usable'],Decimal('.01'))
                if not evidence or evidence['id']!=item.get('yield_record_id') or Decimal(str(evidence['rate']))*qty+Decimal('.005')<target:
                    raise ValidationError('用途称重依据、数量或净需求已变化，请重新比较后采购')
                order.snapshot={**order.snapshot,'purpose':item.get('purpose'),'contract':{
                    'required_usable':float(target),'yield_rate':evidence['rate'],'yield_record_id':evidence['id'],
                    'process':evidence['process'],'evidence_scope':evidence['scope']}}
                order.save(update_fields=['snapshot'])
            created.append(order)
        receipt.orders = [o.id for o in created]; receipt.save(update_fields=['orders'])
    return Response({'orders': [order_data(o, request.user) for o in created]}, status=201)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def order_action(request, pk, action):
    u = request.user
    if action in ['ship', 'receive', 'resolve', 'accept-resolution']:
        from .workflow import order_workflow
        return order_workflow(request, pk, action)
    with transaction.atomic():
        o = visible_orders(u).select_for_update().filter(pk=pk).first()
        if not o:
            raise NotFound('订单不存在或不属于当前账号')
        buyer = o.user_id in buyer_ids(u, 'manage')
        seller = u.role == 'admin' or (o.product and o.product.owner_id in supplier_ids(u,'manage'))
        if action == 'cancel':
            if not buyer or o.status != 'pending' or o.payment_status != 'unpaid':
                raise ValidationError('仅买方可取消尚未提交付款确认的待付款订单')
            release_order(o, u)
            notice(o.product.owner, f'订单 #{o.id} 已取消', '库存已释放')
        elif action == 'submit-payment':
            if not buyer or o.status != 'pending' or o.payment_status != 'unpaid':
                raise ValidationError('当前订单无法提交付款确认')
            reference = str(request.data.get('reference', '')).strip()
            if len(reference) < 4:
                raise ValidationError('请填写转账流水号或付款凭证说明，至少4个字符')
            o.payment_reference = reference[:200]
            o.payment_status = 'review'
            event(o, u, '买方提交付款确认', '等待收款方核对到账')
            o.save()
            notice(o.product.owner, f'订单 #{o.id} 待核对收款')
        elif action == 'confirm-payment':
            if not seller or o.status != 'pending' or o.payment_status != 'review':
                raise ValidationError('只有收款方可以确认待核对付款')
            o.payment_status, o.status = 'confirmed', 'paid'
            event(o, u, '收款方已确认到账', '进入备货流程')
            o.save()
            notice(o.user, f'订单 #{o.id} 收款已确认')
        elif action == 'reject-payment':
            if not seller or o.payment_status != 'review' or o.status != 'pending':
                raise ValidationError('当前无待核对付款')
            o.payment_status = 'unpaid'
            event(o, u, '付款核对未通过', str(request.data.get('note', '请核实流水号后重新提交'))[:500])
            o.save()
            notice(o.user, f'订单 #{o.id} 请重新核实付款')
        else:
            raise ValidationError('不支持的订单操作')
    return Response(order_data(o,request.user))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_product(request, pk=None):
    role(request.user, 'supplier', 'admin')
    data = request.data
    if pk:
        ps = Product.objects.filter(pk=pk, is_deleted=False)
        if request.user.role != 'admin':
            ps = ps.filter(owner_id__in=supplier_ids(request.user,'manage'))
        p = ps.first()
        if not p:
            raise NotFound()
    else:
        p = Product(owner=request.user,is_demo=settings.DEBUG and request.user.username.startswith('demo_'))
    if not str(data.get('name', '')).strip():
        raise ValidationError('请填写商品名称')
    for field in ['name', 'origin', 'variety', 'grade', 'packaging', 'description', 'image_url']:
        if field in data:
            setattr(p, field, str(data[field])[:2000 if field == 'description' else 300])
    if data.get('category') not in dict(Product.CATEGORY_CHOICES):
        raise ValidationError('商品分类不正确')
    p.category = data['category']
    p.retail_price = number(data.get('retail_price'), Decimal('.01'))
    if pk and data.get('unit',p.unit)!=p.unit and p.batches.exists():
        raise ValidationError('已有实物批次的商品不能改变计量单位，请新建对应规格，避免库存单位混用')
    p.unit = str(data.get('unit', 'kg'))
    if p.unit not in ['kg', '斤', '箱', '件']:
        raise ValidationError('不支持的计量单位')
    p.min_order = integer(data.get('min_order', 1), 1)
    p.delivery_days = integer(data.get('delivery_days', 2), 0, 90)
    p.packaging_fee = number(data.get('packaging_fee', p.packaging_fee))
    p.freight_fee = number(data.get('freight_fee', p.freight_fee))
    p.quantity_step = number(data.get('quantity_step', p.quantity_step), Decimal('.01'))
    loc = str(data.get('location', '')).strip()
    if loc and not coordinates(loc):
        raise ValidationError('请输入正确的经度,纬度；未知时留空')
    p.location = loc
    with transaction.atomic():
        p.save()
        if isinstance(data.get('price_tiers'), list):
            p.price_tiers.all().delete()
            for tier in data['price_tiers'][:8]:
                p.price_tiers.create(min_quantity=integer(tier.get('min_quantity'), 1),
                                     wholesale_price=number(tier.get('price'), Decimal('.01')))
    return Response(product_data(p, True))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def product_action(request, pk):
    role(request.user, 'supplier', 'admin')
    qs = Product.objects.filter(pk=pk, is_deleted=False)
    if request.user.role != 'admin':
        qs = qs.filter(owner_id__in=supplier_ids(request.user,'manage'))
    p = qs.first()
    if not p:
        raise NotFound()
    state = request.data.get('status')
    if state not in ['on_sale', 'off_shelf']:
        raise ValidationError('状态不正确')
    if state == 'on_sale' and not p.batches.filter(status='released', quantity__gt=0).exists():
        raise ValidationError('请先创建并放行至少一个库存批次')
    p.status = state
    p.off_shelf_reason = str(request.data.get('reason', '主动调整供货'))[:255]
    p.save()
    return Response(product_data(p, True))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_batch(request):
    role(request.user, 'supplier', 'admin')
    qs = Product.objects.filter(pk=request.data.get('product_id'), is_deleted=False)
    if request.user.role != 'admin':
        qs = qs.filter(owner_id__in=supplier_ids(request.user,'manage'))
    p = qs.first()
    if not p:
        raise NotFound('商品不存在或没有管理权限')
    b = StockBatch.objects.create(product=p, code=f'B{timezone.now():%y%m%d}-{uuid.uuid4().hex[:6].upper()}',
        quantity=number(request.data.get('quantity'), Decimal('.01')),
        grade=str(request.data.get('grade', p.grade))[:30], packaging=str(request.data.get('packaging', p.packaging))[:80],
        size_mm=integer(request.data.get('size_mm', 0), 0, 2000),
        harvest_date=day(request.data.get('harvest_date')), available_date=day(request.data.get('available_date'), timezone.localdate()),
        note=str(request.data.get('note', ''))[:2000], status='pending',
        storage_condition=str(request.data.get('storage_condition', ''))[:120],
        removal_date=day(request.data.get('removal_date')))
    movement(b, request.user, 'inbound', quantity=b.quantity, note='登记入库实物数量')
    notice(p.owner, f'批次 {b.code} 已入库待检', '请完成抽样检查与人工复核', '/quality')
    return Response(batch_data(b), status=201)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def inspect_batch(request, pk):
    role(request.user, 'supplier', 'admin')
    with transaction.atomic():
        qs = StockBatch.objects.select_for_update().select_related('product__owner').filter(pk=pk)
        if request.user.role != 'admin':
            qs = qs.filter(product__owner_id__in=supplier_ids(request.user,'inspect'))
        b = qs.first()
        if not b:
            raise NotFound()
        if request.data.get('version') is not None and int(request.data['version']) != b.version:
            raise ValidationError('批次已被更新，请保留草稿并载入最新记录后提交')
        n = integer(request.data.get('sample_size'), 1)
        k = integer(request.data.get('defect_count'), 0, n)
        metrics=request.data.get('metrics',{})
        if not isinstance(metrics,dict):raise ValidationError('分项检查格式错误')
        metrics={key:integer(metrics.get(key,0),0,n) for key in ['rot','size']}
        state = request.data.get('status', 'pending')
        if state not in ['released', 'pending', 'quarantine']:
            raise ValidationError('请选择复核处置结果')
        if state=='released' and metrics['rot']>0:raise ValidationError('本次发现腐坏目标，请先隔离处理并重新复核')
        b.sample_size, b.defect_count, b.status = n, k, state
        b.note = str(request.data.get('note', ''))[:2000]
        b.inspections = [*b.inspections, {'sample_size': n, 'defect_count': k, 'status': state,
            'note': b.note, 'actor': request.user.username, 'time': timezone.now().isoformat(),
            'metrics': metrics, 'position': str(request.data.get('position', ''))[:160]}]
        b.save()
        movement(b, request.user, 'inspect', note=f'人工复核：{state}')
        stock_sync(b.product)
        if state != 'released':
            for o in b.orders.filter(status__in=['pending', 'paid']).select_related('user'):
                notice(o.user, f'订单 #{o.id} 批次进入复核', '供应方正在核实库存品质；发货前须重新放行')
        notice(b.product.owner, f'批次 {b.code} 复核已更新', b.note, '/quality')
    return Response(batch_data(b))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_demand(request):
    role(request.user, 'retail')
    d = request.data
    for key in ['title', 'keyword', 'destination']:
        if not str(d.get(key, '')).strip():
            raise ValidationError('请填写需求标题、采购品种和目的地')
    deadline = day(d.get('deadline'))
    if not deadline or deadline < timezone.localdate():
        raise ValidationError('到货日期不能早于今天')
    unit = str(d.get('unit', 'kg'))
    from .fulfilment_api import site_for
    site = site_for(request.user, d.get('site_id'), 'manage')
    if unit not in ['kg', '斤', '箱', '件']:
        raise ValidationError('计量单位不正确')
    demand = PurchaseDemand.objects.create(buyer=site.company.owner if site else request.user, site=site, title=str(d['title'])[:160], keyword=str(d['keyword'])[:80],
        quantity=number(d.get('quantity'), Decimal('.01')), budget=number(d.get('budget'), Decimal('.01')),
        unit=unit, min_size=integer(d.get('min_size', 0), 0, 2000), grade=str(d.get('grade', ''))[:30],
        packaging=str(d.get('packaging', ''))[:80], tolerance=float(number(d.get('tolerance', 10), Decimal(0), Decimal(100))),
        deadline=deadline, destination=str(d['destination'])[:200], note=str(d.get('note', ''))[:2000],
        location=str(d.get('location', ''))[:80],
        purpose=d.get('purpose') if d.get('purpose') in PURPOSES else 'fresh',
        flexible_fields=[x for x in d.get('flexible_fields', []) if x in FLEXIBLE],
        priority=integer(d.get('priority', 1), 1, 3), arrival_window=str(d.get('arrival_window', ''))[:80],
        is_demo=settings.DEBUG and request.user.username.startswith('demo_'))
    return Response(demand_data(demand, request.user), status=201)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def quote_demand(request, pk):
    role(request.user, 'supplier')
    d = PurchaseDemand.objects.filter(pk=pk, status='open', deadline__gte=timezone.localdate()).first()
    b = StockBatch.objects.select_related('product__owner').filter(pk=request.data.get('batch_id'), product__owner_id__in=supplier_ids(request.user,'manage')).first()
    if not d or not b: raise ValidationError('需求已关闭或批次不可用')
    if d.sheet and d.sheet.cutoff_at and d.sheet.cutoff_at < timezone.now():
        raise ValidationError('该采购单已过截单时间，请采购方重新发布')
    qty = number(request.data.get('quantity'), Decimal('.01'), b.quantity-b.reserved if d.required_usable else min(d.quantity, b.quantity-b.reserved))
    price = number(request.data.get('price'), Decimal('.01'))
    deviations = assess(b, d, qty, price)
    if any(not x['negotiable'] for x in deviations):
        raise ValidationError('；'.join(x['reason'] for x in deviations if not x['negotiable']))
    note = str(request.data.get('note', '')).strip()
    if deviations and not note: raise ValidationError('偏离可协商条件时请说明替代依据')
    terms = json_price(price_for(b.product, qty, price, batch=b))
    if d.required_usable:
        from .coordination import yield_data
        evidence = yield_data(b, d.purpose, d.process)
        if not evidence or evidence['rate'] <= 0:
            raise ValidationError('请先补充该用途和加工方式的称重依据')
        terms.update({'yield_rate': evidence['rate'], 'yield_record_id': evidence['id'], 'committed_usable': float(qty)*evidence['rate']})
    q = DemandQuote.objects.create(demand=d, batch=b, supplier=b.product.owner, price=price, quantity=qty,
        note=note[:2000], deviations=deviations, terms=terms, expires_at=timezone.now()+timedelta(hours=24))
    notice(d.buyer, f'需求「{d.title}」收到新报价', f'{request.user.username} 已报价', f'/demands?demand={d.id}')
    return Response({'id': q.id}, status=201)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def accept_quote(request, pk):
    role(request.user, 'retail')
    with transaction.atomic():
        q = DemandQuote.objects.select_for_update().select_related('demand', 'batch__product__owner').filter(pk=pk, demand__buyer_id__in=buyer_ids(request.user,'manage')).first()
        if not q or q.status != 'pending': raise ValidationError('报价不存在或已处理')
        if q.expires_at and q.expires_at < timezone.now(): raise ValidationError('报价已过期，请联系供应商重新报价')
        d = PurchaseDemand.objects.select_for_update().get(pk=q.demand_id)
        if d.status != 'open' or d.deadline < timezone.localdate(): raise ValidationError('需求已关闭或交期已过')
        if d.sheet and d.sheet.cutoff_at and d.sheet.cutoff_at < timezone.now():
            raise ValidationError('采购单已过截单时间，请核对交期后重新发布')
        remaining = d.quantity-sum(x.quantity-x.released_quantity for x in d.quotes.filter(status='accepted').exclude(order__status='cancelled'))
        qty = min(q.quantity, remaining)
        if d.required_usable:
            from .decisions import remaining_usable
            rate = Decimal(str(q.terms.get('yield_rate', 0)))
            if rate <= 0:
                raise ValidationError('净用量报价缺少称重承诺，请供货方重新报价')
            if remaining_usable(d) <= 0:
                raise ValidationError('净用量需求已被满足')
            if q.quantity*rate > remaining_usable(d)+q.batch.product.quantity_step*rate+Decimal('.005'):
                raise ValidationError('其他报价已覆盖部分净用量，请供货方按剩余缺口重新报价')
            qty = q.quantity
        if qty <= 0: raise ValidationError('需求已被满足')
        b = StockBatch.objects.select_for_update().select_related('product__owner').get(pk=q.batch_id)
        deviations = assess(b, d, qty, q.price)
        if any(not x['negotiable'] for x in deviations): raise ValidationError('；'.join(x['reason'] for x in deviations))
        if deviations and request.data.get('accept_deviations') is not True:
            raise ValidationError('报价偏离了可协商条件，请明确勾选接受差异后再确认')
        costs = json_price(price_for(b.product, qty, q.price))
        if q.terms and (costs['packaging'] != q.terms.get('packaging') or costs['freight'] != q.terms.get('freight')):
            raise ValidationError('费用规则或承接数量已变化，请供应商更新报价后再确认')
        contact = ShippingAddress.objects.filter(user=request.user).order_by('-is_default', '-id').first()
        phone = request.user.phone or (contact.receiver_phone if contact else '')
        if not phone: raise ValidationError('请先在账户设置中补充联系电话或收货地址')
        o = create_order(d.buyer, b, qty, q.price, {'receiver_name': contact.receiver_name if contact else request.user.username,
            'receiver_phone': phone, 'address': d.destination}, site=d.site, sheet=d.sheet,
            promised_date=d.deadline)
        o.promised_date=d.deadline
        o.snapshot={**o.snapshot,'demand_id':d.id,'purpose':d.purpose,'arrival_window':d.arrival_window,
            'contract':{'keyword':d.keyword,'grade':d.grade,'packaging':d.packaging,'min_size':d.min_size,
                'tolerance':d.tolerance,'deadline':d.deadline.isoformat(),'deviations':deviations,
                'required_usable':float(d.required_usable) if d.required_usable else None,
                'yield_rate':q.terms.get('yield_rate'), 'yield_record_id':q.terms.get('yield_record_id'), 'process':d.process}}
        o.save()
        q.status, q.order, q.quantity = 'accepted', o, qty; q.save()
        if d.required_usable:
            d.status = 'ordered' if remaining_usable(d) < Decimal('.005') else 'open'
        else:
            d.status = 'ordered' if qty >= remaining else 'open'
        d.version+=1;d.save()
        if d.status == 'ordered': d.quotes.filter(status='pending').exclude(pk=q.pk).update(status='closed')
    return Response(order_data(o,request.user))


def compatibility(b, d, robust=False):
    return [x['reason'] for x in assess(b,d,robust=robust)]


def compute_allocation(user, data):
    from .decisions import compute
    return compute(user,data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def allocation(request):
    return Response(compute_allocation(request.user, request.data))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_plan(request):
    role(request.user, 'supplier', 'admin')
    # Recompute using server-side input; do not persist client-supplied allocation results.
    result = compute_allocation(request.user, request.data)
    serializable = json.loads(json.dumps(result, cls=DjangoJSONEncoder))
    p = AllocationPlan.objects.create(owner=request.user, name=str(request.data.get('name', '分货方案'))[:100],
                                     mode=result['mode'], result=serializable)
    return Response({'id': p.id, 'name': p.name, 'result': p.result})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def publish_plan(request, pk):
    role(request.user, 'supplier', 'admin')
    with transaction.atomic():
        qs = AllocationPlan.objects.select_for_update().filter(pk=pk)
        if request.user.role != 'admin': qs = qs.filter(owner=request.user)
        plan = qs.first()
        if not plan or plan.status != 'draft': raise ValidationError('方案不存在或已发送')
        count = 0
        for item in plan.result.get('allocations', []):
            b = StockBatch.objects.select_for_update().select_related('product__owner').get(pk=item['batch_id'])
            if request.user.role != 'admin' and b.product.owner_id not in supplier_ids(request.user,'manage'): raise PermissionDenied()
            d = PurchaseDemand.objects.filter(pk=item['demand_id'], status='open').first()
            qty = number(item['quantity'], Decimal('.01'))
            if not d or assess(b,d,qty,number(item['price']),plan.mode=='robust') or b.quantity-b.reserved < qty:
                raise ValidationError('库存或需求已变化，请重新计算方案')
            from .decisions import remaining_demand
            if not d.required_usable and qty>remaining_demand(d):raise ValidationError('需求余量已变化，请重新计算方案')
            terms=json_price(price_for(b.product,qty,number(item['price']),batch=b))
            if d.required_usable:
                from .coordination import yield_data
                evidence=yield_data(b,d.purpose,d.process)
                if not evidence:raise ValidationError('用途称重依据已变化，请重新试算')
                terms.update({'yield_rate':evidence['rate'],'yield_record_id':evidence['id'],'committed_usable':float(qty)*evidence['rate']})
            if Decimal(str(terms['total']))!=Decimal(str(item['amount'])):
                raise ValidationError('方案价格或费用已变化，请重新计算后再发送')
            DemandQuote.objects.create(demand=d, batch=b, supplier=b.product.owner, price=number(item['price']),
                quantity=qty,terms=terms,expires_at=timezone.now()+timedelta(hours=24),
                note=f'分货方案 #{plan.id} · 待采购方确认，不预占库存')
            notice(d.buyer, f'需求「{d.title}」收到分货报价', f'{qty}{d.unit} · {b.code}', '/demands')
            count += 1
        if not count: raise ValidationError('空方案不能发送')
        plan.status = 'sent'; plan.save(update_fields=['status'])
    return Response({'message': f'已发送{count}项报价，等待采购商确认'})


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def notification_api(request):
    if request.method == 'POST':
        request.user.workspace_notifications.filter(read=False).update(read=True)
        return Response({'message': '已全部标为已读'})
    return Response(list(request.user.workspace_notifications.order_by('-created_at')[:50].values()))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def devices(request):
    role(request.user, 'admin')
    result = []
    for dev in DeviceNode.objects.all():
        last = dev.telemetries.order_by('-timestamp').first()
        online = bool(last and (timezone.now()-last.timestamp).total_seconds() < 30)
        result.append({'id': dev.id, 'device_id': dev.device_id, 'location': dev.location, 'online': online,
            'last_seen': last.timestamp if last else None, 'npu_load': last.npu_load if last else None,
            'latency': last.yolo_delay if last else None,'is_mock':dev.device_id.upper().startswith('MOCK'),
            'batch_id':last.batch_id if last else None,'task_id':last.task_id if last else None,
            'observations':last.observations if last else {},
            'history': list(dev.telemetries.order_by('-timestamp')[:24].values('timestamp', 'npu_load', 'yolo_delay'))[::-1]})
    return Response(result)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def users_api(request):
    role(request.user, 'admin')
    if request.method == 'POST':
        u = User.objects.filter(pk=request.data.get('id')).first()
        if not u or u.id == request.user.id or u.is_superuser:
            raise ValidationError('不能修改当前账号或受保护账号')
        if 'active' not in request.data or not isinstance(request.data['active'], bool):
            raise ValidationError('账号状态不正确')
        u.is_active = request.data['active']; u.save(update_fields=['is_active'])
    return Response(list(User.objects.order_by('id').values('id', 'username', 'role', 'phone', 'is_active', 'date_joined')))


@api_view(['POST'])
@permission_classes([AllowAny])
def demo_login(request):
    if not settings.DEBUG: raise PermissionDenied('演示入口仅在本地开发环境开启')
    selected = request.data.get('role')
    names = {'retail': 'demo_buyer', 'supplier': 'demo_supplier', 'admin': 'demo_admin', 'cooperative':'demo_coop'}
    if selected not in names: raise ValidationError('请选择演示身份')
    u = User.objects.filter(username=names[selected], is_active=True).first()
    if not u: raise ValidationError('演示数据尚未初始化，请联系管理员')
    token = RefreshToken.for_user(u)
    return Response({'access': str(token.access_token), 'refresh': str(token),
                     'role': u.role, 'username': u.username, 'user_id': u.id})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_image(request):
    from PIL import Image, UnidentifiedImageError
    from django.core.files.storage import default_storage
    f = request.FILES.get('file')
    if not f or f.size > 8*1024*1024:
        raise ValidationError('请选择8MB以内的JPG或PNG图片')
    try:
        im = Image.open(f)
        fmt = im.format
        if fmt not in ['JPEG', 'PNG'] or im.width*im.height > 40000000: raise ValueError()
        im.verify(); f.seek(0)
    except (UnidentifiedImageError, ValueError, OSError):
        raise ValidationError('图片内容不可识别，仅支持JPG或PNG')
    name = default_storage.save(f'products/{uuid.uuid4().hex}.{"jpg" if fmt == "JPEG" else "png"}', f)
    return Response({'url': request.build_absolute_uri(default_storage.url(name))})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def batch_vision(request, pk):
    from PIL import Image, UnidentifiedImageError
    from django.core.files.storage import default_storage
    from .views import get_vision_model
    model = get_vision_model()
    from .models import QualityInspectionLog
    role(request.user, 'supplier', 'admin')
    qs = StockBatch.objects.select_related('product').filter(pk=pk)
    if request.user.role != 'admin': qs = qs.filter(product__owner_id__in=supplier_ids(request.user,'inspect'))
    b = qs.first()
    if not b: raise NotFound()
    f = request.FILES.get('image')
    if not f or f.size > 8*1024*1024: raise ValidationError('请选择8MB以内的JPG/PNG')
    if model is None: raise ValidationError('本地视觉模型未加载，可继续进行人工抽样与复核')
    try:
        image = Image.open(f)
        if image.format not in ['JPEG', 'PNG'] or image.width*image.height > 40000000: raise ValueError()
        image = image.convert('RGB')
    except (ValueError, OSError, UnidentifiedImageError): raise ValidationError('图片不可识别')
    results = model(image)
    frame = results.pandas().xyxy[0]
    bad = int(frame['name'].str.contains('bad|defect|rotten', case=False).sum())
    results.render()
    from io import BytesIO
    from django.core.files.base import ContentFile
    buf = BytesIO(); Image.fromarray(results.ims[0]).save(buf, format='JPEG')
    name = default_storage.save(f'quality/processed/{uuid.uuid4().hex}.jpg', ContentFile(buf.getvalue()))
    f.seek(0)
    log = QualityInspectionLog.objects.create(product=b.product, raw_image=f, processed_image=name,
        bad_count=bad, inspector=request.user, summary=f'批次 {b.code} 图像发现{bad}个疑似异常目标，待人工确认')
    b.inspections = [*b.inspections, {'type': 'vision', 'defect_count': bad, 'actor': request.user.username,
        'time': timezone.now().isoformat(), 'note': '视觉辅助检查，尚未改变复核或库存状态',
        'image_url': request.build_absolute_uri(log.processed_image.url)}]
    b.save(update_fields=['inspections', 'updated_at'])
    return Response({'bad_count': bad, 'image_url': request.build_absolute_uri(log.processed_image.url),
                     'raw_image': request.build_absolute_uri(log.raw_image.url)})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def assistant(request):
    import requests
    question = str(request.data.get('question', '')).strip()[:1500]
    if not question: raise ValidationError('请输入要了解的问题')
    import re
    quantity=re.search(r'(\d+(?:\.\d+)?)\s*(公斤|千克|kg|斤|箱|件)',question,re.I)
    keyword=next((word for word in ['苹果','黄瓜','脐橙','芒果','香梨','凤梨','水蜜桃','橙','梨','桃'] if word in question),'')
    if quantity and keyword and any(word in question for word in ['采购','买','需要','订']):
        from urllib.parse import quote
        draft={'keyword':keyword,'quantity':float(quantity.group(1)),
            'unit':{'公斤':'kg','千克':'kg'}.get(quantity.group(2).lower(),quantity.group(2).lower()),
            'purpose':'juice' if '榨汁' in question else 'kitchen' if any(word in question for word in ['厨房','食堂','加工']) else 'fresh'}
        if '明天' in question:draft['deadline']=(timezone.localdate()+timedelta(days=1)).isoformat()
        elif '后天' in question:draft['deadline']=(timezone.localdate()+timedelta(days=2)).isoformat()
        return Response({'answer':f'已提取采购草稿：{keyword} {draft["quantity"]:g}{draft["unit"]}。请打开后核对用途、交期、预算和收货信息；当前没有发布需求或创建订单。',
            'source':'采购字段抽取 · 待你核对',
            'actions':[{'label':'打开采购草稿','route':'/procurement?draft='+quote(json.dumps(draft,ensure_ascii=False))}]})
    u = request.user
    orders = visible_orders(u)
    data = {'角色': u.get_role_display(), '订单总量': orders.count(),
        '待收款核对': orders.filter(payment_status='review').count(),
        '待发运': orders.filter(status='paid').count(), '运输中': orders.filter(status='shipped').count(),
        '验收异常': orders.filter(status='issue').count()}
    actions = [{'label': '查看订单履约', 'route': '/orders'}, {'label': '查看采购需求', 'route': '/demands'}]
    if u.role in ['supplier', 'admin']:
        bs = StockBatch.objects.filter(product__is_deleted=False)
        if u.role == 'supplier': bs = bs.filter(product__owner=u)
        data['待复核批次'] = bs.exclude(status='released').count()
        actions += [{'label': '进入品质工作台', 'route': '/quality'}, {'label': '比较分货方案', 'route': '/allocation'}]
    answer = f'当前工作区共有 {data["订单总量"]} 笔订单：{data["待收款核对"]} 笔待收款核对，{data["待发运"]} 笔待发运，{data["运输中"]} 笔运输中，{data["验收异常"]} 笔有验收差异。\n\n'
    if '待复核批次' in data: answer += f'有 {data["待复核批次"]} 个批次需要检查或复核。先核实抽样记录，再决定放行或隔离。\n\n'
    answer += '可从下方入口查看原始记录。分货试算不预占库存；报价由采购商确认后才转为订单。当前统计可能包含明确标记的演示记录。'
    source = '实时记录摘要'
    if settings.DEEPSEEK_API_KEY and request.data.get('allow_external') is True:
        try:
            res = requests.post(f'{settings.DEEPSEEK_BASE_URL}/chat/completions', headers={
                'Authorization': f'Bearer {settings.DEEPSEEK_API_KEY}'}, json={'model': 'deepseek-chat', 'messages': [
                    {'role': 'system', 'content': '你是禾链智配业务助手。只能依据下列授权范围的真实摘要回答。不得编造质量、利润、库存或预测，不执行交易。演示与实际数据可能混合，应提醒核对。用简短中文纯文本回答，不用Markdown。数据：'+json.dumps(data, ensure_ascii=False)},
                    {'role': 'user', 'content': question}], 'max_tokens': 600}, timeout=12)
            res.raise_for_status(); answer = res.json()['choices'][0]['message']['content']; source = 'AI解读 · 请核对业务记录'
        except (requests.RequestException, ValueError, KeyError, IndexError):
            source = 'AI暂不可用 · 已返回实时记录摘要'
    return Response({'answer': answer, 'source': source, 'actions': actions})


urlpatterns = [
    path('bootstrap/', bootstrap), path('market/', market), path('checkout/', checkout),
    path('orders/<int:pk>/<str:action>/', order_action),
    path('products/save/', save_product), path('products/<int:pk>/save/', save_product),
    path('products/<int:pk>/status/', product_action), path('batches/', save_batch),
    path('batches/<int:pk>/inspect/', inspect_batch), path('demands/', create_demand),
    path('batches/<int:pk>/vision/', batch_vision),
    path('demands/<int:pk>/quote/', quote_demand), path('quotes/<int:pk>/accept/', accept_quote),
    path('allocation/', allocation), path('plans/', save_plan), path('plans/<int:pk>/publish/', publish_plan), path('notifications/', notification_api),
    path('devices/', devices), path('users/', users_api), path('demo-login/', demo_login), path('upload/', upload_image),
    path('assistant/', assistant),
]
