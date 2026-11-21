<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useWorkspace, qty, money, dateText } from '@/stores/workspace'
const w = useWorkspace(),
  router = useRouter(),
  search = ref('')
const orders = computed(() =>
  w.state.orders.filter((o) =>
    (o.name + ' ' + o.number + ' ' + o.batch_code + ' ' + o.tracking_number)
      .toLowerCase()
      .includes(search.value.toLowerCase()),
  ),
)
function blocked(o) {
  const ids = o.allocations?.length ? o.allocations.map((a) => a.batch_id) : [o.batch_id]
  return ids.some((id) => {
    const b =
      w.state.batches.find((b) => b.id === id) ||
      w.market.flatMap((p) => p.batches).find((b) => b.id === id)
    return b && b.status !== 'released'
  })
}
const columns = computed(() => [
  {
    key: 'prepare',
    title: w.isBuyer ? '等待供货方发运' : '待拣货 / 装车',
    icon: 'Box',
    rows: orders.value.filter((o) => o.status === 'paid' && o.dispatched_quantity < o.quantity),
  },
  {
    key: 'transit',
    title: w.isBuyer ? '待到货验收' : '运输 / 部分到货',
    icon: 'Van',
    rows: orders.value.filter(
      (o) => o.status === 'shipped' || o.deliveries?.some((d) => d.status === 'shipped'),
    ),
  },
  {
    key: 'issue',
    title: '差异与处理',
    icon: 'Warning',
    rows: orders.value.filter(
      (o) =>
        o.status === 'issue' || o.cases?.some((c) => !['confirmed', 'rejected'].includes(c.status)),
    ),
  },
])
function open(o, action = '') {
  router.push({ path: '/orders', query: { order: o.id, ...(action ? { action } : {}) } })
}
</script>
<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1>{{ w.isBuyer ? '到货与验收' : '交付作业' }}</h1>
        <p>从批次与配送单找到当前任务，分批发运、分次验收，状态同步到订单。</p>
      </div>
      <el-button icon="Refresh" @click="w.refresh()">同步交付进度</el-button>
    </div>
    <div class="panel" style="margin-bottom: 24px">
      <div class="panel-body decision-toolbar">
        <el-input
          v-model="search"
          clearable
          prefix-icon="Search"
          placeholder="输入或扫描枪录入订单号、批次码、运单号"
          style="max-width: 520px"
        /><span class="small muted">扫码枪可直接输入；手机也可手动查找</span>
      </div>
    </div>
    <div class="task-kanban">
      <section v-for="c in columns" :key="c.key" class="task-column">
        <h2>
          <el-icon><component :is="c.icon" /></el-icon> {{ c.title }}
          <span class="muted">{{ c.rows.length }}</span>
        </h2>
        <article v-for="o in c.rows" :key="o.id" class="work-order">
          <div class="fact-line">
            <span>{{ o.number }}</span
            ><span v-if="o.is_demo" class="demo-tag">演示</span>
          </div>
          <h3>{{ o.name }}</h3>
          <div class="kv">
            <span>订单数量</span><b>{{ qty(o.quantity) }} {{ o.unit }}</b>
          </div>
          <div class="kv">
            <span>已发运 / 已合格验收</span
            ><b>{{ qty(o.dispatched_quantity) }} / {{ qty(o.accepted_quantity) }} {{ o.unit }}</b>
          </div>
          <div class="kv">
            <span>{{ w.isBuyer ? '供应方' : '采购方' }}</span
            ><b>{{ w.isBuyer ? o.supplier : o.buyer }}</b>
          </div>
          <p class="small muted" style="line-height: 1.8; margin-top: 12px">{{ o.address }}</p>
          <div v-if="o.promised_date" class="small" style="margin-top: 8px">
            约定 {{ o.promised_date }} 到货
          </div>
          <div
            v-for="d in o.deliveries?.filter((d) => d.status === 'shipped')"
            :key="d.id"
            class="info-strip"
            style="margin-top: 12px; font-size: 11px"
          >
            {{ d.carrier }} / {{ d.tracking_number }}<br />{{ qty(d.quantity) }} {{ o.unit }} 在途
          </div>
          <el-button
            v-if="c.key === 'prepare' && !w.isBuyer && blocked(o)"
            type="warning"
            plain
            size="small"
            @click="router.push('/recovery')"
            >批次待复核，查看补配</el-button
          ><el-button
            v-else-if="c.key === 'prepare' && !w.isBuyer"
            type="primary"
            size="small"
            @click="open(o, 'ship')"
            >登记本次发运</el-button
          ><el-button
            v-else-if="c.key === 'transit' && w.isBuyer"
            type="primary"
            size="small"
            @click="open(o, 'receive')"
            >称重并验收</el-button
          ><el-button v-else plain size="small" @click="open(o)">打开处理详情</el-button>
        </article>
        <div v-if="!c.rows.length" class="compact-empty">这一阶段暂无任务</div>
      </section>
    </div>
  </div>
</template>
