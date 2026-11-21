from datetime import datetime,time,timedelta
from decimal import Decimal
from django.db.models import Count,Sum,Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from .models import SettlementCase


def report_counts(user,params=None,weekly=False):
    from .commerce import visible_orders,day
    params=params or {};qs=visible_orders(user)
    if params.get('exclude_demo')=='1':qs=qs.filter(is_demo=False)
    start=day(params.get('start'));end=day(params.get('end'))
    if start and end and end<start:raise ValidationError('结束日期不能早于开始日期')
    if start:qs=qs.filter(created_at__gte=timezone.make_aware(datetime.combine(start,time.min)))
    if end:qs=qs.filter(created_at__lt=timezone.make_aware(datetime.combine(end+timedelta(days=1),time.min)))
    summary=qs.aggregate(orders=Count('id'),contract=Sum('total_amount'),
        gross=Sum('total_amount',filter=Q(payment_status='confirmed')),
        confirmed_count=Count('id',filter=Q(payment_status='confirmed')),
        completed=Count('id',filter=Q(status='completed')),issues=Count('id',filter=Q(status='issue')),
        pending=Count('id',filter=Q(status='pending')),shipping=Count('id',filter=Q(status='paid')),
        transit=Count('id',filter=Q(status='shipped')))
    adjustments=SettlementCase.objects.filter(order_id__in=qs.values('id'),status='confirmed')
    refunds=adjustments.filter(kind__in=['refund','discount']).aggregate(v=Sum('amount'))['v'] or Decimal(0)
    extra=adjustments.filter(kind='supplement').aggregate(v=Sum('amount'))['v'] or Decimal(0)
    daily_qs=qs
    if weekly:daily_qs=daily_qs.filter(created_at__gte=timezone.make_aware(datetime.combine(timezone.localdate()-timedelta(days=6),time.min)))
    buckets={}
    for created,amount,payment in daily_qs.values_list('created_at','total_amount','payment_status').iterator(chunk_size=500):
        key=timezone.localdate(created).isoformat()
        row=buckets.setdefault(key,{'created_at__date':key,'count':0,'amount':0.,'confirmed_amount':0.})
        row['count']+=1;row['amount']+=float(amount)
        if payment=='confirmed':row['confirmed_amount']+=float(amount)
    return {'orders':summary['orders'],'contract_amount':float(summary['contract'] or 0),
        'confirmed_receipts':float((summary['gross'] or 0)+extra-refunds),
        **{k:summary[k] for k in ['confirmed_count','completed','issues','pending','shipping','transit']},
        'refunds':float(refunds),'supplements':float(extra),
        'cases_open':SettlementCase.objects.filter(order_id__in=qs.values('id')).exclude(status__in=['confirmed','rejected']).count(),
        'stages':list(qs.order_by('status').values('status').annotate(count=Count('id'))),
        'daily':[buckets[k] for k in sorted(buckets)],
        'suppliers':[] if weekly else list(qs.order_by('product__owner__username').values('product__owner__username').annotate(count=Count('id'),amount=Sum('total_amount'))),
        'scope':'平台' if user.role=='admin' else '当前账号',
        'note':'完整记录统计；收付款为人工核对记录，不代表平台营收。'}
