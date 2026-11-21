<template>
  <div class="mall-container">
    <div class="action-header" v-if="userRole === 'supplier'">
      <el-button type="success" size="large" :icon="Plus" @click="router.push('/publish')">
        发布我的农产品
      </el-button>
    </div>

    <el-carousel height="340px" class="main-carousel" trigger="click" indicator-position="outside">
      <el-carousel-item v-for="(banner, index) in banners" :key="index">
        <div class="carousel-box" :style="{ backgroundImage: `url(${banner.image})` }">
          <div class="carousel-mask"></div>
          <div class="carousel-content">
            <h2>{{ banner.title }}</h2>
            <p>{{ banner.subtitle }}</p>
            <el-button type="primary" round @click="scrollToProducts">立即选购</el-button>
          </div>
        </div>
      </el-carousel-item>
    </el-carousel>

    <div class="category-filter-bar">
      <el-tabs v-model="activeCategory" @tab-click="handleCategoryClick">
        <el-tab-pane label="全部分类" name="all" />
        <el-tab-pane label="生鲜果蔬" name="fruits_vegs" />
        <el-tab-pane label="粮油米面" name="grains" />
        <el-tab-pane label="肉蛋奶" name="meat" />
        <el-tab-pane label="干货菌菇" name="dry" />
      </el-tabs>
    </div>

    <div class="toolbar" id="product-list-start">
      <div class="left-tools">
        <span class="sort-label">价格排序：</span>
        <el-radio-group v-model="priceSort" size="small">
          <el-radio-button label="default">默认</el-radio-button>
          <el-radio-button label="asc">从低到高</el-radio-button>
          <el-radio-button label="desc">从高到低</el-radio-button>
        </el-radio-group>
      </div>

      <div class="search-box">
        <el-input
          v-model="searchQuery"
          placeholder="搜索农产品名称..."
          :prefix-icon="Search"
          clearable
        />
      </div>

      <div class="product-count">
        共找到 <span class="num">{{ filteredProductList.length }}</span> 件农产品
      </div>
    </div>

    <div class="product-section">
      <el-row :gutter="20">
        <el-col :span="4" v-for="item in pagedProductList" :key="item.id" style="width: 20%">
          <el-card class="product-card" shadow="hover" @click="goToDetail(item.id)">
            <div class="image-wrapper">
              <img :src="item.image_url || defaultImg" class="product-image" />
              <el-tag class="origin-tag" effect="dark" type="success">{{ item.origin || '产地待补充' }}</el-tag>
            </div>

            <div class="product-info">
              <h3 class="product-title">{{ item.name }}</h3>

              <div class="quantity-select-row">
                <span class="quantity-label">采购数量：</span>
                <el-input-number
                  v-model="item.buyQuantity"
                  :min="1"
                  :max="item.stock || 9999"
                  size="small"
                  @click.stop
                />
              </div>

              <div class="price-action-row">
                <div class="price">
                  ¥<span class="num">{{ item.retail_price }}</span>/斤
                </div>
                <el-button type="primary" size="small" circle @click.stop="handleDirectOrder(item)">
                  <el-icon><ShoppingCart /></el-icon>
                </el-button>
              </div>

              <el-button type="success" plain class="w-100" @click.stop="goToDetail(item.id)">查看溯源档案</el-button>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-empty v-if="filteredProductList.length === 0" description="未搜索到匹配的农产品" />

      <div class="pagination-wrapper" v-if="filteredProductList.length > 0">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="filteredProductList.length"
          layout="total, prev, pager, next, jumper"
          background
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Plus, Search, ShoppingCart } from '@element-plus/icons-vue'
import request from '@/utils/request'

const router = useRouter()
const userRole = ref(localStorage.getItem('user_role') || 'retail')

const productList = ref([])
const activeCategory = ref('all')
const priceSort = ref('default')
const searchQuery = ref('')
const currentPage = ref(1)
const pageSize = ref(15)

const banners = [
  {
    image: 'https://images.unsplash.com/photo-1501004318641-b39e6451bec6?q=80&w=1600',
    title: '智慧农业直采平台',
    subtitle: '源头严选，品质看得见'
  },
  {
    image: 'https://images.unsplash.com/photo-1471193945509-9ad0617afabf?q=80&w=1600',
    title: '新鲜果蔬当季直达',
    subtitle: '支持酒店、食堂、商超批量采购'
  },
  {
    image: new URL('../assets/轮播图3.jpg', import.meta.url).href,
    title: '全链路溯源',
    subtitle: '采购过程透明可追踪'
  }
]

const defaultImg = 'https://images.unsplash.com/photo-1610348725531-843dff563e2c?q=80&w=800'

const fetchProducts = async () => {
  try {
    const res = await request.get('/products/')
    const rawData = res?.data?.results || res?.data || []
    productList.value = rawData.map((product) => ({
      ...product,
      buyQuantity: Number(product.buyQuantity) > 0 ? Number(product.buyQuantity) : 1
    }))
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '获取商品失败，请检查后端服务')
  }
}

const goToDetail = (id) => {
  router.push(`/product/${id}`)
}

const handleCategoryClick = () => {
  currentPage.value = 1
}

const scrollToProducts = () => {
  document.getElementById('product-list-start')?.scrollIntoView({ behavior: 'smooth' })
}

const handleDirectOrder = async (product) => {
  const token = localStorage.getItem('access_token')
  if (!token) {
    ElMessage.warning('请先登录再进行采购')
    router.push('/login')
    return
  }

  try {
    const quantity = Number(product.buyQuantity || 1)
    await request.post('/orders/create/', {
      product: product.id,
      quantity,
      total_amount: Number(product.retail_price || 0) * quantity,
      status: 'pending'
    })
    ElMessage.success(`已成功预订 ${quantity} 斤 ${product.name}`)
  } catch (error) {
    ElMessage.error(error.response?.data?.error || '创建订单失败，请检查库存')
  }
}

const filteredProductList = computed(() => {
  let list = [...productList.value]

  if (searchQuery.value.trim()) {
    const keyword = searchQuery.value.trim().toLowerCase()
    list = list.filter((p) => String(p.name || '').toLowerCase().includes(keyword))
  }

  if (activeCategory.value !== 'all') {
    list = list.filter((p) => p.category === activeCategory.value)
  }

  if (priceSort.value === 'asc') {
    list.sort((a, b) => Number(a.retail_price || 0) - Number(b.retail_price || 0))
  }
  if (priceSort.value === 'desc') {
    list.sort((a, b) => Number(b.retail_price || 0) - Number(a.retail_price || 0))
  }

  return list
})

const pagedProductList = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  const end = currentPage.value * pageSize.value
  return filteredProductList.value.slice(start, end)
})

onMounted(fetchProducts)
</script>

<style scoped>
.mall-container {
  min-height: 100vh;
}

.action-header {
  position: fixed;
  top: 80px;
  right: 40px;
  z-index: 100;
}

.main-carousel {
  margin-bottom: 14px;
}

.carousel-box {
  height: 100%;
  background-size: cover;
  background-position: center;
  position: relative;
  display: flex;
  justify-content: center;
  align-items: center;
  color: #fff;
}

.carousel-mask {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
}

.carousel-content {
  position: relative;
  z-index: 1;
  text-align: center;
}

.category-filter-bar {
  background: #fff;
  border-bottom: 1px solid #eee;
  padding: 0 40px;
}

.toolbar {
  padding: 14px 40px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #f8fafc;
  border-bottom: 1px solid #e5e7eb;
}

.left-tools {
  display: flex;
  align-items: center;
  gap: 12px;
}

.search-box {
  width: 300px;
}

.product-count .num {
  color: #ef4444;
  font-weight: 700;
}

.product-section {
  padding: 24px 40px;
}

.product-card {
  border-radius: 12px;
  margin-bottom: 20px;
  cursor: pointer;
}

.image-wrapper {
  position: relative;
  height: 180px;
  overflow: hidden;
}

.product-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.origin-tag {
  position: absolute;
  left: 8px;
  bottom: 8px;
}

.quantity-select-row {
  margin-top: 10px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.quantity-label {
  font-size: 12px;
  color: #6b7280;
}

.price-action-row {
  margin: 12px 0 10px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.price {
  color: #ef4444;
  font-weight: 700;
}

.price .num {
  font-size: 20px;
}

.w-100 {
  width: 100%;
}

.pagination-wrapper {
  margin-top: 24px;
  display: flex;
  justify-content: center;
  padding-bottom: 40px;
}
</style>
