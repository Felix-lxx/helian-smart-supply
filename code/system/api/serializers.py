from rest_framework import serializers
from .models import User, Product, RemoteSensing, PriceTier, Order, ShippingAddress, ProductActionLog, RealNameAuth, QualityInspectionLog, ProductComment

# 1. 用户信息序列化器
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'role', 'phone')

# 2. 注册序列化器
class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'password', 'role', 'phone')
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        # 显式获取 role 字段
        role = validated_data.get('role', 'retail')
        phone_number = validated_data.get('phone', None)
        if phone_number == '':
            phone_number = None

        user = User.objects.create_user(
            username=validated_data['username'],
            password=validated_data['password'],
            role=role,  # 确保传入正确的角色
            phone=phone_number
        )
        return user

# 3. 商品基础信息序列化器
class ProductSerializer(serializers.ModelSerializer):
    # 在后端就将字符串坐标转为数组，降低前端解析出错率
    coords = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = '__all__'

    def get_coords(self, obj):
        if obj.location and ',' in obj.location:
            try:
                # 自动处理空格和非法字符，确保输出 [经度, 纬度] 数字数组
                return [float(x.strip()) for x in obj.location.split(',')]
            except ValueError:
                return None
        return None

# 4. 遥感数据序列化器
class RemoteSensingSerializer(serializers.ModelSerializer):
    ndvi_index = serializers.SerializerMethodField()
    soil_moisture = serializers.SerializerMethodField()

    class Meta:
        model = RemoteSensing
        fields = ('id', 'product', 'ndvi_index', 'soil_moisture', 'expert_analysis', 'updated_at')

    def get_ndvi_index(self, obj):
        if obj.ndvi_index is None:
            return None
        return round(float(obj.ndvi_index), 2)

    def get_soil_moisture(self, obj):
        if obj.soil_moisture is None:
            return None
        return round(float(obj.soil_moisture), 2)

# 5. 阶梯价格序列化器
class PriceTierSerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceTier
        fields = '__all__'

# 6. 商品详情序列化器 (包含嵌套数据)
class ProductDetailSerializer(serializers.ModelSerializer):
    remote_sensing = RemoteSensingSerializer(read_only=True)
    price_tiers = PriceTierSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = '__all__'

# 收货地址序列化器 (修复 ImportError 的关键)
class ShippingAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingAddress
        fields = '__all__'
        read_only_fields = ('user',)

# 8. 增强后的订单序列化器
class OrderSerializer(serializers.ModelSerializer):
    # 提取显示用的只读字段
    buyer_name = serializers.CharField(source='user.username', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = Order
        fields = (
            'id', 'user', 'product', 'total_amount', 'status',
            'receiver_name', 'receiver_phone', 'address_info',
            'created_at', 'buyer_name', 'product_name'
        )
        read_only_fields = ('user', 'status')

# 9. 卖家编辑商品
class ProductManageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = (
            'id',
            'name',
            'category',
            'origin',
            'retail_price',
            'image_url',
            'status',
            'stock',
            'off_shelf_reason',
        )
        read_only_fields = ('id', 'status', 'stock')

# 10. 商品操作日志
class ProductActionLogSerializer(serializers.ModelSerializer):
    operator_name = serializers.CharField(source='operator.username', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = ProductActionLog
        fields = (
            'id',
            'product',
            'product_name',
            'operator',
            'operator_name',
            'action_type',
            'remark',
            'before_snapshot',
            'after_snapshot',
            'created_at',
        )

class RealNameAuthSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    reviewer_name = serializers.CharField(source='reviewed_by.username', read_only=True)

    class Meta:
        model = RealNameAuth
        fields = (
            'id',
            'user',
            'username',
            'real_name',
            'id_card_masked',
            'face_image_url',
            'status',
            'reject_reason',
            'reviewed_by',
            'reviewer_name',
            'submitted_at',
            'reviewed_at',
        )
        read_only_fields = (
            'id',
            'user',
            'username',
            'id_card_masked',
            'status',
            'reject_reason',
            'reviewed_by',
            'reviewer_name',
            'submitted_at',
            'reviewed_at',
        )

class RealNameSubmitSerializer(serializers.Serializer):
    real_name = serializers.CharField(max_length=50)
    id_card_no = serializers.CharField(max_length=18)
    face_image_url = serializers.URLField(required=False, allow_blank=True)

    def validate_id_card_no(self, value):
        if len(value) not in [15, 18]:
            raise serializers.ValidationError("身份证号格式不正确")
        return value

# api/serializers.py 新增
class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'role', 'phone', 'avatar', 'motto', 'qq_bound', 'email_bound', 'date_joined', 'is_active')
        read_only_fields = ('id', 'username', 'role', 'date_joined', 'is_active', 'qq_bound', 'email_bound')

class QualityLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = QualityInspectionLog
        fields = '__all__'

class ProductCommentSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    user_role = serializers.CharField(source='user.role', read_only=True)
    likes_count = serializers.SerializerMethodField()
    dislikes_count = serializers.SerializerMethodField()
    current_user_vote = serializers.SerializerMethodField()

    # 新增：利用 SerializerMethodField 动态获取当前评论的所有子回复
    replies = serializers.SerializerMethodField()

    class Meta:
        model = ProductComment
        fields = [
            'id', 'user', 'username', 'user_role', 'rating', 'content',
            'is_seller_reply', 'likes_count', 'dislikes_count', 'current_user_vote',
            'parent', 'replies', 'created_at' # 加入 parent 和 replies
        ]
        read_only_fields = ['user', 'is_seller_reply']

    def get_replies(self, obj):
        """递归抓取楼中楼回复，按时间正序排列（早的在上）"""
        if obj.replies.exists():
            # 必须传入 context，这样子评论也能正确判断当前用户的点赞状态
            serializer = ProductCommentSerializer(
                obj.replies.all().order_by('created_at'),
                many=True,
                context=self.context
            )
            return serializer.data
        return []

    def get_likes_count(self, obj):
        """计算该评论的总点赞数"""
        return obj.likes.count()

    def get_dislikes_count(self, obj):
        """计算该评论的总点踩数"""
        return obj.dislikes.count()

    def get_current_user_vote(self, obj):
        """
        判断当前正在看这条评论的用户，之前有没有点过赞或踩。
        这决定了前端页面上那个👍和👎按钮是不是高亮状态。
        """
        request = self.context.get('request')
        # 只有在用户登录的情况下才去查
        if request and request.user.is_authenticated:
            # 如果当前用户在点赞列表里
            if obj.likes.filter(id=request.user.id).exists():
                return 'like'
            # 如果当前用户在点踩列表里
            if obj.dislikes.filter(id=request.user.id).exists():
                return 'dislike'
        return None
