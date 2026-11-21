<template>
  <div class="admin-page">
    <el-card class="page-card">
      <template #header>
        <div class="card-header">
          <span>全站商品监管</span>
          <el-button @click="fetchProducts" icon="Refresh">刷新数据</el-button>
        </div>
      </template>

      <el-table :data="products" v-loading="loading" border stripe>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column label="商品预览" width="100">
          <template #default="{ row }">
            <el-image :src="row.image_url" fit="cover" style="width: 50px; height: 50px; border-radius: 4px" />
          </template>
        </el-table-column>
        <el-table-column prop="name" label="商品名称" min-width="150" />
        <el-table-column prop="owner_name" label="持有者" width="120" />
        <el-table-column prop="retail_price" label="价格" width="90" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'on_sale' ? 'success' : 'info'">{{ statusMap[row.status] }}</el-tag>
          </template>
        </el-table-column>

        <el-table-column label="监管操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'on_sale'"
              type="warning"
              size="small"
              @click="handleOffShelf(row)"
            >强制下架</el-button>
            <el-popconfirm title="确定彻底从数据库删除该商品吗？此操作不可逆！" @confirm="confirmDelete(row)">
              <template #reference>
                <el-button type="danger" size="small">彻底删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="offShelfVisible" title="下架违规商品" width="400px">
      <el-input v-model="offShelfReason" type="textarea" placeholder="请输入下架原因（卖家可见）" />
      <template #footer>
        <el-button @click="offShelfVisible = false">取消</el-button>
        <el-button type="primary" @click="submitOffShelf">确定下架</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'

const products = ref([])
const loading = ref(false)
const statusMap = { on_sale: '上架中', off_shelf: '已下架', draft: '草稿', sold_out: '售罄' }

const offShelfVisible = ref(false)
const offShelfReason = ref('')
const currentProduct = ref(null)

// 获取商品列表
const fetchProducts = async () => {
  loading.value = true
  try {
    const res = await request.get('/admin/products/')
    products.value = res.data
  } catch (e) { ElMessage.error('加载失败') }
  finally { loading.value = false }
}

// 强制下架流程
const handleOffShelf = (row) => {
  currentProduct.value = row
  offShelfReason.value = '违反平台信息发布规范'
  offShelfVisible.value = true
}

const submitOffShelf = async () => {
  try {
    await request.post(`/products/${currentProduct.value.id}/off_shelf/`, {
      reason: offShelfReason.value
    })
    ElMessage.success('已强制下架')
    offShelfVisible.value = false
    fetchProducts()
  } catch (e) { ElMessage.error('操作失败') }
}

// 彻底删除
const confirmDelete = async (row) => {
  try {
    await request.delete(`/admin/products/${row.id}/delete/`)
    ElMessage.success('商品已彻底移除')
    fetchProducts()
  } catch (e) { ElMessage.error('删除失败') }
}

onMounted(fetchProducts)
</script>
