<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { useWorkspace, money, qty, dateText } from '@/stores/workspace'
import BusinessChart from '@/components/BusinessChart.vue'
const w = useWorkspace(),
  route = useRoute(),
  incidentId = ref(null),
  planId = ref(null),
  strategy = ref('stable'),
  marketScope = ref(false),
  flowUnit = ref('kg'),
  comparing = ref(false),
  busy = ref(false),
  creating = ref(false),
  view = ref('changes')
const incidentForm = reactive({
  batch_id: null,
  kind: 'quarantine',
  note: '',
  counted_quantity: 0,
  available_date: '',
})
const incidents = computed(() => w.collaboration.incidents),
  incident = computed(() => incidents.value.find((x) => x.id === incidentId.value))
const plans = computed(() =>
    w.collaboration.recoveries.filter((x) => x.incident_id === incidentId.value),
  ),
  plan = computed(() => plans.value.find((x) => x.id === planId.value) || plans.value[0])
const strategies = {
  stable: ['改动最少', '优先保留供应关系'],
  cost: ['成本优先', '比较当前采购与费用'],
  fast: ['交付优先', '优先较早可供货源'],
}
const statuses = {
  draft: '试算草稿',
  pending: '等待各方确认',
  executed: '已执行补配',
  rejected: '有参与方未接受',
  superseded: '已有更新方案',
}
const participants = computed(() => {
  if (!plan.value) return []
  const m = new Map()
  for (const row of plan.value.result.rows) {
    m.set(row.buyer_id, row.buyer + ' / 采购')
    m.set(
      row.seller_id,
      w.state.products.find((p) => p.owner === row.seller_id)?.supplier || '原供应方',
    )
    for (const p of row.parts) m.set(p.supplier_id, p.supplier + ' / 供货')
  }
  return [...m].map(([id, name]) => ({
    id,
    name,
    decision: plan.value.decisions[String(id)]?.action,
  }))
})
const decidingParty = computed(() =>
  plan.value?.participants.find(
    (id) =>
      (w.state.user.managed_supplier_ids || [w.state.user.id]).includes(id) &&
      !plan.value.decisions[String(id)],
  ),
)
const canDecide = computed(() => plan.value?.status === 'pending' && !!decidingParty.value)
watch(
  () => plan.value?.id,
  () => {
    const units = [...new Set(plan.value?.result.rows.map((r) => r.unit) || [])]
    if (!units.includes(flowUnit.value)) flowUnit.value = units[0] || 'kg'
  },
)
const chart = computed(() => {
  const rows = (plan.value?.result.rows || []).filter((r) => r.unit === flowUnit.value),
    nodes = [],
    links = [],
    seen = new Set()
  for (const r of rows) {
    for (const p of r.parts) {
      for (const [name, label] of [
        [`b${p.batch_id}`, p.batch_code],
        [`o${r.order_id}`, r.number],
      ])
        if (!seen.has(name)) {
          nodes.push({ name, display: label })
          seen.add(name)
        }
      links.push({
        source: `b${p.batch_id}`,
        target: `o${r.order_id}`,
        value: p.quantity,
        display: `${p.batch_code} → ${r.number}\n${qty(p.quantity)} ${r.unit}`,
      })
    }
  }
  return {
    tooltip: { renderMode: 'richText', formatter: (p) => p.data?.display || '' },
    series: [
      {
        type: 'sankey',
        left: 12,
        right: 12,
        top: 20,
        bottom: 20,
        nodeWidth: 12,
        nodeGap: 25,
        data: nodes,
        links,
        label: { formatter: (p) => p.data.display, color: '#315a43', fontSize: 11 },
        levels: [
          { depth: 0, itemStyle: { color: '#377c59' } },
          { depth: 1, itemStyle: { color: '#b9d09f' }, label: { position: 'left' } },
        ],
        lineStyle: { color: 'source', opacity: 0.22, curveness: 0.5 },
        emphasis: { focus: 'adjacency' },
      },
    ],
  }
})
watch(incidentId, () => (planId.value = null))
watch(
  plans,
  (rows) => {
    if (!rows.some((p) => p.id === planId.value)) planId.value = rows[0]?.id || null
  },
  { immediate: true },
)
async function calculate() {
  if (!incidentId.value) return
  busy.value = true
  try {
    const r = await w.act(
      'recovery/',
      { incident_id: incidentId.value, strategy: strategy.value, market: marketScope.value },
      '补配试算已完成，尚未改动订单',
    )
    planId.value = r.id
  } catch {
    // Operation errors are shown by the shared workspace action; dialog cancellation is intentional.
  } finally {
    busy.value = false
  }
}
async function compareStrategies() {
  comparing.value = true
  try {
    for (const key of ['stable', 'cost', 'fast']) {
      const r = await w.act(
        'recovery/',
        { incident_id: incidentId.value, strategy: key, market: marketScope.value },
        '',
      )
      planId.value = r.id
    }
  } catch {
    // Operation errors are shown by the shared workspace action; dialog cancellation is intentional.
  } finally {
    comparing.value = false
  }
}
async function createIncident() {
  try {
    const r = await w.act('incidents/', incidentForm, '异常已登记，受影响采购方已收到待办')
    incidentId.value = r.id
    creating.value = false
    await calculate()
  } catch {
    /* Optional state or user cancellation; keep the current business record. */
  }
}
async function decide(action) {
  try {
    if (action === 'accept')
      await ElMessageBox.confirm(
        '确认接受该方案列出的批次、数量与价差？所有参与方确认后会重新预留库存；额外款项仍需实际核对。',
        '确认补配条件',
        { confirmButtonText: '接受方案', cancelButtonText: '继续核对' },
      )
    await w.act(
      `recovery/${plan.value.id}/`,
      { action, party_id: decidingParty.value },
      action === 'publish' ? '方案已发送给相关采购与供货方' : '决定已记录，其他工作区同步可见',
    )
  } catch {
    /* Optional state or user cancellation; keep the current business record. */
  }
}
function selectIncident(i) {
  incidentId.value = i.id
  strategy.value = 'stable'
}
onMounted(async () => {
  await w.refresh(true)
  if (route.query.plan) {
    const p = w.collaboration.recoveries.find((x) => x.id === Number(route.query.plan))
    if (p) {
      incidentId.value = p.incident_id
      await Promise.resolve()
      planId.value = p.id
      return
    }
  }
  incidentId.value = Number(route.query.incident) || incidents.value[0]?.id
})
</script>
<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1>异常补配</h1>
        <p>先看影响，再调整未发运数量。批次、价格或供货关系的变化由参与方共同确认。</p>
      </div>
      <el-button v-if="!w.isBuyer" type="primary" icon="Warning" @click="creating = true"
        >登记供给异常</el-button
      >
    </div>
    <div class="recovery-grid">
      <aside class="panel">
        <div class="panel-head">
          <h2>供给异常</h2>
          <span class="small muted">{{ incidents.length }} 项</span>
        </div>
        <button
          v-for="i in incidents"
          :key="i.id"
          class="task-list-item"
          :class="{ active: incidentId === i.id }"
          @click="selectIncident(i)"
        >
          <div class="task-meta">
            <b>{{ i.batch_code }}</b
            ><span class="status-badge">{{ i.status === 'resolved' ? '已处理' : '待补配' }}</span>
          </div>
          <strong>{{ i.product }}</strong>
          <p>{{ i.note }}</p>
          <p>{{ dateText(i.created_at) }}</p>
        </button>
        <div v-if="!incidents.length" class="compact-empty">
          暂无登记的供给异常。<br />库存短缺、隔离或延迟发生时，从这里开始协调。
        </div>
      </aside>
      <div v-if="incident">
        <section class="panel">
          <div class="panel-body">
            <div class="decision-toolbar">
              <div>
                <h2>{{ incident.batch_code }} / {{ incident.product }}</h2>
                <p class="small muted" style="margin-top: 10px; line-height: 1.8">
                  {{ incident.note }}
                </p>
              </div>
              <el-button
                v-if="!w.isBuyer && incident.status === 'open'"
                :loading="busy"
                type="primary"
                @click="calculate"
                >生成补配方案</el-button
              >
            </div>
            <div v-if="!w.isBuyer" class="record-actions section-gap">
              <el-checkbox v-model="marketScope">比较其他已上架供货方</el-checkbox>
              <el-button :loading="comparing" plain @click="compareStrategies"
                >比较三种策略</el-button
              >
              <span class="small muted">跨供货方需所有参与方确认及供货款核对后执行发运</span>
            </div>
            <div v-if="!w.isBuyer" class="strategy-controls section-gap">
              <button
                v-for="(s, k) in strategies"
                :key="k"
                :class="{ active: strategy === k }"
                @click="strategy = k"
              >
                <b>{{ s[0] }}</b
                ><small>{{ s[1] }}</small>
              </button>
            </div>
          </div>
        </section>
        <section v-if="plans.length > 1" class="panel section-gap">
          <div class="panel-head">
            <h2>方案并排比较</h2>
            <span class="small muted">均为试算，确认后才改写预留</span>
          </div>
          <div class="recovery-plan-comparison">
            <button
              v-for="p in plans.slice(0, 6)"
              :key="p.id"
              :class="{ active: plan?.id === p.id }"
              @click="planId = p.id"
            >
              <b>{{ strategies[p.strategy]?.[0] }} #{{ p.id }}</b
              ><span
                >恢复 {{ p.result.summary.recovered_orders }} /
                {{ p.result.summary.affected_orders }} 笔</span
              ><strong
                >{{ p.result.summary.amount_change > 0 ? '+' : '' }}¥{{
                  money(p.result.summary.amount_change)
                }}</strong
              ><small
                >{{ p.result.summary.changed_links }} 处新连接 ·
                {{ p.result.summary.supplier_switches }} 次供应方切换</small
              >
            </button>
          </div>
        </section>
        <template v-if="plan"
          ><section class="panel section-gap" v-loading="busy">
            <div class="panel-head">
              <h2>
                方案 #{{ plan.id }} <span class="status-badge">{{ statuses[plan.status] }}</span>
              </h2>
              <el-select v-model="planId" style="width: 200px"
                ><el-option
                  v-for="p in plans"
                  :key="p.id"
                  :value="p.id"
                  :label="'#' + p.id + ' / ' + strategies[p.strategy][0]"
              /></el-select>
            </div>
            <div class="delta-strip">
              <div>
                <span>受影响订单</span
                ><b>{{ plan.result.summary.affected_orders }}<small> 笔</small></b>
              </div>
              <div>
                <span>已找齐替代量</span
                ><b>{{ plan.result.summary.recovered_orders }}<small> 笔</small></b>
              </div>
              <div>
                <span>方案金额变化</span
                ><b
                  >{{ plan.result.summary.amount_change >= 0 ? '+' : '' }}¥{{
                    money(plan.result.summary.amount_change)
                  }}</b
                >
              </div>
              <div>
                <span>计算耗时</span><b>{{ plan.result.summary.elapsed_ms }}<small> ms</small></b>
              </div>
            </div>
            <div class="panel-body">
              <div class="pill-tabs">
                <button :class="{ active: view === 'changes' }" @click="view = 'changes'">
                  逐单变化</button
                ><button :class="{ active: view === 'flow' }" @click="view = 'flow'">
                  补配流向
                </button>
              </div>
              <el-radio-group
                v-if="view === 'flow'"
                v-model="flowUnit"
                class="section-gap"
                size="small"
                ><el-radio-button
                  v-for="u in [...new Set(plan.result.rows.map((r) => r.unit))]"
                  :key="u"
                  :value="u"
                  >{{ u }}</el-radio-button
                ></el-radio-group
              >
              <template v-if="view === 'changes'"
                ><div v-for="r in plan.result.rows" :key="r.order_id" class="allocation-change">
                  <div class="before">
                    <b>{{ incident.batch_code }}</b
                    ><br />{{ r.number }}<br />待恢复 {{ qty(r.required) }} {{ r.unit }}<br />{{
                      r.buyer
                    }}
                  </div>
                  <el-icon><Right /></el-icon>
                  <div>
                    <div class="after">
                      <div v-for="p in r.parts" :key="p.batch_id">
                        <b>{{ p.batch_code }} / {{ p.supplier }}</b
                        ><br />{{ qty(p.quantity) }} {{ r.unit }} × ¥{{ money(p.price)
                        }}<br />供货参考 {{ p.delivery_days }} 天
                      </div>
                    </div>
                    <p v-if="r.shortfall" class="small warn" style="margin-top: 10px">
                      仍缺 {{ qty(r.shortfall) }} {{ r.unit }}，该方案不能发送确认
                    </p>
                    <div class="decision-toolbar" style="margin-top: 12px">
                      <span class="small muted"
                        >此订单价差 {{ r.delta >= 0 ? '+' : '' }}¥{{ money(r.delta) }}</span
                      ><router-link
                        v-if="w.state.orders.some((o) => o.id === r.order_id)"
                        :to="'/orders?order=' + r.order_id"
                        ><el-button link>核对原订单</el-button></router-link
                      >
                    </div>
                  </div>
                </div></template
              ><BusinessChart
                v-else-if="plan.result.rows.some((r) => r.parts.length)"
                :option="chart"
                height="360px"
              /><el-empty v-else description="没有可分配的替代连接" :image-size="70" />
              <p class="data-note">
                {{ plan.result.note }} 其他
                {{ plan.result.preserved_orders }} 笔有效安排保持原样；本次涉及
                {{ plan.result.summary.changed_links }} 条新连接、{{
                  plan.result.summary.supplier_switches
                }}
                次供应方切换。
              </p>
              <div class="approval-line">
                <span
                  v-for="p in participants"
                  :key="p.id"
                  class="approval-person"
                  :class="{ accepted: p.decision === 'accept' }"
                  >{{ p.name }} /
                  {{
                    p.decision === 'accept'
                      ? '已接受'
                      : p.decision === 'reject'
                        ? '未接受'
                        : '待决定'
                  }}</span
                >
              </div>
              <div class="sticky-action">
                <el-button
                  v-if="plan.status === 'draft' && plan.creator_id === w.state.user.id"
                  type="primary"
                  :disabled="
                    plan.result.rows.length === 0 ||
                    plan.result.rows.some((r) => r.shortfall > 0.005)
                  "
                  @click="decide('publish')"
                  >发送给各方确认</el-button
                ><template v-if="canDecide"
                  ><el-button @click="decide('reject')">暂不接受</el-button
                  ><el-button type="primary" @click="decide('accept')"
                    >接受本次补配条件</el-button
                  ></template
                ><span v-if="plan.status === 'executed'" class="good"
                  >库存与订单分配已更新；价差凭证在订单处理单中核对。</span
                >
              </div>
            </div>
          </section></template
        >
        <div v-else class="panel section-gap compact-empty">
          {{
            w.isBuyer
              ? '供应方正在准备替代方案，方案发送后你可在这里比较并确认。'
              : '选择补配策略后生成试算。试算不会预留库存或修改已确认订单。'
          }}
        </div>
      </div>
      <div v-else class="panel compact-empty">
        <el-icon :size="40"><Finished /></el-icon>
        <h2 style="margin: 16px 0">每一次变化，都有可确认的安排</h2>
        <p>异常发生后，集中查看受影响订单与替代方案。<br />已发运记录和其他有效订单保持原样。</p>
      </div>
    </div>
    <el-dialog v-model="creating" title="登记真实供给异常" width="560px"
      ><el-form label-position="top"
        ><el-form-item label="异常批次"
          ><el-select v-model="incidentForm.batch_id" filterable style="width: 100%"
            ><el-option
              v-for="b in w.state.batches"
              :key="b.id"
              :value="b.id"
              :label="b.code + ' / ' + b.product_name" /></el-select></el-form-item
        ><el-form-item label="异常类型"
          ><el-radio-group v-model="incidentForm.kind"
            ><el-radio-button value="quarantine">品质隔离</el-radio-button
            ><el-radio-button value="shortage">实称短缺</el-radio-button
            ><el-radio-button value="delay">供货延迟</el-radio-button></el-radio-group
          ></el-form-item
        ><el-form-item v-if="incidentForm.kind === 'shortage'" label="实际盘点数量"
          ><el-input-number
            v-model="incidentForm.counted_quantity"
            :min="0"
            :precision="2" /></el-form-item
        ><el-form-item v-if="incidentForm.kind === 'delay'" label="调整后的可供日期"
          ><el-date-picker
            v-model="incidentForm.available_date"
            value-format="YYYY-MM-DD" /></el-form-item
        ><el-form-item label="异常证据和说明"
          ><el-input v-model="incidentForm.note" type="textarea" :rows="4" /></el-form-item
      ></el-form>
      <div class="info-strip warning">
        登记后批次将进入隔离状态，并通知受影响采购方。实际库存短缺在补配释放预留后入账，不强行扣成负库存。
      </div>
      <template #footer
        ><el-button @click="creating = false">取消</el-button
        ><el-button type="primary" @click="createIncident">登记异常并试算补配</el-button></template
      ></el-dialog
    >
  </div>
</template>
