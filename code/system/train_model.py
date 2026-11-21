import os
import django
import numpy as np
import lightgbm as lgb

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend_system.settings')
django.setup()

from api.models import Product, Order, RemoteSensing
from api.gee_service import fetch_ndvi_and_soil_moisture, parse_lng_lat


def ensure_remote_sensing(product):
    """
    按优先级获取产品的 NDVI 和土壤湿度数据：
    1. 优先使用数据库已存在的遥感数据
    2. 若数据库无数据，则调用 GEE 服务实时获取
    3. 若 GEE 获取失败，返回安全的默认值
    Args:
        product (Product): 产品对象，需包含 location 字段（经纬度字符串）
    """
    # 检查数据库中是否已存在该产品的遥感数据
    rs = RemoteSensing.objects.filter(product=product).first()
    if rs:
        # 使用数据库中的现有数据，无数据时使用默认值
        ndvi = float(rs.ndvi_index if rs.ndvi_index is not None else 0.5)
        soil = float(rs.soil_moisture if rs.soil_moisture is not None else 30.0)
        return ndvi, soil

    # 解析产品位置字符串获取经纬度
    lng, lat = parse_lng_lat(product.location)
    if lng is not None and lat is not None:
        # 调用 GEE 服务实时获取遥感数据
        payload = fetch_ndvi_and_soil_moisture(lng=lng, lat=lat)
        if payload:
            # 将获取到的数据保存到数据库，便于后续使用
            rs = RemoteSensing.objects.create(
                product=product,
                ndvi_index=float(payload.get('ndvi_index', 0.5)),
                soil_moisture=float(payload.get('soil_moisture', 30.0)),
                expert_analysis=payload.get('expert_analysis', '遥感指标已自动补齐'),
            )
            return float(rs.ndvi_index), float(rs.soil_moisture)

    # 所有方式都失败时返回安全的默认值
    return 0.5, 30.0


def train():
    """"
    训练 LightGBM 需求量预测模型
    基于历史已完成订单的产品价格和遥感数据（NDVI、土壤湿度），
    训练一个回归模型来预测产品需求量。
    模型特征：
        - retail_price: 产品零售价格
        - ndvi_index: 归一化植被指数（反映作物长势）
        - soil_moisture: 土壤湿度百分比（反映土壤墒情）
    模型标签：
        - quantity: 订单购买数量
    训练流程：
        1. 从数据库获取已完成订单数据
        2. 为每个订单产品获取遥感特征（优先 DB，次选 GEE）
        3. 如果历史订单不足 5 条，使用合成数据进行训练
        4. 使用 LightGBM 回归器训练模型
        5. 将训练好的模型保存到文件
    """
    # 1) 准备特征和标签数据
    features = []
    labels = []

    # 获取所有已完成订单，并预加载关联的产品信息（减少数据库查询）
    orders = Order.objects.filter(status='completed',is_demo=False,quantity__isnull=False,quantity__gt=0,product__isnull=False).select_related('product')

    # 使用历史订单数据构建训练集
    if orders.count() >= 5:
        for order in orders:
            p = order.product
            # 获取该产品的遥感特征（NDVI 和土壤湿度）
            ndvi, soil = ensure_remote_sensing(p)
            # 特征：价格 + NDVI + 土壤湿度
            features.append([float(order.unit_price_at_purchase), ndvi, soil])

            # 提取标签（订单数量），处理多种数据来源
            if hasattr(order, 'quantity') and order.quantity is not None:
                # 优先使用 quantity 字段
                label_qty = float(order.quantity)
            else:
                # 若没有 quantity，通过总金额和单价推算
                try:
                    total_amount = float(getattr(order, 'total_amount', 0) or 0)
                    unit_price = float(getattr(order, 'unit_price_at_purchase', 0) or 0)
                    label_qty = round(total_amount / unit_price) if unit_price > 0 else 1
                except (TypeError, ValueError, ZeroDivisionError):
                    label_qty = 1
            # 确保标签至少为 1（最小购买数量）
            labels.append(max(1, label_qty))

    # Training eligibility only; accuracy must still be evaluated on future data.
    if len(features) < 30:
        raise RuntimeError('真实、非演示且数量已知的完成订单不足30笔，不训练或覆盖模型；继续使用规则推荐。')
    features = np.array(features)
    labels = np.array(labels)

    # 3) 训练 LightGBM 回归模型
    model = lgb.LGBMRegressor(
        n_estimators=50,      # 树的数量，控制模型复杂度
        learning_rate=0.05,   # 学习率，控制每棵树对最终结果的贡献
        verbose=-1,           # 静默模式，不输出训练过程日志
        force_col_wise=True   # 按列方式训练，优化内存使用和速度
    )
    model.fit(features, labels)


    # 4) 保存训练好的模型到文件
    model_path = os.path.join(os.path.dirname(__file__), 'recommend_model.txt')
    model.booster_.save_model(model_path)
    print(f'Model saved to {model_path}')


if __name__ == '__main__':
    train()
