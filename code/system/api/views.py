from rest_framework import generics, status, viewsets
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied
import time
import hashlib
import requests
try:
    import torch
except ImportError:
    torch = None
import os
import uuid
from PIL import Image

from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

from django.db import transaction
from django.db.models import Sum, Count
from django.utils import timezone
from django.conf import settings
from django.shortcuts import get_object_or_404

from .models import (
    User, Product, Order, ShippingAddress, QualityInspectionLog,
    ProductActionLog, RealNameAuth, DeviceNode, DeviceTelemetry,
    ProductComment
)
from .serializers import (
    RegisterSerializer,
    ProductSerializer,
    ProductDetailSerializer,
    ProductManageSerializer,
    ProductCommentSerializer,
    ProductActionLogSerializer,
    OrderSerializer,
    ShippingAddressSerializer,
    RealNameAuthSerializer,
    RealNameSubmitSerializer,
    UserProfileSerializer,
    QualityLogSerializer
)

# --- 辅助函数 ---
def mask_id_card(id_card_no: str) -> str:
    if len(id_card_no) < 8: return id_card_no
    return id_card_no[:3] + '********' + id_card_no[-4:]

def hash_id_card(id_card_no: str) -> str:
    return hashlib.sha256(id_card_no.encode('utf-8')).hexdigest()

def is_user_realname_approved(user) -> bool:
    if getattr(user, 'role', '') == 'admin': return True
    auth = RealNameAuth.objects.filter(user=user, status='approved').first()
    return auth is not None

# --- 1. 账号与权限视图---
class RegisterView(APIView):
    permission_classes = (AllowAny,)
    def post(self, request):
        role = request.data.get('role')
        invite_code = request.data.get('invite_code')
        if role == 'admin':
            return Response({"error": "管理员由内部创建，不开放公开注册"}, status=403)
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            user.is_active = True
            user.save()
            return Response({"message": "注册成功"}, status=201)
        return Response(serializer.errors, status=400)

class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        data['role'] = self.user.role
        data['username'] = self.user.username
        data['user_id'] = self.user.id
        return data

class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer

class UserProfileView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserProfileSerializer

    def get_object(self):
        return self.request.user

    def patch(self, request, *args, **kwargs):
        if 'avatar' in request.FILES:
            user = self.get_object()
            user.avatar = request.FILES['avatar']
            user.save()
            return Response({"message": "头像上传成功", "avatar_url": user.avatar.url})
        return super().patch(request, *args, **kwargs)

# --- 2. 管理员监管视图 ---
class AdminUserListView(generics.ListAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        if self.request.user.role != 'admin': return User.objects.none()
        return User.objects.all().order_by('id')

class AdminToggleUserStatusView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, pk):
        if request.user.role != 'admin': return Response({"error": "仅管理员可操作"}, status=403)
        try:
            user = User.objects.get(pk=pk)
            if user.is_superuser: return Response({"error": "不能操作超级管理员"}, status=400)
            user.is_active = not user.is_active
            user.save()
            return Response({"message": f"用户状态已更新为 {'正常' if user.is_active else '禁用'}"})
        except User.DoesNotExist: return Response({"error": "用户不存在"}, status=404)

class AdminProductDeleteView(generics.DestroyAPIView):
    queryset = Product.objects.all()
    permission_classes = [IsAuthenticated]
    def perform_destroy(self, instance):
        if self.request.user.role != 'admin': raise PermissionDenied("仅管理员可操作")
        instance.is_deleted = True
        instance.status = 'off_shelf'
        instance.save(update_fields=['is_deleted', 'status'])

# --- 3. 商品业务视图 ---
class ProductListView(generics.ListAPIView):
    serializer_class = ProductSerializer
    permission_classes = (AllowAny,)
    def get_queryset(self): return Product.objects.filter(status='on_sale', is_deleted=False).order_by('id')

class ProductDetailView(generics.RetrieveAPIView):
    queryset = Product.objects.filter(is_deleted=False)
    serializer_class = ProductDetailSerializer
    permission_classes = (AllowAny,)

class ProductCreateView(generics.CreateAPIView):
    serializer_class = ProductManageSerializer
    permission_classes = [IsAuthenticated]
    def post(self,request,*args,**kwargs):
        return Response({'detail':'旧商品写入已停用，请使用商品与批次工作区统一录入'},status=409)

    def perform_create(self, serializer):
        if self.request.user.role != 'supplier':
            raise PermissionDenied('仅供应商可发布商品')
        if not is_user_realname_approved(self.request.user):
            raise PermissionDenied("请先完成实名认证")

        origin = self.request.data.get('origin', '')
        coords = "108.94,34.34"
        try:
            res = requests.get(f"https://restapi.amap.com/v3/geocode/geo?key={os.getenv('AMAP_API_KEY', '')}&address={origin}", timeout=5).json()
            if res.get('status') == '1' and res.get('geocodes'):
                coords = res['geocodes'][0]['location']
        except:
            pass

        # 处理图片上传
        image_file = self.request.FILES.get('image_file')
        final_image_url = self.request.data.get('image_url', '')

        if image_file:
            ext = image_file.name.split('.')[-1]
            filename = f"{uuid.uuid4().hex}.{ext}"
            relative_path = f"products/{filename}"
            # 存储到磁盘的绝对路径（Django 会处理不同操作系统的路径分隔符）
            abs_path = os.path.join(settings.MEDIA_ROOT, 'products', filename)
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            with open(abs_path, 'wb+') as dest:
                for chunk in image_file.chunks():
                    dest.write(chunk)
            final_image_url = self.request.build_absolute_uri(f"{settings.MEDIA_URL}{relative_path}")

        # 保存商品
        product = serializer.save(
            owner=self.request.user,
            location=coords,
            status='draft',
            image_url=final_image_url
        )

        ProductActionLog.objects.create(
            product=product,
            operator=self.request.user,
            action_type='create',
            remark='创建商品',
            after_snapshot={
                'name': product.name,
                'stock': product.stock,
                'retail_price': float(product.retail_price)
            }
        )

class ProductUpdateView(generics.UpdateAPIView):
    serializer_class = ProductManageSerializer
    permission_classes = [IsAuthenticated]
    def update(self,request,*args,**kwargs):
        return Response({'detail':'请通过商品与批次工作区更新，统一规格和费用规则'},status=409)
    def get_queryset(self): return Product.objects.filter(owner=self.request.user, is_deleted=False)
    def perform_update(self, serializer):
        old = self.get_object()
        before = {'name': old.name, 'retail_price': float(old.retail_price), 'status': old.status, 'stock': old.stock}
        product = serializer.save()
        ProductActionLog.objects.create(product=product, operator=self.request.user, action_type='edit', remark='编辑商品', before_snapshot=before, after_snapshot={'name': product.name, 'retail_price': float(product.retail_price), 'status': product.status, 'stock': product.stock})

class ProductOnSaleView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, pk):
        return Response({'detail':'请通过批次工作区上架，需核对放行库存'},status=409)
        if not is_user_realname_approved(request.user): return Response({"error": "请先实名认证"}, status=403)
        try:
            product = Product.objects.get(pk=pk, owner=request.user, is_deleted=False)
            before = {'status': product.status}
            product.status = 'on_sale'
            product.save()
            ProductActionLog.objects.create(product=product, operator=request.user, action_type='on_sale', before_snapshot=before, after_snapshot={'status': 'on_sale'})
            return Response({"message": "商品已上架"})
        except: return Response({"error": "商品不存在"}, status=404)

class ProductOffShelfView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, pk):
        try:
            product = Product.objects.get(pk=pk) if request.user.role == 'admin' else Product.objects.get(pk=pk, owner=request.user)
            reason = request.data.get('reason')
            if not reason:
                return Response({"error": "商品下架原因不能为空"}, status=400)

            product.status, product.off_shelf_reason = 'off_shelf', reason
            product.save()
            return Response({"message": f"已成功下架：{reason}"})
        except: return Response({"error": "商品不存在"}, status=404)

class ProductDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        try:
            product = Product.objects.get(pk=pk, owner=request.user, is_deleted=False)
        except Product.DoesNotExist:
            return Response({"error": "商品不存在"}, status=404)

        if product.status != 'off_shelf':
            return Response({"error": "仅下架商品可删除"}, status=400)

        before = {"status": product.status, "is_deleted": product.is_deleted}
        product.is_deleted = True
        product.save(update_fields=["is_deleted"])

        ProductActionLog.objects.create(
            product=product,
            operator=request.user,
            action_type='delete',
            remark='删除商品',
            before_snapshot=before,
            after_snapshot={"status": product.status, "is_deleted": product.is_deleted}
        )
        return Response({"message": "商品已删除"})

# --- 4. 订单与交易视图 ---
class OrderCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        return Response({'error': '请通过新版采购清单选择放行批次后下单'}, status=409)

class OrderPayView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, pk):
        return Response({'error': '请在新版订单履约中提交付款确认，由收款方核对'}, status=409)

class OrderShipView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, pk):
        return Response({'error': '请在新版订单履约中登记发运和批次数量'}, status=409)

class OrderDeleteView(generics.DestroyAPIView):
    queryset = Order.objects.all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # 管理员查看全量，买家仅能操作自己的订单数据
        if self.request.user.role == 'admin':
            return Order.objects.all()
        return Order.objects.filter(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        return Response({'error': '订单保留历史记录，请通过新版取消操作释放预留库存'}, status=409)

class OrderStatusUpdateView(APIView):
    permission_classes = [IsAuthenticated]
    def patch(self, request, pk):
        return Response({'error': '请使用新版订单履约操作，状态必须按业务流程流转'}, status=409)

# --- 5. 统计与监控视图 ---
class DeviceReportView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        import os, secrets
        expected = os.getenv('DEVICE_INGEST_TOKEN', '')
        if not expected or not secrets.compare_digest(request.headers.get('X-Device-Token', ''), expected):
            return Response({'error': '设备令牌未配置或无效'}, status=403)
        from .commerce import number,integer
        from .models import StockBatch,InspectionTask
        device_id=str(request.data.get('device_id','')).strip()
        if not device_id or len(device_id)>50:return Response({'detail':'请填写有效的设备编号'},status=400)
        load=number(request.data.get('npu_load',0),maximum=100)
        delay=integer(request.data.get('yolo_delay',0),0,600000)
        batch=StockBatch.objects.filter(pk=request.data.get('batch_id')).first() if request.data.get('batch_id') else None
        task=InspectionTask.objects.filter(pk=request.data.get('task_id')).first() if request.data.get('task_id') else None
        if request.data.get('batch_id') and not batch:return Response({'detail':'关联批次不存在'},status=400)
        if request.data.get('task_id') and (not task or not batch or task.batch_id!=batch.id):return Response({'detail':'任务与批次不匹配'},status=400)
        observations=request.data.get('observations',{})
        if not isinstance(observations,dict) or len(str(observations))>10000:return Response({'detail':'观测数据格式无效'},status=400)
        dev, _ = DeviceNode.objects.get_or_create(device_id=device_id)
        DeviceTelemetry.objects.create(device=dev,npu_load=load,yolo_delay=delay,batch=batch,task=task,
            observations=observations,warning_msg=str(request.data.get('warning_msg','Normal'))[:200])
        return Response({"status": "success"})
    def get(self, request):
        latest = DeviceTelemetry.objects.order_by('-timestamp').first()
        if not latest or (timezone.now() - latest.timestamp).total_seconds() > 15:
            return Response({"status": "offline", "npu_load": 0})
        return Response({"npu_load": latest.npu_load, "yolo_delay": latest.yolo_delay, "warning_msg": latest.warning_msg, "status": "online"})

class SystemDashboardStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != 'admin':
            raise PermissionDenied('平台统计仅供运营管理员查看')
        total_orders = Order.objects.count()
        total_users = User.objects.count()
        total_products = Product.objects.count()
        device_count = DeviceNode.objects.count()
        rev = Order.objects.filter(status__in=['paid','shipped','completed']).aggregate(Sum('total_amount'))['total_amount__sum'] or 0

        return Response({
            "total_orders": total_orders,
            "total_users": total_users,
            "total_products": total_products,
            "device_count": device_count,
            "total_revenue": float(rev),
            "wholesale_count": User.objects.filter(role='purchaser').count(),
            "supplier_count": User.objects.filter(role='supplier').count(),
            "trends": {"revenue": None, "wholesale": None, "supplier": None}
        })

# --- 6. 实名认证视图 ---
class RealNameStatusView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        auth = RealNameAuth.objects.filter(user=request.user).first()
        return Response(RealNameAuthSerializer(auth).data if auth else {"status": "unverified"})

class RealNameSubmitView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        if request.user.role == 'admin': return Response({"error": "管理员无需认证"}, status=400)
        ser = RealNameSubmitSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        auth, _ = RealNameAuth.objects.update_or_create(user=request.user, defaults={'real_name': ser.validated_data['real_name'], 'id_card_masked': mask_id_card(ser.validated_data['id_card_no']), 'id_card_hash': hash_id_card(ser.validated_data['id_card_no']), 'face_image_url': ser.validated_data.get('face_image_url', ''), 'status': 'pending'})
        return Response({"message": "提交成功", "data": RealNameAuthSerializer(auth).data})

class AdminRealNamePendingListView(generics.ListAPIView):
    serializer_class = RealNameAuthSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self): return RealNameAuth.objects.filter(status='pending').order_by('id') if self.request.user.role == 'admin' else RealNameAuth.objects.none()

class AdminRealNameApproveView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, pk):
        if request.user.role != 'admin': raise PermissionDenied('仅管理员可审核')
        auth = RealNameAuth.objects.get(pk=pk)
        auth.status, auth.reviewed_by, auth.reviewed_at = 'approved', request.user, timezone.now()
        auth.save()
        return Response({"message": "已通过"})

class AdminRealNameRejectView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, pk):
        if request.user.role != 'admin': raise PermissionDenied('仅管理员可审核')
        auth = RealNameAuth.objects.get(pk=pk)
        auth.status, auth.reject_reason = 'rejected', request.data.get('reason', '资料不符')
        auth.reviewed_by, auth.reviewed_at = request.user, timezone.now()
        auth.save()
        return Response({"message": "已驳回"})

# --- 7. 其他列表与推荐---
class AddressViewSet(viewsets.ModelViewSet):
    serializer_class = ShippingAddressSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self): return ShippingAddress.objects.filter(user=self.request.user)
    def perform_create(self, serializer):
        with transaction.atomic():
            if serializer.validated_data.get('is_default'):
                ShippingAddress.objects.filter(user=self.request.user).update(is_default=False)
            serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        with transaction.atomic():
            if serializer.validated_data.get('is_default'):
                ShippingAddress.objects.filter(user=self.request.user).exclude(pk=self.get_object().pk).update(is_default=False)
            serializer.save()

class OrderListView(generics.ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self): return Order.objects.filter(user=self.request.user).order_by('id')

class SupplierOrderListView(generics.ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self): return Order.objects.filter(product__owner=self.request.user).order_by('id')

class MyProductListView(generics.ListAPIView):
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self): return Product.objects.filter(owner=self.request.user, is_deleted=False).order_by('id')

class GlobalOrderListView(generics.ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        if self.request.user.role != 'admin': raise PermissionDenied('仅管理员可查询全站订单')
        return Order.objects.select_related('user', 'product').order_by('-created_at')

class ProductActionLogView(generics.ListAPIView):
    serializer_class = ProductActionLogSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self): return ProductActionLog.objects.filter(product_id=self.kwargs['pk'], product__owner=self.request.user).order_by('-created_at')


from .recommend_service import get_predictions
class ProductRecommendView(APIView):
    """
    基于 LightGBM 的双轨推荐系统接口
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # --- 场景 A：供应商（卖家竞品分析轨道）---
        if user.role == 'supplier':
            anchor_product = Product.objects.filter(owner=user, status='on_sale', is_deleted=False).first()
            seller_product_id = anchor_product.id if anchor_product else None

            # 获取原生商品对象列表
            competitor_predictions = get_predictions(
                user_id=user.id,
                request_type="seller",
                seller_product_id=seller_product_id
            )

            # 在视图层安全序列化
            serializer = ProductSerializer(competitor_predictions, many=True)
            return Response({
                "type": "competitor",
                "title": "绔炲搧鎯呮姤锛歀ightGBM 濞佽儊鎰熺煡",
                "advice": "按可售库存与同品类筛选的规则建议，不是预测收益或价格。",
                "data": serializer.data
            })

        # --- 场景 B：采购商（买家猜你喜欢轨道）---
        else:
            # 获取原生商品对象列表
            buyer_predictions = get_predictions(
                user_id=user.id,
                request_type="buyer"
            )

            # 在视图层安全序列化
            serializer = ProductSerializer(buyer_predictions, many=True)
            return Response({
                "type": "buyer",
                "title": "猜你喜欢：优质农产品推荐",
                "advice": "按真实采购品类与可售库存筛选；历史不足时按上架时间展示。",
                "data": serializer.data
            })

class AiAssistantView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        question = request.data.get('question', '')

        biz_context = self._capture_business_context(user)

        system_content = f"""
        你是“智农参谋”AI 助手，服务于智慧农产品系统。
        当前用户信息：
        - 角色：{user.get_role_display()}
        - 业务上下文：{biz_context}

        你的职责：
        - 用户为供应商时：基于竞品与销量信息给出定价、上架和质检建议。
        - 用户为买家时：基于质检与推荐信息给出采购建议。
        - 回复风格：专业、简洁、可执行。
        """

        try:
            payload = {
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": question}
                ],
                "stream": False
            }
            headers = {
                "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            }

            # 执行 10s 超时熔断
            response = requests.post(
                f"{settings.DEEPSEEK_BASE_URL}/chat/completions",
                json=payload,
                headers=headers,
                timeout=10
            )

            res_json = response.json()
            answer = res_json['choices'][0]['message']['content']
            return Response({"answer": answer})

        except Exception as e:
            print(f"DeepSeek 调用出错的具体原因：{e}")
            return Response({"answer": "（智农大脑连接超时）系统已自动启动降级保护，建议稍后重试。"})

    def _capture_business_context(self, user):
        from django.db.models import Sum, Avg

        # 1. 获取全局宏观数据作为底层背景
        total_revenue = Order.objects.filter(status__in=['paid','shipped','completed']).aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        total_products = Product.objects.filter(status='on_sale', is_deleted=False).count()

        global_context = f"当前平台宏观运营数据：全网在售农产品共 {total_products} 种，平台累计交易额 {total_revenue} 元。"

        # 2. 根据不同角色注入深度业务数据
        if user.role == 'supplier':
            my_cats = Product.objects.filter(owner=user).values_list('category', flat=True).distinct()
            comp = Product.objects.filter(category__in=my_cats).exclude(owner=user).order_by('-sales_count').first()
            avg_price = Product.objects.filter(category__in=my_cats, status='on_sale').aggregate(Avg('retail_price'))['retail_price__avg'] or 0

            supplier_context = f"您所在类目的全网平均售价约为 {avg_price:.2f} 元。"
            if comp:
                supplier_context += f" 主要竞争对手 {comp.name} 的销量为 {comp.sales_count}，定价为 {comp.retail_price} 元。"
            return f"{global_context} {supplier_context}"

        # 3. 针对买家注入最新 AI 质检与推荐依据
        recent_logs = QualityInspectionLog.objects.order_by('-created_at')[:5]
        if recent_logs.exists():
            total_bad = sum([log.bad_count for log in recent_logs])
            buyer_context = f"近期端云协同 YOLO 质检显示，最近批次共检出坏果 {total_bad} 个。"
            return f"{global_context} {buyer_context}"

        return f"{global_context} 当前市场供应充足，平台质检通过率较高。"

# --- 全局加载 YOLOv5 模型（GPU 加速）---
os.environ.setdefault('YOLOv5_AUTOINSTALL', 'false')
os.environ.setdefault('YOLO_AUTOINSTALL', 'false')
os.environ.setdefault('YOLO_CONFIG_DIR', str(settings.BASE_DIR.parent.parent / '.run' / 'ultralytics'))
DEVICE = '0' if torch is not None and torch.cuda.is_available() else 'cpu'
WEIGHTS_PATH = os.path.join(settings.BASE_DIR, 'best.pt')
YOLOV5_LOCAL_DIR = os.path.join(settings.BASE_DIR.parent.parent, 'vendor', 'yolov5')

model = None
if torch is None:
    print('Optional image inference disabled: install requirements-ai.txt to enable it')
elif not os.path.exists(WEIGHTS_PATH):
    print(f'Local model file not found: {WEIGHTS_PATH}')
elif not os.path.isdir(YOLOV5_LOCAL_DIR):
    print(f'Local yolov5 repo not found: {YOLOV5_LOCAL_DIR}')
else:
    try:
        model = torch.hub.load(
            YOLOV5_LOCAL_DIR,
            'custom',
            path=WEIGHTS_PATH,
            device=DEVICE,
            source='local'
        )
        print(f'Loaded local model: {WEIGHTS_PATH}')
    except Exception as e:
        print(f'Failed to load local model: {e}')

class QualityInspectionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if model is None:
            return Response({"error": "YOLO local model is not loaded"}, status=503)
        if request.user.role != 'admin':
            return Response({"error": "仅管理员可执行 AI 质量审计"}, status=403)

        image_file = request.FILES.get('image')
        product_id = request.data.get('product_id')

        # 1. YOLOv5 实时推理
        img = Image.open(image_file)
        results = model(img)

        # 2. 解析结果
        df = results.pandas().xyxy[0]
        # 这里的正则会捕捉你标注时使用的各类坏果标签名
        bad_df = df[df['name'].str.contains('bad|defect|rotten', case=False)]

        # 3. 渲染标注图并保存
        results.render()
        processed_img = Image.fromarray(results.ims[0])

        file_name = f"det_{uuid.uuid4()}.jpg"
        # 1. 专门用于 URL 的相对路径（强制使用正斜杠 /）
        rel_path = f"quality/processed/{file_name}"

        # 2. 专门用于系统本地存储文件的绝对路径（使用 os.path.join 适配 Windows）
        abs_path = os.path.join(settings.MEDIA_ROOT, 'quality', 'processed', file_name)

        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        processed_img.save(abs_path)

        # 4. 持久化日志
        # 假设已正确导入 QualityInspectionLog 模型
        log = QualityInspectionLog.objects.create(
            product_id=product_id,
            raw_image=image_file,
            processed_image=rel_path,
            bad_count=len(bad_df),
            summary=f"AI 完成自动审计：检出异常位点 {len(bad_df)} 处。",
            inspector=request.user
        )

        return Response({
            "message": "AI 审计完成，质检日志已同步",
            "bad_count": len(bad_df),
            # 使用 request.build_absolute_uri 动态生成完整绝对路径，避免 Vue 图片 404
            "image_url": request.build_absolute_uri(log.processed_image.url)
        })

class QualityLogListView(generics.ListAPIView):
    queryset = QualityInspectionLog.objects.all().order_by('-created_at')[:30]
    serializer_class = QualityLogSerializer
    permission_classes = [AllowAny]

class CommentListCreateView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request, product_id):
        sort_type = request.query_params.get('sort', 'time')
        comments = ProductComment.objects.filter(product_id=product_id, parent__isnull=True)

        if sort_type == 'heat':
            comments = comments.annotate(
                heat=Count('likes', distinct=True) - Count('dislikes', distinct=True)
            ).order_by('-heat', '-created_at')
        else:
            comments = comments.order_by('-created_at')

        serializer = ProductCommentSerializer(comments, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request, product_id):
        user = request.user
        product = get_object_or_404(Product, id=product_id)

        if user.role == 'admin':
            return Response({"detail": "管理员无权参与商品评论"}, status=status.HTTP_403_FORBIDDEN)

        rating = request.data.get('rating')
        content = request.data.get('content')
        parent_id = request.data.get('parent_id')

        if not content:
            return Response({"detail": "评论内容不能为空"}, status=status.HTTP_400_BAD_REQUEST)

        parent_comment = None
        if parent_id:
            parent_comment = get_object_or_404(ProductComment, id=parent_id)
            rating = None

        # --- 开始角色逻辑判定 ---
        if user.role == 'supplier':
            if product.owner.id != user.id:
                return Response({"detail": "您只能回复自己发布的商品"}, status=status.HTTP_403_FORBIDDEN)
            comment = ProductComment.objects.create(
                product=product, user=user, content=content,
                is_seller_reply=True, parent=parent_comment
            )
            return Response(ProductCommentSerializer(comment, context={'request': request}).data)

        elif user.role == 'purchaser' or user.role == 'retail': # 包含零售用户角色
            if rating is not None:
                if not isinstance(rating, int) or not 1 <= rating <= 5:
                    return Response({'detail': '评分应为1到5'}, status=400)
                if not Order.objects.filter(user=user, product=product, status='completed').exists():
                    return Response({'detail': '完成交易后才能进行商品评分'}, status=403)
            if not parent_comment:
                has_rated = ProductComment.objects.filter(product=product, user=user, rating__isnull=False).exists()
                if has_rated and rating is not None:
                    rating = None

            comment = ProductComment.objects.create(
                product=product, user=user, content=content,
                rating=rating, is_seller_reply=False, parent=parent_comment
            )
            return Response(ProductCommentSerializer(comment, context={'request': request}).data)

        # 核心修复：增加最后的兜底返回，防止返回 NoneType
        return Response({"detail": "您的账号角色无法发布评论"}, status=status.HTTP_400_BAD_REQUEST)

        if user.role == 'purchaser':
            if not parent_comment:
                has_rated = ProductComment.objects.filter(product=product, user=user, rating__isnull=False).exists()
                if has_rated and rating is not None:
                    rating = None

            comment = ProductComment.objects.create(
                product=product, user=user, content=content,
                rating=rating, is_seller_reply=False, parent=parent_comment
            )
            return Response(ProductCommentSerializer(comment, context={'request': request}).data)


class CommentDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        if request.user.role != 'admin':
            return Response({"detail": "仅管理员可删除评论"}, status=status.HTTP_403_FORBIDDEN)

        comment = get_object_or_404(ProductComment, pk=pk)
        comment.delete()
        return Response({"detail": "删除成功"}, status=status.HTTP_204_NO_CONTENT)


class CommentVoteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if request.user.role == 'admin':
            return Response({"detail": "管理员不可参与互动"}, status=status.HTTP_403_FORBIDDEN)

        action = request.data.get('action')
        comment = get_object_or_404(ProductComment, pk=pk)
        user = request.user

        if action == 'like':
            if user in comment.likes.all():
                comment.likes.remove(user)
            else:
                comment.likes.add(user)
                comment.dislikes.remove(user)
        elif action == 'dislike':
            if user in comment.dislikes.all():
                comment.dislikes.remove(user)
            else:
                comment.dislikes.add(user)
                comment.likes.remove(user)

        return Response({"detail": "操作成功"})
