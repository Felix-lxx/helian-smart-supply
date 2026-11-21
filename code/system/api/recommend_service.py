import os
from django.conf import settings
from api.models import Product, Order, RemoteSensing, User


def _top_on_sale_products(limit=6):
    """当算法轨道不可用时，至少返回在售商品，避免前端空白。"""
    return list(Product.objects.filter(status='on_sale', is_deleted=False).order_by('-id')[:limit])


def _build_seller_candidates(user, seller_product_id):
    """
    构建卖家端推荐候选集，采用渐进式降级策略，避免界面空白。
    降级策略（按优先级从高到低）：
    1. 严格匹配：相同品类 + 相同产地
    2. 中等匹配：相同品类
    3. 宽松匹配：所有在售商品（排除卖家自己的商品）
    4. 最终降级：包含卖家自己的在售商品
    Args:
        user: 当前用户对象
        seller_product_id: 卖家商品ID（用于寻找相似商品）
    """
    all_on_sale = Product.objects.filter(status='on_sale', is_deleted=False)
    if not user:
        return all_on_sale

    if not seller_product_id:
        cands = all_on_sale.exclude(owner=user)
        return cands if cands.exists() else all_on_sale

    try:
        target_product = Product.objects.get(id=seller_product_id, owner=user)
    except Product.DoesNotExist:
        cands = all_on_sale.exclude(owner=user)
        return cands if cands.exists() else all_on_sale

    # 1) 相同品类 + 相同产地
    cands = all_on_sale.filter(
        category=target_product.category,
        origin=target_product.origin,
    ).exclude(owner=user)
    if cands.exists():
        return cands

    # 2) 相同品类
    cands = all_on_sale.filter(category=target_product.category).exclude(owner=user)
    if cands.exists():
        return cands

    # 3) 所有在售商品（排除自己）
    cands = all_on_sale.exclude(owner=user)
    if cands.exists():
        return cands

    # 4) 包含自己的在售商品
    return all_on_sale


def get_predictions(user_id=None, request_type='buyer', seller_product_id=None):
    """Deterministic business fallback; no random or synthetic personalization."""
    from django.db.models import F
    candidates=Product.objects.filter(status='on_sale',is_deleted=False,batches__status='released',
        batches__quantity__gt=F('batches__reserved')).distinct()
    if request_type=='seller' and seller_product_id:
        anchor=Product.objects.filter(pk=seller_product_id,owner_id=user_id).first()
        if anchor:
            same=candidates.filter(category=anchor.category).exclude(owner_id=user_id)
            if same.exists():candidates=same
    elif user_id:
        categories=Order.objects.filter(user_id=user_id,status='completed',is_demo=False).values_list('product__category',flat=True)
        preferred=candidates.filter(category__in=categories)
        if preferred.exists():candidates=preferred
    return list(candidates.order_by('-created_at','id')[:6])
