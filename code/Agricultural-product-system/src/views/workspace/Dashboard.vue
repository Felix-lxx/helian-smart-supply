<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useWorkspace, money, qty, dateText } from '@/stores/workspace'
import BusinessChart from '@/components/BusinessChart.vue'
import OriginMap from '@/components/OriginMap.vue'
import StatusBadge from '@/components/StatusBadge.vue'
const w = useWorkspace(),
  router = useRouter()
const stats = computed(() => w.state.stats),
  today = new Date().toLocaleDateString('zh-CN', { month: 'long', day: 'numeric', weekday: 'long' })
const tasks = computed(() =>
  w.isBuyer
    ? [
        ['待付款', stats.value.pending, 'Wallet', '/orders?status=pending'],
        ['待收货', stats.value.transit, 'Van', '/orders?status=shipped'],
        ['待处理差异', stats.value.issues, 'Warning', '/orders?status=issue'],
      ]
    : [
        [
          '待核对收款',
          w.state.orders.filter((o) => o.payment_status === 'review').length,
          'Wallet',
          '/orders',
        ],
        ['待发运', stats.value.shipping, 'Van', '/orders?status=paid'],
        [
          '待复核批次',
          w.state.batches.filter((b) => b.status !== 'released').length,
          'CircleCheck',
          '/quality',
        ],
      ],
)
const trend = computed(() => ({
  color: ['#247b59'],
  tooltip: { trigger: 'axis' },
  grid: { left: 50, right: 22, top: 25, bottom: 30 },
  xAxis: {
    type: 'category',
    data: stats.value.trend?.map((x) => x.date.slice(5)),
    axisLine: { lineStyle: { color: '#dce5df' } },
    axisTick: { show: false },
  },
  yAxis: {
    type: 'value',
    name: '订单 / 笔',
    minInterval: 1,
    splitLine: { lineStyle: { color: '#edf1ee' } },
    axisLabel: { color: '#819086' },
  },
  series: [
    {
      type: 'bar',
      barMaxWidth: 25,
      data: stats.value.trend?.map((x) => x.orders),
      itemStyle: { borderRadius: [4, 4, 0, 0] },
    },
  ],
}))
const batchChart = computed(() => ({
  color: ['#278663', '#dbb367', '#bbc7bf'],
  tooltip: { trigger: 'item', formatter: '{b}: {c} 批' },
  series: [
    {
      type: 'pie',
      radius: ['62%', '78%'],
      center: ['50%', '48%'],
      label: { show: false },
      data: [
        { name: '已放行', value: w.state.batches.filter((b) => b.status === 'released').length },
        { name: '待检查', value: w.state.batches.filter((b) => b.status === 'pending').length },
        {
          name: '隔离复核',
          value: w.state.batches.filter((b) => b.status === 'quarantine').length,
        },
      ],
    },
  ],
  legend: {
    bottom: 3,
    icon: 'circle',
    itemHeight: 8,
    itemWidth: 8,
    textStyle: { color: '#75847a', fontSize: 11 },
  },
}))
</script>
<template>
  <div class="page" v-loading="w.loading">
    <div class="page-head">
      <div>
        <h1>{{ w.isBuyer ? '采购工作台' : w.isAdmin ? '运营工作台' : '经营工作台' }}</h1>
        <p>
          {{ today }} · 欢迎回来，{{ w.state.user.username }}。{{
            w.isBuyer ? '从合适的货源开始，跟进每一笔交付。' : '掌握供需变化，把每一批货交付到位。'
          }}
        </p>
      </div>
      <div class="head-actions">
        <el-button :icon="'Refresh'" @click="w.refresh()">同步数据</el-button
        ><el-button type="primary" @click="router.push(w.isBuyer ? '/demands' : '/allocation')"
          >{{ w.isBuyer ? '发布采购需求' : '进入分货实验室'
          }}<el-icon style="margin-left: 8px"><Right /></el-icon
        ></el-button>
      </div>
    </div>
    <div class="metrics">
      <div class="metric">
        <div class="metric-label">{{ stats.scope }}已确认收款金额</div>
        <div class="metric-value">¥{{ money(stats.amount) }}</div>
        <div class="metric-foot">按收款确认记录计算 · 含标记演示的记录</div>
      </div>
      <div class="metric">
        <div class="metric-label">订单总量</div>
        <div class="metric-value">{{ qty(stats.orders) }}<small> 笔</small></div>
        <div class="metric-foot">全部交易状态，历史记录保留</div>
      </div>
      <div class="metric">
        <div class="metric-label">已完成验收</div>
        <div class="metric-value">{{ stats.completed || 0 }}<small> 笔</small></div>
        <div class="metric-foot">买方验收或双方确认处理完成</div>
      </div>
      <div class="metric">
        <div class="metric-label">{{ w.isBuyer ? '可选货源' : '管理批次' }}</div>
        <div class="metric-value">
          {{ w.isBuyer ? w.market.length : w.state.batches.length
          }}<small> {{ w.isBuyer ? '项' : '批' }}</small>
        </div>
        <div class="metric-foot">来源于当前可见业务数据</div>
      </div>
    </div>
    <div class="grid-2">
      <section class="panel">
        <div class="panel-head">
          <h2>今天，先处理这些</h2>
          <span class="small muted">待办直接连接业务</span>
        </div>
        <div class="task-grid">
          <button v-for="[name, count, icon, path] in tasks" :key="name" @click="router.push(path)">
            <el-icon><component :is="icon" /></el-icon><b>{{ count || 0 }}</b
            ><span>{{ name }}</span
            ><el-icon class="task-arrow"><Right /></el-icon>
          </button>
        </div>
        <div class="panel-head chart-heading">
          <h2>近七日订单</h2>
          <span class="small muted">按创建日期统计</span>
        </div>
        <BusinessChart :option="trend" height="225px" />
      </section>
      <section class="panel">
        <div class="panel-head">
          <h2>批次品质分布</h2>
          <router-link to="/quality" v-if="!w.isBuyer" class="small good"
            >查看品质工作台</router-link
          ><span v-else class="small muted">可见货源</span>
        </div>
        <div class="donut">
          <BusinessChart :option="batchChart" height="235px" />
          <div class="donut-center">
            <b>{{ w.state.batches.length }}</b
            ><span>可见批次</span>
          </div>
        </div>
        <div class="quality-summary">
          <span class="good"
            >{{ w.state.batches.filter((b) => b.status === 'released').length }} 批已放行</span
          ><span class="muted">放行依据以人工复核记录为准</span>
        </div>
      </section>
    </div>
    <div class="grid-2 section-gap">
      <section class="panel">
        <div class="panel-head">
          <h2>近期订单</h2>
          <router-link to="/orders" class="small good"
            >查看全部 <el-icon><Right /></el-icon
          ></router-link>
        </div>
        <el-table
          :data="w.state.orders.slice(0, 5)"
          @row-click="() => router.push('/orders')"
          style="cursor: pointer"
          ><el-table-column label="货品 / 订单" min-width="190"
            ><template #default="{ row }"
              ><div class="table-product">
                <el-image :src="row.image_url" class="thumb" fit="cover" />
                <div>
                  <strong>{{ row.name }}</strong
                  ><small>{{ row.number }}</small>
                </div>
              </div></template
            ></el-table-column
          ><el-table-column label="金额" width="120"
            ><template #default="{ row }"
              ><span class="amount">¥{{ money(row.total_amount) }}</span></template
            ></el-table-column
          ><el-table-column label="进度" width="120"
            ><template #default="{ row }"
              ><StatusBadge :value="row.status" /></template></el-table-column
        ></el-table>
        <div v-if="!w.state.orders.length" class="empty-state">
          还没有订单，从发布需求或选择货源开始。
        </div>
      </section>
      <section class="network-panel">
        <div class="network-top">
          <h2>连接每一处好产地</h2>
          <router-link to="/origins"
            >展开网络 <el-icon><TopRight /></el-icon
          ></router-link>
        </div>
        <OriginMap
          :products="w.market"
          height="250px"
          dark
          @select="(id) => router.push('/product/' + id)"
        />
        <p>仅展示已录入有效经纬度的货源 · 点击产地查看详情</p>
      </section>
    </div>
    <section class="panel section-gap">
      <div class="panel-head">
        <h2>业务动态</h2>
        <span class="small muted">来自跨端处理记录</span>
      </div>
      <div class="panel-body activity-list">
        <div v-for="n in w.state.notifications.slice(0, 4)" :key="n.id" class="list-row">
          <div>
            <h3>{{ n.title }}</h3>
            <p>{{ n.content }}</p>
          </div>
          <span class="small muted">{{ dateText(n.created_at) }}</span>
        </div>
        <p v-if="!w.state.notifications.length" class="muted small">
          订单、报价与质检变化会同步到这里。
        </p>
      </div>
    </section>
  </div>
</template>
<style scoped>
.metric-value small {
  font-size: 12px;
  font-weight: 400;
  color: var(--muted);
}
.task-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  padding: 8px 15px;
}
.task-grid button {
  border: 0;
  background: transparent;
  text-align: left;
  position: relative;
  padding: 22px 16px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  color: #4a6b58;
  border-radius: 8px;
}
.task-grid button:hover {
  background: #f1f6f2;
}
.task-grid b {
  font-size: 28px;
  text-align: right;
  font-weight: 600;
  color: #243d2d;
}
.task-grid button > .el-icon:first-child {
  font-size: 21px;
}
.task-grid span {
  font-size: 12px;
  color: #77887b;
}
.task-arrow {
  justify-self: end;
}
.chart-heading {
  padding-top: 13px;
  border-top: 1px solid var(--line);
  border-bottom: 0;
}
.donut {
  position: relative;
}
.donut-center {
  position: absolute;
  inset: 78px 0 auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  pointer-events: none;
}
.donut-center b {
  font-size: 33px;
  font-weight: 500;
}
.donut-center span {
  font-size: 11px;
  color: var(--muted);
  margin-top: 5px;
}
.quality-summary {
  display: flex;
  flex-direction: column;
  gap: 8px;
  text-align: center;
  font-size: 12px;
  padding: 12px 20px 25px;
}
.network-panel {
  background: #173a2e;
  border-radius: 12px;
  color: #e0eedc;
  overflow: hidden;
}
.network-top {
  padding: 23px 24px 0;
  display: flex;
  justify-content: space-between;
  gap: 10px;
}
.network-top h2 {
  font-size: 16px;
}
.network-top a {
  font-size: 11px;
  color: #b8d0b7;
}
.network-panel > p {
  font-size: 10px;
  color: #b7cbb9;
  padding: 0 24px 20px;
}
.activity-list {
  padding-top: 0;
  padding-bottom: 0;
}
@media (max-width: 760px) {
  .task-grid {
    padding: 5px;
  }
  .task-grid button {
    padding: 18px 8px;
  }
  .task-grid b {
    font-size: 24px;
  }
}
</style>
