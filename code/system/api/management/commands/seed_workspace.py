from datetime import timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from api.models import User, Product, StockBatch, PurchaseDemand, ShippingAddress, Order, WorkspaceNotification
from api.commerce import create_order, event


class Command(BaseCommand):
    help = 'Create clearly labelled, idempotent local demo workspace; never overwrite existing records.'

    @transaction.atomic
    def handle(self, *args, **kwargs):
        accounts = {}
        for name, role in [('demo_buyer', 'retail'), ('demo_supplier', 'supplier'), ('demo_admin', 'admin'), ('demo_coop', 'supplier')]:
            u, created = User.objects.get_or_create(username=name, defaults={'role': role, 'phone': None})
            if created:
                u.set_password('Demo@2026'); u.save()
            accounts[name] = u
        buyer, seller, coop = accounts['demo_buyer'], accounts['demo_supplier'], accounts['demo_coop']
        today = timezone.localdate()
        crops = [
            ('洛川红富士苹果', '陕西省延安市洛川县', '109.432,35.762', '苹果', 6.8, '优选级', 85, '5kg箱装', 640, 'photo-1560806887-1e4cd0b6cbd6', seller),
            ('洛川红富士苹果', '陕西省延安市洛川县', '109.432,35.762', '苹果', 4.2, '标准级', 70, '散装', 420, 'photo-1560806887-1e4cd0b6cbd6', seller),
            ('赣南纽荷尔脐橙', '江西省赣州市信丰县', '114.923,25.386', '脐橙', 5.6, '优选级', 80, '5kg箱装', 780, 'photo-1547514701-42782101795e', seller),
            ('攀枝花凯特芒果', '四川省攀枝花市仁和区', '101.738,26.498', '芒果', 9.8, '优选级', 100, '5kg箱装', 280, 'photo-1553279768-865429fa0078', seller),
            ('库尔勒香梨', '新疆巴音郭楞州库尔勒市', '86.175,41.726', '香梨', 7.2, '标准级', 65, '散装', 520, 'photo-1615484477778-ca3b77940c25', coop),
            ('寿光鲜采黄瓜', '山东省潍坊市寿光市', '118.791,36.856', '黄瓜', 3.6, '标准级', 0, '散装', 900, 'photo-1449300079323-02e209d9d3a6', coop),
            ('海南金钻凤梨', '海南省澄迈县', '110.006,19.738', '凤梨', 5.8, '标准级', 90, '散装', 460, 'photo-1550258987-190a2d41a8ba', coop),
            ('阳山水蜜桃', '江苏省无锡市惠山区', '120.119,31.572', '水蜜桃', 12.0, '优选级', 75, '3kg礼盒', 160, 'photo-1629828874514-c1e5103f0550', seller),
        ]
        products, batches = [], []
        for i, (name, origin, loc, variety, price, grade, size, pack, qty, photo, owner) in enumerate(crops):
            p, created = Product.objects.get_or_create(name=name, owner=owner, grade=grade, is_demo=True,
                defaults={'category': 'fruits_vegs', 'origin': origin, 'location': loc, 'variety': variety,
                    'retail_price': price, 'unit': 'kg', 'stock': qty, 'packaging': pack, 'min_order': 10,
                    'delivery_days': 2, 'status': 'on_sale',
                    'image_url': f'https://images.unsplash.com/{photo}?auto=format&fit=crop&w=900&q=85',
                    'description': f'{origin}产地供货。按批次管理库存、抽样复核及交付记录。此货源为本地演示样例，不代表真实供应。'})
            if created:
                p.price_tiers.create(min_quantity=100, wholesale_price=Decimal(str(price)) - Decimal('.30'))
                p.price_tiers.create(min_quantity=300, wholesale_price=Decimal(str(price)) - Decimal('.60'))
            b, _ = StockBatch.objects.get_or_create(code=f'DEMO-{i+1:03d}', defaults={
                'product': p, 'quantity': qty, 'grade': grade, 'packaging': pack, 'size_mm': size,
                'harvest_date': today-timedelta(days=2), 'available_date': today,
                'status': 'pending' if i == 7 else 'released', 'sample_size': 80 if i % 2 else 200,
                'defect_count': [2, 4, 1, 2, 2, 3, 1, 0][i],
                'note': '演示抽样记录，供业务流程体验；不是实际检测或品质证明。'})
            products.append(p); batches.append(b)
        specs = [
            ('门店周配 · 优选苹果', '苹果', 180, 7.5, 80, '优选级', '5kg箱装', 5),
            ('餐饮集采 · 标准苹果', '苹果', 240, 5.0, 65, '标准级', '散装', 12),
            ('社区团购 · 赣南脐橙', '脐橙', 320, 6.0, 75, '', '5kg箱装', 5),
            ('水果门店 · 凯特芒果', '芒果', 140, 10.5, 90, '优选级', '', 8),
            ('厨房日配 · 新鲜黄瓜', '黄瓜', 360, 4.2, 0, '', '散装', 10),
            ('活动采购 · 当季凤梨', '凤梨', 120, 6.5, 0, '', '', 10),
        ]
        for title, word, qty, budget, size, grade, pack, tolerance in specs:
            PurchaseDemand.objects.get_or_create(buyer=buyer, title=title, is_demo=True,
                defaults={'keyword': word, 'quantity': qty, 'budget': budget, 'unit': 'kg', 'min_size': size,
                    'grade': grade, 'packaging': pack, 'tolerance': tolerance, 'deadline': today+timedelta(days=5),
                    'destination': '四川省成都市武侯区科华北路 · 演示收货点', 'location': '104.073,30.630',
                    'note': '演示采购需求，可修改场景试算；成交须由采购方确认。'})
        ShippingAddress.objects.get_or_create(user=buyer, detail_address='成都市武侯区科华北路88号（演示地址）',
            defaults={'receiver_name': '采购联系人', 'receiver_phone': '13800000000', 'is_default': True})
        if not Order.objects.filter(user=buyer, is_demo=True).exists():
            for index, state in enumerate(['pending', 'paid', 'shipped', 'completed']):
                b = batches[index]
                o = create_order(buyer, b, Decimal('20'), address={'receiver_name': '演示采购员',
                    'receiver_phone': '13800000000', 'address': '成都市武侯区 · 演示收货点'})
                o.status = state
                if state != 'pending': o.payment_status = 'confirmed'; o.payment_reference = 'DEMO-TRANSFER'
                if state in ['shipped', 'completed']:
                    b.quantity -= o.quantity; b.reserved -= o.quantity; b.save()
                    o.carrier, o.tracking_number = '本地配送（演示）', f'DEMO-SHIP-{index}'
                if state == 'completed': o.accepted_quantity = o.quantity
                event(o, seller, '演示历史事件', '此订单为演示记录，不代表实际交易或收款')
                o.save()
        self.stdout.write(self.style.SUCCESS('Demo workspace ready: demo_buyer / demo_supplier / demo_admin; password Demo@2026. All business samples are labelled.'))
