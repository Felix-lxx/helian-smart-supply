<template>
  <div class="my-products-page">
    <el-card class="page-card">
      <template #header>
        <div class="header-row">
          <span class="title">我的商品</span>
          <div class="header-actions">
            <el-button type="primary" @click="goPublish">发布新商品</el-button>
            <el-button @click="fetchMyProducts">刷新</el-button>
          </div>
        </div>
      </template>

      <el-table :data="products" v-loading="loading" border stripe>
        <el-table-column prop="name" label="商品名称" min-width="180" />

        <el-table-column prop="category" label="分类" width="120">
          <template #default="{ row }">
            {{ categoryMap[row.category] || row.category }}
          </template>
        </el-table-column>

        <el-table-column prop="retail_price" label="价格(元)" width="120" />
        <el-table-column prop="stock" label="库存" width="100" />

        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusTagMap[row.status] || 'info'">
              {{ statusTextMap[row.status] || row.status }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="created_at" label="创建时间" min-width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>

        <el-table-column label="操作" min-width="380" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status !== 'on_sale'"
              type="success"
              size="small"
              @click="handleOnSale(row)"
            >
              上架
            </el-button>

            <el-button
              v-if="row.status === 'on_sale'"
              type="warning"
              size="small"
              @click="openOffShelfDialog(row)"
            >
              下架
            </el-button>

            <el-button
              type="primary"
              size="small"
              plain
              @click="viewLogs(row)"
            >
              查看记录
            </el-button>

            <el-popconfirm
              v-if="row.status === 'off_shelf'"
              title="确认删除该商品吗？删除后不可恢复。"
              @confirm="handleDelete(row)"
            >
              <template #reference>
                <el-button type="danger" size="small" plain>删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="!loading && products.length === 0" class="empty-tip">
        暂无商品，先去发布一个吧。
      </div>
    </el-card>

    <el-dialog v-model="offShelfDialogVisible" title="商品下架" width="500px">
      <el-form label-width="90px" @submit.prevent>
        <el-form-item label="商品名称">
          <span>{{ currentProduct?.name }}</span>
        </el-form-item>
        <el-form-item label="下架原因" required>
          <el-input
            v-model="offShelfReason"
            type="textarea"
            :rows="4"
            placeholder="请输入下架原因（必填）"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="offShelfDialogVisible = false">取消</el-button>
        <el-button type="warning" :loading="offShelfLoading" @click="confirmOffShelf">
          确认下架
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="logDialogVisible" title="商品操作记录" width="900px">
      <el-table :data="productLogs" border stripe v-loading="logLoading">
        <el-table-column prop="action_type" label="操作类型" width="120">
          <template #default="{ row }">
            {{ actionTextMap[row.action_type] || row.action_type }}
          </template>
        </el-table-column>

        <el-table-column prop="operator_name" label="操作人" width="120" />
        <el-table-column prop="remark" label="备注" min-width="180" />

        <el-table-column prop="created_at" label="时间" min-width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
      </el-table>

      <div v-if="!logLoading && productLogs.length === 0" class="empty-tip">
        暂无操作记录
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'

const router = useRouter()

const loading = ref(false)
const logLoading = ref(false)
const offShelfLoading = ref(false)

const products = ref([])
const productLogs = ref([])

const offShelfDialogVisible = ref(false)
const logDialogVisible = ref(false)
const currentProduct = ref(null)
const offShelfReason = ref('')

const categoryMap = {
  fruits_vegs: '生鲜果蔬',
  grains: '粮油米面',
  meat: '肉禽蛋奶',
  dry: '干货菌菇'
}

const statusTextMap = {
  draft: '草稿',
  on_sale: '上架中',
  off_shelf: '已下架',
  sold_out: '已售罄'
}

const statusTagMap = {
  draft: 'info',
  on_sale: 'success',
  off_shelf: 'warning',
  sold_out: 'danger'
}

const actionTextMap = {
  create: '创建商品',
  edit: '编辑商品',
  on_sale: '商品上架',
  off_shelf: '商品下架',
  delete: '删除商品',
  restore: '恢复商品'
}

const getAuthHeaders = () => {
  const token = localStorage.getItem('access_token')
  return { Authorization: `Bearer ${token}` }
}

const checkRole = () => {
  const role = localStorage.getItem('user_role')
  if (role !== 'supplier') {
    ElMessage.error('只有供应商可以访问我的商品')
    router.replace('/products')
  }
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  if (Number.isNaN(date.getTime())) return dateStr
  return date.toLocaleString()
}

const fetchMyProducts = async () => {
  // 我的商品页主数据入口，统一刷新列表状态。
  loading.value = true
  try {
    const res = await request.get('/products/mine/', { headers: getAuthHeaders() })
    products.value = res.data
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || error?.response?.data?.error || '获取我的商品失败')
  } finally {
    loading.value = false
  }
}

const handleOnSale = async (row) => {
  // 上架动作完成后立即回拉列表，确保按钮状态与后端一致。
  try {
    await request.post(`/products/${row.id}/on_sale/`, {}, { headers: getAuthHeaders() })
    ElMessage.success('商品已上架')
    fetchMyProducts()
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || error?.response?.data?.error || '商品上架失败')
  }
}

const openOffShelfDialog = (row) => {
  currentProduct.value = row
  offShelfReason.value = ''
  offShelfDialogVisible.value = true
}

const confirmOffShelf = async () => {
  // 下架必须携带原因，和后端风控规则保持一致。
  if (!currentProduct.value) return
  if (!offShelfReason.value || offShelfReason.value.trim() === '') {
    return ElMessage.warning('请填写下架原因')
  }

  offShelfLoading.value = true
  try {
    await request.post(`/products/${currentProduct.value.id}/off_shelf/`, { reason: offShelfReason.value.trim() })
    ElMessage.success('商品已下架')
    offShelfDialogVisible.value = false
    fetchMyProducts()
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || error?.response?.data?.error || '下架操作失败')
  } finally {
    offShelfLoading.value = false
  }
}

const viewLogs = async (row) => {
  // 异步加载单个商品的操作日志，避免初次加载压力过大。
  currentProduct.value = row
  logDialogVisible.value = true
  logLoading.value = true
  productLogs.value = []

  try {
    const res = await request.get(`/products/${row.id}/logs/`, { headers: getAuthHeaders() })
    productLogs.value = res.data
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || error?.response?.data?.error || '获取商品记录失败')
  } finally {
    logLoading.value = false
  }
}

const handleDelete = async (row) => {
  // 删除仅对已下架商品开放（后端会二次校验）。
  try {
    await request.delete(`/products/${row.id}/delete/`, { headers: getAuthHeaders() })
    ElMessage.success('商品已删除')
    fetchMyProducts()
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || error?.response?.data?.error || '删除失败：仅下架商品允许删除')
  }
}

const goPublish = () => {
  router.push('/publish')
}

onMounted(() => {
  checkRole()
  fetchMyProducts()
})
</script>

<style scoped>
.my-products-page {
  padding: 20px;
}

.page-card {
  border-radius: 18px;
}

.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.title {
  font-size: 20px;
}

.empty-tip {
  margin-top: 16px;
  color: #909399;
}
</style>
