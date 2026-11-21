<template>
  <div class="orders-container">
    <el-row :gutter="20" class="stat-cards">
      <el-col :span="8">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-title">{{ statTitle }}</div>
          <div class="stat-value">{{ sourceOrders.length }} <span class="unit">笔</span></div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-title">累计交易金额(元)</div>
          <div class="stat-value text-danger">¥{{ totalPaidAmount }}</div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-title">节省中间成本(15%)</div>
          <div class="stat-value text-success">¥{{ savedCost }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="table-card mt-20">
      <el-tabs v-model="activeTab" type="border-card">
        <el-tab-pane label="我的采购单" name="buyer" v-if="userRole !== 'supplier'">
          <div class="mb-20">
            <el-button type="primary" :icon="Location" @click="openAddressManager" size="small">管理收货地址</el-button>
          </div>
          <el-table :data="orderList" v-loading="loading" stripe style="width: 100%">
            <el-table-column prop="id" label="订单号" width="90" />
            <el-table-column label="购买商品" min-width="180">
              <template #default="{ row }">
                <span style="font-weight: bold; color: #303133;">{{ getProductName(row) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="订单金额" width="120">
              <template #default="{ row }"><span class="price-text">¥{{ row.total_amount }}</span></template>
            </el-table-column>
            <el-table-column label="订单状态" width="120">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)" effect="dark" round>
                  {{ getStatusText(row.status) }}
                </el-tag>
              </template>
            </el-table-column>

            <el-table-column label="操作" width="220" fixed="right">
              <template #default="{ row }">
                <el-button size="small" type="info" plain @click="openDetails(row)">详情</el-button>
                <el-button v-if="row.status === 'pending'" size="small" type="danger" @click="openPayDialog(row)">支付</el-button>

                <el-popconfirm
                  v-if="row.status === 'pending'"
                  title="确认彻底删除该待支付订单吗？"
                  @confirm="handleDelete(row.id)"
                >
                  <template #reference>
                    <el-button size="small" type="danger" plain>删除</el-button>
                  </template>
                </el-popconfirm>

                <el-button
                  v-else
                  size="small"
                  type="danger"
                  plain
                  @click="showPaidDeleteWarning"
                >
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="收到新订单" name="seller" v-if="userRole === 'supplier'">
          <el-table :data="soldList" stripe style="width: 100%" v-loading="loading">
            <el-table-column prop="id" label="单号" width="80" />
            <el-table-column prop="product_name" label="货品名称" />
            <el-table-column label="订单金额" width="120">
              <template #default="{ row }"><span class="price-text">¥{{ row.total_amount }}</span></template>
            </el-table-column>
            <el-table-column label="买家收货信息" width="280">
              <template #default="{ row }">
                <div v-if="row.receiver_name">
                  <b>{{ row.receiver_name }}</b> ({{ row.receiver_phone }})<br />
                  <span class="text-mini">{{ row.address_info }}</span>
                </div>
                <el-tag v-else type="info" size="small">等待客户支付</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="120">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)">{{ getStatusText(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="180">
              <template #default="{ row }">
                <el-button size="small" type="info" plain @click="openDetails(row)">详情</el-button>
                <el-button
                  v-if="row.status === 'paid'"
                  type="success"
                  size="small"
                  @click="handleShip(row.id)"
                >确认发货</el-button>
                <el-tag v-else-if="row.status === 'shipped'" type="info">已发货</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="我的收货地址" name="address" v-if="userRole !== 'supplier'">
          <el-button type="primary" :icon="Plus" @click="addrFormVisible = true" size="small">新增地址</el-button>
          <el-row :gutter="20" class="mt-20">
            <el-col :span="8" v-for="addr in addressList" :key="addr.id">
              <el-card shadow="hover" class="addr-card">
                <b>{{ addr.receiver_name }}</b> {{ addr.receiver_phone }}
                <p class="text-mini">{{ addr.detail_address }}</p>
              </el-card>
            </el-col>
          </el-row>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-dialog v-model="payVisible" title="安全支付收银台" width="500px" center destroy-on-close>
      <div class="pay-checkout-container">
        <div class="pay-order-header">
          <div class="amount-box">
            <span class="symbol">¥</span>
            <span class="num">{{ currentOrder?.total_amount }}</span>
          </div>
          <p class="order-id">订单编号：{{ currentOrder?.id }}</p>
        </div>

        <el-divider content-position="left">收货信息确认</el-divider>
        <el-select v-model="selectedAddrId" placeholder="请选择收货地址" style="width: 100%; margin-bottom: 20px;">
          <el-option
            v-for="a in addressList"
            :key="a.id"
            :label="`${a.receiver_name} (${a.receiver_phone})`"
            :value="a.id"
          />
        </el-select>

        <el-divider content-position="left">选择支付方式</el-divider>
        <el-tabs v-model="payMethod" type="card" class="pay-methods-tabs">
          <el-tab-pane name="alipay" label="支付宝" />
          <el-tab-pane name="wechat" label="微信支付" />
          <el-tab-pane name="card" label="银行卡" />
        </el-tabs>
      </div>

      <template #footer>
        <div class="pay-footer">
          <el-button type="info" @click="payVisible = false">取消</el-button>
          <el-button
            type="primary"
            :loading="payLoading"
            @click="handleRealPay"
            :disabled="!selectedAddrId"
          >
            我已完成支付
          </el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog v-model="addrFormVisible" title="新增收货地址" width="400px">
      <el-form :model="addrForm" label-width="80px">
        <el-form-item label="姓名"><el-input v-model="addrForm.receiver_name" /></el-form-item>
        <el-form-item label="电话"><el-input v-model="addrForm.receiver_phone" /></el-form-item>
        <el-form-item label="详细地址"><el-input type="textarea" v-model="addrForm.detail_address" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button type="primary" @click="saveAddress" style="width: 100%">保存地址</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="detailsVisible" title="采购明细单" width="600px">
      <div v-loading="detailLoading">
        <div v-if="productDetail" class="detail-rich-box">
          <img :src="productDetail.image_url" class="detail-img" />
          <div class="detail-info">
            <h3>{{ productDetail.name }}</h3>
            <p>源头产地：{{ productDetail.origin }}</p>
            <p class="price-text">直供单价：¥{{ productDetail.retail_price }} / 斤</p>
            <p>订单总计：¥{{ currentOrder?.total_amount }}</p>
            <el-divider v-if="userRole === 'supplier'"></el-divider>
            <div v-if="userRole === 'supplier' && currentOrder?.receiver_name">
              <p style="font-size: 13px; color: #666;"><b>收货信息：</b></p>
              <p style="font-size: 13px;">收货人：{{ currentOrder.receiver_name }}</p>
              <p style="font-size: 13px;">联系电话：{{ currentOrder.receiver_phone }}</p>
              <p style="font-size: 13px;">地址：{{ currentOrder.address_info }}</p>
            </div>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Location, Plus } from '@element-plus/icons-vue'
import request from '@/utils/request'

const userRole = ref(localStorage.getItem('user_role'))
const activeTab = ref(userRole.value === 'supplier' ? 'seller' : 'buyer')

const orderList = ref([])
const soldList = ref([])
const addressList = ref([])
const loading = ref(false)
const detailLoading = ref(false)

const detailsVisible = ref(false)
const payVisible = ref(false)
const addrFormVisible = ref(false)

const currentOrder = ref(null)
const productDetail = ref(null)
const selectedAddrId = ref(null)
const addrForm = ref({ receiver_name: '', receiver_phone: '', detail_address: '' })

const payMethod = ref('alipay')
const payLoading = ref(false)

const sourceOrders = computed(() => (userRole.value === 'supplier' ? soldList.value : orderList.value))
const statTitle = computed(() => (userRole.value === 'supplier' ? '我收到的订单' : '我的有效订单'))

const validOrders = computed(() => {
  return sourceOrders.value.filter((o) => ['paid', 'shipped', 'completed'].includes(o.status))
})

const totalPaidAmount = computed(() => {
  return validOrders.value
    .reduce((sum, o) => sum + Number.parseFloat(o.total_amount || 0), 0)
    .toFixed(2)
})

const savedCost = computed(() => {
  return (Number.parseFloat(totalPaidAmount.value || 0) * 0.15).toFixed(2)
})

const fetchOrders = async () => {
  loading.value = true
  try {
    const res = await request.get('/orders/')
    orderList.value = res.data.results || res.data || []
  } catch {
    ElMessage.error('获取订单失败')
  } finally {
    loading.value = false
  }
}

const fetchSoldOrders = async () => {
  loading.value = true
  try {
    const res = await request.get('/orders/supplier/')
    soldList.value = res.data.results || res.data || []
  } catch {
    ElMessage.error('获取供应商订单失败')
  } finally {
    loading.value = false
  }
}

const fetchAddresses = async () => {
  try {
    const res = await request.get('/addresses/')
    addressList.value = res.data.results || res.data || []
  } catch {
    ElMessage.error('获取地址失败')
  }
}

const openAddressManager = () => {
  activeTab.value = 'address'
}

const openPayDialog = (row) => {
  currentOrder.value = row
  payVisible.value = true
  fetchAddresses()
}

const handleRealPay = async () => {
  if (!selectedAddrId.value) {
    ElMessage.warning('请选择收货地址')
    return
  }

  const addr = addressList.value.find((a) => a.id === selectedAddrId.value)
  if (!addr) {
    ElMessage.warning('收货地址无效')
    return
  }

  payLoading.value = true
  try {
    await request.post(`/orders/${currentOrder.value.id}/pay/`, {
      receiver_name: addr.receiver_name,
      receiver_phone: addr.receiver_phone,
      address_info: addr.detail_address,
      pay_method: payMethod.value
    })

    ElMessage.success('支付成功，等待商家发货')
    payVisible.value = false
    await fetchOrders()
  } catch {
    ElMessage.error('支付失败，请稍后重试')
  } finally {
    payLoading.value = false
  }
}

const handleShip = async (id) => {
  try {
    await request.post(`/orders/${id}/ship/`, {})
    ElMessage.success('已确认发货')
    await fetchSoldOrders()
  } catch {
    ElMessage.error('发货操作失败')
  }
}

const saveAddress = async () => {
  try {
    await request.post('/addresses/', addrForm.value)
    ElMessage.success('地址添加成功')
    addrFormVisible.value = false
    await fetchAddresses()
  } catch {
    ElMessage.error('保存失败')
  }
}

const openDetails = async (row) => {
  currentOrder.value = row
  detailsVisible.value = true
  detailLoading.value = true
  const pId = row.product?.id || row.product

  try {
    const res = await request.get(`/products/${pId}/`)
    productDetail.value = res.data
  } catch {
    ElMessage.error('获取详情失败')
  } finally {
    detailLoading.value = false
  }
}

const showPaidDeleteWarning = () => {
  ElMessage({
    message: '该订单已支付或进入物流阶段，无法删除。',
    type: 'warning',
    duration: 3500
  })
}

const handleDelete = async (id) => {
  const targetOrder = orderList.value.find((o) => o.id === id)
  if (targetOrder && targetOrder.status !== 'pending') {
    showPaidDeleteWarning()
    return
  }

  try {
    await request.delete(`/orders/${id}/delete/`)
    ElMessage.success('订单已删除')
    await fetchOrders()
  } catch (e) {
    const serverError = e.response?.data?.error || e.response?.data?.detail
    ElMessage.warning(serverError || '删除失败，请检查网络与权限')
    await fetchOrders()
  }
}

const getStatusText = (s) => ({ pending: '待付款', paid: '待发货', shipped: '已发货', completed: '已收货' }[s] || s)
const getStatusType = (s) => ({ pending: 'danger', paid: 'warning', shipped: 'success', completed: 'info' }[s] || 'info')
const getProductName = (row) => row.product_name || '货品同步中...'

onMounted(async () => {
  if (userRole.value === 'supplier') {
    await fetchSoldOrders()
  } else {
    await fetchOrders()
    await fetchAddresses()
  }
})
</script>

<style scoped>
.orders-container { padding: 20px; background: white; min-height: 100vh; }
.stat-cards { margin-bottom: 20px; }
.stat-card { text-align: center; border-radius: 12px; }
.stat-title { font-size: 14px; color: #909399; margin-bottom: 10px; }
.stat-value { font-size: 28px; font-weight: bold; }
.unit { font-size: 14px; color: #666; margin-left: 4px; }
.text-danger { color: #f56c6c; }
.text-success { color: #67c23a; }
.price-text { color: #f56c6c; font-weight: bold; }
.detail-rich-box { display: flex; gap: 20px; }
.detail-img { width: 140px; height: 140px; object-fit: cover; border-radius: 8px; }
.addr-card { margin-bottom: 10px; border-left: 4px solid #409eff; }
.text-mini { font-size: 12px; color: #999; }
.mt-20 { margin-top: 20px; }
.mb-20 { margin-bottom: 20px; }
.pay-checkout-container { padding: 10px 5px; }
.pay-order-header { text-align: center; margin-bottom: 20px; }
.amount-box { color: #f56c6c; margin-bottom: 5px; }
.amount-box .symbol { font-size: 20px; font-weight: bold; }
.amount-box .num { font-size: 36px; font-weight: bold; }
.order-id { font-size: 12px; color: #999; }
.pay-footer { display: flex; gap: 10px; }
.pay-footer .el-button { flex: 1; }
</style>
