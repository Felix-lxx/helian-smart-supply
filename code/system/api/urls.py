# api/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    MyTokenObtainPairView,
    RegisterView,
    ProductListView,
    ProductDetailView,
    ProductCreateView,
    AddressViewSet,
    OrderListView,
    SupplierOrderListView,
    OrderCreateView,
    OrderPayView,
    OrderShipView,
    MyProductListView,
    ProductUpdateView,
    ProductOnSaleView,
    ProductOffShelfView,
    ProductDeleteView,
    AdminUserListView,
    AdminToggleUserStatusView,
    AdminProductDeleteView,
    ProductActionLogView,
    DeviceReportView,
    OrderDeleteView,
    OrderStatusUpdateView,
    GlobalOrderListView,
    ProductRecommendView,
    SystemDashboardStatsView,
    RealNameStatusView,
    RealNameSubmitView,
    AdminRealNamePendingListView,
    AdminRealNameApproveView,
    AdminRealNameRejectView,
    UserProfileView,
    AiAssistantView,
    QualityInspectionView,
    QualityLogListView,
    CommentListCreateView,
    CommentDeleteView,
    CommentVoteView
)


# 注册 ViewSet 路由
router = DefaultRouter()
router.register(r'addresses', AddressViewSet, basename='address')

# URL 路由配置
urlpatterns = [
    path('workspace/', include('api.map_api')),
    path('workspace/', include('api.collaboration_api')),
    path('workspace/', include('api.commerce')),
    # 路由器包含的 ViewSet 路由（如 addresses/）
    path('', include(router.urls)),

    # 认证相关
    path('login/', MyTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('register/', RegisterView.as_view(), name='register'),

    # 商品管理接口
    path('products/', ProductListView.as_view(), name='product-list'),
    path('products/<int:pk>/', ProductDetailView.as_view(), name='product-detail'),
    path('products/create/', ProductCreateView.as_view(), name='product-create'),
    path('products/mine/', MyProductListView.as_view(), name='my-products-list'),
    path('products/<int:pk>/update/', ProductUpdateView.as_view(), name='product-update'),
    path('products/<int:pk>/on_sale/', ProductOnSaleView.as_view(), name='product-on-sale'),
    path('products/<int:pk>/off_shelf/', ProductOffShelfView.as_view(), name='product-off-shelf'),
    path('products/<int:pk>/delete/', ProductDeleteView.as_view(), name='product-delete'),
    path('products/<int:pk>/logs/', ProductActionLogView.as_view(), name='product-logs'),

    # 订单管理接口
    path('orders/', OrderListView.as_view(), name='order-list'),
    path('orders/supplier/', SupplierOrderListView.as_view(), name='supplier-order-list'),
    path('orders/create/', OrderCreateView.as_view(), name='order-create'),
    path('orders/<int:pk>/pay/', OrderPayView.as_view(), name='order-pay'),
    path('orders/<int:pk>/ship/', OrderShipView.as_view(), name='order-ship'),
    path('orders/<int:pk>/delete/', OrderDeleteView.as_view(), name='order-delete'),

    # 用户资料与实名认证
    path('user/profile/', UserProfileView.as_view(), name='user-profile'),
    path('realname/status/', RealNameStatusView.as_view(), name='realname-status'),
    path('realname/submit/', RealNameSubmitView.as_view(), name='realname-submit'),

    # 管理员接口 - 用户管理
    path('admin/users/', AdminUserListView.as_view(), name='admin-user-list'),
    path('admin/users/<int:pk>/toggle-status/', AdminToggleUserStatusView.as_view(), name='admin-user-toggle'),

    # 管理员接口 - 商品管理
    path('admin/products/', ProductListView.as_view(), name='admin-product-list'),
    path('admin/products/<int:pk>/delete/', AdminProductDeleteView.as_view(), name='admin-product-delete'),

    # 管理员接口 - 订单管理
    path('admin/orders/', GlobalOrderListView.as_view(), name='admin-order-list'),
    path('orders/all/', GlobalOrderListView.as_view(), name='all-orders-compat'),

    # 管理员接口 - 实名认证审核
    path('admin/realname/pending/', AdminRealNamePendingListView.as_view(), name='admin-realname-pending'),
    path('admin/realname/<int:pk>/approve/', AdminRealNameApproveView.as_view(), name='admin-realname-approve'),
    path('admin/realname/<int:pk>/reject/', AdminRealNameRejectView.as_view(), name='admin-realname-reject'),

    # 系统与工具接口
    path('sys/stats/', SystemDashboardStatsView.as_view(), name='system-stats-compat'),
    path('system/stats/', SystemDashboardStatsView.as_view(), name='system-stats'),
    path('device/report/', DeviceReportView.as_view(), name='device-report'),
    path('recommend/', ProductRecommendView.as_view(), name='product-recommend'),
    path('assistant/ask/', AiAssistantView.as_view(), name='ai-assistant'),

    # 质量检测接口
    path('quality/inspect/', QualityInspectionView.as_view(), name='ai-inspect'),
    path('quality/logs/', QualityLogListView.as_view(), name='quality-logs-public'),

    # 评论管理接口
    path('products/<int:product_id>/comments/', CommentListCreateView.as_view(), name='comment-list-create'),
    path('comments/<int:pk>/delete/', CommentDeleteView.as_view(), name='comment-delete'),
    path('comments/<int:pk>/vote/', CommentVoteView.as_view(), name='comment-vote'),
]
