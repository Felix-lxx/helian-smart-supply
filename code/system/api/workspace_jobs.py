from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from .models import Order,DemandQuote,PurchaseDemand,ScheduledJobRun,WorkspaceNotification


def run_due_jobs():
    from .commerce import release_order,notice
    now=timezone.now();released=0
    for pk in Order.objects.filter(status='pending',payment_status='unpaid',created_at__lt=now-timedelta(hours=24)).values_list('pk',flat=True):
        with transaction.atomic():
            o=Order.objects.select_for_update().select_related('product__owner','user').get(pk=pk)
            if o.status=='pending' and o.payment_status=='unpaid':
                release_order(o,o.user);released+=1
                notice(o.user,f'订单 #{o.id} 付款预留已到期','预留已释放，关联需求已恢复缺口',f'/orders?order={o.id}')
    expired=DemandQuote.objects.filter(status='pending',expires_at__lt=now).update(status='expired')
    closed=PurchaseDemand.objects.filter(status='open',deadline__lt=timezone.localdate()).update(status='expired')
    reminders=0
    for o in Order.objects.filter(status__in=['paid','shipped'],promised_date__lte=timezone.localdate()+timedelta(days=1)).select_related('user'):
        title=f'订单 #{o.id} 临近约定到货日期'
        if not WorkspaceNotification.objects.filter(recipient=o.user,title=title,created_at__gte=now-timedelta(days=1)).exists():
            notice(o.user,title,str(o.promised_date),f'/orders?order={o.id}');reminders+=1
    result={'released':released,'expired_quotes':expired,'expired_demands':closed,'reminders':reminders}
    latest=ScheduledJobRun.objects.order_by('-created_at').first()
    if any(result.values()) or not latest or latest.created_at<now-timedelta(minutes=5):
        ScheduledJobRun.objects.create(name='预留、报价与交期检查',result=result)
    return result
