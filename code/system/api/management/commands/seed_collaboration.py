"""Idempotent, clearly labelled collaboration scenarios. Never reset user edits."""
import json
from datetime import timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone
from api.models import (User,StockBatch,PurchaseDemand,DemandQuote,SupplyIncident,RecoveryPlan,
    InspectionTask,Company,CompanyMember,BusinessSite)
from api.commerce import create_order,notice,stock_sync
from api.commerce_rules import movement
from api.decisions import recovery_compute


class Command(BaseCommand):
    help='补充明确标记的用途采购、复检与异常补配演示，不覆盖已有记录。'
    @transaction.atomic
    def handle(self,*args,**kwargs):
        buyer=User.objects.get(username='demo_buyer');supplier=User.objects.get(username='demo_supplier')
        admin=User.objects.get(username='demo_admin')
        first=StockBatch.objects.get(code='DEMO-001')
        for code,usable in [('DEMO-001',95),('DEMO-002',80)]:
            b=StockBatch.objects.get(code=code)
            if b.product.is_demo and b.input_weight is None:
                b.input_weight=100;b.usable_weight=usable
                b.weight_note='演示分拣参数，用于展示成本计算；不是实际称重结果。';b.save()
        source,created=StockBatch.objects.get_or_create(code='DEMO-REC-01',defaults={
            'product':first.product,'quantity':80,'grade':first.grade,'packaging':first.packaging,
            'size_mm':first.size_mm,'status':'released','sample_size':200,'defect_count':1,
            'available_date':timezone.localdate(),'note':'异常补配演示专用批次，非真实库存。'})
        if created:
            movement(source,supplier,'inbound',80,note='演示初始化，非真实入库')
            d=PurchaseDemand.objects.create(buyer=buyer,title='演示门店 · 异常批次补配',keyword='苹果',quantity=40,
                unit=first.product.unit,budget=10,min_size=70,grade=first.grade,packaging=first.packaging,
                deadline=timezone.localdate()+timedelta(days=5),destination='成都市（演示收货点）',purpose='fresh',
                priority=2,status='ordered',is_demo=True)
            o=create_order(buyer,source,Decimal(40),address={'receiver_name':'演示采购联系人','receiver_phone':'13800000000','address':d.destination})
            o.status='paid';o.payment_status='confirmed';o.payment_reference='DEMO-RECEIPT';o.promised_date=d.deadline
            o.snapshot={**o.snapshot,'demand_id':d.id,'purpose':'fresh','contract':{'deadline':d.deadline.isoformat()}};o.save()
            DemandQuote.objects.create(demand=d,batch=source,supplier=supplier,price=o.unit_price_at_purchase,quantity=40,
                status='accepted',order=o,note='演示已承接报价，非真实成交。')
            i=SupplyIncident.objects.create(batch=source,creator=supplier,kind='quarantine',note='演示：发运前复核需要隔离，协调替代批次。')
            source.status='quarantine';source.save();movement(source,supplier,'incident',note=i.note);stock_sync(source.product)
            result=recovery_compute(supplier,i,'stable')
            p=RecoveryPlan.objects.create(incident=i,creator=supplier,strategy='stable',result=json.loads(json.dumps(result,cls=DjangoJSONEncoder)))
            notice(buyer,'演示订单有补配方案待协调','供货方可发送方案后，你在采购端确认。',f'/recovery?plan={p.id}')
        peach=StockBatch.objects.filter(code='DEMO-008').first()
        if peach and not InspectionTask.objects.filter(batch=peach).exists():
            InspectionTask.objects.create(batch=peach,creator=supplier,target_sample=50,metric='appearance',
                position='演示抽样计划：前、中、后段随机取样',note='演示待执行任务，不代表已完成真实抽检。')
        for owner,name,site_name,address,coords in [
            (buyer,'演示连锁采购主体','演示城市收货点','成都市行政区域示例，非真实经营地址','104.0665,30.5723'),
            (supplier,'演示产地供给主体','演示产地集配点','陕西洛川行政区域示例，非真实经营地址','109.432,35.762')]:
            company,_=Company.objects.get_or_create(owner=owner,name=name)
            CompanyMember.objects.get_or_create(company=company,user=owner,defaults={'job':'owner'})
            BusinessSite.objects.get_or_create(company=company,name=site_name,defaults={'address':address,'location':coords,
                'contact':'演示联系人','phone':'13800000000'})
        self.stdout.write('Collaboration demo scenarios ready; existing edits preserved.')
