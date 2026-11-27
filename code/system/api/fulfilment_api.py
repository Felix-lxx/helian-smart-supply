"""Procurement sheets, purpose evidence, work tasks and actionable control views."""
from datetime import datetime, time, timedelta
from decimal import Decimal
import json
import uuid
from django.db import transaction
from django.db.models import Q, Count, Sum
from django.urls import path
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied, NotFound
from .models import (User, Company, BusinessSite, ProcurementSheet, PurchaseDemand, Order,
    StockBatch, PurposeYieldRecord, BatchGradingRecord, FulfilmentTask, WeightReconciliation,
    SupplierSettlement, SettlementCase, BusinessEvent, WorkspaceNotification)
from .access import supplier_ids, buyer_ids, participant_ids
from .coordination import (visible_sheets, visible_tasks, task_data, net_options, yield_data,
    close_task, sync_order_tasks, settlement_data)


def company_for(user, pk, action='read'):
    if not pk:
        return None
    c = Company.objects.filter(pk=pk).first()
    if not c or (user.role != 'admin' and c.owner_id not in buyer_ids(user, action)):
        raise PermissionDenied('当前岗位无权操作该采购主体')
    if c.owner.role != 'retail':
        raise ValidationError('请选择采购主体')
    return c


def site_for(user, pk, action='read', company=None):
    if not pk:
        return None
    site = BusinessSite.objects.select_related('company__owner').filter(pk=pk).first()
    if not site or (user.role != 'admin' and site.company.owner_id not in buyer_ids(user, action)):
        raise PermissionDenied('当前岗位无权使用该收货点')
    if company and site.company_id != company.id:
        raise ValidationError('收货点与采购主体不一致')
    return site


def scoped_orders(request,qs):
    from .commerce import day,integer
    params=request.query_params
    if params.get('date'):
        date=day(params['date'])
        qs=qs.filter(Q(promised_date=date)|Q(promised_date__isnull=True,created_at__date=date))
    if params.get('unit'):qs=qs.filter(snapshot__unit=params['unit'])
    if params.get('site'):qs=qs.filter(site_id=integer(params['site'],1))
    if params.get('exclude_demo')=='1':qs=qs.filter(is_demo=False)
    if params.get('active')=='1':qs=qs.exclude(status__in=['cancelled','refunded'])
    return qs


def sheet_data(sheet, user):
    from .commerce import demand_data, visible_orders
    orders = visible_orders(user).filter(sheet=sheet)
    return {'id': sheet.id, 'title': sheet.title, 'buyer': sheet.buyer.username,
        'company_id': sheet.company_id, 'company': sheet.company.name if sheet.company else sheet.buyer.username,
        'delivery_date': sheet.delivery_date, 'cutoff_at': sheet.cutoff_at, 'status': sheet.status,
        'template': sheet.template, 'note': sheet.note, 'created_at': sheet.created_at,
        'lines': [demand_data(d, user) for d in sheet.demands.select_related('buyer', 'site').prefetch_related('quotes')],
        'order_ids': list(orders.values_list('id', flat=True)), 'order_count': orders.count(),
        'amount': float(orders.aggregate(v=Sum('total_amount'))['v'] or 0)}


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def sheets(request):
    from .commerce import number, integer, day, notice
    from .commerce_rules import PURPOSES, FLEXIBLE
    u = request.user
    if request.method == 'POST':
        if u.role != 'retail':
            raise PermissionDenied('请由采购岗位建立采购单')
        data = request.data
        key = str(data.get('submission_key', ''))[:80]
        if not key:
            raise ValidationError('缺少提交标识，请刷新后重试')
        old = ProcurementSheet.objects.filter(creator=u, submission_key=key).first()
        if old:
            return Response(sheet_data(old, u))
        lines = data.get('lines', [])
        if not isinstance(lines, list) or not 1 <= len(lines) <= 100:
            raise ValidationError('请填写1至100项采购明细')
        date = day(data.get('delivery_date'))
        if not date or date < timezone.localdate():
            raise ValidationError('请选择今天或以后的到货日期')
        company = company_for(u, data.get('company_id'), 'manage')
        owner = company.owner if company else u
        cutoff = None
        if data.get('cutoff_at'):
            try:
                cutoff = datetime.fromisoformat(str(data['cutoff_at']).replace('Z', '+00:00'))
                if timezone.is_naive(cutoff):
                    cutoff = timezone.make_aware(cutoff)
                if cutoff <= timezone.now():
                    raise ValueError()
            except (ValueError, TypeError):
                raise ValidationError('截单时间需为有效的未来时间')
        with transaction.atomic():
            sheet = ProcurementSheet.objects.create(buyer=owner, creator=u, company=company,
                title=str(data.get('title') or f'{date} 门店集采')[:160], delivery_date=date,
                cutoff_at=cutoff, submission_key=key, template=data.get('template') is True,
                note=str(data.get('note', ''))[:2000])
            for index, row in enumerate(lines):
                site = site_for(u, row.get('site_id'), 'manage', company)
                if site and site.company.owner_id != owner.id:
                    raise ValidationError('同一集采单的收货点必须属于所选采购主体')
                keyword = str(row.get('keyword', '')).strip()[:80]
                unit = row.get('unit', 'kg')
                purpose = row.get('purpose', 'fresh')
                if not keyword or unit not in ['kg', '斤', '箱', '件'] or purpose not in PURPOSES:
                    raise ValidationError(f'第{index+1}项的品种、用途或单位不完整')
                destination = site.address if site else str(row.get('destination', '')).strip()
                if not destination:
                    raise ValidationError(f'第{index+1}项请选择收货点或填写地址')
                usable = number(row['required_usable'], Decimal('.01')) if row.get('required_usable') else None
                if usable and unit not in ['kg', '斤']:
                    raise ValidationError('净用量需求请选择重量单位')
                PurchaseDemand.objects.create(sheet=sheet, site=site, buyer=owner,
                    title=f'{site.name if site else "采购"} · {keyword}'[:160], keyword=keyword,
                    quantity=number(row.get('quantity'), Decimal('.01')), unit=unit,
                    budget=number(row.get('budget'), Decimal('.01')), purpose=purpose,
                    required_usable=usable, process=str(row.get('process', ''))[:80],
                    min_size=integer(row.get('min_size', 0), 0, 2000), grade=str(row.get('grade', ''))[:30],
                    packaging=str(row.get('packaging', ''))[:80], tolerance=number(row.get('tolerance', 10), maximum=100),
                    deadline=date, destination=destination[:200], location=site.location if site else '',
                    arrival_window=str(row.get('arrival_window', ''))[:80],
                    flexible_fields=[x for x in row.get('flexible_fields', []) if x in FLEXIBLE],
                    priority=integer(row.get('priority', 1), 1, 3), note=str(row.get('note', ''))[:2000],
                    is_demo=owner.username.startswith('demo_'))
            BusinessEvent.objects.create(actor=u, demand=sheet.demands.first(), title='多门店采购单已发布', note=sheet.title)
            return Response(sheet_data(sheet, u), status=201)
    qs = visible_sheets(u).order_by('-id')
    return Response({'items': [sheet_data(s, u) for s in qs[:100]], 'total': qs.count()})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def net_preview(request):
    return Response(net_options(request.user, request.data))


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def yields(request, pk):
    from .collaboration_api import batch_for
    from .commerce import number
    from .commerce_rules import PURPOSES
    if request.method == 'GET':
        b = StockBatch.objects.select_related('product').filter(pk=pk, product__is_deleted=False).first()
        if not b:
            raise NotFound()
        return Response([{'id': r.id, 'purpose': r.purpose, 'process': r.process,
            'input_weight': float(r.input_weight), 'usable_weight': float(r.usable_weight),
            'rate': round(float(r.usable_weight/r.input_weight)*100, 2), 'scope': r.scope,
            'note': r.note, 'actor': r.actor.username, 'created_at': r.created_at, 'is_demo': b.product.is_demo}
            for r in b.yield_records.select_related('actor').order_by('-id')[:100]])
    with transaction.atomic():
        b = batch_for(request.user, pk, True, 'inspect')
        if b.product.unit not in ['kg', '斤']:
            raise ValidationError('用途净得率需按重量记录，不以箱数推断重量')
        purpose = request.data.get('purpose')
        process = str(request.data.get('process', '')).strip()
        note = str(request.data.get('note', '')).strip()
        if purpose not in PURPOSES or not process or not note:
            raise ValidationError('请填写用途、加工方式与称重依据')
        gross = number(request.data.get('input_weight'), Decimal('.01'), b.quantity or Decimal('10000000'))
        usable = number(request.data.get('usable_weight'), maximum=gross)
        scope = request.data.get('scope', 'sample')
        if scope not in ['sample', 'whole']:
            raise ValidationError('请选择样本实称或整批实称')
        if scope == 'whole' and gross != b.quantity:
            raise ValidationError('整批实称投入量须与当前批次数量一致；部分称重请选择样本')
        record = PurposeYieldRecord.objects.create(batch=b, actor=request.user, purpose=purpose,
            process=process[:80], input_weight=gross, usable_weight=usable, scope=scope, note=note[:2000])
        BusinessEvent.objects.create(batch=b, actor=request.user, title='用途称重依据已更新', note=f'{process} · {usable}/{gross}{b.product.unit}')
        return Response({'id': record.id, 'evidence': yield_data(b, purpose, process)}, status=201)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def grading(request, pk):
    from .collaboration_api import batch_for
    from .commerce import number, integer, stock_sync, batch_data
    from .commerce_rules import movement, PURPOSES
    rows = request.data.get('outputs', [])
    if not isinstance(rows, list) or not 1 <= len(rows) <= 8:
        raise ValidationError('请填写1至8个分级结果')
    note = str(request.data.get('note', '')).strip()
    if not note:
        raise ValidationError('请记录实际分级及损耗依据')
    with transaction.atomic():
        b = batch_for(request.user, pk, True)
        if request.data.get('version') != b.version:
            raise ValidationError('批次数量已变化，请载入最新版本再确认分级')
        gross = number(request.data.get('input_quantity'), Decimal('.01'), b.quantity-b.reserved)
        loss = number(request.data.get('loss_quantity', 0), maximum=gross)
        prepared = []
        for row in rows:
            q = number(row.get('quantity'), Decimal('.01'), gross)
            purpose = row.get('purpose', 'fresh')
            if purpose not in PURPOSES:
                raise ValidationError('用途不正确')
            prepared.append((row, q, purpose))
        if sum(q for _, q, _ in prepared)+loss != gross:
            raise ValidationError('各分级数量加损耗必须等于投入量；原批次未修改')
        b.quantity -= gross
        b.save()
        movement(b, request.user, 'grading_out', -gross, note=note)
        outputs = []
        for row, q, purpose in prepared:
            child = StockBatch.objects.create(product=b.product, parent=b, code=f'{b.code}-G{uuid.uuid4().hex[:6].upper()}',
                quantity=q, grade=str(row.get('grade', b.grade))[:30], packaging=str(row.get('packaging', b.packaging))[:80],
                size_mm=integer(row.get('size_mm') or b.size_mm,0,2000), intended_purpose=purpose,
                sale_price=number(row.get('price'), Decimal('.01')), status='pending',
                harvest_date=b.harvest_date, available_date=b.available_date, removal_date=b.removal_date,
                storage_condition=b.storage_condition, inspections=b.inspections, note='分级后待人工复核。'+note)
            movement(child, request.user, 'grading_in', q, note=f'来自 {b.code}；待复核')
            outputs.append({'batch_id': child.id, 'code': child.code, 'quantity': float(q),
                'grade': child.grade, 'purpose': purpose, 'price': float(child.sale_price)})
        record = BatchGradingRecord.objects.create(batch=b, actor=request.user, input_quantity=gross,
            loss_quantity=loss, outputs=outputs, note=note)
        stock_sync(b.product)
        BusinessEvent.objects.create(batch=b, actor=request.user, title='分级称重已入账',
            note=f'投入 {gross}，分级 {gross-loss}，损耗 {loss}{b.product.unit}')
        return Response({'id': record.id, 'batch': batch_data(b), 'outputs': outputs, 'loss': float(loss)}, status=201)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def tasks(request, pk=None):
    from .commerce import integer
    qs = visible_tasks(request.user)
    if request.method=='GET' and any(request.query_params.get(k) for k in ['date','unit','site','exclude_demo']):
        from .commerce import visible_orders
        qs=qs.filter(order_id__in=scoped_orders(request,visible_orders(request.user)).values('id'))
    if request.method == 'POST':
        with transaction.atomic():
            t = qs.select_for_update().filter(pk=pk).first()
            if not t:
                raise NotFound('任务不存在或不属于当前岗位')
            u = request.user
            allowed = u.role == 'admin' or (t.kind in ['receive', 'replacement', 'return'] and t.order.user_id in buyer_ids(u, 'receive')) or (
                t.kind in ['pick', 'dispatch'] and t.supplier_id in supplier_ids(u, 'dispatch'))
            if not allowed:
                raise PermissionDenied('当前岗位仅可查看此任务')
            if request.data.get('version') != t.version:
                raise ValidationError('任务已更新，请载入最新版本再操作')
            if t.status in ['done', 'cancelled']:
                raise ValidationError('该任务已结束')
            action = request.data.get('action')
            note = str(request.data.get('note', '')).strip()[:2000]
            if action == 'claim':
                if t.assignee_id and t.assignee_id != u.id:
                    raise ValidationError('该任务已被领取，请联系负责人转派')
                t.assignee = u
                t.status = 'active'
            elif action == 'block':
                if not note:
                    raise ValidationError('请填写阻塞原因')
                t.status = 'blocked'
                t.note = note
            elif action == 'complete':
                if t.kind != 'pick':
                    raise ValidationError('发运、收货任务需通过实际发运或验收表单完成')
                if not note:
                    raise ValidationError('请记录分拣数量与核对凭证')
                close_task(t, u, note)
                BusinessEvent.objects.create(order=t.order, batch=t.batch, actor=u, title='分拣任务已完成', note=note)
                return Response(task_data(t))
            elif action == 'assign':
                person = User.objects.filter(pk=request.data.get('assignee_id'), is_active=True).first()
                identity = t.order.user_id if t.kind in ['receive', 'replacement', 'return'] else t.supplier_id
                ids = buyer_ids(person, 'receive') if person and person.role == 'retail' else supplier_ids(person, 'dispatch') if person else set()
                if not person or identity not in ids:
                    raise ValidationError('该人员没有执行此任务的岗位授权')
                t.assignee = person
            else:
                raise ValidationError('不支持的任务动作')
            t.version += 1
            t.events = [*t.events, {'action': action, 'actor': u.username, 'note': note, 'time': timezone.now().isoformat()}]
            t.save()
            return Response(task_data(t))
    if pk:
        t = qs.filter(pk=pk).first()
        if not t:
            raise NotFound()
        return Response(task_data(t))
    counts = dict(qs.values_list('status').annotate(n=Count('id')))
    if request.query_params.get('status'):
        qs = qs.filter(status=request.query_params['status'])
    else:
        qs = qs.exclude(status='cancelled')
    if request.query_params.get('kind'):
        qs = qs.filter(kind=request.query_params['kind'])
    if request.query_params.get('site'):
        qs = qs.filter(site_id=integer(request.query_params['site'], 1))
    query = request.query_params.get('search', '').strip()
    if query:
        if query.isdigit():
            qs = qs.filter(Q(pk=int(query)) | Q(order_id=int(query)))
        elif query.startswith('HL') and len(query)>8 and query[2:].isdigit():
            qs = qs.filter(order_id=int(query[8:]))
        else:
            qs = qs.filter(Q(order__product__name__icontains=query) | Q(batch__code__icontains=query) |
            Q(order__tracking_number__icontains=query) | Q(site__name__icontains=query))
    page = integer(request.query_params.get('page', 1), 1, 100000)
    return Response({'items': [task_data(t) for t in qs.order_by('due_at', '-id')[(page-1)*30:page*30]],
        'total': qs.count(), 'counts': counts, 'page': page})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def order_list(request):
    from .commerce import visible_orders, order_data, integer, day
    qs = scoped_orders(request,visible_orders(request.user))
    if request.query_params.get('dispatched')=='1':qs=qs.filter(allocations__dispatched__gt=0).distinct()
    query = request.query_params.get('search', '').strip()
    if query:
        if query.isdigit():
            qs = qs.filter(pk=int(query))
        else:
            qs = qs.filter(Q(product__name__icontains=query) | Q(user__username__icontains=query) | Q(product__owner__username__icontains=query))
    if request.query_params.get('id'):
        qs = qs.filter(pk=integer(request.query_params['id'], 1))
    status = request.query_params.get('status')
    if request.query_params.get('sheet'):
        qs = qs.filter(sheet_id=integer(request.query_params['sheet'],1))
    counts=dict(qs.values_list('status').annotate(n=Count('id')))
    payment_review=qs.filter(payment_status='review').count()
    if status and status != 'all':
        qs = qs.filter(status=status)
    page = integer(request.query_params.get('page', 1), 1, 100000)
    return Response({'items': [order_data(o, request.user) for o in qs[(page-1)*20:page*20]],
        'total': qs.count(), 'page': page, 'counts':counts, 'payment_review':payment_review})


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def accounts(request, pk=None):
    from .commerce import visible_orders, event, number
    from .workflow import finish_order_if_clear
    u = request.user
    orders = scoped_orders(request,visible_orders(u))
    if request.method == 'POST':
        with transaction.atomic():
            r = WeightReconciliation.objects.select_for_update().select_related('order__product__owner').filter(pk=pk, order_id__in=orders.values('id')).first()
            if not r:
                raise NotFound()
            if request.data.get('action') == 'resubmit':
                if r.order.user_id not in buyer_ids(u,'receive') or r.status != 'disputed':
                    raise PermissionDenied('请由收货岗位在对方提出复核后补充依据')
                note=str(request.data.get('note','')).strip()
                if not note:raise ValidationError('请补充实际称重和验收依据')
                r.note=f'{r.note}\n{u.username} 补充：{note}'[-4000:]
                r.status='pending';r.save()
                event(r.order,u,'实重对账依据已补充',f'对账单 #{r.id} · {note}')
                return Response({'id':r.id,'status':r.status})
            if u.role != 'admin' and r.order.product.owner_id not in supplier_ids(u, 'manage'):
                raise PermissionDenied('请由交易供货方核对合格实收重量')
            if r.status != 'pending':
                raise ValidationError('该实重差额已处理')
            if request.data.get('action') == 'reject':
                note = str(request.data.get('note', '')).strip()
                if not note:
                    raise ValidationError('请填写需要重新核对的依据')
                # A rejected measurement remains an open discrepancy until revised and agreed.
                r.note = note
                r.status = 'disputed'
            elif request.data.get('action') == 'confirm':
                r.status = 'confirmed'
                r.confirmed_at = timezone.now()
                if r.difference_amount:
                    r.case = SettlementCase.objects.create(order=r.order, creator=u,
                        kind='supplement' if r.difference_amount > 0 else 'discount', status='accepted',
                        amount=abs(r.difference_amount), note=f'实重对账 #{r.id} 双方确认的数量尾差，依原成交单价；请实际执行后登记凭证。')
            else:
                raise ValidationError('不支持的对账动作')
            r.save()
            event(r.order, u, '实重对账已更新', f'对账单 #{r.id} · {r.status}')
            quality_open=any(d.receipt.get('quality_issue') or d.receipt.get('packaging_issue') or
                d.receipt.get('accepted',0)<d.receipt.get('received',0) for d in r.order.deliveries.filter(status='received'))
            finish_order_if_clear(r.order,resolved=not quality_open)
            r.order.save()
    reconciliations = WeightReconciliation.objects.filter(order_id__in=orders.values('id')).select_related('order__product', 'order__user', 'delivery')
    if u.role=='supplier':
        reconciliations=reconciliations.filter(order__product__owner_id__in=supplier_ids(u))
    payables = SupplierSettlement.objects.select_related('payer', 'supplier', 'order__product')
    if u.role != 'admin':
        payables = payables.filter(Q(payer_id__in=supplier_ids(u)) | Q(supplier_id__in=supplier_ids(u))) if u.role == 'supplier' else payables.none()
    cases = SettlementCase.objects.filter(order_id__in=orders.values('id')).select_related('order__product')
    if u.role == 'supplier':
        cases = cases.filter(order__product__owner_id__in=supplier_ids(u))
    return Response({'reconciliations': [{'id': r.id, 'order_id': r.order_id, 'product': r.order.snapshot.get('name'),
        'buyer_id': r.order.user_id, 'seller_id': r.order.product.owner_id, 'unit': r.order.snapshot.get('unit'),
        'expected': float(r.expected_quantity), 'received': float(r.received_quantity), 'accepted': float(r.accepted_quantity),
        'difference': float(r.difference_amount), 'status': r.status, 'note': r.note, 'case_id': r.case_id,
        'created_at': r.created_at} for r in reconciliations.order_by('-id')[:200]],
        'supplier_settlements': [settlement_data(s) for s in payables.order_by('-id')[:200]],
        'cases': [{'id': c.id, 'order_id': c.order_id, 'product': c.order.snapshot.get('name'), 'kind': c.kind,
            'amount': float(c.amount), 'quantity': float(c.quantity), 'status': c.status,
            'note': c.note, 'reference': c.reference} for c in cases.order_by('-id')[:200]],
        'summary': {'weight_pending': reconciliations.filter(status__in=['pending', 'disputed']).count(),
            'cases_pending': cases.exclude(status__in=['confirmed', 'rejected']).count(),
            'supply_pending': payables.exclude(status__in=['confirmed', 'cancelled']).count()}})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def supply_payment(request, pk):
    with transaction.atomic():
        s = SupplierSettlement.objects.select_for_update().select_related('payer', 'supplier', 'order').filter(pk=pk).first()
        if not s:
            raise NotFound()
        u = request.user
        action = request.data.get('action')
        if action == 'record':
            if s.payer_id not in supplier_ids(u, 'manage') or s.status != 'pending':
                raise PermissionDenied('请由原交易供货方在待执行状态登记实际付款')
            reference = str(request.data.get('reference', '')).strip()
            if len(reference) < 4:
                raise ValidationError('请填写实际付款凭证，至少4个字符')
            s.status, s.reference = 'recorded', reference[:200]
        elif action == 'confirm':
            if s.supplier_id not in supplier_ids(u, 'manage') or s.status != 'recorded':
                raise PermissionDenied('请由替代供货方核对到账')
            s.status = 'confirmed'
        else:
            raise ValidationError('不支持的动作')
        s.events = [*s.events, {'action': action, 'actor': u.username, 'time': timezone.now().isoformat()}]
        s.save()
        return Response(settlement_data(s))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def control(request):
    from .commerce import visible_orders, number, day, coordinates, integer
    from .decisions import remaining_demand, remaining_usable
    u = request.user
    date = day(request.query_params.get('date'), timezone.localdate())
    unit = request.query_params.get('unit', 'kg')
    if unit not in ['kg', '斤', '箱', '件']:
        raise ValidationError('单位不正确')
    start = timezone.make_aware(datetime.combine(date, time.min))
    end = start+timedelta(days=1)
    all_orders = visible_orders(u)
    orders = all_orders.filter(Q(promised_date=date) | Q(promised_date__isnull=True, created_at__gte=start, created_at__lt=end),snapshot__unit=unit)
    demands = PurchaseDemand.objects.select_related('buyer', 'site').prefetch_related('quotes__order').filter(deadline=date,unit=unit)
    if u.role == 'retail':
        demands = demands.filter(buyer_id__in=buyer_ids(u))
    site_id = request.query_params.get('site')
    if site_id:
        site_id = integer(site_id, 1)
        orders = orders.filter(site_id=site_id)
        demands = demands.filter(site_id=site_id)
    if request.query_params.get('exclude_demo') == '1':
        orders = orders.filter(is_demo=False)
        demands = demands.filter(is_demo=False)
    selected = list(orders.select_related('site', 'product__owner', 'user', 'batch').prefetch_related('allocations__batch__product', 'deliveries', 'tasks'))
    active = [o for o in selected if o.status not in ['cancelled', 'refunded']]
    weighted = [o for o in active if o.snapshot.get('unit') == unit]
    managed=supplier_ids(u)
    def foreign(o):return u.role=='supplier' and o.product.owner_id not in managed
    def parts(o):return [a for a in o.allocations.all() if not foreign(o) or a.batch.product.owner_id in managed]
    def promised_quantity(o):return sum(a.quantity for a in parts(o)) if foreign(o) else o.quantity or 0
    def accepted_quantity(o):return sum(Decimal(str(d.receipt.get('accepted',0))) for d in o.deliveries.all() if d.supplier_id in managed) if foreign(o) else o.accepted_quantity or 0
    promised = sum(float(promised_quantity(o)) for o in weighted)
    accepted = sum(float(accepted_quantity(o)) for o in weighted)
    dispatched = sum(float(a.dispatched) for o in weighted for a in parts(o))
    gap_rows = []
    gap = 0.
    for d in demands:
        remaining = remaining_demand(d)
        if d.status == 'open' and remaining > 0:
            usable = remaining_usable(d)
            if d.unit == unit:
                gap += float(remaining)
            gap_rows.append({'id': d.id, 'title': d.title, 'keyword': d.keyword, 'unit': d.unit,
                'quantity': float(remaining), 'required_usable': float(usable) if usable is not None else None,
                'site': d.site.name if d.site else d.destination, 'priority': d.priority,
                'purpose': d.purpose, 'deadline': d.deadline})
    task_qs = visible_tasks(u).filter(order_id__in=orders.values('id'))
    tasks_open = task_qs.exclude(status__in=['done', 'cancelled'])
    nodes = {}
    links = []
    for o in active:
        target = None
        if o.site and coordinates(o.site.location):
            target = -o.site_id
            nodes.setdefault(target, {'id': target, 'site_id': o.site_id, 'name': o.site.name, 'origin': o.site.address,
                'coords': coordinates(o.site.location), 'kind': 'site', 'stock': 0, 'unit': '笔关联订单',
                'verified': o.site.location_verified, 'coordinate_source': o.site.coordinate_source,
                'coordinate_system': o.site.coordinate_system})
            nodes[target]['stock'] += 1
        for a in parts(o):
            p = a.batch.product
            if not coordinates(p.location):
                continue
            nodes.setdefault(p.id, {'id': p.id, 'name': p.origin or p.name, 'origin': p.origin, 'coords': coordinates(p.location),
                'kind': 'supply', 'stock': 0, 'unit': '个履约批次', 'verified': False,
                'coordinate_source': '供货方录入产地', 'coordinate_system': '待供货方核对'})
            nodes[p.id]['stock'] += 1
            if target:
                links.append({'source': p.id, 'target': target, 'order_id': o.id,
                    'label': f'{o.snapshot.get("name", "")} · {a.quantity}{o.snapshot.get("unit", "")} · {o.site.name}',
                    'status': o.status, 'kind': 'relationship'})
    # Sites without an active order remain selectable, clearly shown as business records.
    sites = BusinessSite.objects.select_related('company')
    if u.role != 'admin':
        sites = sites.filter(Q(company__owner_id__in=participant_ids(u, 'read')) | Q(pk__in=all_orders.values('site_id'))).distinct()
    site_rows = []
    for site in sites:
        site_rows.append({'id': site.id, 'name': site.name, 'kind': site.kind, 'company': site.company.name,
            'address': site.address, 'location': site.location, 'verified': site.location_verified})
        if (not site_id or site.id == site_id) and coordinates(site.location) and -site.id not in nodes:
            nodes[-site.id] = {'id': -site.id, 'site_id': site.id, 'name': site.name, 'origin': site.address,
                'coords': coordinates(site.location), 'kind': 'site', 'stock': 0, 'unit': '笔关联订单',
                'verified': site.location_verified, 'coordinate_source': site.coordinate_source,
                'coordinate_system': site.coordinate_system}
    risks = []
    for o in active:
        isolated = [a.batch.code for a in parts(o) if a.batch.status != 'released' and a.quantity > a.dispatched]
        if isolated:
            risks.append({'id': f'batch-{o.id}', 'order_id': o.id, 'kind': '批次待复核', 'title': o.snapshot.get('name'),
                'note': '、'.join(isolated), 'route': '/recovery', 'severity': 3})
        if o.status == 'issue':
            risks.append({'id': f'issue-{o.id}', 'order_id': o.id, 'kind': '验收差异', 'title': o.snapshot.get('name'),
                'note': o.issue, 'route': f'/orders?order={o.id}', 'severity': 2})
        if o.promised_date and o.promised_date < timezone.localdate() and o.status != 'completed':
            risks.append({'id': f'late-{o.id}', 'order_id': o.id, 'kind': '超过到货日', 'title': o.snapshot.get('name'),
                'note': str(o.promised_date), 'route': f'/orders?order={o.id}', 'severity': 3})
    for t in tasks_open.filter(Q(status='blocked') | Q(due_at__lt=timezone.now()))[:20]:
        risks.append({'id': f'task-{t.id}', 'order_id': t.order_id, 'kind': '作业阻塞' if t.status == 'blocked' else '任务超时',
            'title': t.order.snapshot.get('name'), 'note': t.note, 'route': f'/workboard?task={t.id}', 'severity': 3})
    from .coordination import TASK_NAMES
    stages = [{'key': key, 'label': label, 'total': task_qs.filter(kind=key).count(),
        'done': task_qs.filter(kind=key, status='done').count()} for key, label in TASK_NAMES.items() if key in ['pick', 'dispatch', 'receive', 'replacement']]
    events = BusinessEvent.objects.filter(Q(order_id__in=all_orders.values('id')) |
        Q(demand__buyer_id__in=buyer_ids(u)) | Q(batch__product__owner_id__in=supplier_ids(u)))
    if u.role == 'admin':
        events = BusinessEvent.objects.all()
    open_cases = SettlementCase.objects.filter(order_id__in=orders.values('id')).exclude(status__in=['confirmed', 'rejected'])
    if u.role=='supplier':open_cases=open_cases.filter(order__product__owner_id__in=supplier_ids(u))
    return Response({'date': date, 'unit': unit, 'as_of': timezone.now(), 'role': u.role,
        'kpis': {'orders': len(active), 'promised': round(promised, 2), 'accepted': round(accepted, 2),
            'dispatched': round(dispatched, 2), 'gap': round(gap, 2), 'gap_lines': len(gap_rows),
            'completed': sum(o.status == 'completed' for o in active),
            'completion': round(sum(o.status == 'completed' for o in active)/len(active)*100, 1) if active else None,
            'tasks_open': tasks_open.count(), 'tasks_overdue': tasks_open.filter(due_at__lt=timezone.now()).count(),
            'cases_amount': float(open_cases.aggregate(v=Sum('amount'))['v'] or 0),
            'demo_orders': sum(o.is_demo for o in active)},
        'gaps': sorted(gap_rows, key=lambda x: -x['priority'])[:30],
        'risks': sorted(risks, key=lambda x: -x['severity'])[:30], 'nodes': list(nodes.values()), 'links': links,
        'sites': site_rows, 'stages': stages,
        'tasks': [task_data(t) for t in task_qs.exclude(status='cancelled').order_by('due_at', '-id')[:60]],
        'orders': [{'id': o.id, 'name': o.snapshot.get('name'), 'number': f'HL{o.created_at:%y%m%d}{o.id:05d}',
            'quantity': float(promised_quantity(o)), 'unit': o.snapshot.get('unit'), 'status': o.status,
            'site': o.site.name if o.site else o.address_info, 'supplier': o.product.owner.username,
            'promised_date': o.promised_date, 'is_demo': o.is_demo,
            'dispatched': float(sum(a.dispatched for a in parts(o))), 'accepted': float(accepted_quantity(o))} for o in active[:30]],
        'events': list(events.order_by('-id').values('id', 'title', 'note', 'order_id', 'batch_id', 'created_at')[:30]),
        'note': '按所选到货日和单位统计；地图连线表示履约关联，非车辆位置或道路导航。'})


urlpatterns = [path('sheets/', sheets), path('net-preview/', net_preview),
    path('batches/<int:pk>/yields/', yields), path('batches/<int:pk>/grading/', grading),
    path('tasks/', tasks), path('tasks/<int:pk>/', tasks), path('orders/list/', order_list),
    path('accounts/', accounts), path('accounts/<int:pk>/', accounts),
    path('supplier-payments/<int:pk>/', supply_payment), path('control/', control)]
