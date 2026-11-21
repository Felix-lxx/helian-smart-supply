import os
import threading
from datetime import timedelta

from django.utils import timezone

try:
    import ee
except ImportError:
    ee = None


_EE_INIT_LOCK = threading.Lock()
_EE_READY = False


def _to_float(value):
    """将输入值安全转换为浮点数，转换失败时返回 None"""
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def initialize_gee():
    """
    初始化 Google Earth Engine 服务
    支持两种认证方式：
    1) 使用环境变量配置的服务账号凭据
    2) 使用本地 `earthengine authenticate` 命令生成的用户凭据
    Returns:
        bool: 初始化成功返回 True，失败返回 False
    """
    global _EE_READY
    if _EE_READY:
        return True
    if ee is None:
        return False

    with _EE_INIT_LOCK:
        if _EE_READY:
            return True

        project = os.getenv("GEE_PROJECT")
        service_account = os.getenv("GEE_SERVICE_ACCOUNT")
        private_key_file = os.getenv("GEE_PRIVATE_KEY_FILE")

        try:
            # 优先使用服务账号认证
            if service_account and private_key_file and os.path.exists(private_key_file):
                credentials = ee.ServiceAccountCredentials(service_account, private_key_file)
                ee.Initialize(credentials, project=project)
            else:
                # 回退到本地用户认证
                if project:
                    ee.Initialize(project=project)
                else:
                    ee.Initialize()
            _EE_READY = True
            return True
        except Exception as exc:
            print(f"GEE initialization failed: {exc}")
            return False


def fetch_ndvi_and_soil_moisture(lng, lat, lookback_days=45):
    """
    从 Google Earth Engine 获取指定点的遥感数据（NDVI 和土壤湿度）

    通过 MODIS 和 SMAP 卫星数据计算指定经纬度点的归一化植被指数和表层土壤湿度，
    并给出简单的农业分析建议。

    Args:
        lng (float): 经度坐标
        lat (float): 纬度坐标
        lookback_days (int): 回溯天数，用于筛选卫星影像，默认 45 天

    Returns:
        dict or None: 成功时返回包含以下字段的字典，失败时返回 None
            - ndvi_index (float): NDVI 值，范围 [-1, 1]，归一化处理后的植被指数
            - soil_moisture (float): 土壤湿度百分比，范围 [0, 100]
            - expert_analysis (str): 基于 NDVI 和土壤湿度的农业分析建议
    """
    if not initialize_gee():
        return None

    lng = _to_float(lng)
    lat = _to_float(lat)
    if lng is None or lat is None:
        return None

    try:
        point = ee.Geometry.Point([lng, lat])
        sample_geom = point.buffer(5_000)  # 创建 5km 缓冲区用于采样
        end_date = timezone.now().date() + timedelta(days=1)
        start_date = end_date - timedelta(days=max(lookback_days, 16))

        start_str = start_date.isoformat()
        end_str = end_date.isoformat()

        # 获取 NDVI 数据（MODIS MOD13Q1 产品）
        ndvi_image = (
            ee.ImageCollection("MODIS/061/MOD13Q1")
            .filterBounds(point)
            .filterDate(start_str, end_str)
            .select("NDVI")
            .median()  # 使用中位数合成影像，减少云污染
        )
        ndvi_dict = (
            ndvi_image.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=sample_geom,
                scale=250,  # MODIS NDVI 原始分辨率 250m
                bestEffort=True,
                maxPixels=1_000_000,
            )
            .getInfo()
        )
        ndvi_raw = ndvi_dict.get("NDVI") if isinstance(ndvi_dict, dict) else None

        # 获取土壤湿度数据（SMAP SPL4SMGP 产品）
        soil_image = (
            ee.ImageCollection("NASA/SMAP/SPL4SMGP/008")
            .filterBounds(point)
            .filterDate(start_str, end_str)
            .select("sm_surface")  # 表层土壤湿度
            .median()
        )
        soil_dict = (
            soil_image.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=sample_geom,
                scale=10_000,  # SMAP 产品分辨率较低，使用 10km
                bestEffort=True,
                maxPixels=1_000_000,
            )
            .getInfo()
        )

        # 兼容不同版本的 SMAP 数据字段名
        if isinstance(soil_dict, dict):
            soil_raw = soil_dict.get("sm_surface")
            if soil_raw is None:
                soil_raw = soil_dict.get("ssm")
            if soil_raw is None:
                soil_raw = soil_dict.get("susm")
        else:
            soil_raw = None

        # NDVI 后处理：缩放转换（原始值范围 0-10000）
        ndvi = _to_float(ndvi_raw)
        if ndvi is not None:
            ndvi = max(-1.0, min(1.0, ndvi * 0.0001))

        # 土壤湿度后处理：转换为百分比（0-100）
        soil = _to_float(soil_raw)
        if soil is not None:
            if soil <= 1.0:  # 如果值为小数形式，转换为百分比
                soil *= 100.0
            soil = max(0.0, min(100.0, soil))

        if ndvi is None or soil is None:
            return None

        # 生成农业分析建议
        analysis_parts = []
        if ndvi is not None:
            if ndvi >= 0.6:
                analysis_parts.append("植被长势良好")
            elif ndvi >= 0.3:
                analysis_parts.append("植被长势中等")
            else:
                analysis_parts.append("植被长势偏弱")
        if soil is not None:
            if soil >= 35:
                analysis_parts.append("土壤湿度较充足")
            elif soil >= 20:
                analysis_parts.append("土壤湿度适中")
            else:
                analysis_parts.append("土壤偏干建议关注灌溉")

        return {
            "ndvi_index": ndvi,
            "soil_moisture": soil,
            "expert_analysis": "；".join(analysis_parts) if analysis_parts else "遥感指标已更新",
        }
    except Exception as exc:
        print(f"GEE query failed: {exc}")
        return None


def parse_lng_lat(location_str):
    """
    解析经纬度字符串
    从 "经度,纬度" 格式的字符串中提取并转换为浮点数。
    Args:
        location_str (str): 格式如 "120.5, 31.2" 的经纬度字符串
    Returns:
        tuple: (lng, lat)，解析失败时返回 (None, None)
    """
    if not location_str or "," not in location_str:
        return None, None
    try:
        lng_text, lat_text = location_str.split(",", 1)
        return float(lng_text.strip()), float(lat_text.strip())
    except (TypeError, ValueError):
        return None, None
