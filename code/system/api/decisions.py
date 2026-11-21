"""Constraint allocation, measured-cost comparisons and incident recovery."""
import json
import math
from decimal import Decimal
from time import perf_counter
from datetime import timedelta
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError, PermissionDenied
from .models import (StockBatch, PurchaseDemand, Order, OrderAllocation, RecoveryPlan,
                     SettlementCase, SupplyIncident)
from .commerce_rules import assess, price_for, json_price, allocations_for, movement, public_weight, hard_quality_reason
from .access import supplier_ids


def remaining_demand(d):
    return max(Decimal(0), d.quantity-sum(q.quantity-q.released_quantity for q in d.quotes.filter(status='accepted').exclude(order__status='cancelled')))


def solve_options(options, batch_caps, demand_caps, strategy='cost'):
    """Integer step quantities + one price tier per edge, then lexicographic costs."""
    import numpy as np
    from scipy.optimize import milp, Bounds, LinearConstraint
    from scipy.sparse import lil_matrix
    if not options: return [], {'solver': 'empty', 'optimal': True}
    m=len(options)
    batch_rows={bid:i for i,bid in enumerate(batch_caps)}
    demand_rows={did:i+len(batch_rows) for i,did in enumerate(demand_caps)}
    pairs=sorted({(x['batch_id'],x['demand_id']) for x in options})
    pair_rows={pair:i+len(batch_rows)+len(demand_rows) for i,pair in enumerate(pairs)}
    offset=len(batch_rows)+len(demand_rows)+len(pair_rows)
    matrix=lil_matrix((offset+2*m,2*m),dtype=float)
    lower=np.full(offset+2*m,-np.inf);upper=np.zeros(offset+2*m)
    for bid,idx in batch_rows.items():upper[idx]=batch_caps[bid]
    for did,idx in demand_rows.items():upper[idx]=demand_caps[did]
    for pair,idx in pair_rows.items():upper[idx]=1
    for i,x in enumerate(options):
        matrix[batch_rows[x['batch_id']],i]=x['step']
        matrix[demand_rows[x['demand_id']],i]=x['step']
        matrix[pair_rows[(x['batch_id'],x['demand_id'])],m+i]=1
        matrix[offset+2*i,i]=1;matrix[offset+2*i,m+i]=-x['maximum']
        matrix[offset+2*i+1,i]=-1;matrix[offset+2*i+1,m+i]=x['minimum']
    constraint = LinearConstraint(matrix.tocsr(), lower, upper)
    bounds = Bounds(np.zeros(m*2), np.array([x['maximum'] for x in options]+[1]*m))
    coverage = np.array([x['step']*x.get('priority',1)/max(demand_caps[x['demand_id']],.01) for x in options]+[0]*m)
    first = milp(-coverage, integrality=np.ones(m*2), bounds=bounds, constraints=constraint,
                 options={'time_limit': 6, 'mip_rel_gap': .001})
    if first.x is None: raise ValidationError('约束求解未完成，请减少候选范围后重试')
    monetary=np.array([x['unit_price']*x['step'] for x in options]+[x.get('fixed_cost',0) for x in options])
    if strategy=='stable':objective=np.array([0.]*m+[(m+1)*x.get('change_cost',1)+1 for x in options])
    elif strategy=='fast':objective=np.array([x.get('delivery_days',0)*x['step'] for x in options]+[0.]*m)
    else:objective=monetary
    best = float(coverage@first.x)
    second = milp(np.array(objective), integrality=np.ones(m*2), bounds=bounds,
        constraints=[constraint, LinearConstraint(coverage, best-1e-7, np.inf)],
        options={'time_limit': 6, 'mip_rel_gap': .001})
    result = second if second.x is not None else first
    all_optimal=bool(first.success and second.success)
    if strategy in ['stable','fast'] and second.x is not None:
        change_best=float(objective@second.x)
        third=milp(monetary,integrality=np.ones(m*2),bounds=bounds,
            constraints=[constraint,LinearConstraint(coverage,best-1e-7,np.inf),
                         LinearConstraint(objective,-np.inf,change_best+1e-7)],
            options={'time_limit':6,'mip_rel_gap':.001})
        if third.x is not None:result=third
        all_optimal=all_optimal and bool(third.success)
    selected = []
    for i,x in enumerate(options):
        steps = int(round(float(result.x[i])))
        if steps: selected.append({**x, 'quantity': round(steps*x['step'],2)})
    return selected, {'solver': 'HiGHS MILP', 'optimal': all_optimal,
                      'gap': float(getattr(result,'mip_gap',0) or 0)}


def options_for(b, d, cap, required, override=None, original=False):
    p = b.product; step = float(p.quantity_step)
    if step <= 0: return []
    tiers = [(float(p.min_order), float(p.retail_price))]
    tiers.extend((float(t.min_quantity), float(t.wholesale_price)) for t in p.price_tiers.order_by('min_quantity'))
    tiers = sorted(dict(tiers).items())
    if override is not None: tiers = [(float(p.min_order), float(override))]
    rows = []
    for i,(start,unit) in enumerate(tiers):
        lo = max(float(p.min_order),start)
        hi = min(cap, required, (tiers[i+1][0]-.01) if i+1<len(tiers) else float('inf'))
        minimum,maximum = math.ceil((lo-1e-7)/step),math.floor((hi+1e-7)/step)
        if maximum < minimum: continue
        rows.append({'batch_id':b.id,'demand_id':d.id,'step':step,'minimum':minimum,'maximum':maximum,
            'unit_price':unit+float(p.packaging_fee),'goods_price':unit,'fixed_cost':float(p.freight_fee),
            'delivery_days':p.delivery_days,'change_cost':0 if original else 1,'priority':getattr(d,'priority',1)})
    return rows


def compute(user, data):
    from .commerce import role, batch_data, demand_data, number
    started = perf_counter(); role(user,'supplier','admin')
    qs = StockBatch.objects.select_related('product__owner').prefetch_related('product__price_tiers').filter(
        product__is_deleted=False, product__status='on_sale')
    if user.role == 'supplier': qs=qs.filter(product__owner_id__in=supplier_ids(user,'manage'))
    batches=list(qs.order_by('id')[:100])
    demands=list(PurchaseDemand.objects.filter(status='open',deadline__gte=timezone.localdate()).select_related('buyer').order_by('-priority','deadline','id')[:100])
    needs={d.id:remaining_demand(d) for d in demands}; robust=data.get('mode')=='robust'
    caps={b.id:float(max(Decimal(0),b.quantity-b.reserved)) if b.status=='released' else 0 for b in batches}
    overrides=data.get('capacities',{})
    if not isinstance(overrides,dict): raise ValidationError('库存场景格式错误')
    for b in batches:
        if str(b.id) in overrides: caps[b.id]=float(number(overrides[str(b.id)],Decimal(0),Decimal(str(caps[b.id]))))
    matrix=[]; candidates=[]
    for b in batches:
        for d in demands:
            opts=options_for(b,d,caps[b.id],float(needs[d.id])) if caps[b.id]>0 and needs[d.id]>0 else []
            compatible=[]; all_issues=[]
            for option in opts:
                issues=assess(b,d,Decimal(str(option['minimum']*option['step'])),option['goods_price'],robust)
                if not issues: compatible.append(option)
                all_issues.extend(issues)
            if not opts: all_issues=assess(b,d,robust=robust)+[{'field':'stock','reason':'可用量不足起订量或需求已满足','negotiable':False}]
            matrix.append({'batch_id':b.id,'demand_id':d.id,'compatible':bool(compatible),
                'reasons':[] if compatible else list(dict.fromkeys(x['reason'] for x in all_issues)),
                'negotiable':list({x['field'] for x in all_issues if x.get('negotiable')})})
            candidates.extend(compatible)
    allocations=[]; certificates=[]; by_batch={b.id:b for b in batches}; by_demand={d.id:d for d in demands}
    for unit in sorted({d.unit for d in demands}):
        options=[x for x in candidates if by_demand[x['demand_id']].unit==unit]
        selected,cert=solve_options(options,caps,{d.id:float(needs[d.id]) for d in demands if d.unit==unit})
        certificates.append(cert)
        for x in selected:
            b,d=by_batch[x['batch_id']],by_demand[x['demand_id']]
            cost=price_for(b.product,Decimal(str(x['quantity'])))
            allocations.append({'batch_id':b.id,'batch_code':b.code,'product':b.product.name,'demand_id':d.id,
                'demand':d.title,'buyer':d.buyer.username,'quantity':x['quantity'],'unit':unit,
                'price':float(cost['unit_price']),'amount':float(cost['total']),'pricing':json_price(cost)})
    shortfalls=[]
    for d in demands:
        filled=round(sum(a['quantity'] for a in allocations if a['demand_id']==d.id),2)
        shortfalls.append({'id':d.id,'title':d.title,'quantity':float(needs[d.id]),'filled':filled,
                          'remaining':round(max(0,float(needs[d.id])-filled),2),'unit':d.unit})
    drows=[]
    for d in demands:
        row=demand_data(d,user);row['quantity']=float(needs[d.id]);drows.append(row)
    return {'batches':[batch_data(b) for b in batches],'demands':drows,'matrix':matrix,'allocations':allocations,
        'shortfalls':shortfalls,'mode':'robust' if robust else 'standard','capacities':caps,
        'method':'整数包装增量与阶梯价约束 · 优先级覆盖比例最大化，再最小到货金额',
        'certificate':certificates,'summary':{'covered_orders':sum(s['remaining']<.005 for s in shortfalls),
        'orders':len(demands),'amount':round(sum(a['amount'] for a in allocations),2),'links':len(allocations),
        'elapsed_ms':round((perf_counter()-started)*1000,1)},
        'disclaimer':'试算不锁库存；费用使用当前已录入规则；求解状态可核对，不声称原创算法。'}


def recovery_compute(user, incident, strategy):
    """Replan only undelivered allocations touched by this incident. Other orders are fixed."""
    from .commerce import visible_orders, role
    started=perf_counter(); role(user,'supplier','admin')
    if user.role!='admin' and incident.batch.product.owner_id not in supplier_ids(user,'manage'): raise PermissionDenied()
    affected=list(Order.objects.filter(allocations__batch=incident.batch,status__in=['pending','paid','issue']).exclude(
        status='cancelled').select_related('product__owner','user').distinct())
    # Legacy orders are converted only within the caller's transaction when explicitly simulating.
    legacy=list(Order.objects.filter(batch=incident.batch,status__in=['pending','paid']).exclude(
        pk__in=[o.pk for o in affected]).select_related('product__owner','user'))
    for o in legacy: allocations_for(o)
    affected+=legacy
    all_batches=list(StockBatch.objects.select_related('product__owner').filter(status='released',
        product__is_deleted=False,product__status='on_sale').exclude(pk=incident.batch_id))
    if user.role!='admin': all_batches=[b for b in all_batches if b.product.owner_id in supplier_ids(user,'manage')]
    caps={b.id:float(max(Decimal(0),b.quantity-b.reserved)) for b in all_batches}
    needed={}; options=[]; source={}; order_map={o.id:o for o in affected}
    for o in affected:
        qty=sum(a.quantity-a.dispatched for a in allocations_for(o) if a.batch_id==incident.batch_id)
        if qty<=0: continue
        needed[o.id]=float(qty); source[o.id]=qty
        quotes=o.demandquote_set.filter(status='accepted').select_related('demand')
        quote=quotes.first()
        for b in all_batches:
            if b.product.unit!=o.snapshot.get('unit') or b.product.category!=o.product.category:
                continue
            if quote:
                # Contractual conditions remain hard during recovery; no implied relaxation.
                issues=assess(b,quote.demand,quantity=max(Decimal(b.product.min_order),qty),unit_price=o.unit_price_at_purchase)
                if issues: continue
            elif b.product.variety!=o.product.variety or b.grade!=o.snapshot.get('grade') or b.packaging!=o.snapshot.get('packaging'):
                continue
            from types import SimpleNamespace
            proxy=SimpleNamespace(id=o.id,priority=1)
            opts=options_for(b,proxy,caps[b.id],float(qty))
            if quote:
                opts=[x for x in opts if not assess(b,quote.demand,Decimal(str(x['minimum']*x['step'])),x['goods_price'])]
            for x in opts:
                x['delivery_days']=b.product.delivery_days
                x['change_cost']=0 if b.product.owner_id==o.product.owner_id else 1
            options.extend(opts)
    selected=[]; certificates=[]
    for unit in sorted({o.snapshot.get('unit') for o in affected}):
        subset={oid:n for oid,n in needed.items() if order_map[oid].snapshot.get('unit')==unit}
        choices=[x for x in options if x['demand_id'] in subset]
        sol,cert=solve_options(choices,caps,subset,strategy);selected+=sol;certificates.append(cert)
    bmap={b.id:b for b in all_batches}; rows=[]
    for o in affected:
        if o.id not in needed:continue
        parts=[]
        for x in selected:
            if x['demand_id']!=o.id:continue
            b=bmap[x['batch_id']]
            costs=json_price(price_for(b.product,Decimal(str(x['quantity'])),x['goods_price']))
            parts.append({'batch_id':b.id,'batch_code':b.code,'product':b.product.name,'supplier_id':b.product.owner_id,
                'supplier':b.product.owner.username,'quantity':x['quantity'],'price':x['goods_price'],
                'delivery_days':b.product.delivery_days,'version':b.version,'pricing':costs})
        filled=round(sum(x['quantity'] for x in parts),2)
        original_parts=[a for a in allocations_for(o) if a.batch_id==incident.batch_id and a.quantity>a.dispatched]
        old_amount=Decimal(0)
        for a in original_parts:
            terms=a.terms or o.snapshot.get('pricing',{})
            original_total=Decimal(str(terms.get('total',a.quantity*a.unit_price)))
            old_amount+=original_total*(a.quantity-a.dispatched)/a.quantity
        delta=round(sum(x['pricing']['total'] for x in parts)-float(old_amount),2)
        rows.append({'order_id':o.id,'number':f'HL{o.created_at:%y%m%d}{o.id:05d}','buyer_id':o.user_id,
            'buyer':o.user.username,'seller_id':o.product.owner_id,'product':o.snapshot.get('name'),
            'unit':o.snapshot.get('unit'),'required':needed[o.id],'filled':filled,
            'shortfall':round(needed[o.id]-filled,2),'delta':delta,'order_version':o.version,'parts':parts})
    return {'rows':rows,'strategy':strategy,'certificate':certificates,
        'summary':{'affected_orders':len(rows),'recovered_orders':sum(r['shortfall']<.005 for r in rows),
            'amount_change':round(sum(r['delta'] for r in rows),2),'changed_links':sum(len(r['parts']) for r in rows),
            'supplier_switches':sum(p['supplier_id']!=r['seller_id'] for r in rows for p in r['parts']),
            'elapsed_ms':round((perf_counter()-started)*1000,1)},
        'preserved_orders':visible_orders(user).filter(status__in=['paid','pending']).exclude(pk__in=needed).count(),
        'note':'仅改配异常批次尚未发运的数量。已发运货物保持原记录，采购方与涉及供应方均确认后才执行。'}


def execute_recovery(plan, actor):
    from .commerce import stock_sync, event, notice
    all_ids=sorted({plan.incident.batch_id}|{p['batch_id'] for r in plan.result['rows'] for p in r['parts']})
    batches={b.id:b for b in StockBatch.objects.select_for_update().filter(pk__in=all_ids).order_by('id')}
    for row in sorted(plan.result['rows'],key=lambda r:r['order_id']):
        if row['shortfall']>.005: raise ValidationError('方案仍有缺口，请重新补配后发起确认')
        o=Order.objects.select_for_update().get(pk=row['order_id'])
        if o.version!=row['order_version'] or o.status not in ['paid','pending','issue']:
            raise ValidationError(f'订单 {row["number"]} 已变化，请重新计算，原订单未改写')
        current=allocations_for(o,True)
        old_parts=[a for a in current if a.batch_id==plan.incident.batch_id and a.quantity>a.dispatched]
        release=sum(a.quantity-a.dispatched for a in old_parts)
        if release!=Decimal(str(row['required'])): raise ValidationError('原预留已变化，请重新试算')
        old=batches[plan.incident.batch_id]
        old.reserved-=release;old.save();movement(old,actor,'recovery_release',reserved=-release,order=o)
        for a in old_parts:
            if a.dispatched:a.quantity=a.dispatched;a.save(update_fields=['quantity'])
            else:a.delete()
        for part in row['parts']:
            b=batches[part['batch_id']];qty=Decimal(str(part['quantity']))
            if b.status!='released' or hard_quality_reason(b) or b.quantity-b.reserved<qty or b.version!=part['version']:
                raise ValidationError('替代批次已变化，请重新计算；本次操作已回滚')
            OrderAllocation.objects.create(order=o,batch=b,quantity=qty,unit_price=part['price'],terms=part.get('pricing',{}))
            b.reserved+=qty;b.save();movement(b,actor,'recovery_reserve',reserved=qty,order=o)
            # A batch used by multiple rows has a new version within this same transaction.
            for rr in plan.result['rows']:
                for pp in rr['parts']:
                    if pp['batch_id']==b.id: pp['version']=b.version
            stock_sync(b.product)
        delta=Decimal(str(row['delta']))
        if delta:
            kind='supplement' if delta>0 else 'discount'
            SettlementCase.objects.create(order=o,creator=actor,kind=kind,amount=abs(delta),status='accepted',
                note=f'补配方案 #{plan.id} 经各方确认的价差；需登记实际执行凭证。')
        o.snapshot={**o.snapshot,'recovery_plan':plan.id,'recovery_delta':float(delta)}
        o.version+=1
        event(o,actor,'异常补配已由各方确认',f'方案 #{plan.id}；仅调整未发运分配，差额 {delta}')
        o.save();stock_sync(old.product)
        notice(o.user,f'订单 #{o.id} 补配已执行',f'方案 #{plan.id}',f'/orders?order={o.id}')
    plan.status='executed';plan.save()
    plan.incident.status='resolved';plan.incident.save(update_fields=['status'])
    old=batches[plan.incident.batch_id]
    if plan.incident.kind=='shortage':
        actual=Decimal(str(plan.incident.details.get('counted_quantity',old.quantity)))
        if actual<old.reserved:raise ValidationError('尚有未解除的预留，无法登记实际短缺')
        change=actual-old.quantity;old.quantity=actual;old.save()
        movement(old,actor,'count_adjustment',quantity=change,note=f'异常 #{plan.incident_id} 实称数量入账')
        stock_sync(old.product)
    if plan.incident.kind=='delay' and plan.incident.details.get('available_date'):
        from datetime import date
        old.available_date=date.fromisoformat(plan.incident.details['available_date']);old.save(update_fields=['available_date'])
    plan.incident.plans.exclude(pk=plan.id).filter(status__in=['draft','pending']).update(status='superseded')
