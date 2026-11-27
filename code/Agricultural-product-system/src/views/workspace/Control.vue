<script setup>
defineOptions({ name: 'BusinessControl' })
import { ref, reactive, computed, watch, defineAsyncComponent, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useWorkspace, money, qty, dateText, todayPlus, labels } from '@/stores/workspace'
import { useBusinessFeed } from '@/composables/useBusinessFeed'
import request from '@/utils/request'
import OriginMap from '@/components/OriginMap.vue'
const OnlineOriginMap = defineAsyncComponent(() => import('@/components/OnlineOriginMap.vue'))
const w = useWorkspace(),
  router = useRouter(),
  online = ref(true),
  config = ref(null),
  selected = ref(null),
  sideTab = ref('risks'),
  detailView = ref(''),
  focusedRisk = ref(null)
const filters = reactive({ date: todayPlus(0), unit: 'kg', site: '', exclude_demo: false })
const data = ref({
  kpis: {},
  gaps: [],
  risks: [],
  nodes: [],
  links: [],
  sites: [],
  stages: [],
  tasks: [],
  orders: [],
  events: [],
})
const { busy, error, updated, refresh } = useBusinessFeed(async () => {
  const response = await request.get('/workspace/control/', {
    params: { ...filters, exclude_demo: filters.exclude_demo ? '1' : '0' },
    timeout: 30000,
  })
  data.value = response.data
})
watch(
  () => JSON.stringify(filters),
  () => {
    selected.value = null
    refresh()
  },
)
onMounted(async () => {
  try {
    config.value = (await request.get('/workspace/maps/config/')).data
  } catch {
    /* Optional state or user cancellation; keep the current business record. */
  }
})
const visibleMetrics = computed(() =>
  metrics.value.filter((m) => ['当日约定量', '采购待覆盖', '到货完成', '作业待办'].includes(m[0])),
)
const active = computed(() => data.value.nodes.find((n) => n.id === selected.value))
const metrics = computed(() => [
  ['当日约定量', qty(data.value.kpis.promised), filters.unit, 'Box'],
  ['采购待覆盖', qty(data.value.kpis.gap), filters.unit, 'Connection'],
  ['已发运量', qty(data.value.kpis.dispatched), filters.unit, 'Van'],
  [
    '到货完成',
    data.value.kpis.completion == null ? '—' : data.value.kpis.completion + '%',
    '按订单',
    'CircleCheck',
  ],
  ['作业待办', data.value.kpis.tasks_open || 0, '项', 'Tickets'],
  ['待处理差额', money(data.value.kpis.cases_amount), '元', 'Wallet'],
])
function open(path) {
  router.push(path)
}
function openMetric(name) {
  const path =
    name === '作业待办'
      ? '/workboard'
      : name === '待处理差额'
        ? '/accounts'
        : name === '采购待覆盖'
          ? '/demands'
          : '/orders'
  router.push({
    path,
    query: {
      active: '1',
      date: filters.date,
      site: filters.site || undefined,
      unit: filters.unit,
      exclude_demo: filters.exclude_demo ? '1' : undefined,
      status: name === '到货完成' ? 'completed' : name === '采购待覆盖' ? 'open' : undefined,
      dispatched: name === '已发运量' ? '1' : undefined,
    },
  })
}
function locate(gap) {
  router.push({
    path: w.isBuyer ? '/procurement' : '/allocation',
    query: w.isBuyer ? { demand: gap.id } : {},
  })
}
function inspectRisk(r) {
  focusedRisk.value = r
  selected.value = data.value.links.find((l) => l.order_id === r.order_id)?.target || null
  detailView.value = 'risk'
}
function point(id) {
  selected.value = selected.value === id ? null : id
}
function focusSite() {
  if (active.value?.site_id) filters.site = String(active.value.site_id)
}
async function toggleFull() {
  try {
    if (document.fullscreenElement) await document.exitFullscreen()
    else await document.documentElement.requestFullscreen()
  } catch {
    ElMessage.info('当前窗口不支持全屏，可使用浏览器全屏模式')
  }
}
</script>

<template>
  <div class="control-screen">
    <header class="control-header">
      <div class="control-heading">
        <button class="control-home" aria-label="返回工作区" @click="open('/home')">
          <el-icon><ArrowLeft /></el-icon>
        </button>
        <h1>履约调度<span>禾链智配</span></h1>
      </div>
      <div class="control-header-actions">
        <span>{{
          updated ? '更新于 ' + updated.toLocaleTimeString('zh-CN', { hour12: false }) : '正在同步'
        }}</span
        ><button @click="detailView = 'orders'">交付明细</button
        ><button @click="detailView = 'events'">业务动态</button
        ><button aria-label="切换全屏" @click="toggleFull">
          <el-icon><FullScreen /></el-icon>
        </button>
      </div>
    </header>
    <div class="control-toolbar">
      <div class="control-scope">
        <select v-model="filters.site" aria-label="业务站点">
          <option value="">全部站点</option>
          <option v-for="s in data.sites" :key="s.id" :value="String(s.id)">
            {{ s.name }}
          </option></select
        ><input v-model="filters.date" type="date" aria-label="约定到货日期" /><select
          v-model="filters.unit"
          aria-label="数量单位"
        >
          <option v-for="u in ['kg', '斤', '箱', '件']" :key="u">{{ u }}</option></select
        ><label><input v-model="filters.exclude_demo" type="checkbox" />排除演示</label>
      </div>
      <button class="control-refresh" aria-label="刷新大屏" @click="refresh()">
        <el-icon><Refresh /></el-icon><span>{{ busy ? '同步中' : '刷新' }}</span>
      </button>
    </div>
    <div v-if="error" class="control-error">
      {{ error }}<button @click="refresh()">重新连接</button>
    </div>
    <section class="control-metrics" aria-label="当前业务摘要">
      <button v-for="[name, value, unit] in visibleMetrics" :key="name" @click="openMetric(name)">
        <span>{{ name }}</span>
        <p>
          <b>{{ value }}</b
          ><small>{{ unit }}</small>
        </p>
      </button>
    </section>
    <div class="control-workspace">
      <section class="screen-map-panel">
        <div class="screen-map-heading">
          <div>
            <h2>供给与交付网络</h2>
            <span>{{ data.nodes.length }} 个业务点</span>
          </div>
          <span>{{ config?.enabled && online ? '天地图底图' : '行政区概览' }}</span>
        </div>
        <div class="screen-map">
          <OnlineOriginMap
            v-if="config?.enabled && online"
            :products="data.nodes"
            :links="data.links"
            :tile-url="config.tile_url"
            :selected="selected"
            height="100%"
            @select="point"
            @unavailable="online = false"
          />
          <OriginMap
            v-else
            class="screen-offline-map"
            :products="data.nodes"
            :selected="selected"
            :links="data.links"
            dark
            height="100%"
            @select="point"
          />
          <div v-if="!online || !config?.enabled" class="map-mode-note">
            行政区概览 <button v-if="config?.enabled" @click="online = true">重试在线地图</button>
          </div>
          <div v-if="active" class="map-business-pop">
            <button class="map-pop-close" aria-label="关闭点位" @click="selected = null">
              <el-icon><Close /></el-icon></button
            ><span>{{ active.kind === 'site' ? '收货站点' : '供货产地' }}</span>
            <h3>{{ active.name }}</h3>
            <p>{{ active.origin }}</p>
            <small>{{
              active.verified ? '位置已核对' : active.coordinate_source || '位置待核对'
            }}</small
            ><button v-if="active.site_id" @click="focusSite">
              查看该站点业务 <el-icon><ArrowRight /></el-icon></button
            ><button v-else @click="open('/origins')">
              查看关联货源 <el-icon><ArrowRight /></el-icon>
            </button>
          </div>
        </div>
        <div class="screen-map-legend">
          <span><i />供货产地</span><span><i class="site-dot" />收货点</span
          ><span><i class="line-dot" />业务关联</span><small>连线为业务关系，非道路路线</small>
        </div>
      </section>
      <aside class="screen-queue">
        <div class="screen-queue-tabs" role="tablist" aria-label="调度事项">
          <button
            :class="{ active: sideTab === 'risks' }"
            role="tab"
            :aria-selected="sideTab === 'risks'"
            @click="sideTab = 'risks'"
          >
            异常 <span>{{ data.risks.length }}</span></button
          ><button
            :class="{ active: sideTab === 'gaps' }"
            role="tab"
            :aria-selected="sideTab === 'gaps'"
            @click="sideTab = 'gaps'"
          >
            缺口 <span>{{ data.kpis.gap_lines || 0 }}</span></button
          ><button
            :class="{ active: sideTab === 'tasks' }"
            role="tab"
            :aria-selected="sideTab === 'tasks'"
            @click="sideTab = 'tasks'"
          >
            任务 <span>{{ data.kpis.tasks_open || 0 }}</span>
          </button>
        </div>
        <div class="screen-queue-content">
          <template v-if="sideTab === 'risks'"
            ><button
              v-for="r in data.risks"
              :key="r.id"
              class="screen-queue-item"
              @click="inspectRisk(r)"
            >
              <span class="queue-risk-kind"
                ><el-icon><Warning /></el-icon>{{ r.kind }}</span
              >
              <h3>{{ r.title }}</h3>
              <p>{{ r.note || '查看业务记录并核对处理方案' }}</p>
              <span class="queue-item-action"
                >查看影响 <el-icon><ArrowRight /></el-icon
              ></span>
            </button>
            <div v-if="!data.risks.length" class="screen-empty">
              <el-icon><CircleCheck /></el-icon>
              <h3>当前没有待协调异常</h3>
              <p>可切换查看采购缺口或作业任务。</p>
            </div></template
          >
          <template v-else-if="sideTab === 'gaps'"
            ><button
              v-for="g in data.gaps"
              :key="g.id"
              class="screen-queue-item gap-item"
              @click="locate(g)"
            >
              <h3>
                {{ g.keyword
                }}<b
                  >{{ qty(g.quantity) }} <small>{{ g.unit }}</small></b
                >
              </h3>
              <p>{{ g.site }}</p>
              <span v-if="g.required_usable != null" class="queue-net-note"
                >净需求 {{ qty(g.required_usable) }} {{ g.unit }}</span
              ><span class="queue-item-action"
                >{{ w.isBuyer ? '比较货源' : '查看供货方案' }} <el-icon><ArrowRight /></el-icon
              ></span>
            </button>
            <div v-if="!data.gaps.length" class="screen-empty">
              <el-icon><CircleCheck /></el-icon>
              <h3>当前没有采购缺口</h3>
            </div></template
          >
          <template v-else
            ><button
              v-for="t in data.tasks.filter((t) => !['done', 'cancelled'].includes(t.status))"
              :key="t.id"
              class="screen-queue-item"
              @click="open('/workboard?task=' + t.id)"
            >
              <span class="queue-task-kind"
                >{{ t.kind_label }} <em v-if="t.overdue">已超时</em></span
              >
              <h3>{{ t.product }}</h3>
              <p>{{ t.site || t.supplier }}</p>
              <div class="queue-task-meta">
                <b
                  >{{ qty(t.quantity) }} <small>{{ t.unit }}</small></b
                ><span>{{ t.assignee || '待领取' }}</span>
              </div>
            </button>
            <div v-if="!data.kpis.tasks_open" class="screen-empty">
              <el-icon><CircleCheck /></el-icon>
              <h3>当前没有待处理任务</h3>
            </div></template
          >
        </div>
        <div class="screen-queue-footer">
          <span>按当前日期与站点显示</span
          ><button
            @click="
              open(
                sideTab === 'risks' ? '/recovery' : sideTab === 'gaps' ? '/demands' : '/workboard',
              )
            "
          >
            查看全部 <el-icon><ArrowRight /></el-icon>
          </button>
        </div>
      </aside>
    </div>
    <section class="control-stages">
      <span>作业进度</span
      ><button
        v-for="s in data.stages.filter((s) => s.total > 0)"
        :key="s.key"
        @click="open('/workboard?kind=' + s.key)"
      >
        <span>{{ s.label }}</span>
        <div><i :style="{ width: (s.done / s.total) * 100 + '%' }" /></div>
        <b>{{ s.done }} / {{ s.total }}</b></button
      ><span v-if="!data.stages.some((s) => s.total > 0)" class="no-stages"
        >当前范围暂无作业任务</span
      ><small v-if="data.kpis.demo_orders">含 {{ data.kpis.demo_orders }} 笔演示订单</small>
    </section>
    <el-drawer
      :model-value="!!detailView"
      @close="detailView = ''"
      :title="
        detailView === 'orders' ? '交付明细' : detailView === 'events' ? '业务动态' : '异常影响'
      "
      :size="'min(540px, 100vw)'"
    >
      <template v-if="detailView === 'orders'"
        ><div v-for="o in data.orders" :key="o.id" class="control-detail-record">
          <div>
            <h3>{{ o.name }}</h3>
            <span>{{ o.number }}</span>
          </div>
          <p>{{ o.site }}</p>
          <div>
            <b>{{ qty(o.quantity) }} {{ o.unit }}</b
            ><span>{{ labels[o.status] || o.status }}</span>
          </div>
          <el-button link type="primary" @click="open('/orders?order=' + o.id)">查看订单</el-button>
        </div>
        <el-empty v-if="!data.orders.length" description="当前范围暂无交付记录"
      /></template>
      <template v-else-if="detailView === 'events'"
        ><article v-for="e in data.events" :key="e.id" class="control-detail-record">
          <h3>{{ e.title }}</h3>
          <p>{{ e.note }}</p>
          <small>{{ dateText(e.created_at) }}</small
          ><el-button
            v-if="e.order_id"
            link
            type="primary"
            @click="open('/orders?order=' + e.order_id)"
            >关联订单</el-button
          >
        </article>
        <el-empty v-if="!data.events.length" description="暂无业务动态"
      /></template>
      <template v-else-if="focusedRisk"
        ><div class="control-risk-detail">
          <span>{{ focusedRisk.kind }}</span>
          <h2>{{ focusedRisk.title }}</h2>
          <p>{{ focusedRisk.note || '请核对关联订单与实际作业记录。' }}</p>
          <p v-if="focusedRisk.order_id">关联订单 #{{ focusedRisk.order_id }}</p>
          <el-button type="primary" @click="open(focusedRisk.route)"
            >进入业务处理 <el-icon><ArrowRight /></el-icon
          ></el-button></div
      ></template>
    </el-drawer>
  </div>
</template>
<style scoped>
.control-screen {
  min-height: 100vh;
  background: #0c192b;
  color: #c7d5e7;
  padding: 0 32px 20px;
  font-family: 'Segoe UI', 'Microsoft YaHei UI', 'Microsoft YaHei', sans-serif;
}
.control-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  height: 82px;
  border-bottom: 1px solid #24364e;
}
.control-heading {
  display: flex;
  align-items: center;
  gap: 20px;
}
.control-home {
  display: grid;
  place-items: center;
  border: 1px solid #344861;
  border-radius: 7px;
  width: 33px;
  height: 33px;
  color: #a5bedf;
  background: transparent;
  cursor: pointer;
}
.control-home:hover {
  background: #1c304c;
}
.control-header h1 {
  font-size: 25px;
  font-weight: 600;
  letter-spacing: 0.4px;
  color: #ebf2fc;
}
.control-header h1 span {
  font-size: 13px;
  font-weight: 400;
  color: #7894b7;
  margin-left: 20px;
}
.control-header-actions {
  display: flex;
  align-items: center;
  gap: 24px;
}
.control-header-actions > span {
  font-size: 12px;
  color: #7b96b8;
}
.control-header-actions > button {
  background: transparent;
  border: 0;
  color: #a1b9d7;
  cursor: pointer;
  font-size: 13px;
  padding: 7px 0;
}
.control-header-actions > button:hover {
  color: #e9f1ff;
}
.control-header-actions .el-icon {
  font-size: 18px;
}
.control-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 23px 0 22px;
}
.control-scope {
  display: flex;
  gap: 13px;
  align-items: center;
  flex-wrap: wrap;
}
.control-scope > select,
.control-scope > input {
  height: 34px;
  border: 1px solid #334861;
  border-radius: 6px;
  background: #14273f;
  color: #b9cbe2;
  padding: 0 12px;
  font-size: 12px;
  color-scheme: dark;
  max-width: 220px;
}
.control-scope > select:nth-of-type(2) {
  width: 76px;
}
.control-scope label {
  display: flex;
  gap: 7px;
  align-items: center;
  font-size: 12px;
  color: #91a9c9;
  margin-left: 4px;
}
.control-scope label input {
  accent-color: #4a82d2;
}
.control-refresh {
  display: flex;
  align-items: center;
  gap: 8px;
  background: transparent;
  border: 0;
  color: #9cb7d6;
  font-size: 12px;
  cursor: pointer;
  padding: 8px;
}
.control-refresh > .el-icon {
  font-size: 16px;
}
.control-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 30px;
  margin: 0 0 25px;
  padding: 6px 0 25px;
  border-bottom: 1px solid #263a51;
}
.control-metrics > button {
  background: transparent;
  border: 0;
  padding: 0;
  text-align: left;
  color: #9bb2d0;
  cursor: pointer;
}
.control-metrics > button > span {
  font-size: 13px;
  line-height: 1.7;
}
.control-metrics p {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-top: 9px;
}
.control-metrics b {
  font-size: 32px;
  font-weight: 550;
  font-variant-numeric: tabular-nums;
  color: #edf5ff;
  line-height: 1.2;
  letter-spacing: -0.5px;
}
.control-metrics small {
  font-size: 12px;
  color: #8ba6c8;
}
.control-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 330px;
  gap: 24px;
  height: calc(100dvh - 346px);
  min-height: 460px;
  max-height: 900px;
}
.screen-map-panel {
  display: flex;
  flex-direction: column;
  min-width: 0;
  border: 1px solid #263e58;
  background: #10243c;
  border-radius: 10px;
  overflow: hidden;
}
.screen-map-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 14px;
  padding: 21px 23px;
  border-bottom: 1px solid #223a54;
  flex-shrink: 0;
}
.screen-map-heading > div {
  display: flex;
  gap: 17px;
  align-items: center;
}
.screen-map-heading h2 {
  font-size: 16px;
  color: #d7e7fa;
  font-weight: 550;
}
.screen-map-heading span {
  font-size: 12px;
  color: #819dbe;
}
.screen-map-heading > span {
  font-size: 11px;
  color: #8cb1ca;
  white-space: nowrap;
}
.screen-map {
  position: relative;
  flex: 1;
  min-height: 280px;
  overflow: hidden;
}
.screen-map :deep(.online-map-wrap),
.screen-map :deep(.screen-offline-map) {
  position: absolute;
  inset: 0;
  width: 100% !important;
  height: 100% !important;
}
.screen-map-legend {
  padding: 15px 22px;
  display: flex;
  align-items: center;
  gap: 22px;
  border-top: 1px solid #223a54;
  flex-wrap: wrap;
  font-size: 11px;
  color: #88a5c8;
}
.screen-map-legend > span {
  display: flex;
  align-items: center;
  gap: 7px;
  white-space: nowrap;
}
.screen-map-legend i {
  width: 5px;
  height: 5px;
  background: #61d5d2;
  border-radius: 50%;
}
.screen-map-legend i.site-dot {
  border-radius: 1px;
  background: #dab06f;
}
.screen-map-legend i.line-dot {
  width: 14px;
  height: 1px;
  background: #7aa7ce;
  border-radius: 0;
}
.screen-map-legend small {
  margin-left: auto;
  font-size: 11px;
  color: #7b96b8;
}
.map-mode-note {
  position: absolute;
  bottom: 12px;
  left: 15px;
  background: #10273fd9;
  padding: 8px 11px;
  border-radius: 5px;
  color: #adc5df;
  font-size: 11px;
  z-index: 10;
}
.map-mode-note button {
  border: 0;
  background: none;
  padding: 0;
  margin-left: 13px;
  color: #78c5d0;
  cursor: pointer;
  font: inherit;
}
.map-business-pop {
  position: absolute;
  bottom: 50px;
  left: 22px;
  z-index: 30;
  width: 300px;
  max-width: calc(100% - 44px);
  padding: 22px;
  background: #16304c;
  border: 1px solid #48637d;
  border-radius: 8px;
  box-shadow: 0 12px 25px #05101e66;
}
.map-business-pop > span {
  font-size: 12px;
  color: #8eb4cf;
}
.map-business-pop h3 {
  font-size: 16px;
  color: #e0efff;
  line-height: 1.6;
  margin-top: 10px;
}
.map-business-pop p {
  font-size: 13px;
  color: #adc1d9;
  line-height: 1.8;
  margin-top: 9px;
}
.map-business-pop > small {
  display: block;
  color: #c8ad80;
  font-size: 12px;
  line-height: 1.8;
  margin: 12px 0;
}
.map-business-pop > button:not(.map-pop-close) {
  background: none;
  border: 0;
  color: #9fc9ef;
  cursor: pointer;
  font-size: 12px;
  display: flex;
  gap: 9px;
  align-items: center;
  padding: 8px 0 0;
}
.map-pop-close {
  position: absolute;
  right: 11px;
  top: 11px;
  background: none;
  border: 0;
  color: #adc5df;
  cursor: pointer;
}
.screen-queue {
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: #10233b;
  border: 1px solid #263d56;
  border-radius: 10px;
  overflow: hidden;
}
.screen-queue-tabs {
  display: flex;
  gap: 25px;
  flex-shrink: 0;
  padding: 0 22px;
  border-bottom: 1px solid #263e58;
}
.screen-queue-tabs > button {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 23px 0 20px;
  margin-bottom: -1px;
  background: none;
  border: 0;
  border-bottom: 2px solid transparent;
  color: #8ba3c2;
  font-size: 14px;
  cursor: pointer;
  white-space: nowrap;
}
.screen-queue-tabs > button.active {
  color: #e1f0ff;
  border-bottom-color: #68b2d3;
}
.screen-queue-tabs span {
  font-size: 12px;
  color: #88a9cd;
}
.screen-queue-content {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 0 22px;
  scrollbar-width: thin;
  scrollbar-color: #36516f transparent;
}
.screen-queue-item {
  display: block;
  width: 100%;
  background: transparent;
  border: 0;
  border-bottom: 1px solid #263c55;
  text-align: left;
  padding: 25px 0;
  cursor: pointer;
}
.screen-queue-item:hover h3 {
  color: #a0d3fa;
}
.screen-queue-item h3 {
  font-size: 15px;
  font-weight: 500;
  line-height: 1.7;
  color: #d2e3f7;
  margin-top: 10px;
}
.screen-queue-item p {
  font-size: 12px;
  color: #90a9c8;
  line-height: 1.85;
  margin-top: 8px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.queue-risk-kind {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 12px;
  color: #e0b476;
}
.queue-item-action {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 12px;
  color: #8eb8dd;
  margin-top: 16px;
}
.gap-item h3 {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 13px;
  margin-top: 0;
}
.gap-item h3 b {
  font-size: 22px;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}
.gap-item h3 small {
  font-size: 12px;
  color: #8ba3c2;
  font-weight: 400;
}
.queue-net-note {
  display: block;
  margin-top: 9px;
  font-size: 12px;
  color: #c2b18c;
}
.queue-task-kind {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #85a7cb;
  font-size: 12px;
}
.queue-task-kind em {
  font-size: 11px;
  font-style: normal;
  color: #d9ac70;
}
.queue-task-meta {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  margin-top: 15px;
}
.queue-task-meta b {
  font-size: 21px;
  color: #d0e4fa;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}
.queue-task-meta b small {
  font-size: 12px;
  color: #85a3c5;
  font-weight: 400;
}
.queue-task-meta > span {
  font-size: 12px;
  color: #819fc0;
}
.screen-queue-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 17px 22px;
  border-top: 1px solid #263c55;
  flex-shrink: 0;
  font-size: 11px;
  color: #819bbd;
}
.screen-queue-footer button {
  background: none;
  border: 0;
  color: #9ec5e7;
  cursor: pointer;
  font-size: 12px;
  display: flex;
  gap: 5px;
  align-items: center;
}
.screen-empty {
  padding: 65px 12px;
  text-align: center;
  color: #819dbf;
}
.screen-empty > .el-icon {
  font-size: 28px;
  color: #65b1ad;
  margin-bottom: 19px;
}
.screen-empty h3 {
  font-weight: 400;
  font-size: 14px;
  color: #aec4df;
  line-height: 1.8;
}
.screen-empty p {
  font-size: 12px;
  color: #819dbf;
  line-height: 1.8;
  margin-top: 9px;
}
.control-stages {
  display: flex;
  align-items: center;
  gap: 30px;
  padding: 25px 0 0;
  color: #8ba5c6;
  font-size: 12px;
}
.control-stages > span:first-child {
  flex-shrink: 0;
  color: #96b0d0;
}
.control-stages > button {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 140px;
  background: none;
  border: 0;
  padding: 0;
  color: #9eb8d8;
  font-size: 12px;
  cursor: pointer;
}
.control-stages > button > div {
  height: 4px;
  width: 70px;
  background: #253c55;
  border-radius: 2px;
  overflow: hidden;
}
.control-stages > button i {
  display: block;
  height: 100%;
  background: #51a6b3;
  border-radius: 2px;
}
.control-stages > button b {
  font-size: 12px;
  font-weight: 400;
  white-space: nowrap;
}
.control-stages > small {
  margin-left: auto;
  font-size: 11px;
  white-space: nowrap;
  color: #7996b8;
}
.no-stages {
  color: #6f8eae;
}
.control-error {
  background: #503c29;
  color: #ecd2aa;
  border-radius: 7px;
  font-size: 13px;
  padding: 12px 16px;
  margin-bottom: 20px;
  display: flex;
  justify-content: space-between;
  gap: 20px;
}
.control-error button {
  background: none;
  border: 0;
  color: #ecd2aa;
  cursor: pointer;
  font: inherit;
}
.control-detail-record {
  padding: 22px 0;
  border-bottom: 1px solid #e6ecf4;
}
.control-detail-record > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 15px;
}
.control-detail-record h3 {
  font-size: 15px;
  color: #304b6e;
  font-weight: 550;
  line-height: 1.7;
}
.control-detail-record span,
.control-detail-record small {
  font-size: 12px;
  color: #788da8;
  line-height: 1.8;
}
.control-detail-record p {
  font-size: 13px;
  color: #6e839e;
  line-height: 1.8;
  margin: 12px 0;
}
.control-detail-record b {
  font-size: 15px;
  font-weight: 500;
  color: #395b85;
}
.control-detail-record > .el-button {
  margin-top: 15px;
  padding-left: 0;
}
.control-risk-detail > span {
  font-size: 13px;
  color: #9a763e;
}
.control-risk-detail h2 {
  font-size: 24px;
  line-height: 1.6;
  color: #304967;
  margin-top: 16px;
}
.control-risk-detail p {
  font-size: 14px;
  line-height: 1.9;
  color: #71839b;
  margin-top: 20px;
}
.control-risk-detail > .el-button {
  margin-top: 30px;
}
@media (min-width: 1800px) {
  .control-screen {
    padding-left: 42px;
    padding-right: 42px;
  }
  .control-workspace {
    grid-template-columns: minmax(0, 1fr) 370px;
    gap: 28px;
  }
  .control-header {
    height: 90px;
  }
  .control-metrics {
    margin-bottom: 30px;
    padding-bottom: 30px;
  }
  .control-metrics b {
    font-size: 38px;
  }
  .control-workspace {
    height: calc(100dvh - 375px);
  }
}
@media (max-width: 1100px) {
  .control-screen {
    padding: 0 23px 20px;
  }
  .control-workspace {
    grid-template-columns: minmax(0, 1fr) 290px;
    gap: 18px;
  }
  .control-header-actions {
    gap: 18px;
  }
  .control-header-actions > span {
    display: none;
  }
  .control-metrics {
    gap: 20px;
  }
  .screen-map-legend {
    gap: 17px;
  }
  .screen-map-legend small {
    width: 100%;
    margin: 0;
  }
  .screen-map-heading > div {
    gap: 10px;
  }
  .screen-map-heading > div > span {
    display: none;
  }
  .control-stages {
    gap: 20px;
    flex-wrap: wrap;
  }
  .control-stages > small {
    margin-left: auto;
  }
  .screen-queue-tabs {
    gap: 20px;
  }
}
@media (max-width: 700px) {
  .control-screen {
    padding: 0 16px 20px;
  }
  .control-header {
    height: 72px;
  }
  .control-heading {
    gap: 13px;
  }
  .control-header h1 {
    font-size: 20px;
  }
  .control-header h1 span {
    display: none;
  }
  .control-header-actions {
    gap: 17px;
  }
  .control-header-actions > button {
    font-size: 12px;
  }
  .control-header-actions > button:nth-of-type(2) {
    display: none;
  }
  .control-toolbar {
    padding: 20px 0;
  }
  .control-scope {
    gap: 10px;
    flex: 1;
  }
  .control-scope > select,
  .control-scope > input {
    max-width: 153px;
    padding: 0 9px;
    height: 34px;
  }
  .control-scope label {
    margin: 0;
    font-size: 11px;
  }
  .control-refresh {
    align-self: flex-start;
    padding: 7px 0;
    margin-top: 0;
  }
  .control-refresh > span {
    display: none;
  }
  .control-metrics {
    grid-template-columns: 1fr 1fr;
    gap: 24px 18px;
    margin-bottom: 22px;
    padding-bottom: 25px;
  }
  .control-metrics b {
    font-size: 29px;
  }
  .control-metrics > button > span {
    font-size: 12px;
  }
  .control-workspace {
    display: flex;
    flex-direction: column;
    height: auto;
    min-height: 0;
    gap: 22px;
    max-height: none;
  }
  .screen-map-panel {
    height: 410px;
    flex: none;
  }
  .screen-map {
    min-height: 0;
  }
  .screen-map-heading {
    padding: 19px 16px;
  }
  .screen-map-heading h2 {
    font-size: 14px;
  }
  .screen-map-heading > span {
    font-size: 10px;
  }
  .screen-map-legend {
    padding: 12px 16px;
    gap: 13px;
    font-size: 10px;
  }
  .screen-map-legend small {
    font-size: 10px;
  }
  .map-mode-note {
    font-size: 10px;
    left: 10px;
    bottom: 10px;
    max-width: calc(100% - 20px);
  }
  .map-mode-note button {
    margin-left: 10px;
  }
  .screen-queue {
    height: 350px;
    flex: none;
  }
  .screen-queue-tabs {
    padding: 0 19px;
    gap: 30px;
  }
  .screen-queue-tabs > button {
    padding: 19px 0 17px;
    font-size: 14px;
  }
  .screen-queue-content {
    padding: 0 20px;
  }
  .screen-queue-item {
    padding: 22px 0;
  }
  .screen-queue-footer {
    padding: 15px 19px;
  }
  .control-stages {
    gap: 18px;
    padding: 25px 2px 0;
    align-items: flex-start;
  }
  .control-stages > span:first-child {
    width: 100%;
    font-size: 12px;
  }
  .control-stages > small {
    margin: 0;
    width: 100%;
  }
  .control-stages > button {
    font-size: 11px;
    gap: 10px;
  }
  .control-stages > button > div {
    width: 65px;
  }
}
</style>
