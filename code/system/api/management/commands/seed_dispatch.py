"""Clearly labelled, idempotent multi-site fulfilment demo. No production records changed."""
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from api.models import (User, Company, CompanyMember, BusinessSite, StockBatch, Product,
    PurposeYieldRecord, ProcurementSheet, PurchaseDemand, Order, SettlementCase)
from api.commerce import create_order, event
from api.coordination import sync_order_tasks
from api.transport import transport_action


class Command(BaseCommand):
    help = '补齐明确标识的多门店集采、用途称重、作业和实重对账演示；不重置已有操作。'

    @transaction.atomic
    def handle(self, *args, **options):
        buyer=User.objects.get(username='demo_buyer')
        supplier=User.objects.get(username='demo_supplier')
        coop=User.objects.get(username='demo_coop')
        today=timezone.localdate()
        company,_=Company.objects.get_or_create(owner=buyer,name='演示连锁采购主体',defaults={'kind':'buyer'})
        CompanyMember.objects.get_or_create(company=company,user=buyer,defaults={'job':'owner'})
        specs=[('演示武侯门店','成都市武侯区行政区域演示点，非真实门店','104.0435,30.6418','store'),
            ('演示锦江门店','成都市锦江区行政区域演示点，非真实门店','104.0835,30.6563','store'),
            ('演示高新门店','成都市高新区行政区域演示点，非真实门店','104.0658,30.5514','store'),
            ('演示中央厨房','成都市郫都区行政区域演示点，非真实厨房','103.9005,30.7951','kitchen')]
        sites=[]
        for name,address,location,kind in specs:
            site,_=BusinessSite.objects.get_or_create(company=company,name=name,defaults={'address':address,
                'location':location,'kind':kind,'coordinate_source':'行政区域演示坐标','location_verified':False,
                'contact':'演示收货员','phone':'13800000000'})
            sites.append(site)
        image=Product.objects.filter(is_demo=True,variety='苹果').first()
        alt,_=Product.objects.get_or_create(owner=coop,name='演示同城红富士苹果',is_demo=True,defaults={
            'variety':'苹果','category':'fruits_vegs','retail_price':Decimal('7.40'),'unit':'kg','grade':'优选级',
            'packaging':'5kg箱装','status':'on_sale','min_order':10,'delivery_days':0,
            'origin':'四川成都（演示集配点，非真实供货）','location':'103.995,30.681',
            'image_url':image.image_url if image else '', 'description':'明确标识的跨供货方补配演示，不代表真实供应。'})
        alt_batch,_=StockBatch.objects.get_or_create(code='DEMO-ALT-APPLE',defaults={'product':alt,'quantity':240,
            'grade':'优选级','packaging':'5kg箱装','size_mm':85,'status':'released','sample_size':200,'defect_count':1,
            'available_date':today,'note':'演示同城补配与用途称重参数，非实际质量证明。'})
        for batch in StockBatch.objects.filter(product__is_demo=True,product__unit='kg').exclude(code='DEMO-REC-01'):
            for purpose,process,rate in [('fresh','整果挑选',Decimal('.95')),('kitchen','去皮去核',Decimal('.78')),('juice','清洗榨汁',Decimal('.83'))]:
                if batch.code=='DEMO-002':
                    rate={'fresh':Decimal('.80'),'kitchen':Decimal('.82'),'juice':Decimal('.85')}[purpose]
                if not batch.yield_records.filter(purpose=purpose,process=process).exists():
                    PurposeYieldRecord.objects.create(batch=batch,actor=batch.product.owner,purpose=purpose,process=process,
                        input_weight=100,usable_weight=100*rate,scope='sample',
                        note='演示作业参数，用于解释净用量反算；非真实称重或加工结果。')
        sheet,created=ProcurementSheet.objects.get_or_create(creator=buyer,submission_key='DEMO-DISPATCH-V3',defaults={
            'buyer':buyer,'company':company,'title':'演示 · 多门店与中央厨房集采','delivery_date':today,'template':True,
            'note':'用于展示多门店报价、实际作业、验收和对账链路，全部为演示记录。'})
        if created:
            available=list(StockBatch.objects.select_related('product__owner').filter(product__is_demo=True,status='released',
                product__unit='kg').exclude(code__startswith='DEMO-REC').order_by('id'))
            for i in range(12):
                batch=available[i%len(available)]
                batch.refresh_from_db()
                if batch.quantity-batch.reserved<20:continue
                site=sites[i%len(sites)]
                qty=Decimal(20)
                d=PurchaseDemand.objects.create(buyer=buyer,sheet=sheet,site=site,title=f'{site.name} · {batch.product.variety}',
                    keyword=batch.product.variety,quantity=qty,unit='kg',budget=20,deadline=today,destination=site.address,
                    location=site.location,purpose='kitchen' if site.kind=='kitchen' else 'fresh',status='ordered',is_demo=True)
                o=create_order(buyer,batch,qty,address={'receiver_name':site.contact,'receiver_phone':site.phone,'address':site.address},
                    site=site,sheet=sheet,promised_date=today,settlement_basis='accepted_weight' if i in [5,8] else 'contract',weight_tolerance=2)
                o.snapshot={**o.snapshot,'demand_id':d.id,'dispatch_demo':True}
                from api.models import DemandQuote
                DemandQuote.objects.create(demand=d,batch=batch,supplier=batch.product.owner,price=o.unit_price_at_purchase,
                    quantity=qty,status='accepted',order=o,terms=o.snapshot['pricing'],note='演示承接报价，非实际成交。')
                if i!=11:
                    o.status='paid';o.payment_status='confirmed';o.payment_reference='DEMO-RECEIPT'
                    o.save();event(o,batch.product.owner,'演示收款核对','用于体验作业流程，非真实收款。')
                if i in [2,3,4,5,6,7,8,9]:
                    transport_action(SimpleNamespace(user=batch.product.owner,data={'quantity':20,'carrier':'演示交接配送',
                        'tracking_number':f'DEMO-DELIVERY-{o.id}','supplier_id':batch.product.owner_id}),o,'ship')
                if i in [5,6,7,8,9]:
                    received=Decimal('19.80') if i in [5,8] else qty
                    accepted=Decimal(18) if i==9 else received
                    transport_action(SimpleNamespace(user=buyer,data={'delivery_id':o.deliveries.first().id,
                        'received_quantity':float(received),'accepted_quantity':float(accepted),
                        'quality_issue':'演示：规格与验收约定存在差异' if i==9 else '',
                        'note':'演示验收记录，非实际称重。'}),o,'receive')
                sync_order_tasks(o,batch.product.owner)
            for i,(word,q,net) in enumerate([('苹果',80,None),('黄瓜',60,None),('苹果',50,Decimal(38))]):
                site=sites[i%len(sites)]
                PurchaseDemand.objects.create(buyer=buyer,sheet=sheet,site=site,title=f'{site.name} · 追加{word}',
                    keyword=word,quantity=q,unit='kg',budget=10,deadline=today,destination=site.address,location=site.location,
                    purpose='kitchen' if net else 'fresh',required_usable=net,process='去皮去核' if net else '',
                    tolerance=10,priority=3 if i==0 else 2,is_demo=True,note='演示未覆盖需求，供方案比较。')
        # Only enrich missing links of labelled demo records; never rewrite user-modified dates or outcomes.
        for i,o in enumerate(Order.objects.filter(is_demo=True,site__isnull=True).select_related('product__owner','user')):
            o.site=sites[i%len(sites)]
            if not o.promised_date:o.promised_date=today
            o.save(update_fields=['site','promised_date'])
            sync_order_tasks(o,o.product.owner)
        self.stdout.write(self.style.SUCCESS('Dispatch demo ready: sites, purpose evidence, procurement sheet, tasks and actual-weight reconciliation. All records labelled.'))
