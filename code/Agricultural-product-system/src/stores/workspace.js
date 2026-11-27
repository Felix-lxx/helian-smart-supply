import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'
export const labels = {
  pending: '待确认',
  paid: '待发运',
  shipped: '运输中',
  completed: '已完成',
  cancelled: '已取消',
  issue: '验收异常',
  refunded: '已退款',
  on_sale: '在售',
  off_shelf: '已下架',
  draft: '草稿',
  released: '已放行',
  quarantine: '隔离待复核',
  open: '征集中',
  ordered: '已转订单',
  unpaid: '待付款',
  review: '待核对收款',
  confirmed: '已核实到账',
  sent: '已发送报价',
  accepted: '已接受',
  closed: '已关闭',
  expired: '已到期',
  superseded: '已有更新方案',
  retail: '采购商',
  supplier: '供应商',
  admin: '运营管理员',
}
export const money = (v) =>
  Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
export const qty = (v) => Number(v || 0).toLocaleString('zh-CN', { maximumFractionDigits: 2 })
export const dateText = (v) =>
  v
    ? new Date(v).toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      })
    : '—'
export const todayPlus = (n) => {
  const d = new Date()
  d.setDate(d.getDate() + n)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
export const useWorkspace = defineStore('workspace', () => {
  const state = ref({
    user: { role: localStorage.getItem('user_role') || 'retail' },
    products: [],
    batches: [],
    orders: [],
    demands: [],
    notifications: [],
    plans: [],
    stats: { trend: [] },
  })
  const market = ref([]),
    loading = ref(false),
    lastSync = ref(null),
    error = ref('')
  const role = computed(() => state.value.user.role),
    isAdmin = computed(() => role.value === 'admin'),
    isSupplier = computed(() => role.value === 'supplier'),
    isBuyer = computed(() => role.value === 'retail'),
    unread = computed(() => state.value.notifications.filter((n) => !n.read).length)
  let inflight = null
  const collaboration = ref({
    tasks: [],
    priorities: [],
    incidents: [],
    recoveries: [],
    cases: [],
    ledger: [],
    job: null,
    sites: [],
  })
  async function refresh(silent = false) {
    if (inflight) return inflight
    if (!silent) loading.value = true
    inflight = (async () => {
      try {
        const [s, m, c] = await Promise.all([
          request.get('/workspace/bootstrap/'),
          request.get('/workspace/market/'),
          request.get('/workspace/collaboration/', { timeout: 30000 }),
        ])
        state.value = s.data
        market.value = m.data
        collaboration.value = c.data
        lastSync.value = new Date()
        error.value = ''
      } catch (e) {
        error.value = e.response?.data?.detail || '同步失败，请检查服务连接'
        if (!silent) ElMessage.error(error.value)
      } finally {
        loading.value = false
        inflight = null
      }
    })()
    return inflight
  }
  async function act(path, payload = {}, message = '已保存') {
    try {
      const r = await request.post(`/workspace/${path}`, payload, { timeout: 30000 })
      if (message) ElMessage.success(message)
      // A poll started before this write may still carry the previous state.
      if (inflight) await inflight
      await refresh(true)
      window.dispatchEvent(new CustomEvent('hl-business-change'))
      return r.data
    } catch (e) {
      const d = e.response?.data
      ElMessage.error(
        typeof d === 'string' ? d : d?.detail || d?.error || '操作未完成，请检查输入或重试',
      )
      throw e
    }
  }
  const cart = ref(
    JSON.parse(localStorage.getItem(`hl-cart-${localStorage.getItem('user_id')}`) || '[]'),
  )
  function persistCart() {
    localStorage.setItem(`hl-cart-${localStorage.getItem('user_id')}`, JSON.stringify(cart.value))
  }
  function addCart(p, b, n, meta = {}) {
    n = Number(n)
    const step = Number(p.quantity_step || 1)
    if (
      !Number.isFinite(n) ||
      n < p.min_order ||
      n > b.available ||
      Math.abs(n / step - Math.round(n / step)) > 1e-5
    ) {
      ElMessage.warning(
        `请按 ${step}${p.unit} 增量采购，起订 ${p.min_order}${p.unit}，不超过可售库存`,
      )
      return false
    }
    const old = cart.value.find((x) => x.batch_id === b.id)
    if (old && (old.purpose || meta.purpose) && (old.purpose !== meta.purpose || old.process !== meta.process || old.yield_record_id !== meta.yield_record_id)) {
      ElMessage.warning('该批次已使用另一采购口径加入清单，请先核对或移除原明细')
      return false
    }
    if (old) {
      if (old.quantity+n>b.available) { ElMessage.warning('合并后的采购量超过可售库存'); return false }
      old.quantity += n
      if (meta.required_usable) old.required_usable = Number(old.required_usable||0)+Number(meta.required_usable)
    }
    else
      cart.value.push({
        batch_id: b.id,
        product_id: p.id,
        name: p.name,
        image_url: p.image_url,
        supplier: p.supplier,
        unit: p.unit,
        price: b.price ?? p.retail_price,
        quantity: n,
        available: b.available,
        code: b.code,
        min_order: p.min_order,
        quantity_step: p.quantity_step,
        ...meta,
      })
    persistCart()
    ElMessage.success('已加入采购清单')
    return true
  }
  function logout() {
    for (const k of ['access_token', 'refresh_token', 'user_role', 'username', 'user_id'])
      localStorage.removeItem(k)
    window.location.assign('/login')
  }
  return {
    state,
    collaboration,
    market,
    loading,
    lastSync,
    error,
    role,
    isAdmin,
    isSupplier,
    isBuyer,
    unread,
    refresh,
    act,
    cart,
    persistCart,
    addCart,
    logout,
  }
})
