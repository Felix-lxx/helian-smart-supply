from django.db import models
from django.contrib.auth.models import AbstractUser
# 引入评论系统所需的依赖
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Avg

# 1. 自定义用户表
class User(AbstractUser):
    ROLE_CHOICES = (
        ('retail', '普通零售用户'),
        ('supplier', '源头供应商/农户'),
        ('admin', '管理员'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='retail', verbose_name="账号身份")
    phone = models.CharField(max_length=11, unique=True, null=True, blank=True, verbose_name="手机号")
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True, verbose_name="用户头像")
    motto = models.CharField(max_length=100, blank=True, verbose_name="个性签名")
    qq_bound = models.BooleanField(default=False, verbose_name="QQ绑定状态")
    email_bound = models.BooleanField(default=False, verbose_name="邮箱绑定状态")
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sys_user'
        verbose_name = '系统用户'
        verbose_name_plural = verbose_name

# 2. 农产品表
class Product(models.Model):
    CATEGORY_CHOICES = (('fruits_vegs', '生鲜果蔬'), ('grains', '米面粮油'), ('meat', '肉禽蛋奶'), ('dry', '干货菌菇'))
    STATUS_CHOICES = (('draft', '草稿'), ('on_sale', '上架中'), ('off_shelf', '已下架'), ('sold_out', '已售罄'))

    name = models.CharField(max_length=100, verbose_name='商品名称')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, verbose_name='商品分类')
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='products', verbose_name='商家')
    retail_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='零售价')
    stock = models.PositiveIntegerField(default=0, verbose_name='库存')

    # 销量与评分字段
    sales_count = models.PositiveIntegerField(default=0, verbose_name="累计销量")
    rating_score = models.FloatField(default=5.0, verbose_name="商品评分")

    image_url = models.URLField(max_length=500, null=True, blank=True, verbose_name='商品图片')
    location = models.CharField(max_length=255, null=True, blank=True, verbose_name='产地经纬度')
    origin = models.CharField(max_length=255, null=True, blank=True, verbose_name='产地溯源名称')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name='商品状态')
    is_deleted = models.BooleanField(default=False, verbose_name="是否删除")
    off_shelf_reason = models.CharField(max_length=255, null=True, blank=True, verbose_name="下架原因")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    unit = models.CharField(max_length=12, default='斤')
    variety = models.CharField(max_length=80, blank=True)
    grade = models.CharField(max_length=30, default='标准级')
    packaging = models.CharField(max_length=80, default='散装')
    min_order = models.PositiveIntegerField(default=1)
    delivery_days = models.PositiveIntegerField(default=2)
    description = models.TextField(blank=True)
    packaging_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    freight_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    quantity_step = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    is_demo = models.BooleanField(default=False)

    class Meta:
        db_table = 'biz_product'
        verbose_name = '农产品'

# 3. 批发阶梯价
class PriceTier(models.Model):
    product = models.ForeignKey(Product, related_name='price_tiers', on_delete=models.CASCADE, verbose_name="关联农产品")
    min_quantity = models.IntegerField(verbose_name="起订量(斤)")
    wholesale_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="批发单价(元/斤)")

    class Meta:
        db_table = 'biz_price_tier'

# 4. 遥感监测数据
class RemoteSensing(models.Model):
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name='remote_sensing', verbose_name="关联农产品")
    ndvi_index = models.FloatField(verbose_name="植被生长指数(NDVI)")
    soil_moisture = models.FloatField(verbose_name="土壤湿度(%)")
    expert_analysis = models.TextField(verbose_name="专家智能解读")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'biz_remote_sensing'

# 5. 收货地址
class ShippingAddress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    receiver_name = models.CharField(max_length=50, verbose_name="收货人姓名")
    receiver_phone = models.CharField(max_length=20, verbose_name="收货电话")
    detail_address = models.TextField(verbose_name="详细地址")
    is_default = models.BooleanField(default=False)

    class Meta:
        db_table = 'biz_shipping_address'

# 6. 订单表 (含价格快照)
class Order(models.Model):
    STATUS_CHOICES = (('pending', '等待付款'), ('paid', '已支付(待发货)'), ('shipped', '已发运'), ('completed', '已完成'), ('cancelled', '已取消'), ('issue', '验收异常'), ('refunded', '已退款'))
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="采购方")
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, verbose_name="购买的商品")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="订单总金额")
    unit_price_at_purchase = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="成交单价快照")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="订单状态")
    receiver_name = models.CharField(max_length=50, null=True, blank=True, verbose_name="收货人姓名")
    receiver_phone = models.CharField(max_length=20, null=True, blank=True, verbose_name="收货电话")
    address_info = models.TextField(null=True, blank=True, verbose_name="详细地址信息")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="下单时间")
    quantity = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    snapshot = models.JSONField(default=dict, blank=True)
    batch = models.ForeignKey('StockBatch', null=True, blank=True, on_delete=models.PROTECT, related_name='orders')
    payment_status = models.CharField(max_length=30, default='unpaid')
    payment_reference = models.CharField(max_length=200, blank=True)
    carrier = models.CharField(max_length=100, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True)
    accepted_quantity = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    receipt = models.JSONField(default=dict, blank=True)
    version = models.PositiveIntegerField(default=1)
    promised_date = models.DateField(null=True, blank=True)
    issue = models.TextField(blank=True)
    resolution = models.TextField(blank=True)
    events = models.JSONField(default=list, blank=True)
    is_demo = models.BooleanField(default=False)

    class Meta:
        db_table = 'biz_order'

# 7. 商品操作日志
class ProductActionLog(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='action_logs')
    operator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action_type = models.CharField(max_length=20)
    remark = models.CharField(max_length=255, null=True, blank=True)
    before_snapshot = models.JSONField(null=True, blank=True)
    after_snapshot = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'biz_product_action_log'

# 8. 实名认证表
class RealNameAuth(models.Model):
    STATUS_CHOICES = (('unverified', '未认证'), ('pending', '待审核'), ('approved', '已通过'), ('rejected', '已驳回'))
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='realname_auth')
    real_name = models.CharField(max_length=50)
    id_card_masked = models.CharField(max_length=30)
    id_card_hash = models.CharField(max_length=128)
    face_image_url = models.URLField(max_length=500, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reject_reason = models.CharField(max_length=255, null=True, blank=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_realnames')
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

# 9. 监控设备持久化模型
class DeviceNode(models.Model):
    device_id = models.CharField("设备编号", max_length=50, unique=True)
    location = models.CharField("部署地点", max_length=100, default="产地监控站")
    status = models.CharField("当前状态", max_length=20, default='online')
    last_seen = models.DateTimeField(auto_now=True)

class DeviceTelemetry(models.Model):
    device = models.ForeignKey(DeviceNode, on_delete=models.CASCADE, related_name='telemetries')
    npu_load = models.FloatField("NPU负载")
    yolo_delay = models.IntegerField("推理延迟(ms)")
    warning_msg = models.CharField("告警信息", max_length=200, default='Normal')
    timestamp = models.DateTimeField(auto_now_add=True)
    batch = models.ForeignKey('StockBatch', null=True, blank=True, on_delete=models.PROTECT, related_name='telemetries')
    task = models.ForeignKey('InspectionTask', null=True, blank=True, on_delete=models.PROTECT, related_name='telemetries')
    observations = models.JSONField(default=dict, blank=True)

class QualityInspectionLog(models.Model):
    """
    第一阶段新增：坏果检测日志模型
    存储检测原图、AI 标注后的图片路径以及坏果数量
    """
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, related_name='quality_logs')
    raw_image = models.ImageField(upload_to='quality/raw/', verbose_name="质检原图")
    processed_image = models.ImageField(upload_to='quality/processed/', verbose_name="AI标注图")
    bad_count = models.IntegerField(default=0, verbose_name="坏果检出数")
    summary = models.CharField(max_length=255, verbose_name="检测结论")
    inspector = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="检测管理员")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="检测时间")

    class Meta:
        db_table = 'biz_quality_log'
        verbose_name = '坏果检测日志'

# 10. 商品评价与互动表
class ProductComment(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='comments', verbose_name="关联商品")
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="评论者")
    rating = models.IntegerField(null=True, blank=True, verbose_name="商品打分(1-5)")
    content = models.TextField(verbose_name="评论/回复内容")
    is_seller_reply = models.BooleanField(default=False, verbose_name="是否为商家直复")

    # 实现楼中楼的核心树形关联字段
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies', verbose_name="父评论")

    likes = models.ManyToManyField(User, related_name='liked_comments', blank=True, verbose_name="点赞用户")
    dislikes = models.ManyToManyField(User, related_name='disliked_comments', blank=True, verbose_name="点踩用户")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        db_table = 'biz_product_comment'
        verbose_name = '商品评价'
        ordering = ['-created_at']

# 当评论保存或删除时，自动计算并更新该商品的平均分
@receiver([post_save, post_delete], sender=ProductComment)
def update_product_rating(sender, instance, **kwargs):
    product = instance.product
    # 仅计算带有 rating 的评论
    avg_rating = product.comments.filter(rating__isnull=False).aggregate(Avg('rating'))['rating__avg']
    if avg_rating:
        product.rating_score = round(avg_rating, 1) # 保留一位小数
    else:
        product.rating_score = 0.0 # 默认0分
    product.save()


class StockBatch(models.Model):
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='batches')
    code = models.CharField(max_length=64, unique=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    reserved = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    grade = models.CharField(max_length=30, default='标准级')
    packaging = models.CharField(max_length=80, default='散装')
    size_mm = models.PositiveIntegerField(default=0)
    harvest_date = models.DateField(null=True, blank=True)
    available_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, default='pending')
    sample_size = models.PositiveIntegerField(default=0)
    defect_count = models.PositiveIntegerField(default=0)
    note = models.TextField(blank=True)
    inspections = models.JSONField(default=list, blank=True)
    input_weight = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    usable_weight = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    weight_note = models.CharField(max_length=300, blank=True)
    storage_condition = models.CharField(max_length=120, blank=True)
    removal_date = models.DateField(null=True, blank=True)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT, related_name='children')
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class PurchaseDemand(models.Model):
    buyer = models.ForeignKey(User, on_delete=models.PROTECT, related_name='demands')
    title = models.CharField(max_length=160)
    keyword = models.CharField(max_length=80)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    unit = models.CharField(max_length=12, default='kg')
    budget = models.DecimalField(max_digits=10, decimal_places=2)
    min_size = models.PositiveIntegerField(default=0)
    grade = models.CharField(max_length=30, blank=True)
    packaging = models.CharField(max_length=80, blank=True)
    tolerance = models.FloatField(default=10)
    deadline = models.DateField()
    destination = models.CharField(max_length=200)
    location = models.CharField(max_length=80, blank=True)
    note = models.TextField(blank=True)
    purpose = models.CharField(max_length=30, default='fresh')
    flexible_fields = models.JSONField(default=list, blank=True)
    priority = models.PositiveIntegerField(default=1)
    arrival_window = models.CharField(max_length=80, blank=True)
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, default='open')
    is_demo = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class DemandQuote(models.Model):
    demand = models.ForeignKey(PurchaseDemand, on_delete=models.PROTECT, related_name='quotes')
    batch = models.ForeignKey(StockBatch, on_delete=models.PROTECT)
    supplier = models.ForeignKey(User, on_delete=models.PROTECT)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    note = models.TextField(blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    deviations = models.JSONField(default=list, blank=True)
    terms = models.JSONField(default=dict, blank=True)
    released_quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, default='pending')
    order = models.ForeignKey(Order, null=True, blank=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class AllocationPlan(models.Model):
    owner = models.ForeignKey(User, on_delete=models.PROTECT)
    name = models.CharField(max_length=100)
    mode = models.CharField(max_length=30, default='standard')
    result = models.JSONField(default=dict)
    status = models.CharField(max_length=20, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)


class WorkspaceNotification(models.Model):
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='workspace_notifications')
    title = models.CharField(max_length=200)
    content = models.TextField(blank=True)
    route = models.CharField(max_length=100, default='/orders')
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class CheckoutSubmission(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    key = models.CharField(max_length=80)
    payload_hash = models.CharField(max_length=64)
    orders = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'key'], name='unique_checkout_submission')]


class InventoryMovement(models.Model):
    batch = models.ForeignKey(StockBatch, on_delete=models.PROTECT, related_name='movements')
    order = models.ForeignKey(Order, null=True, blank=True, on_delete=models.PROTECT)
    actor = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    kind = models.CharField(max_length=30)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    reserved_delta = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=12, decimal_places=2)
    reserved_balance = models.DecimalField(max_digits=12, decimal_places=2)
    note = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class InspectionTask(models.Model):
    batch = models.ForeignKey(StockBatch, on_delete=models.PROTECT, related_name='review_tasks')
    demand = models.ForeignKey(PurchaseDemand, null=True, blank=True, on_delete=models.PROTECT)
    creator = models.ForeignKey(User, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, default='open')
    target_sample = models.PositiveIntegerField(default=50)
    metric = models.CharField(max_length=40, default='appearance')
    position = models.CharField(max_length=160, blank=True)
    note = models.TextField(blank=True)
    result = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)


class SupplyIncident(models.Model):
    batch = models.ForeignKey(StockBatch, on_delete=models.PROTECT, related_name='incidents')
    creator = models.ForeignKey(User, on_delete=models.PROTECT)
    kind = models.CharField(max_length=30)
    note = models.TextField()
    details = models.JSONField(default=dict)
    status = models.CharField(max_length=20, default='open')
    created_at = models.DateTimeField(auto_now_add=True)


class RecoveryPlan(models.Model):
    incident = models.ForeignKey(SupplyIncident, on_delete=models.PROTECT, related_name='plans')
    creator = models.ForeignKey(User, on_delete=models.PROTECT)
    strategy = models.CharField(max_length=30, default='stable')
    result = models.JSONField(default=dict)
    status = models.CharField(max_length=30, default='draft')
    decisions = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)


class OrderAllocation(models.Model):
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='allocations')
    batch = models.ForeignKey(StockBatch, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    dispatched = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    terms = models.JSONField(default=dict, blank=True)


class DeliveryRecord(models.Model):
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='deliveries')
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    allocations = models.JSONField(default=list)
    carrier = models.CharField(max_length=100)
    tracking_number = models.CharField(max_length=120)
    status = models.CharField(max_length=20, default='shipped')
    receipt = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    received_at = models.DateTimeField(null=True, blank=True)


class SettlementCase(models.Model):
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='cases')
    creator = models.ForeignKey(User, on_delete=models.PROTECT)
    kind = models.CharField(max_length=30)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    note = models.TextField()
    status = models.CharField(max_length=30, default='proposed')
    reference = models.CharField(max_length=200, blank=True)
    evidence = models.JSONField(default=list)
    events = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Company(models.Model):
    owner = models.ForeignKey(User, on_delete=models.PROTECT, related_name='companies')
    name = models.CharField(max_length=100)
    kind = models.CharField(max_length=30, default='buyer')
    created_at = models.DateTimeField(auto_now_add=True)


class CompanyMember(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='members')
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name='company_memberships')
    job = models.CharField(max_length=30, default='viewer')
    class Meta:
        constraints = [models.UniqueConstraint(fields=['company', 'user'], name='unique_company_member')]


class BusinessSite(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='sites')
    name = models.CharField(max_length=100)
    address = models.CharField(max_length=300)
    location = models.CharField(max_length=80, blank=True)
    contact = models.CharField(max_length=80, blank=True)
    phone = models.CharField(max_length=30, blank=True)


class ScheduledJobRun(models.Model):
    name = models.CharField(max_length=80)
    result = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
