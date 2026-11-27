<script setup>
defineOptions({ name: 'BusinessOverview' })
import { ref, reactive, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useWorkspace, qty, money, dateText, todayPlus } from '@/stores/workspace'
import { useBusinessFeed } from '@/composables/useBusinessFeed'
import request from '@/utils/request'
import StatusBadge from '@/components/StatusBadge.vue'
const w = useWorkspace(),
  router = useRouter(),
  tab = ref('tasks'),
  activity = ref(false),
  shortcuts = ref(false)
const filters = reactive({ date: todayPlus(0), unit: 'kg' })
const data = ref({ kpis: {}, orders: [], risks: [], stages: [], events: [], gaps: [], tasks: [] })
const { busy, error, updated, refresh } = useBusinessFeed(async () => {
  data.value = (await request.get('/workspace/control/', { params: filters, timeout: 30000 })).data
})
watch(
  () => JSON.stringify(filters),
  () => refresh(),
)
const pending = computed(() =>
  data.value.tasks.filter((t) => !['done', 'cancelled'].includes(t.status)),
)
const entries = computed(() =>
  w.isBuyer
    ? [
        ['门店集采', '汇总多门店采购需求', 'Tickets', '/purchase-plans'],
        ['用途采购', '按净用量比较货源', 'ScaleToOriginal', '/procurement'],
        ['订单与对账', '跟进交付与数量差额', 'Wallet', '/orders'],
      ]
    : [
        ['供货排程', '匹配需求与可供批次', 'Connection', '/allocation'],
        ['分级称重', '登记实际作业结果', 'SetUp', '/grading'],
        ['订单与对账', '跟进发运与款项核对', 'Wallet', '/orders'],
      ],
)
const tabs = computed(() => [
  ['tasks', '待处理任务', pending.value.length],
  ['orders', '今日交付', data.value.kpis.orders || 0],
  ['risks', '异常事项', data.value.risks.length],
])
const primary = computed(() =>
  w.isBuyer
    ? ['新建集采单', '/purchase-plans?create=1']
    : w.isAdmin
      ? ['打开调度中心', '/control']
      : ['进入现场作业', '/workboard'],
)
function open(path) {
  router.push(path)
}
function scoped(path, query = {}) {
  router.push({ path, query: { ...filters, active: '1', ...query } })
}
function taskAction(t) {
  open('/workboard?task=' + t.id)
}
</script>
<template>
  <div class="page focused-home" v-loading="busy && !updated">
    <div class="page-head">
      <div>
        <h1>工作台</h1>
        <p>
          {{
            w.isBuyer
              ? '处理今天的采购与到货'
              : w.isAdmin
                ? '跟进今天的交付与异常'
                : '处理今天的备货与发运'
          }}
        </p>
      </div>
      <div class="head-actions">
        <el-button class="mobile-shortcuts" @click="shortcuts = true">快捷入口</el-button
        ><el-button type="primary" icon="Plus" @click="open(primary[1])">{{
          primary[0]
        }}</el-button>
      </div>
    </div>
    <div v-if="error" class="business-error">
      {{ error }}<el-button link @click="refresh()">重试</el-button>
    </div>
    <div class="home-context">
      <div class="page-controls">
        <el-date-picker
          v-model="filters.date"
          type="date"
          value-format="YYYY-MM-DD"
          :clearable="false"
          style="width: 150px"
        /><el-select v-model="filters.unit" style="width: 80px"
          ><el-option v-for="u in ['kg', '斤', '箱', '件']" :key="u" :value="u" /></el-select
        ><el-button text icon="Refresh" @click="refresh()" aria-label="刷新工作台" />
      </div>
      <span v-if="data.kpis.demo_orders" class="source-label">含演示数据</span
      ><el-button text class="activity-entry" icon="Clock" @click="activity = true"
        >业务动态</el-button
      >
    </div>
    <section class="home-summary" aria-label="今日业务摘要">
      <button @click="scoped('/workboard')">
        <span>待处理任务</span><strong>{{ data.kpis.tasks_open || 0 }}<small>项</small></strong>
      </button>
      <button @click="scoped('/orders')">
        <span>当日交付</span
        ><strong
          >{{ data.kpis.completed || 0 }}<small>/ {{ data.kpis.orders || 0 }} 笔完成</small></strong
        >
      </button>
      <button @click="scoped('/demands', { status: 'open' })">
        <span>采购缺口</span
        ><strong
          >{{ qty(data.kpis.gap) }}<small>{{ filters.unit }}</small></strong
        >
      </button>
      <button @click="scoped('/accounts')">
        <span>待处理差额</span><strong><small>¥</small>{{ money(data.kpis.cases_amount) }}</strong>
      </button>
    </section>
    <div class="home-layout">
      <section class="home-queue">
        <div class="queue-tabs" role="tablist" aria-label="今日事项">
          <button
            v-for="[key, name, count] in tabs"
            :key="key"
            role="tab"
            :aria-selected="tab === key"
            :class="{ active: tab === key }"
            @click="tab = key"
          >
            {{ name }}<span>{{ count }}</span>
          </button>
        </div>
        <template v-if="tab === 'tasks'">
          <div class="queue-caption">
            <span>事项与货品</span><span>收货点 / 执行方</span><span>数量</span><span>操作</span>
          </div>
          <article v-for="t in pending.slice(0, 6)" :key="t.id" class="home-row">
            <div>
              <span class="row-kind">{{ t.kind_label }}</span>
              <h3>{{ t.product }}</h3>
              <small>{{ t.batch_code || t.number }}</small>
            </div>
            <div class="row-context">
              <b>{{ t.site || t.supplier || '待确认交接点' }}</b
              ><small>{{ t.assignee || '尚未领取' }}{{ t.overdue ? ' · 已超时' : '' }}</small>
            </div>
            <b class="row-quantity"
              >{{ qty(t.quantity) }}<small>{{ t.unit }}</small></b
            >
            <el-button
              type="primary"
              link
              @click="t.kind === 'pick' ? open('/workboard?task=' + t.id) : taskAction(t)"
              >处理任务<el-icon><ArrowRight /></el-icon
            ></el-button>
          </article>
          <div v-if="!pending.length" class="queue-empty">
            <el-icon><CircleCheck /></el-icon>
            <h3>所选日期没有待处理任务</h3>
            <p>实际发运后会生成到货验收任务。</p>
            <el-button @click="open('/workboard')">查看全部待办</el-button>
          </div>
          <div v-if="pending.length" class="queue-footer">
            <span>{{ pending.length > 6 ? '显示前6项待办' : '待办随实际业务进度更新' }}</span
            ><el-button link @click="scoped('/workboard')"
              >查看全部任务 <el-icon><ArrowRight /></el-icon
            ></el-button>
          </div>
        </template>
        <template v-else-if="tab === 'orders'">
          <div class="queue-caption">
            <span>货品与订单</span><span>收货点</span><span>进度</span><span>操作</span>
          </div>
          <article v-for="o in data.orders.slice(0, 6)" :key="o.id" class="home-row">
            <div>
              <h3>{{ o.name }}</h3>
              <small>{{ o.number }}</small>
            </div>
            <div class="row-context">
              <b>{{ o.site }}</b
              ><small>{{ qty(o.quantity) }} {{ o.unit }}</small>
            </div>
            <StatusBadge :value="o.status" /><el-button
              link
              type="primary"
              @click="open('/orders?order=' + o.id)"
              >查看订单 <el-icon><ArrowRight /></el-icon
            ></el-button>
          </article>
          <div v-if="!data.orders.length" class="queue-empty">
            <h3>所选日期暂无交付</h3>
            <p>调整到货日期，或建立一张集采单。</p>
          </div>
          <div class="queue-footer">
            <span>按约定到货日显示</span
            ><el-button link @click="scoped('/orders')"
              >全部订单 <el-icon><ArrowRight /></el-icon
            ></el-button>
          </div>
        </template>
        <template v-else>
          <article v-for="r in data.risks.slice(0, 6)" :key="r.id" class="home-risk">
            <span class="risk-symbol"
              ><el-icon><Warning /></el-icon
            ></span>
            <div>
              <span class="row-kind">{{ r.kind }}</span>
              <h3>{{ r.title }}</h3>
              <p>{{ r.note }}</p>
            </div>
            <el-button type="primary" link @click="open(r.route)"
              >去处理 <el-icon><ArrowRight /></el-icon
            ></el-button>
          </article>
          <div v-if="!data.risks.length" class="queue-empty">
            <el-icon><CircleCheck /></el-icon>
            <h3>当前没有需要协调的异常</h3>
          </div>
        </template>
      </section>
      <aside class="home-sidebar">
        <h2>常用操作</h2>
        <button
          v-for="[name, note, icon, path] in entries"
          :key="path"
          class="home-shortcut"
          @click="open(path)"
        >
          <el-icon><component :is="icon" /></el-icon
          ><span
            ><b>{{ name }}</b
            ><small>{{ note }}</small></span
          ><el-icon><ArrowRight /></el-icon>
        </button>
        <div class="home-progress">
          <div>
            <h2>交付进度</h2>
            <span>{{ data.kpis.completion == null ? '—' : data.kpis.completion + '%' }}</span>
          </div>
          <el-progress
            :percentage="Math.min(100, data.kpis.completion || 0)"
            :show-text="false"
            :stroke-width="5"
          />
          <p>已完成 {{ data.kpis.completed || 0 }} / {{ data.kpis.orders || 0 }} 笔订单</p>
          <el-button text @click="open('/control')"
            >打开履约调度中心 <el-icon><ArrowRight /></el-icon
          ></el-button>
        </div>
      </aside>
    </div>
    <el-drawer v-model="activity" title="业务动态" size="420px"
      ><div v-for="e in data.events.slice(0, 15)" :key="e.id" class="home-event">
        <b>{{ e.title }}</b>
        <p>{{ e.note }}</p>
        <small>{{ dateText(e.created_at) }}</small
        ><el-button v-if="e.order_id" link @click="open('/orders?order=' + e.order_id)"
          >查看关联订单</el-button
        >
      </div>
      <el-empty v-if="!data.events.length" description="暂无业务动态"
    /></el-drawer>
    <el-drawer v-model="shortcuts" title="常用操作" size="100%"
      ><button
        v-for="[name, note, icon, path] in entries"
        :key="path"
        class="home-shortcut"
        @click="open(path)"
      >
        <el-icon><component :is="icon" /></el-icon
        ><span
          ><b>{{ name }}</b
          ><small>{{ note }}</small></span
        ><el-icon><ArrowRight /></el-icon></button
    ></el-drawer>
  </div>
</template>
<style scoped>
.home-context {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
}
.home-context .activity-entry {
  margin-left: auto;
}
.home-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  padding: 0 0 30px;
  border-bottom: 1px solid #e0e5ed;
  margin-bottom: 32px;
  gap: 24px;
}
.home-summary button {
  background: transparent;
  border: 0;
  text-align: left;
  padding: 0 0 0 24px;
  border-left: 1px solid #dce3ed;
  cursor: pointer;
}
.home-summary button:first-child {
  padding-left: 0;
  border-left: 0;
}
.home-summary button > span {
  font-size: 13px;
  color: #63738a;
}
.home-summary strong {
  display: block;
  margin-top: 10px;
  font-size: 32px;
  line-height: 1.3;
  font-weight: 600;
  color: #162c48;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.6px;
}
.home-summary small {
  font-size: 13px;
  font-weight: 400;
  color: #6b788d;
  margin-left: 7px;
  letter-spacing: 0;
}
.home-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 260px;
  gap: 36px;
  align-items: start;
}
.home-queue {
  background: #fff;
  border: 1px solid #e4e9f0;
  border-radius: 12px;
  overflow: hidden;
}
.queue-tabs {
  display: flex;
  gap: 28px;
  padding: 0 24px;
  border-bottom: 1px solid #e7ebf2;
}
.queue-tabs > button {
  border: 0;
  background: transparent;
  padding: 21px 0 18px;
  font-size: 15px;
  color: #68768a;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  cursor: pointer;
  white-space: nowrap;
}
.queue-tabs > button.active {
  color: #264ebf;
  border-bottom-color: #365ee9;
  font-weight: 600;
}
.queue-tabs > button > span {
  font-size: 12px;
  color: #7c889a;
  margin-left: 9px;
  font-weight: 400;
}
.queue-caption,
.home-row {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(0, 1.15fr) 100px 100px;
  gap: 20px;
  align-items: center;
}
.queue-caption {
  padding: 14px 24px;
  background: #fafbfe;
  font-size: 12px;
  color: #78869a;
}
.queue-caption > span:last-child {
  text-align: right;
}
.home-row {
  padding: 20px 24px;
  border-bottom: 1px solid #edf0f5;
  min-height: 100px;
}
.home-row:last-child {
  border-bottom: 0;
}
.home-row h3,
.home-risk h3 {
  font-size: 15px;
  font-weight: 600;
  line-height: 1.6;
  color: #263b54;
}
.home-row small {
  display: block;
  font-size: 12px;
  line-height: 1.7;
  color: #78879b;
  margin-top: 4px;
  overflow-wrap: anywhere;
}
.row-kind {
  font-size: 12px;
  color: #6b7c92;
  display: block;
  margin-bottom: 5px;
}
.row-context b {
  font-weight: 400;
  font-size: 13px;
  line-height: 1.7;
  color: #53677f;
}
.row-quantity {
  font-size: 17px;
  font-weight: 550;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.row-quantity small {
  display: inline;
  font-size: 12px;
  margin-left: 5px;
  font-weight: 400;
}
.home-row > .el-button {
  justify-self: end;
  font-size: 13px;
  white-space: nowrap;
}
.queue-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 17px 24px;
  color: #79869a;
  font-size: 12px;
}
.home-sidebar > h2,
.home-progress h2 {
  font-size: 14px;
  color: #374d66;
  font-weight: 600;
  margin: 4px 0 14px;
}
.home-shortcut {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px 0;
  background: transparent;
  border: 0;
  border-bottom: 1px solid #e3e8f0;
  width: 100%;
  text-align: left;
  cursor: pointer;
}
.home-shortcut > .el-icon:first-child {
  color: #6883aa;
  font-size: 20px;
  flex-shrink: 0;
}
.home-shortcut > span {
  flex: 1;
  min-width: 0;
}
.home-shortcut b {
  font-size: 14px;
  font-weight: 500;
  color: #334e6f;
}
.home-shortcut small {
  display: block;
  font-size: 12px;
  line-height: 1.7;
  color: #77869c;
  margin-top: 4px;
}
.home-shortcut > .el-icon:last-child {
  color: #8a9bb1;
  font-size: 13px;
  flex-shrink: 0;
}
.home-progress {
  margin-top: 35px;
}
.home-progress > div:first-child {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 15px;
}
.home-progress h2 {
  margin: 0;
}
.home-progress > div > span {
  font-size: 14px;
  color: #46658d;
}
.home-progress p {
  font-size: 12px;
  line-height: 1.8;
  color: #75859a;
  margin-top: 12px;
}
.home-progress > .el-button {
  padding-left: 0;
  margin-top: 12px;
  font-size: 12px;
}
.queue-empty {
  padding: 70px 28px;
  text-align: center;
}
.queue-empty > .el-icon {
  font-size: 32px;
  color: #619b91;
  margin-bottom: 16px;
}
.queue-empty h3 {
  font-size: 16px;
  color: #405875;
  font-weight: 500;
}
.queue-empty p {
  font-size: 13px;
  color: #72839a;
  line-height: 1.8;
  margin-top: 10px;
}
.queue-empty > .el-button {
  margin-top: 22px;
}
.home-risk {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 23px 24px;
  border-bottom: 1px solid #edf0f5;
}
.risk-symbol {
  color: #ad813c;
  font-size: 20px;
  flex-shrink: 0;
}
.home-risk > div {
  flex: 1;
  min-width: 0;
}
.home-risk p {
  font-size: 13px;
  color: #718098;
  line-height: 1.8;
  margin-top: 6px;
  max-width: 58ch;
}
.home-risk > .el-button {
  white-space: nowrap;
}
.home-event {
  padding: 20px 0;
  border-bottom: 1px solid #e8edf3;
}
.home-event b {
  font-size: 14px;
  color: #304c6d;
}
.home-event p {
  font-size: 13px;
  color: #687d96;
  line-height: 1.8;
  margin: 8px 0;
}
.home-event small {
  font-size: 12px;
  color: #7a899f;
  display: block;
}
.home-event .el-button {
  padding-left: 0;
  margin-top: 12px;
}
.mobile-shortcuts {
  display: none;
}
@media (max-width: 1250px) {
  .home-layout {
    grid-template-columns: minmax(0, 1fr) 220px;
    gap: 24px;
  }
  .queue-caption,
  .home-row {
    grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr) 72px 80px;
    gap: 14px;
  }
  .queue-tabs {
    gap: 20px;
    padding: 0 20px;
  }
  .queue-caption,
  .home-row {
    padding-left: 20px;
    padding-right: 20px;
  }
  .home-summary strong {
    font-size: 29px;
  }
}
@media (max-width: 1050px) {
  .home-layout {
    grid-template-columns: 1fr;
  }
  .home-sidebar {
    display: none;
  }
  .mobile-shortcuts {
    display: inline-flex;
  }
}
@media (max-width: 600px) {
  .home-context {
    gap: 8px;
    margin-bottom: 24px;
    flex-wrap: wrap;
  }
  .home-context .source-label {
    margin-left: auto;
  }
  .home-context .activity-entry {
    display: none;
  }
  .home-summary {
    grid-template-columns: 1fr 1fr;
    gap: 26px 20px;
    padding-bottom: 26px;
    margin-bottom: 26px;
  }
  .home-summary button {
    padding: 0;
    border: 0;
  }
  .home-summary strong {
    font-size: 28px;
  }
  .home-summary small {
    font-size: 12px;
  }
  .queue-tabs {
    padding: 0 16px;
    gap: 17px;
    overflow-x: auto;
  }
  .queue-tabs > button {
    font-size: 13px;
    padding: 18px 0 15px;
  }
  .queue-tabs > button > span {
    margin-left: 5px;
  }
  .queue-caption {
    display: none;
  }
  .home-row {
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 12px;
    padding: 21px 18px;
  }
  .home-row .row-context {
    grid-row: 2;
    grid-column: 1;
  }
  .home-row .row-quantity,
  .home-row > .status-badge {
    grid-row: 1;
    grid-column: 2;
    justify-self: end;
  }
  .home-row > .el-button {
    grid-row: 2;
    grid-column: 2;
  }
  .home-row h3 {
    font-size: 14px;
  }
  .home-row .row-context b {
    font-size: 12px;
  }
  .home-row .row-context small {
    display: none;
  }
  .home-row .row-kind {
    margin-bottom: 4px;
  }
  .queue-footer {
    padding: 16px;
    font-size: 11px;
  }
  .home-risk {
    padding: 20px 17px;
    gap: 11px;
  }
  .home-risk .row-kind {
    font-size: 11px;
  }
  .home-risk h3 {
    font-size: 14px;
  }
  .home-risk p {
    font-size: 12px;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .home-risk > .el-button {
    font-size: 12px;
  }
  .risk-symbol {
    display: none;
  }
}
</style>
