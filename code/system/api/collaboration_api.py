"""Cross-workspace actions. No synthetic scores, predictions or payment execution."""
import json
from decimal import Decimal
from datetime import timedelta
from types import SimpleNamespace
from django.db import transaction
from django.db.models import Q, Sum, Count
from django.utils import timezone
from django.urls import path
from django.core.serializers.json import DjangoJSONEncoder
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied, NotFound
from .models import (StockBatch, Product, Order, PurchaseDemand, DemandQuote, InspectionTask,
    InventoryMovement, SupplyIncident, RecoveryPlan, SettlementCase, ScheduledJobRun,
    Company, CompanyMember, BusinessSite, User)
from .commerce_rules import assess, price_for, json_price, movement, public_weight, PURPOSES, FLEXIBLE, hard_quality_reason
from .decisions import remaining_demand, recovery_compute, execute_recovery
from .access import supplier_ids


def batch_for(user, pk, lock=False, action='manage'):
    from .commerce import role
    role(user,'supplier','admin')
    qs=StockBatch.objects.select_related('product__owner')
    if lock:qs=qs.select_for_update()
    if user.role!='admin':qs=qs.filter(product__owner_id__in=supplier_ids(user,action))
    b=qs.filter(pk=pk).first()
    if not b:raise NotFound('批次不存在或无操作权限')
    return b


def plan_participants(plan):
    return {uid for row in plan.result.get('rows',[]) for uid in
            [row['buyer_id'],row['seller_id'],*[p['supplier_id'] for p in row['parts']]]}


def inspection_priority(batch, demands=None):
    from .commerce import wilson
    blocked=[]
    for d in demands if demands is not None else PurchaseDemand.objects.filter(status='open',deadline__gte=timezone.localdate()):
        issues=assess(batch,d,robust=True)
        fields={x['field'] for x in issues}
        if fields and fields<= {'quality','evidence'} and batch.status in ['released','pending']:
            remaining=remaining_demand(d)
            if remaining>0:
                blocked.append({'id':d.id,'title':d.title,'quantity':float(remaining),'unit':d.unit,
                    'tolerance':d.tolerance,'deadline':d.deadline,'priority':d.priority})
    lo,hi=wilson(batch.sample_size,batch.defect_count)
    priority=round(sum(x['priority'] for x in blocked)*(hi-lo),2)
    return {'batch_id':batch.id,'code':batch.code,'product':batch.product.name,'interval':[lo,hi],
        'sample_size':batch.sample_size,'defect_count':batch.defect_count,'blocked_demands':blocked,
        'priority':priority,'reason':'受影响需求优先级之和 × 外观区间宽度；规则排序，不是风险概率'}


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def workspace(request):
    from .commerce import visible_orders, batch_data
    u=request.user;orders=visible_orders(u)
    batches=StockBatch.objects.select_related('product__owner').prefetch_related('product__price_tiers').filter(product__is_deleted=False)
    if u.role=='supplier':batches=batches.filter(product__owner_id__in=supplier_ids(u))
    if u.role=='retail':batches=batches.filter(orders__user=u).distinct()
    tasks=InspectionTask.objects.select_related('batch__product','demand').order_by('-id')
    if u.role!='admin':tasks=tasks.filter(Q(batch__product__owner_id__in=supplier_ids(u))|Q(creator=u))
    incidents=SupplyIncident.objects.select_related('batch__product','creator').order_by('-id')
    if u.role!='admin':incidents=incidents.filter(Q(batch__product__owner_id__in=supplier_ids(u))|Q(batch__orders__user=u)).distinct()
    plans=[]
    for p in RecoveryPlan.objects.select_related('incident__batch').order_by('-id')[:100]:
        if u.role=='admin' or p.creator_id==u.id or plan_participants(p)&supplier_ids(u,'manage'):
            plans.append({'id':p.id,'incident_id':p.incident_id,'batch_code':p.incident.batch.code,
                'strategy':p.strategy,'result':p.result,'status':p.status,'decisions':p.decisions,
                'participants':list(plan_participants(p)),'creator_id':p.creator_id,'created_at':p.created_at})
    if u.role!='admin' and plans:
        incidents=SupplyIncident.objects.select_related('batch__product','creator').filter(
            Q(pk__in=[p['incident_id'] for p in plans])|Q(pk__in=incidents.values('id'))).distinct().order_by('-id')
    cases=SettlementCase.objects.filter(order_id__in=orders.values('id')).select_related('order__product','creator')
    ledger=InventoryMovement.objects.filter(batch_id__in=batches.values('id')).select_related('batch','actor').order_by('-id')
    sites=BusinessSite.objects.select_related('company')
    if u.role!='admin':sites=sites.filter(Q(company__owner=u)|Q(company__members__user=u)).distinct()
    priorities=[]
    if u.role!='retail' and request.query_params.get('priorities')=='1':
        demands=list(PurchaseDemand.objects.filter(status='open',deadline__gte=timezone.localdate()))
        priorities=sorted([inspection_priority(b,demands) for b in batches[:100]],key=lambda x:-x['priority'])
    return Response({'tasks':[{'id':t.id,'batch_id':t.batch_id,'batch_code':t.batch.code,'product':t.batch.product.name,
        'demand_id':t.demand_id,'status':t.status,'target_sample':t.target_sample,'metric':t.metric,
        'position':t.position,'note':t.note,'result':t.result,'created_at':t.created_at,'completed_at':t.completed_at} for t in tasks[:100]],
        'priorities':priorities,
        'incidents':[{'id':i.id,'batch_id':i.batch_id,'batch_code':i.batch.code,'product':i.batch.product.name,
            'kind':i.kind,'note':i.note,'details':i.details,'status':i.status,'created_at':i.created_at} for i in incidents[:100]],
        'recoveries':plans,
        'cases':[{'id':c.id,'order_id':c.order_id,'product':c.order.snapshot.get('name',c.order.product.name),
            'buyer_id':c.order.user_id,'seller_id':c.order.product.owner_id,'kind':c.kind,'quantity':float(c.quantity),
            'amount':float(c.amount),'note':c.note,'status':c.status,'reference':c.reference,'events':c.events,
            'created_at':c.created_at} for c in cases.order_by('-id')[:200]],
        'ledger':[{'id':m.id,'batch_id':m.batch_id,'batch_code':m.batch.code,'kind':m.kind,
            'quantity':float(m.quantity),'reserved_delta':float(m.reserved_delta),'balance':float(m.balance),
            'reserved_balance':float(m.reserved_balance),'order_id':m.order_id,'actor':m.actor.username if m.actor else '历史',
            'note':m.note,'created_at':m.created_at} for m in ledger[:150]],
        'job':ScheduledJobRun.objects.order_by('-id').values('name','result','created_at').first(),
        'purposes':PURPOSES,'sites':[{'id':s.id,'name':s.name,'address':s.address,'location':s.location,
            'company':s.company.name,'contact':s.contact,'phone':s.phone} for s in sites]})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def compare(request):
    from .commerce import number, integer, day, batch_data
    data=request.data
    demand=None
    if data.get('demand_id'):
        demand=PurchaseDemand.objects.filter(pk=data['demand_id']).first()
        if not demand or (request.user.role=='retail' and demand.buyer_id!=request.user.id):raise PermissionDenied()
        defaults={key:getattr(demand,key) for key in ['keyword','unit','min_size','grade','packaging','budget','deadline','tolerance','flexible_fields','purpose']}
        defaults['quantity']=remaining_demand(demand)
        data={**defaults,**data}
    demand=SimpleNamespace(keyword=str(data.get('keyword','')),quantity=number(data.get('quantity',100),Decimal('.01')),
        unit=data.get('unit','kg'),min_size=integer(data.get('min_size',0),0,2000),grade=str(data.get('grade','')),
        packaging=str(data.get('packaging','')),budget=number(data.get('budget',100),Decimal('.01')),
        deadline=day(data.get('deadline'),timezone.localdate()+timedelta(days=7)),
        tolerance=float(number(data.get('tolerance',10),Decimal(0),Decimal(100))),
        flexible_fields=[f for f in data.get('flexible_fields',[]) if f in FLEXIBLE],
        purpose=data.get('purpose','fresh'))
    ps=StockBatch.objects.select_related('product__owner').prefetch_related('product__price_tiers').filter(
        product__is_deleted=False,product__status='on_sale')
    rows=[]
    for b in ps.order_by('id')[:200]:
        if demand.keyword and demand.keyword.lower() not in (b.product.name+' '+b.product.variety).lower():continue
        available=max(Decimal(0),b.quantity-b.reserved) if b.status=='released' and not hard_quality_reason(b) else Decimal(0)
        quantity=min(demand.quantity,available) if b.product.unit==demand.unit else Decimal(0)
        issues=assess(b,demand,quantity=max(quantity,Decimal('.01')),robust=bool(data.get('robust')))
        costs=None
        try:costs=price_for(b.product,quantity)
        except ValidationError:pass
        weight=public_weight(b)
        actual_yield=(weight['yield_rate']/100) if weight['yield_rate'] else None
        scenario=data.get('scenario_yield',{}).get(str(b.id)) if isinstance(data.get('scenario_yield',{}),dict) else None
        used_yield=float(number(scenario,Decimal('.01'),Decimal(100)))/100 if scenario is not None else actual_yield
        net=float(quantity)*used_yield if used_yield else None
        rows.append({'batch':batch_data(b),'quantity':float(quantity),'pricing':json_price(costs) if costs else None,
            'issues':issues,'compatible':not issues,'negotiable':bool(issues) and all(i['negotiable'] for i in issues),
            'yield_source':'情景假设' if scenario is not None else ('演示称重记录' if b.product.is_demo else '批次实称记录') if actual_yield else '待核实',
            'yield_rate':round(used_yield*100,2) if used_yield else None,'usable_quantity':round(net,2) if net else None,
            'net_cost':round(float(costs['total'])/net,2) if costs and net else None,
            'arrival':max(b.available_date or timezone.localdate(),timezone.localdate())+timedelta(days=b.product.delivery_days),
            'shortfall':float(max(Decimal(0),demand.quantity-quantity))})
    key=data.get('sort','cost')
    rows.sort(key=lambda x:(not x['compatible'], (x['net_cost'] if x['net_cost'] is not None else float('inf')) if key=='net' else
        (x['pricing']['total']/max(x['quantity'],.01) if x['pricing'] else float('inf'))))
    return Response({'rows':rows,'quantity':float(demand.quantity),'purpose':demand.purpose,
        'disclaimer':'净得率来自录入的分拣称重或明确情景参数，不能从图片异常数量推算。'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def preview(request):
    from .commerce import number
    rows=[]
    items=request.data.get('items',[])
    if not isinstance(items,list) or len(items)>30:raise ValidationError('请选择不超过30项货源')
    for item in items:
        b=StockBatch.objects.select_related('product').filter(pk=item.get('batch_id')).first()
        if not b:raise ValidationError('清单中的批次不存在')
        q=number(item.get('quantity'),Decimal('.01'))
        if b.status!='released' or hard_quality_reason(b) or b.product.status!='on_sale' or b.product.is_deleted or q>b.quantity-b.reserved:
            raise ValidationError(f'{b.code} 库存或上架状态已变化，请调整清单')
        costs=price_for(b.product,q)
        rows.append({'batch_id':b.id,'code':b.code,**json_price(costs)})
    stable=[{k:v for k,v in row.items() if k!='expires_at'} for row in rows]
    return Response({'items':rows,'total':round(sum(r['total'] for r in rows),2),
        'signature':__import__('hashlib').sha256(json.dumps(stable,sort_keys=True,default=str).encode()).hexdigest(),
        'quoted_at':timezone.now()})


def pricing_signature(items):
    from .commerce import number
    rows=[]
    for item in items:
        b=StockBatch.objects.select_related('product').get(pk=item['batch_id'])
        costs=json_price(price_for(b.product,number(item['quantity'],Decimal('.01'))))
        costs.pop('expires_at',None)
        rows.append({'batch_id':b.id,'code':b.code,**costs})
    return __import__('hashlib').sha256(json.dumps(rows,sort_keys=True,default=str).encode()).hexdigest()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def measure(request,pk):
    from .commerce import number
    with transaction.atomic():
        b=batch_for(request.user,pk,True,'inspect')
        if b.product.unit not in ['kg','斤']:raise ValidationError('当前只对重量单位录入分拣称重，不自动换算箱或件')
        if request.data.get('version') is not None and int(request.data['version'])!=b.version:raise ValidationError('批次已更新，请重新载入')
        b.input_weight=number(request.data.get('input_weight'),Decimal('.01'))
        b.usable_weight=number(request.data.get('usable_weight'),Decimal(0),b.input_weight)
        b.weight_note=str(request.data.get('note','')).strip()[:300]
        if not b.weight_note:raise ValidationError('请填写分拣用途、样本范围和剔除依据')
        b.save();movement(b,request.user,'weigh',note=b.weight_note)
        return Response(public_weight(b))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def stock_operation(request,pk):
    from .commerce import number,stock_sync,batch_data
    with transaction.atomic():
        b=batch_for(request.user,pk,True)
        kind=request.data.get('kind');qty=number(request.data.get('quantity'),Decimal('.01'),b.quantity-b.reserved)
        note=str(request.data.get('note','')).strip()
        if not note:raise ValidationError('请说明库存操作依据')
        if kind not in ['loss','split']:raise ValidationError('请选择损耗登记或分级拆批')
        b.quantity-=qty;b.save();movement(b,request.user,kind,-qty,note=note);stock_sync(b.product)
        child=None
        if kind=='split':
            import uuid
            child=StockBatch.objects.create(product=b.product,parent=b,code=f'{b.code}-S{uuid.uuid4().hex[:5].upper()}',
                quantity=qty,grade=str(request.data.get('grade',b.grade))[:30],packaging=b.packaging,size_mm=b.size_mm,
                harvest_date=b.harvest_date,available_date=b.available_date,status='pending',
                storage_condition=b.storage_condition,removal_date=b.removal_date,note=note)
            movement(child,request.user,'split_in',qty,note=f'来自 {b.code}；待复核')
        return Response({'batch':batch_data(b),'child':batch_data(child) if child else None})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def review_task(request,pk=None):
    from .commerce import integer,number,notice,stock_sync,wilson
    with transaction.atomic():
        if pk:
            t=InspectionTask.objects.select_for_update().select_related('batch__product').filter(pk=pk).first()
            if not t:raise NotFound()
            b=batch_for(request.user,t.batch_id,True,'inspect')
            if t.status!='open':raise ValidationError('任务已处理，请勿重复提交')
            n=integer(request.data.get('sample_size'),1);k=integer(request.data.get('defect_count'),0,n)
            metric=t.metric;position=str(request.data.get('position',t.position)).strip()
            if not position:raise ValidationError('请记录抽样箱次或位置')
            note=str(request.data.get('note','')).strip()
            state=request.data.get('status','pending')
            if state not in ['pending','released','quarantine']:raise ValidationError('请选择复核结果')
            if metric=='rot' and k>0 and state=='released':raise ValidationError('检测到腐坏目标需隔离复核，不能作为外观等级放行')
            if metric!='rot' and state=='released' and hard_quality_reason(b):
                raise ValidationError('仍有未解除的腐坏记录或移出日期限制，本项检查不能替代专项复核')
            # Each planned inspection is an independent sample; do not repeatedly pool selective results.
            t.result={'sample_size':n,'defect_count':k,'interval':wilson(n,k),'position':position,'note':note,
                'metric':metric,'status':state,'actor':request.user.username,'time':timezone.now().isoformat()}
            if metric=='appearance':b.sample_size,b.defect_count=n,k
            b.status=state;b.note=note
            b.inspections=[*b.inspections,{**t.result,'type':'review','task_id':t.id,
                'metrics':{metric:k}}];b.save();movement(b,request.user,'review',note=note);stock_sync(b.product)
            t.status='completed';t.completed_at=timezone.now();t.save()
            from .commerce import visible_orders
            for o in Order.objects.filter(batch=b,status__in=['pending','paid']).select_related('user'):
                notice(o.user,f'订单 #{o.id} 的复检已完成',f'{b.code} · {state}',f'/orders?order={o.id}')
        else:
            b=batch_for(request.user,request.data.get('batch_id'),True,'inspect')
            if InspectionTask.objects.filter(batch=b,status='open').exists():raise ValidationError('该批次已有待执行任务')
            metric=request.data.get('metric','appearance')
            if metric not in ['appearance','rot','size']:raise ValidationError('检查指标不正确')
            t=InspectionTask.objects.create(batch=b,creator=request.user,
                target_sample=integer(request.data.get('target_sample',50),1,100000),metric=metric,
                position=str(request.data.get('position',''))[:160],note=str(request.data.get('note',''))[:2000])
            notice(b.product.owner,f'{b.code} 已安排复检',t.note,f'/reviews?task={t.id}')
        return Response({'id':t.id,'status':t.status})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def incident(request):
    from .commerce import notice,stock_sync,number
    with transaction.atomic():
        b=batch_for(request.user,request.data.get('batch_id'),True)
        if b.incidents.filter(status='open').exists():raise ValidationError('该批次已有未处理异常，请先完成补配')
        kind=request.data.get('kind','quarantine')
        if kind not in ['quarantine','shortage','delay']:raise ValidationError('请选择异常类型')
        note=str(request.data.get('note','')).strip()
        if not note:raise ValidationError('请填写异常依据和处理说明')
        details={}
        if kind=='shortage':details['counted_quantity']=float(number(request.data.get('counted_quantity'),Decimal(0),b.quantity))
        if kind=='delay':
            from .commerce import day
            delayed=day(request.data.get('available_date'))
            if not delayed or delayed<timezone.localdate():raise ValidationError('请填写延迟后的可供货日期')
            details['available_date']=delayed.isoformat()
        i=SupplyIncident.objects.create(batch=b,creator=request.user,kind=kind,note=note,details=details)
        b.status='quarantine';b.save();movement(b,request.user,'incident',note=note);stock_sync(b.product)
        for o in Order.objects.filter(Q(batch=b)|Q(allocations__batch=b),status__in=['pending','paid','issue']).select_related('user').distinct():
            notice(o.user,f'订单 #{o.id} 批次发生异常',f'{b.code}：{note}',f'/recovery?incident={i.id}')
        return Response({'id':i.id})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def recovery(request,pk=None):
    from .commerce import notice
    with transaction.atomic():
        if not pk:
            i=SupplyIncident.objects.select_related('batch__product').filter(pk=request.data.get('incident_id'),status='open').first()
            if not i:raise ValidationError('异常不存在或已完成')
            strategy=request.data.get('strategy','stable')
            if strategy not in ['stable','cost','fast']:raise ValidationError('补配策略不正确')
            result=recovery_compute(request.user,i,strategy)
            p=RecoveryPlan.objects.create(incident=i,creator=request.user,strategy=strategy,
                result=json.loads(json.dumps(result,cls=DjangoJSONEncoder)))
            return Response({'id':p.id,'result':p.result,'status':p.status})
        p=RecoveryPlan.objects.select_for_update().select_related('incident__batch__product').filter(pk=pk).first()
        if not p or (request.user.role!='admin' and not (plan_participants(p)|{p.creator_id})&supplier_ids(request.user,'manage')):raise PermissionDenied()
        action=request.data.get('action')
        if action=='publish':
            if p.creator_id!=request.user.id or p.status!='draft':raise ValidationError('仅创建方可以发送草稿')
            if not p.result['rows'] or any(r['shortfall']>.005 for r in p.result['rows']):raise ValidationError('方案仍有缺口，不能要求各方确认')
            p.status='pending';p.save()
            for uid in plan_participants(p):
                notice(User.objects.get(pk=uid),f'异常补配方案 #{p.id} 待确认',p.incident.note[:200],f'/recovery?plan={p.id}')
        elif action in ['accept','reject']:
            party=int(request.data.get('party_id') or request.user.id)
            if p.status!='pending' or party not in plan_participants(p) or party not in supplier_ids(request.user,'manage'):raise ValidationError('当前无需你确认或无代表此方的授权')
            key=str(party)
            if key in p.decisions:raise ValidationError('你已提交决定，请勿重复确认')
            p.decisions={**p.decisions,key:{'action':action,'actor':request.user.username,'time':timezone.now().isoformat()}}
            if action=='reject':p.status='rejected'
            elif all(p.decisions.get(str(uid),{}).get('action')=='accept' for uid in plan_participants(p)):
                execute_recovery(p,request.user)
            p.save()
        else:raise ValidationError('不支持此动作')
        return Response({'id':p.id,'status':p.status})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def settlement(request,pk):
    from .workflow import case_action
    return case_action(request,pk)


@api_view(['GET','POST'])
@permission_classes([IsAuthenticated])
def company_api(request):
    u=request.user
    if request.method=='POST':
        action=request.data.get('action')
        with transaction.atomic():
            if action=='create':
                name=str(request.data.get('name','')).strip()
                if not name:raise ValidationError('请填写主体名称')
                c=Company.objects.create(owner=u,name=name[:100],kind=request.data.get('kind','buyer'))
                CompanyMember.objects.create(company=c,user=u,job='owner')
            else:
                c=Company.objects.filter(pk=request.data.get('company_id'),owner=u).first()
                if not c:raise PermissionDenied('仅主体创建者可维护成员和站点')
                if action=='site':
                    from .commerce import coordinates
                    name,address=str(request.data.get('name','')).strip(),str(request.data.get('address','')).strip()
                    if not name or not address:raise ValidationError('请填写站点名称与地址')
                    loc=str(request.data.get('location','')).strip()
                    if loc and not coordinates(loc):raise ValidationError('经纬度格式不正确，未知请留空')
                    BusinessSite.objects.create(company=c,name=name[:100],address=address[:300],location=loc[:80],
                        contact=str(request.data.get('contact',''))[:80],phone=str(request.data.get('phone',''))[:30])
                elif action=='member':
                    member=User.objects.filter(username=request.data.get('username')).first()
                    job=request.data.get('job','viewer')
                    if not member or job not in ['manager','buyer','quality','dispatch','viewer']:raise ValidationError('用户不存在或岗位不正确')
                    if member.id==u.id:raise ValidationError('不能修改主体创建者岗位')
                    CompanyMember.objects.update_or_create(company=c,user=member,defaults={'job':job})
                else:raise ValidationError('不支持此动作')
    qs=Company.objects.all() if u.role=='admin' else Company.objects.filter(Q(owner=u)|Q(members__user=u)).distinct()
    return Response([{'id':c.id,'name':c.name,'kind':c.kind,'owner_id':c.owner_id,
        'members':list(c.members.values('id','user_id','user__username','job')),
        'sites':list(c.sites.values())} for c in qs])


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def analytics(request):
    from .reporting import report_counts
    return Response(report_counts(request.user,request.query_params))


urlpatterns=[path('collaboration/',workspace),path('compare/',compare),path('pricing/preview/',preview),
    path('batches/<int:pk>/measure/',measure),path('batches/<int:pk>/stock/',stock_operation),
    path('reviews/',review_task),path('reviews/<int:pk>/',review_task),path('incidents/',incident),
    path('recovery/',recovery),path('recovery/<int:pk>/',recovery),path('cases/<int:pk>/',settlement),
    path('companies/',company_api),path('analytics/',analytics)]
