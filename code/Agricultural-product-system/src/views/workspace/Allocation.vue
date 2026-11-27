<script setup>
import { ref, computed, onMounted } from 'vue'
import { useWorkspace, money, qty, dateText } from '@/stores/workspace'
import BusinessChart from '@/components/BusinessChart.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import request from '@/utils/request'
import { ElMessage } from 'element-plus'
const w = useWorkspace(),
  result = ref(null),
  original = ref(null),
  mode = ref('standard'),
  tab = ref('flow'),
  busy = ref(false),
  saving = ref(false),
  unit = ref('kg'),
  selectedCell = ref(null),
  selectedFlow = ref(null),
  scenarioBatch = ref(null),
  capacity = ref(0),
  savedId = ref(null),
  planName = ref('当日供需分货方案')
const bs = computed(() => (result.value?.batches || []).filter((b) => b.unit === unit.value)),
  ds = computed(() => (result.value?.demands || []).filter((d) => d.unit === unit.value)),
  links = computed(() => (result.value?.allocations || []).filter((a) => a.unit === unit.value))
const matrix = computed(
  () => new Map((result.value?.matrix || []).map((c) => [c.batch_id + '-' + c.demand_id, c])),
)
const scenarios = computed(() =>
  w.state.batches.filter((b) => b.status === 'released' && b.available > 0),
)
const changed = computed(() => {
  if (!original.value || !result.value) return 0
  const before = new Map(
    original.value.allocations.map((a) => [a.batch_id + '-' + a.demand_id, a.quantity]),
  )
  const after = new Map(
    result.value.allocations.map((a) => [a.batch_id + '-' + a.demand_id, a.quantity]),
  )
  return new Set(
    [...before.keys(), ...after.keys()].filter(
      (k) => Math.abs((before.get(k) || 0) - (after.get(k) || 0)) > 0.01,
    ),
  ).size
})
const chart = computed(() => {
  const nodes = [],
    seen = new Set()
  for (const a of links.value) {
    for (const [name, label] of [
      [`b${a.batch_id}`, a.batch_code + '\n' + a.product],
      [`d${a.demand_id}`, a.demand],
    ])
      if (!seen.has(name)) {
        nodes.push({ name, display: label })
        seen.add(name)
      }
  }
  return {
    tooltip: {
      trigger: 'item',
      formatter: (p) =>
        p.data?.source
          ? `${p.data.display}\n${qty(p.data.value)} ${unit.value}`
          : p.data?.display || '',
      renderMode: 'richText',
    },
    series: [
      {
        type: 'sankey',
        left: 15,
        right: 15,
        top: 25,
        bottom: 25,
        nodeWidth: 12,
        nodeGap: 22,
        layoutIterations: 32,
        emphasis: { focus: 'adjacency' },
        label: { color: '#405b49', fontSize: 11, formatter: (p) => p.data.display },
        levels: [
          {
            depth: 0,
            itemStyle: { color: '#327b59' },
            lineStyle: { color: 'source', opacity: 0.22 },
          },
          { depth: 1, itemStyle: { color: '#bdcf94' }, label: { position: 'left' } },
        ],
        data: nodes,
        links: links.value.map((a) => ({
          source: `b${a.batch_id}`,
          target: `d${a.demand_id}`,
          value: a.quantity,
          display: `${a.batch_code} → ${a.demand}`,
        })),
        lineStyle: { curveness: 0.48 },
      },
    ],
  }
})
async function calculate(scenario = false) {
  busy.value = true
  savedId.value = null
  try {
    const payload = { mode: mode.value }
    if (scenario && scenarioBatch.value)
      payload.capacities = { [scenarioBatch.value]: capacity.value }
    const r = (await request.post('/workspace/allocation/', payload, { timeout: 60000 })).data
    result.value = r
    selectedFlow.value = null
    if (!scenario) original.value = JSON.parse(JSON.stringify(r))
    selectedCell.value = null
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '计算未完成，请检查服务')
  } finally {
    busy.value = false
  }
}
async function save() {
  saving.value = true
  try {
    const payload = { mode: mode.value, name: planName.value }
    if (scenarioBatch.value && result.value?.capacities)
      payload.capacities = result.value.capacities
    const r = await w.act('plans/', payload, '方案已保存，可发送报价供采购商确认')
    savedId.value = r.id
    result.value = r.result
  } catch {
  } finally {
    saving.value = false
  }
}
async function publish(id) {
  saving.value = true
  try {
    await w.act(`plans/${id}/publish/`, {}, '分货报价已发送，采购商确认后生成订单')
    savedId.value = null
  } catch {
  } finally {
    saving.value = false
  }
}
function cell(b, d) {
  selectedCell.value = { batch: b, demand: d, ...matrix.value.get(b.id + '-' + d.id) }
}
function inspectFlow(data) {
  if (!data?.source) return
  selectedFlow.value = links.value.find(
    (a) => `b${a.batch_id}` === data.source && `d${a.demand_id}` === data.target,
  )
}
onMounted(() => calculate())
</script>
<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1>分货实验室</h1>
        <p>先核对条件，再计算分配。比较抽检证据与库存变化，最后由采购商确认成交。</p>
      </div>
      <div class="head-actions">
        <el-button
          icon="Refresh"
          :loading="busy"
          @click="
            () => {
              scenarioBatch = null
              calculate()
            }
          "
          >重新计算</el-button
        ><el-button
          type="primary"
          :loading="saving"
          :disabled="!result?.allocations.length"
          @click="save"
          >保存本次方案</el-button
        >
      </div>
    </div>
    <div class="lab-controls panel">
      <div class="mode-options">
        <button
          :class="{ active: mode === 'standard' }"
          @click="
            () => {
              mode = 'standard'
              calculate()
            }
          "
        >
          <el-icon><Operation /></el-icon>
          <div><b>基础适配</b><small>按规格、交期与观察缺陷率筛选</small></div></button
        ><button
          :class="{ active: mode === 'robust' }"
          @click="
            () => {
              mode = 'robust'
              calculate()
            }
          "
        >
          <el-icon><CircleCheck /></el-icon>
          <div><b>保守证据模式</b><small>使用95%抽检区间上界比较阈值</small></div>
        </button>
      </div>
      <div class="lab-unit">
        <span>查看单位</span
        ><el-select v-model="unit" style="width: 90px"
          ><el-option v-for="u in ['kg', '斤', '箱', '件']" :key="u" :value="u"
        /></el-select>
      </div>
    </div>
    <div class="metrics" style="margin-top: 20px">
      <div class="metric">
        <div class="metric-label">完全覆盖需求</div>
        <div class="metric-value">
          {{ result?.summary.covered_orders || 0
          }}<small> / {{ result?.summary.orders || 0 }} 笔</small>
        </div>
        <div class="metric-foot">按当前剩余需求计算</div>
      </div>
      <div class="metric">
        <div class="metric-label">方案采购金额</div>
        <div class="metric-value">¥{{ money(result?.summary.amount) }}</div>
        <div class="metric-foot">含已录入包装与运费，不代表利润或成交</div>
      </div>
      <div class="metric">
        <div class="metric-label">分配连接</div>
        <div class="metric-value">{{ result?.summary.links || 0 }}<small> 条</small></div>
        <div class="metric-foot">起订量、库存与需求上限约束</div>
      </div>
      <div class="metric">
        <div class="metric-label">本次计算耗时</div>
        <div class="metric-value">{{ result?.summary.elapsed_ms || 0 }}<small> ms</small></div>
        <div class="metric-foot">服务器实际记录</div>
      </div>
    </div>
    <section class="panel" v-loading="busy">
      <div class="toolbar">
        <div class="pill-tabs">
          <button :class="{ active: tab === 'flow' }" @click="tab = 'flow'">分货流向</button
          ><button :class="{ active: tab === 'matrix' }" @click="tab = 'matrix'">
            标准匹配矩阵</button
          ><button :class="{ active: tab === 'details' }" @click="tab = 'details'">
            精确分配明细
          </button>
        </div>
        <span class="small muted">{{ result?.method }}</span>
      </div>
      <div v-if="tab === 'flow'" class="panel-body">
        <div class="flow-labels"><span>可售批次 / 供给</span><span>采购需求 / 去向</span></div>
        <BusinessChart
          v-if="links.length"
          :option="chart"
          height="420px"
          @select="inspectFlow"
        /><el-empty
          v-else
          description="当前条件下没有可分配连接，查看匹配矩阵了解原因"
          :image-size="90"
        />
        <div v-if="selectedFlow" class="info-strip">
          <span
            >{{ selectedFlow.batch_code }} → {{ selectedFlow.demand }}：
            {{ qty(selectedFlow.quantity) }} {{ selectedFlow.unit }}， 单价 ¥{{
              money(selectedFlow.price)
            }}，采购额 ¥{{ money(selectedFlow.amount) }}</span
          >
          <el-button link type="primary" @click="tab = 'details'">查看分配明细</el-button>
        </div>
        <p class="data-note">
          连线宽度表示数量，仅在相同计量单位内绘制。试算不会预占库存；点击图中连线查看精确分配量。
        </p>
      </div>
      <div v-else-if="tab === 'matrix'" class="matrix-layout">
        <div class="matrix-scroll">
          <table class="match-table">
            <thead>
              <tr>
                <th>供货批次</th>
                <th v-for="d in ds" :key="d.id">
                  {{ d.title
                  }}<small>{{ qty(d.quantity) }}{{ d.unit }} · ¥{{ money(d.budget) }}以内</small>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="b in bs" :key="b.id">
                <th>
                  {{ b.code }}<small>{{ b.product_name }} · {{ b.size_mm }}mm</small>
                </th>
                <td v-for="d in ds" :key="d.id">
                  <button
                    :class="matrix.get(b.id + '-' + d.id)?.compatible ? 'match-yes' : 'match-no'"
                    @click="cell(b, d)"
                  >
                    <el-icon
                      ><CircleCheck v-if="matrix.get(b.id + '-' + d.id)?.compatible" /><Minus
                        v-else /></el-icon
                    >{{ matrix.get(b.id + '-' + d.id)?.compatible ? '条件适配' : '存在冲突' }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
          <el-empty
            v-if="!ds.length || !bs.length"
            description="当前单位下暂无批次或需求"
            :image-size="60"
          />
        </div>
        <div class="match-explanation">
          <template v-if="selectedCell"
            ><h3>{{ selectedCell.batch.code }}</h3>
            <p>{{ selectedCell.demand.title }}</p>
            <div v-if="selectedCell.compatible" class="info-strip">
              已满足当前模式的品种、单位、尺寸、等级、包装、预算及交期条件。仍需采购方确认。
            </div>
            <div v-for="reason in selectedCell.reasons" :key="reason" class="reason-row">
              <el-icon><Warning /></el-icon>{{ reason }}
            </div></template
          >
          <div v-else class="empty-state" style="padding: 35px 5px">
            <el-icon size="25"><Pointer /></el-icon>
            <p>点击矩阵单元格<br />查看判断依据</p>
          </div>
        </div>
      </div>
      <el-table v-else :data="links"
        ><el-table-column prop="batch_code" label="供货批次" width="145" /><el-table-column
          prop="product"
          label="货品"
          min-width="150"
        /><el-table-column prop="demand" label="采购需求" min-width="210" /><el-table-column
          label="分配量"
          width="120"
          ><template #default="{ row }"
            >{{ qty(row.quantity) }} {{ row.unit
            }}<small v-if="row.usable_quantity != null" class="data-note" style="display: block"
              >预计可用 {{ qty(row.usable_quantity) }} {{ row.unit }}</small
            ></template
          ></el-table-column
        ><el-table-column label="单价" width="110"
          ><template #default="{ row }">¥{{ money(row.price) }}</template></el-table-column
        ><el-table-column label="含录入费用金额" width="145"
          ><template #default="{ row }"
            ><b class="good">¥{{ money(row.amount) }}</b></template
          ></el-table-column
        ></el-table
      >
    </section>
    <div class="grid-equal section-gap">
      <section class="panel">
        <div class="panel-head">
          <h2>库存短缺推演</h2>
          <span class="demo-tag">场景试算 · 不改实物</span>
        </div>
        <div class="panel-body">
          <el-select
            v-model="scenarioBatch"
            placeholder="选择一个放行批次"
            style="width: 100%"
            @change="
              (id) => {
                capacity = scenarios.find((b) => b.id === id)?.available || 0
              }
            "
            ><el-option
              v-for="b in scenarios"
              :key="b.id"
              :label="b.code + ' · ' + b.product_name + ' · 可用' + b.available + b.unit"
              :value="b.id" /></el-select
          ><template v-if="scenarioBatch"
            ><div class="kv">
              <span>场景可用量 / {{ scenarios.find((b) => b.id === scenarioBatch)?.unit }}</span
              ><b>{{ qty(capacity) }}</b>
            </div>
            <el-slider
              v-model="capacity"
              :min="0"
              :max="scenarios.find((b) => b.id === scenarioBatch)?.available || 0"
              :step="1"
            /><el-button type="primary" plain :loading="busy" @click="calculate(true)"
              >按短缺数量重新分配</el-button
            ></template
          >
          <div v-if="original && result" class="scenario-compare">
            <div>
              <span>原方案金额</span><b>¥{{ money(original.summary.amount) }}</b>
            </div>
            <div>
              <span>场景金额变化</span
              ><b :class="result.summary.amount < original.summary.amount ? 'warn' : 'good'"
                >{{ result.summary.amount - original.summary.amount >= 0 ? '+' : ''
                }}{{ money(result.summary.amount - original.summary.amount) }}</b
              >
            </div>
            <div>
              <span>变化连接</span><b>{{ changed }} 条</b>
            </div>
          </div>
          <p class="data-note">
            场景使用全量约束重算，当前不宣称“增量重排算法创新”。已确认订单不会被试算改写。
          </p>
        </div>
      </section>
      <section class="panel">
        <div class="panel-head">
          <h2>未满足需求</h2>
          <span class="small muted">明确缺口，不强行分配</span>
        </div>
        <div class="panel-body">
          <div
            v-for="s in result?.shortfalls.filter((s) => s.remaining > 0.01)"
            :key="s.id"
            class="list-row"
          >
            <div>
              <h3>{{ s.title }}</h3>
              <p>已覆盖 {{ qty(s.filled) }} / {{ qty(s.quantity) }} {{ s.unit }}</p>
            </div>
            <b class="warn small"
              >{{ s.is_net ? '净用量缺口' : '缺' }} {{ qty(s.remaining) }} {{ s.unit }}</b
            >
          </div>
          <div
            v-if="result && !result.shortfalls.some((s) => s.remaining > 0.01)"
            class="empty-state"
            style="padding: 35px 0"
          >
            当前方案已覆盖全部可见需求。
          </div>
          <div v-if="savedId" class="info-strip section-gap">
            方案 #{{
              savedId
            }}
            已保存。发送后生成报价，由采购商确认，届时再校验并预留库存。<el-button
              type="primary"
              :loading="saving"
              style="margin-top: 12px"
              @click="publish(savedId)"
              >发送分货报价</el-button
            >
          </div>
        </div>
      </section>
    </div>
    <section class="panel section-gap">
      <div class="panel-head">
        <h2>已保存方案</h2>
        <span class="small muted">历史快照，发送时重新校验货源</span>
      </div>
      <el-table :data="w.state.plans"
        ><el-table-column prop="name" label="方案名称" min-width="180" /><el-table-column
          label="筛选模式"
          width="140"
          ><template #default="{ row }">{{
            row.mode === 'robust' ? '保守证据' : '基础适配'
          }}</template></el-table-column
        ><el-table-column label="采购金额" width="140"
          ><template #default="{ row }"
            >¥{{ money(row.result.summary?.amount) }}</template
          ></el-table-column
        ><el-table-column label="状态" width="130"
          ><template #default="{ row }"
            ><StatusBadge :value="row.status" /></template></el-table-column
        ><el-table-column label="保存时间" min-width="135"
          ><template #default="{ row }">{{ dateText(row.created_at) }}</template></el-table-column
        ><el-table-column label="操作" width="120"
          ><template #default="{ row }"
            ><el-button
              v-if="row.status === 'draft'"
              link
              type="primary"
              :loading="saving"
              @click="publish(row.id)"
              >发送报价</el-button
            ><span v-else class="small muted">等待买方处理</span></template
          ></el-table-column
        ></el-table
      >
    </section>
    <p class="data-note">
      分配采用现成优化求解器，不声称原创算法；保守模式是证据筛选对照。不同单位分别求解，尺寸须有可靠测量记录，抽样区间不能代替其他质量检查。
    </p>
  </div>
</template>
<style scoped>
.lab-controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px;
  gap: 15px;
  flex-wrap: wrap;
}
.mode-options {
  display: flex;
  gap: 9px;
}
.mode-options button {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 18px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  text-align: left;
  color: #708074;
}
.mode-options button.active {
  background: #edf5ec;
  border-color: #aecab0;
  color: #286a45;
}
.mode-options .el-icon {
  font-size: 23px;
}
.mode-options b {
  font-size: 13px;
  font-weight: 500;
  display: block;
}
.mode-options small {
  font-size: 10px;
  display: block;
  margin-top: 7px;
}
.lab-unit {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: var(--muted);
}
.metric-value small {
  font-size: 12px;
  font-weight: 400;
  color: var(--muted);
}
.flow-labels {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--muted);
  padding: 0 10px;
}
.matrix-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 235px;
}
.matrix-scroll {
  overflow: auto;
  padding: 10px 5px;
}
.match-table {
  border-collapse: collapse;
  min-width: 100%;
  font-size: 12px;
}
.match-table th {
  padding: 15px;
  text-align: left;
  font-weight: 500;
  background: #fafcf9;
  min-width: 170px;
}
.match-table small {
  display: block;
  color: var(--muted);
  font-size: 10px;
  margin-top: 7px;
  font-weight: 400;
}
.match-table td {
  padding: 12px;
  border-top: 1px solid var(--line);
  text-align: center;
}
.match-table td button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 0;
  border-radius: 5px;
  padding: 8px 10px;
  font-size: 11px;
  white-space: nowrap;
}
.match-yes {
  background: #e6f3e9;
  color: #26764c;
}
.match-no {
  background: #f3f1ec;
  color: #8b846d;
}
.match-explanation {
  border-left: 1px solid var(--line);
  padding: 22px;
  min-height: 250px;
}
.match-explanation > p {
  font-size: 12px;
  color: var(--muted);
  margin: 12px 0 20px;
}
.reason-row {
  font-size: 12px;
  display: flex;
  gap: 7px;
  align-items: center;
  color: #9a7836;
  padding: 9px 0;
}
.scenario-compare {
  margin-top: 25px;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}
.scenario-compare span {
  display: block;
  font-size: 10px;
  color: var(--muted);
  margin-bottom: 9px;
}
.scenario-compare b {
  font-size: 17px;
  font-weight: 500;
}
@media (max-width: 900px) {
  .matrix-layout {
    grid-template-columns: 1fr;
  }
  .match-explanation {
    border-left: 0;
    border-top: 1px solid var(--line);
    min-height: 100px;
  }
  .mode-options {
    flex-wrap: wrap;
  }
  .mode-options button {
    padding: 10px;
  }
}
</style>
