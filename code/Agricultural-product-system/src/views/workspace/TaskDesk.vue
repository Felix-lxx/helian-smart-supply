<script setup>
import { ref, reactive, computed, watch, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import QRCode from 'qrcode'
import { useWorkspace, qty, dateText } from '@/stores/workspace'
import { useBusinessFeed } from '@/composables/useBusinessFeed'
import request from '@/utils/request'
const w = useWorkspace(),
  route = useRoute(),
  router = useRouter(),
  data = ref({ items: [], total: 0, counts: {} }),
  selected = ref(null),
  detail = ref(null),
  working = ref(false),
  label = ref(null),
  qr = ref(''),
  scanner = ref(false),
  video = ref(null),
  detailVisible = ref(!!route.query.task)
const filters = reactive({
  status: 'queued',
  kind: route.query.kind || '',
  search: route.query.search || '',
  page: 1,
})
const names = {
  queued: '待领取',
  active: '进行中',
  blocked: '受阻待协调',
  done: '已完成',
  cancelled: '已取消',
}
let searchTimer,
  stream,
  scanning = false
const { busy, error, refresh } = useBusinessFeed(async () => {
  const r = await request.get('/workspace/tasks/', {
    params: { ...route.query, ...filters },
    timeout: 30000,
  })
  data.value = r.data
  if (route.query.task && selected.value !== Number(route.query.task))
    selected.value = Number(route.query.task)

  if (selected.value) {
    const item = r.data.items.find((t) => t.id === selected.value)
    if (item) detail.value = item
    else {
      try {
        detail.value = (await request.get('/workspace/tasks/' + selected.value + '/')).data
      } catch {
        detail.value = null
      }
    }
  }
})
watch(
  () => JSON.stringify([filters.status, filters.kind, filters.page]),
  () => refresh(),
)
watch(
  () => route.query.task,
  async (id) => {
    if (id) {
      selected.value = Number(id)
      detailVisible.value = true
      await loadDetail()
    }
  },
)
watch(
  () => route.query.kind,
  (k) => {
    filters.kind = k || ''
    filters.page = 1
  },
)
const canWork = computed(() => {
  const t = detail.value
  if (!t) return false
  if (w.isAdmin) return true
  return ['receive', 'replacement', 'return'].includes(t.kind)
    ? (w.state.user.managed_buyer_ids || [w.state.user.id]).includes(t.buyer_id)
    : (w.state.user.dispatch_supplier_ids || [w.state.user.id]).includes(t.supplier_id)
})
async function loadDetail() {
  if (!selected.value) return
  try {
    detail.value = (await request.get('/workspace/tasks/' + selected.value + '/')).data
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '无法读取任务')
  }
}
function choose(t) {
  detailVisible.value = true
  selected.value = t.id
  detail.value = t
  router.replace({ query: { ...route.query, task: t.id } })
}
function search() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    filters.page = 1
    refresh()
  }, 350)
}
async function action(name) {
  const t = detail.value
  if (!t) return
  try {
    let note = ''
    if (name === 'block' || name === 'complete') {
      const p = await ElMessageBox.prompt(
        name === 'block'
          ? '记录阻塞原因，便于其他岗位协调。'
          : '记录本次已分拣数量、标签或实际核对依据。',
        name === 'block' ? '登记作业阻塞' : '完成分拣核对',
        { inputType: 'textarea', inputValidator: (v) => !!v?.trim() || '请填写实际依据' },
      )
      note = p.value
    }
    working.value = true
    await w.act(`tasks/${t.id}/`, { action: name, version: t.version, note }, '任务状态已同步')
    await refresh()
    await loadDetail()
  } catch {
    // Operation errors are shown by the shared workspace action; dialog cancellation is intentional.
  } finally {
    working.value = false
  }
}
function perform() {
  const t = detail.value
  if (t)
    router.push({
      path: '/orders',
      query: {
        order: t.order_id,
        action: ['receive', 'replacement'].includes(t.kind) ? 'receive' : 'ship',
        delivery: t.delivery_id || undefined,
        supplier: t.supplier_id || undefined,
      },
    })
}
async function showLabel(t) {
  label.value = t
  qr.value = await QRCode.toDataURL(window.location.origin + '/workboard?task=' + t.id, {
    width: 280,
    margin: 2,
    color: { dark: '#182c46', light: '#ffffff' },
  })
}
function downloadLabel() {
  const a = document.createElement('a')
  a.href = qr.value
  a.download = `禾链作业标签-${label.value.id}.png`
  a.click()
}
async function scan() {
  if (!('BarcodeDetector' in window) || !navigator.mediaDevices?.getUserMedia) {
    ElMessage.info('当前浏览器不支持相机扫码，可用扫码枪或输入任务、批次和配送单号')
    return
  }
  scanner.value = true
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })
    await new Promise((r) => setTimeout(r, 50))
    video.value.srcObject = stream
    await video.value.play()
    scanning = true
    const detector = new window.BarcodeDetector({ formats: ['qr_code', 'code_128', 'ean_13'] })
    while (scanning) {
      const found = await detector.detect(video.value)
      if (found.length) {
        const raw = found[0].rawValue
        let taskId
        try {
          const url = new URL(raw, location.origin)
          if (url.origin === location.origin && url.pathname === '/workboard')
            taskId = url.searchParams.get('task')
        } catch {
          /* Optional state or user cancellation; keep the current business record. */
        }
        stopScan()
        if (taskId) {
          selected.value = Number(taskId)
          detailVisible.value = true
          await loadDetail()
          router.replace({ query: { task: taskId } })
        } else {
          filters.search = raw
          search()
        }
        break
      }
      await new Promise((r) => setTimeout(r, 400))
    }
  } catch {
    stopScan()
    ElMessage.info('相机不可用，请使用扫码枪或手动录入')
  }
}
function stopScan() {
  scanning = false
  stream?.getTracks().forEach((t) => t.stop())
  stream = null
  scanner.value = false
}
onBeforeUnmount(() => {
  clearTimeout(searchTimer)
  stopScan()
})
</script>
<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1>{{ w.isBuyer ? '到货与验收作业' : '现场作业中心' }}</h1>
        <p>领取实际任务，完成分拣、装车与验收。每次交接都更新关联订单。</p>
      </div>
      <div class="head-actions">
        <el-button icon="Camera" @click="scan">相机扫码</el-button
        ><el-button icon="Refresh" @click="refresh()">同步任务</el-button>
      </div>
    </div>
    <div v-if="error" class="business-error">
      {{ error }}<el-button link @click="refresh()">重试</el-button>
    </div>
    <div class="task-state-tabs">
      <button
        v-for="[key, name, icon] in [
          ['queued', '待领取', 'Tickets'],
          ['active', '进行中', 'Loading'],
          ['blocked', '受阻待协调', 'Warning'],
          ['done', '已完成', 'CircleCheck'],
        ]"
        :key="key"
        :class="{ active: filters.status === key }"
        @click="
          () => {
            filters.status = key
            filters.page = 1
          }
        "
      >
        <span
          ><el-icon><component :is="icon" /></el-icon>{{ name }}</span
        ><b>{{ data.counts[key] || 0 }}</b>
      </button>
    </div>
    <div class="panel task-searchbar">
      <el-input
        v-model="filters.search"
        clearable
        placeholder="输入任务编号、品种、批次或配送单号，支持扫码枪"
        prefix-icon="Search"
        @input="search"
      /><el-select v-model="filters.kind" clearable placeholder="全部作业类型"
        ><el-option
          v-for="[k, n] in [
            ['pick', '分拣备货'],
            ['dispatch', '装车发运'],
            ['receive', '到货验收'],
            ['replacement', '补发验收'],
          ]"
          :key="k"
          :value="k"
          :label="n" /></el-select
      ><span>完整业务队列 · {{ data.total }} 项</span>
    </div>
    <div class="task-desk-layout">
      <section class="task-cards" v-loading="busy">
        <button
          v-for="t in data.items"
          :key="t.id"
          class="task-desk-card"
          :class="{ selected: selected === t.id, blocked: t.status === 'blocked' }"
          @click="choose(t)"
        >
          <div class="task-card-top">
            <span class="task-type-icon"
              ><el-icon
                ><component
                  :is="
                    t.kind === 'pick' ? 'Goods' : t.kind === 'dispatch' ? 'Van' : 'CircleCheck'
                  " /></el-icon></span
            ><b>{{ t.kind_label }}</b
            ><span
              class="status-badge"
              :class="t.status === 'blocked' ? 'issue' : t.status === 'done' ? 'confirmed' : 'open'"
              >{{ names[t.status] }}</span
            >
          </div>
          <div class="task-product">
            <h3>{{ t.product }} <em v-if="t.is_demo">演示</em></h3>
            <p>{{ t.batch_code || t.note }}</p>
          </div>
          <div class="task-card-quantity">
            <b
              >{{ qty(t.quantity) }}<small>{{ t.unit }}</small></b
            ><span>{{ t.site || '按订单收货地址' }}</span>
          </div>
          <div class="task-card-bottom">
            <span
              ><el-icon><User /></el-icon>{{ t.assignee || '待领取' }}</span
            ><span :class="{ late: t.overdue }"
              >{{ t.due_at ? dateText(t.due_at) : '未约定具体时限'
              }}{{ t.overdue ? ' · 已超时' : '' }}</span
            >
          </div>
        </button>
        <div v-if="!data.items.length && !busy" class="panel empty-business">
          <el-icon size="35"><CircleCheck /></el-icon>
          <p>当前筛选下没有{{ names[filters.status] }}任务</p>
          <small>确认收款后生成备货与发运任务，实际发运后生成验收任务。</small>
        </div>
        <el-pagination
          v-if="data.total > 30"
          v-model:current-page="filters.page"
          :total="data.total"
          :page-size="30"
          layout="prev,pager,next"
        />
      </section>
    </div>
    <el-dialog :model-value="!!label" @close="label = null" title="作业标签" width="420px"
      ><div v-if="label" class="task-label-preview">
        <img :src="qr" alt="作业任务二维码" />
        <h3>{{ label.product }}</h3>
        <b>{{ label.batch_code || label.number }}</b>
        <p>{{ qty(label.quantity) }} {{ label.unit }} · {{ label.kind_label }}</p>
        <small>{{ label.site }}</small
        ><span v-if="label.is_demo" class="source-label">演示作业</span>
        <p class="data-note">
          扫码后需登录有权限的工作区。此标签关联作业任务，不代表已装箱或已交付。
        </p>
      </div>
      <template #footer
        ><el-button type="primary" icon="Download" @click="downloadLabel"
          >下载二维码标签</el-button
        ></template
      ></el-dialog
    ><el-dialog v-model="scanner" @closed="stopScan" title="扫描作业或批次码" width="520px"
      ><video ref="video" class="task-camera" autoplay playsinline muted></video>
      <p class="data-note">图像仅用于本机识别二维码，不上传相机画面。</p></el-dialog
    >
  </div>
  <el-drawer v-model="detailVisible" title="处理作业任务" :size="'min(460px, 100vw)'">
    <div v-if="detail" class="task-detail">
      <div class="panel-head">
        <h2>任务 #{{ detail.id }}</h2>
        <el-button link icon="PriceTag" @click="showLabel(detail)">作业标签</el-button>
      </div>
      <div class="panel-body">
        <div class="task-detail-heading">
          <span>{{ detail.kind_label }}</span>
          <h2>{{ detail.product }}</h2>
          <p>{{ detail.number }}</p>
        </div>
        <div class="task-detail-quantity">
          <b>{{ qty(detail.quantity) }}</b
          ><span>{{ detail.unit }}</span>
        </div>
        <div class="kv">
          <span>当前状态</span><b>{{ names[detail.status] }}</b>
        </div>
        <div class="kv">
          <span>负责人</span><b>{{ detail.assignee || '待领取' }}</b>
        </div>
        <div class="kv">
          <span>实际履约方</span><b>{{ detail.supplier || '按交付单' }}</b>
        </div>
        <div class="kv">
          <span>收货点</span><b>{{ detail.site || '按订单地址' }}</b>
        </div>
        <p class="task-detail-address">{{ detail.address }}</p>
        <div v-if="detail.batch_code" class="kv">
          <span>作业批次</span><b>{{ detail.batch_code }}</b>
        </div>
        <p v-if="detail.note" class="task-detail-note">{{ detail.note }}</p>
        <div
          v-if="canWork && !['done', 'cancelled'].includes(detail.status)"
          class="task-detail-actions"
        >
          <el-button
            v-if="!detail.assignee_id || detail.status === 'blocked'"
            :loading="working"
            type="primary"
            @click="action('claim')"
            >{{ detail.status === 'blocked' ? '继续处理' : '领取并开始' }}</el-button
          ><el-button
            v-if="detail.kind === 'pick'"
            :loading="working"
            type="primary"
            plain
            @click="action('complete')"
            >记录分拣完成</el-button
          ><el-button v-else-if="detail.kind === 'dispatch'" type="primary" @click="perform"
            >登记实际发运</el-button
          ><el-button
            v-else-if="['receive', 'replacement'].includes(detail.kind)"
            type="primary"
            @click="perform"
            >称重并验收</el-button
          ><el-button :loading="working" @click="action('block')">登记阻塞</el-button>
        </div>
        <el-button
          link
          type="primary"
          class="task-open-order"
          @click="router.push('/orders?order=' + detail.order_id)"
          >打开关联订单与全部证据<el-icon><ArrowRight /></el-icon
        ></el-button>
        <section v-if="detail.events.length" class="task-event-log">
          <h3>作业记录</h3>
          <article v-for="(e, i) in detail.events.slice().reverse()" :key="i">
            <b
              >{{ e.actor }} ·
              {{
                {
                  claim: '领取任务',
                  complete: '完成分拣',
                  done: '实际作业已完成',
                  block: '登记阻塞',
                  cancelled: '任务已关闭',
                  assign: '任务已转派',
                }[e.action] || e.action
              }}</b
            >
            <p>{{ e.note }}</p>
            <time>{{ dateText(e.time) }}</time>
          </article>
        </section>
      </div>
    </div></el-drawer
  >
</template>
<style scoped>
.task-detail {
  position: sticky;
  top: 91px;
}
.task-detail .panel-head {
  padding: 18px 21px;
}
.task-detail .panel-head > .el-button {
  font-size: 12px;
}
.task-detail-heading > span {
  font-size: 12px;
  color: #8aa1bf;
}
.task-detail-heading h2 {
  font-size: 20px;
  color: #3b5b80;
  margin: 13px 0 9px;
  line-height: 1.6;
}
.task-detail-heading p {
  font-size: 12px;
  color: #6b819c;
}
.task-detail-quantity {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin: 24px 0 14px;
  color: #667e9a;
}
.task-detail-quantity b {
  font-size: 39px;
  letter-spacing: -1px;
  font-weight: 600;
  color: #446d9e;
  font-variant-numeric: tabular-nums;
}
.task-detail-quantity span {
  font-size: 13px;
}
.task-detail .kv {
  font-size: 12px;
  gap: 20px;
  padding: 13px 0;
}
.task-detail .kv > span {
  color: #667e9a;
  white-space: nowrap;
}
.task-detail .kv > b {
  color: #6682a5;
  font-size: 12px;
  font-weight: 500;
  text-align: right;
}
.task-detail-address {
  font-size: 12px;
  line-height: 1.9;
  color: #91a7c2;
  margin: 12px 0;
}
.task-detail-note {
  padding: 12px 14px;
  background: #f4f7fc;
  color: #667e9a;
  font-size: 12px;
  line-height: 1.9;
  margin: 15px 0;
  border-radius: 7px;
}
.task-detail-actions {
  display: flex;
  gap: 9px;
  flex-wrap: wrap;
  margin-top: 20px;
}
.task-detail-actions > .el-button {
  font-size: 12px;
  margin: 0;
}
.task-open-order {
  margin-top: 19px;
  font-size: 12px;
}
.task-event-log {
  border-top: 1px solid #e8eef6;
  padding-top: 20px;
  margin-top: 20px;
}
.task-event-log > h3 {
  font-size: 13px;
  color: #6f89a9;
}
.task-event-log article {
  padding: 15px 0;
  border-bottom: 1px solid #edf1f7;
}
.task-event-log b {
  font-size: 12px;
  color: #7a94b1;
  font-weight: 500;
}
.task-event-log p {
  font-size: 12px;
  color: #667e9a;
  margin-top: 7px;
  line-height: 1.8;
}
.task-event-log time {
  font-size: 12px;
  color: #b0bdce;
  display: block;
  margin-top: 7px;
}
.task-label-preview {
  text-align: center;
  padding: 10px 10px 20px;
}
.task-label-preview > img {
  width: 220px;
  max-width: 100%;
  height: auto;
}
.task-label-preview h3 {
  font-size: 18px;
  color: #36567d;
  margin: 15px 0;
}
.task-label-preview > b {
  color: #7190b8;
  font-size: 13px;
}
.task-label-preview > p:not(.data-note) {
  font-size: 13px;
  color: #7894b5;
  margin: 12px 0;
}
.task-label-preview > small {
  display: block;
  color: #6b819c;
  font-size: 13px;
  margin: 12px 0;
}
.task-label-preview > .data-note {
  font-size: 12px;
  margin-top: 20px;
}
.task-camera {
  width: 100%;
  border-radius: 9px;
  background: #10223d;
  min-height: 250px;
  object-fit: cover;
}
@media (max-width: 760px) {
  .task-detail {
    position: static;
    order: -1;
  }
  .task-detail .panel-body {
    padding: 21px;
  }
  .task-detail-quantity {
    float: right;
    margin: 10px 0 0 20px;
  }
  .task-detail .kv {
    clear: both;
  }
  .task-detail-heading h2 {
    font-size: 20px;
    margin: 9px 0;
  }
  .task-detail-actions > .el-button {
    min-height: 41px;
    font-size: 13px;
  }
  .task-detail .task-event-log {
    display: none;
  }
}

.task-state-tabs {
  display: flex;
  gap: 28px;
  border-bottom: 1px solid #dfe6ee;
  margin-bottom: 26px;
  overflow-x: auto;
}
.task-state-tabs > button {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 17px 0;
  border: 0;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: #6a7c95;
  cursor: pointer;
  white-space: nowrap;
  font-size: 14px;
}
.task-state-tabs > button.active {
  border-bottom-color: #365ee9;
  color: #365ee9;
}
.task-state-tabs > button > span {
  font-size: 14px;
}
.task-state-tabs > button > b {
  font-size: 13px;
  font-weight: 400;
  color: inherit;
}
.task-state-tabs .el-icon {
  display: none;
}
.task-searchbar {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
  background: transparent;
  border: 0;
}
.task-searchbar > .el-input {
  max-width: 470px;
  min-width: 200px;
  flex: 1;
}
.task-searchbar > .el-select {
  width: 180px;
  flex-shrink: 0;
}
.task-searchbar > span {
  font-size: 12px;
  color: #74869e;
  margin-left: auto;
  white-space: nowrap;
}
.task-desk-layout {
  display: block;
}
.task-cards {
  display: block;
  background: #fff;
  border: 1px solid #e3e9f1;
  border-radius: 12px;
  overflow-y: auto;
  max-height: calc(100dvh - 350px);
  min-height: 180px;
  scrollbar-width: thin;
  scrollbar-color: #ccd6e5 transparent;
}
.task-desk-card {
  display: grid;
  grid-template-columns: 125px minmax(180px, 1.5fr) minmax(130px, 1fr) 165px;
  align-items: center;
  gap: 24px;
  width: 100%;
  padding: 23px 25px;
  border: 0;
  border-bottom: 1px solid #e8edf4;
  border-radius: 0;
  background: #fff;
  text-align: left;
  color: #344e6d;
  font: inherit;
  font-size: 14px;
  cursor: pointer;
  min-height: 95px;
}
.task-desk-card:last-child {
  border-bottom: 0;
}
.task-desk-card:hover {
  background: #f8faff;
}
.task-desk-card.selected {
  background: #f6f9ff;
}
.task-card-top {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 9px;
}
.task-card-top > b {
  font-size: 13px;
  font-weight: 500;
  color: #526f94;
}
.task-card-top > .status-badge {
  font-size: 11px;
}
.task-type-icon {
  display: none;
}
.task-product {
  min-width: 0;
}
.task-product h3 {
  font-size: 14px;
  color: #2d4667;
  line-height: 1.7;
  font-weight: 550;
  overflow-wrap: anywhere;
}
.task-product h3 em {
  font-size: 11px;
  font-weight: 400;
  font-style: normal;
  color: #9a763d;
  white-space: nowrap;
}
.task-product p {
  font-size: 12px;
  line-height: 1.8;
  color: #7b8ca2;
  margin-top: 6px;
  overflow-wrap: anywhere;
}
.task-card-quantity b {
  font-size: 22px;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
  color: #3e618a;
  line-height: 1.4;
}
.task-card-quantity b small {
  font-size: 12px;
  font-weight: 400;
  color: #7b8ca2;
  margin-left: 6px;
}
.task-card-quantity > span {
  display: block;
  font-size: 12px;
  color: #6d829d;
  line-height: 1.8;
  margin-top: 6px;
}
.task-card-bottom {
  display: grid;
  gap: 10px;
  color: #7488a2;
  font-size: 12px;
}
.task-card-bottom > span:first-child {
  display: flex;
  gap: 6px;
  align-items: center;
}
.task-card-bottom .late {
  color: #aa7e3e;
}
.task-cards > .empty-business {
  border: 0;
  background: transparent;
}
.task-cards > .el-pagination {
  padding: 16px;
  justify-content: center;
}
.task-detail {
  position: static;
}
.task-detail .panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 0 20px;
  border-bottom: 1px solid #e7edf4;
  gap: 15px;
}
.task-detail .panel-head > h2 {
  font-size: 16px;
}
.task-detail .panel-head > .el-button {
  font-size: 12px;
}
.task-detail .panel-body {
  padding: 24px 0;
}
.task-detail .task-detail-quantity {
  float: none;
  margin: 24px 0;
}
.task-detail .task-event-log {
  display: block;
}
.task-detail .task-detail-actions > .el-button {
  font-size: 13px;
  min-height: 40px;
}
@media (max-width: 1100px) {
  .task-desk-card {
    grid-template-columns: 110px minmax(150px, 1.3fr) minmax(120px, 1fr);
    gap: 20px;
  }
  .task-card-bottom {
    display: none;
  }
  .task-searchbar {
    flex-wrap: wrap;
  }
  .task-searchbar > span {
    margin-left: 0;
  }
  .task-cards {
    max-height: calc(100dvh - 360px);
  }
}
@media (max-width: 600px) {
  .task-state-tabs {
    gap: 18px;
  }
  .task-state-tabs > button {
    gap: 7px;
  }
  .task-state-tabs > button > span,
  .task-state-tabs > button > b {
    font-size: 12px;
  }
  .task-searchbar {
    gap: 12px;
  }
  .task-searchbar > .el-input {
    flex-basis: 100%;
    max-width: none;
    min-width: 0;
  }
  .task-searchbar > .el-select {
    width: 155px;
  }
  .task-searchbar > span {
    font-size: 11px;
  }
  .task-cards {
    max-height: none;
  }
  .task-desk-card {
    grid-template-columns: minmax(0, 1fr) 100px;
    padding: 21px 18px;
    gap: 15px 12px;
    min-height: 140px;
  }
  .task-card-top {
    grid-column: 1;
    grid-row: 1;
  }
  .task-product {
    grid-column: 1;
    grid-row: 2;
  }
  .task-product h3 {
    font-size: 14px;
  }
  .task-product p {
    font-size: 11px;
  }
  .task-card-quantity {
    grid-column: 2;
    grid-row: 1/3;
    text-align: right;
  }
  .task-card-quantity b {
    font-size: 23px;
  }
  .task-card-quantity > span {
    font-size: 11px;
  }
  .task-detail .task-detail-quantity {
    float: none;
  }
}
</style>
