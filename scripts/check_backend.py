"""Bounded business smoke, isolated in memory; never edits the user's database."""
import os, sys, uuid
from pathlib import Path
from decimal import Decimal
from datetime import timedelta
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'code/system'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'backend_system.settings'
from django.conf import settings
settings.DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
settings.ALLOWED_HOSTS = ['testserver', '127.0.0.1', 'localhost']
settings.DEEPSEEK_API_KEY = ''
settings.TIANDITU_API_KEY = ''
import django
django.setup()
from django.core.management import call_command
from django.utils import timezone
from api.models import BusinessSite, FulfilmentTask, Order, PurchaseDemand, RecoveryPlan, StockBatch, SupplierSettlement, User, WeightReconciliation
from api.commerce import create_order, event
from api.decisions import compute, remaining_usable
from rest_framework.test import APIClient
call_command('migrate', interactive=False, verbosity=0)
for seed in ['seed_workspace', 'seed_collaboration', 'seed_dispatch']:
    call_command(seed, verbosity=0)
buyer = User.objects.get(username='demo_buyer')
seller = User.objects.get(username='demo_supplier')
coop = User.objects.get(username='demo_coop')
admin = User.objects.get(username='demo_admin')
client = APIClient()

def api(user, method, path, data=None, status=200):
    client.force_authenticate(user=user)
    r = getattr(client, method)('/api/workspace/' + path, data=data or {}, format='json')
    assert r.status_code == status, (path, r.status_code, str(r.data)[:1600])
    return r.data
for u in [buyer, seller, coop, admin]:
    for path in ['bootstrap/', 'collaboration/', 'control/', 'tasks/', 'accounts/', 'sheets/', 'orders/list/']:
        api(u, 'get', path)
print('PASS: all role workspaces and new read endpoints')
site = BusinessSite.objects.filter(company__owner=buyer).first()
payload = {'title': 'Smoke multi-store', 'submission_key': str(uuid.uuid4()), 'company_id': site.company_id, 'delivery_date': str(timezone.localdate() + timedelta(days=5)), 'lines': [{'site_id': site.id, 'keyword': '苹果', 'quantity': 60, 'required_usable': 40, 'process': '去皮去核', 'purpose': 'kitchen', 'unit': 'kg', 'budget': 20, 'tolerance': 10}]}
sheet = api(buyer, 'post', 'sheets/', payload, 201)
assert api(buyer, 'post', 'sheets/', payload)['id'] == sheet['id']
d = PurchaseDemand.objects.get(pk=sheet['lines'][0]['id'])
preview = api(buyer, 'post', 'net-preview/', {'keyword': '苹果', 'purpose': 'kitchen', 'process': '去皮去核', 'required_usable': 40, 'unit': 'kg', 'budget': 20, 'deadline': str(d.deadline)})
row = next((r for r in preview['rows'] if r['compatible']))
assert row['gross'] * row['evidence']['rate'] >= 40
b = StockBatch.objects.select_related('product').get(pk=row['batch']['id'])
q = api(b.product.owner, 'post', f'demands/{d.id}/quote/', {'batch_id': b.id, 'quantity': row['gross'], 'price': row['pricing']['unit_price']}, 201)
order = api(buyer, 'post', f'quotes/{q['id']}/accept/')
d.refresh_from_db()
assert remaining_usable(d) < Decimal('.005') and d.status == 'ordered'
assert order['sheet_id'] == sheet['id'] and order['site_id'] == site.id
plan = compute(admin, {'strategy': 'cost', 'mode': 'robust'})
assert isinstance(plan, dict)
print('PASS: multi-site sheet, purpose evidence, net-use quote acceptance and allocation solver')
b.refresh_from_db()
before = b.quantity
grade = api(b.product.owner, 'post', f'batches/{b.id}/grading/', {'version': b.version, 'input_quantity': 10, 'loss_quantity': 1, 'note': 'isolated smoke actual split', 'outputs': [{'quantity': 6, 'grade': '鲜销级', 'purpose': 'fresh', 'price': 8}, {'quantity': 3, 'grade': '加工级', 'purpose': 'kitchen', 'price': 4}]}, 201)
b.refresh_from_db()
assert b.quantity == before - 10
assert sum((Decimal(str(x['quantity'])) for x in grade['outputs'])) + Decimal(str(grade['loss'])) == 10
assert StockBatch.objects.get(pk=grade['outputs'][0]['batch_id']).status == 'pending'
print('PASS: grading quantity conservation and pending review')
b = StockBatch.objects.select_related('product__owner').get(code='DEMO-ALT-APPLE')
pricing = api(buyer, 'post', 'pricing/preview/', {'items': [{'batch_id': b.id, 'quantity': 20}]})
o = api(buyer, 'post', 'checkout/', {'idempotency_key': str(uuid.uuid4()), 'items': [{'batch_id': b.id, 'quantity': 20}], 'pricing_signature': pricing['signature'], 'site_id': site.id, 'address': {'receiver_name': site.contact, 'receiver_phone': site.phone, 'address': site.address}, 'promised_date': str(timezone.localdate()), 'settlement_basis': 'accepted_weight', 'weight_tolerance_pct': 2}, 201)['orders'][0]
oid = o['id']
api(buyer, 'post', f'orders/{oid}/submit-payment/', {'reference': 'SMOKE-PAY'})
api(coop, 'post', f'orders/{oid}/confirm-payment/')
tasks = api(coop, 'get', 'tasks/', {'search': str(oid)})['items']
pick = next((t for t in tasks if t['kind'] == 'pick'))
api(coop, 'post', f'tasks/{pick['id']}/', {'action': 'complete', 'version': pick['version'], 'note': 'actual checked 20kg'})
o = api(coop, 'post', f'orders/{oid}/ship/', {'quantity': 20, 'gross_weight': 21, 'tare_weight': 1, 'supplier_id': coop.id, 'carrier': 'smoke carrier', 'tracking_number': 'SMOKE-DELIVERY'})
delivery = o['deliveries'][-1]
o = api(buyer, 'post', f'orders/{oid}/receive/', {'delivery_id': delivery['id'], 'gross_weight': 20.8, 'tare_weight': 1, 'accepted_quantity': 19.8, 'note': 'actual test receipt'})
assert o['accepted_quantity'] == 19.8 and o['status'] == 'issue'
r = WeightReconciliation.objects.get(order_id=oid)
api(coop, 'post', f'accounts/{r.id}/', {'action': 'reject', 'note': 'please attach weighing record'})
api(buyer, 'post', f'accounts/{r.id}/', {'action': 'resubmit', 'note': 'scale number and acceptance record checked'})
api(coop, 'post', f'accounts/{r.id}/', {'action': 'confirm'})
r.refresh_from_db()
assert r.case_id and r.difference_amount < 0
api(coop, 'post', f'cases/{r.case_id}/', {'action': 'execute', 'reference': 'SMOKE-REFUND'})
api(buyer, 'post', f'cases/{r.case_id}/', {'action': 'confirm'})
assert Order.objects.get(pk=oid).status == 'completed'
assert not FulfilmentTask.objects.filter(order_id=oid).exclude(status__in=['done', 'cancelled']).exists()
print('PASS: tasks, physical dispatch, net acceptance, disputed weight, actual refund reconciliation')
b.refresh_from_db()
o = create_order(buyer, b, Decimal(20), address={'receiver_name': 'Test', 'receiver_phone': '13800000000', 'address': 'Test'}, promised_date=timezone.localdate())
o.status = 'paid'
o.payment_status = 'confirmed'
o.save()
event(o, coop, 'Smoke payment')
api(coop, 'post', f'orders/{o.id}/ship/', {'quantity': 20, 'supplier_id': coop.id, 'carrier': 'smoke', 'tracking_number': 'SMOKE-A'})
api(buyer, 'post', f'orders/{o.id}/receive/', {'received_quantity': 20, 'accepted_quantity': 18, 'quality_issue': 'two rejected'})
api(coop, 'post', f'orders/{o.id}/resolve/', {'kind': 'replacement', 'quantity': 2, 'note': 'replace rejected quantity'})
case = o.cases.latest('id')
api(buyer, 'post', f'cases/{case.id}/', {'action': 'accept'})
api(coop, 'post', f'cases/{case.id}/', {'action': 'execute', 'reference': 'SMOKE-REPLACE', 'batch_id': b.id})
api(buyer, 'post', f'cases/{case.id}/', {'action': 'confirm'}, 400)
delivery = case.deliveries.get()
api(buyer, 'post', f'orders/{o.id}/receive/', {'delivery_id': delivery.id, 'received_quantity': 2, 'accepted_quantity': 2})
api(buyer, 'post', f'cases/{case.id}/', {'action': 'confirm'})
assert Order.objects.get(pk=o.id).accepted_quantity == 20
print('PASS: replacement cannot complete before actual receipt')
original = StockBatch.objects.select_related('product').get(code='DEMO-001')
source = StockBatch.objects.create(product=original.product, code='SMOKE-RECOVERY', quantity=40, grade=original.grade, packaging=original.packaging, size_mm=85, status='released', sample_size=200, defect_count=1)
o = create_order(buyer, source, Decimal(20), address={'receiver_name': 'Test', 'receiver_phone': '13800000000', 'address': 'Test'}, promised_date=timezone.localdate() + timedelta(days=5))
o.status = 'paid'
o.payment_status = 'confirmed'
o.save()
event(o, seller, 'Smoke payment')
incident = api(seller, 'post', 'incidents/', {'batch_id': source.id, 'kind': 'quarantine', 'note': 'isolated shortage'})
StockBatch.objects.filter(product__owner=seller).exclude(pk=source.id).update(status='quarantine')
plan = api(seller, 'post', 'recovery/', {'incident_id': incident['id'], 'strategy': 'stable', 'market': True})
assert plan['result']['summary']['recovered_orders'] == 1, plan
api(seller, 'post', f'recovery/{plan['id']}/', {'action': 'publish'})
for participant in [seller, buyer, coop]:
    api(participant, 'post', f'recovery/{plan['id']}/', {'action': 'accept'})
assert RecoveryPlan.objects.get(pk=plan['id']).status == 'executed'
settlement = SupplierSettlement.objects.get(order=o)
api(seller, 'post', f'supplier-payments/{settlement.id}/', {'action': 'record', 'reference': 'SMOKE-INTERNAL'})
api(coop, 'post', f'supplier-payments/{settlement.id}/', {'action': 'confirm'})
for case in o.cases.filter(kind='supplement'):
    api(buyer, 'post', f'cases/{case.id}/', {'action': 'execute', 'reference': 'SMOKE-DELTA'})
    api(seller, 'post', f'cases/{case.id}/', {'action': 'confirm'})
external = api(coop, 'get', 'orders/list/', {'id': o.id})['items'][0]
assert external['allocations'] and all((a['supplier_id'] == coop.id for a in external['allocations']))
assert not external['can_manage_trade'] and external['can_ship'] and (not external['cases'])
api(coop, 'post', f'orders/{o.id}/ship/', {'quantity': 20, 'supplier_id': coop.id, 'carrier': 'smoke replacement supplier', 'tracking_number': 'SMOKE-EXTERNAL'})
api(buyer, 'post', f'orders/{o.id}/receive/', {'received_quantity': 20, 'accepted_quantity': 20})
assert Order.objects.get(pk=o.id).status == 'completed'
print('PASS: market recovery, three-party consent, internal payable, external-supplier shipment and acceptance')
print('DISPATCH_SMOKE_PASS')
