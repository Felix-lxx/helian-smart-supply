<template>
    <div class="admin-page">
      <el-card class="page-card">
        <template #header>
          <div class="card-header">
            <span>订单管理</span>
            <el-button @click="fetchOrders">刷新</el-button>
          </div>
        </template>

        <el-alert
          title="当前为管理员订单管理页面。若后端尚未接入 /api/admin/orders/，页面会正常打开但列表为空。"
          type="info"
          :closable="false"
          class="mb-16"
        />

        <el-table :data="orders" v-loading="loading" border stripe>
          <el-table-column prop="id" label="订单ID" width="100" />
          <el-table-column prop="buyer_name" label="买家" width="140" />
          <el-table-column prop="product_name" label="商品名称" min-width="180" />
          <el-table-column prop="total_amount" label="金额" width="120" />
          <el-table-column prop="status" label="状态" width="120">
            <template #default="{ row }">
              <el-tag :type="statusTagMap[row.status] || 'info'">
                {{ statusMap[row.status] || row.status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="下单时间" min-width="180">
            <template #default="{ row }">
              {{ formatDate(row.created_at) }}
            </template>
          </el-table-column>
        </el-table>

        <div v-if="!loading && orders.length === 0" class="empty-tip">
          暂无订单数据，或后端管理员订单接口尚未接入。
        </div>
      </el-card>
    </div>
  </template>

  <script setup>
  import { ref, onMounted } from 'vue'
  import { ElMessage } from 'element-plus'
  import request from '@/utils/request'

  const orders = ref([])
  const loading = ref(false)

  const statusMap = {
    pending: '待支付',
    paid: '已支付',
    shipped: '已发货',
    completed: '已完成'
  }

  const statusTagMap = {
    pending: 'warning',
    paid: 'primary',
    shipped: 'success',
    completed: 'success'
  }

  // 获取认证头
  const getAuthHeaders = () => {
    const token = localStorage.getItem('access_token')
    return {
      Authorization: `Bearer ${token}`
    }
  }

  // 日期格式化
  const formatDate = (dateStr) => {
    if (!dateStr) return '-'
    const date = new Date(dateStr)
    if (Number.isNaN(date.getTime())) return dateStr
    return date.toLocaleString()
  }

  // 获取订单数据
  const fetchOrders = async () => {
    loading.value = true
    try {
      const res = await request.get('/admin/orders/', {
        headers: getAuthHeaders()
      })
      orders.value = res.data
    } catch (error) {
      orders.value = []
      ElMessage.warning('管理员订单接口暂未接通或无数据')
    } finally {
      loading.value = false
    }
  }

  onMounted(() => {
    fetchOrders()
  })
  </script>

  <style scoped>
  .admin-page {
    padding: 20px;
  }
  .page-card {
    border-radius: 18px;
  }
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .mb-16 {
    margin-bottom: 16px;
  }
  .empty-tip {
    margin-top: 16px;
    text-align: center;
    color: #909399;
  }
  </style>
