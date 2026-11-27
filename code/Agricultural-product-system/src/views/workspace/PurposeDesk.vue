<script setup>
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useWorkspace, money, qty, todayPlus, dateText } from '@/stores/workspace'
import request from '@/utils/request'
import BusinessChart from '@/components/BusinessChart.vue'
const w = useWorkspace(),
  router = useRouter(),
  route = useRoute(),
  mode = ref('net'),
  rows = ref([]),
  selected = ref([]),
  busy = ref(false),
  error = ref(''),
  evidence = ref(null),
  reviewed = ref(''),
  advanced = ref(false),
  comparing = ref(false),
  detail = ref(null),
  showUnavailable = ref(false)
const form = reactive({
  keyword: '苹果',
  required_usable: 80,
  quantity: 100,
  unit: 'kg',
  purpose: 'kitchen',
  process: '',
  budget: 10,
  deadline: todayPlus(3),
  min_size: 0,
  tolerance: 10,
  grade: '',
  packaging: '',
  flexible_fields: [],
})
const purposes = {
  fresh: ['门店鲜销', '整果陈列与鲜销', 'Shop'],
  kitchen: ['厨房加工', '按净用量安排原料', 'Dish'],
  juice: ['榨汁加工', '按处理方式核对净得率', 'ColdDrink'],
}
const signature = computed(() => JSON.stringify([mode.value, form])),
  stale = computed(() => !!reviewed.value && signature.value !== reviewed.value)
const chosen = computed(() => rows.value.filter((r) => selected.value.includes(r.batch.id)))
const chart = computed(() => {
  const list = rows.value
    .filter((r) => r.net_cost != null && selected.value.includes(r.batch.id))
    .slice(0, 3)
  return {
    grid: { left: 112, right: 43, top: 12, bottom: 25 },
    tooltip: {
      trigger: 'axis',
      renderMode: 'richText',
      formatter: (p) => p.map((x) => `${x.name}：¥${x.value} / 净可用${form.unit}`).join('\n'),
    },
    xAxis: {
      type: 'value',
      name: '元',
      splitLine: { lineStyle: { color: '#edf1f7' } },
      axisLabel: { color: '#94a6bd', fontSize: 10 },
    },
    yAxis: {
      type: 'category',
      data: list.map((r) => r.batch.code).reverse(),
      axisTick: { show: false },
      axisLine: { show: false },
      axisLabel: { color: '#718baa', fontSize: 10 },
    },
    series: [
      {
        type: 'bar',
        barMaxWidth: 15,
        label: { show: true, position: 'right', color: '#5a7caa', fontSize: 10, formatter: '¥{c}' },
        data: list
          .slice()
          .reverse()
          .map((r) => ({
            value: r.net_cost,
            batch_id: r.batch.id,
            itemStyle: {
              color: selected.value.includes(r.batch.id) ? '#426ce3' : '#bccde8',
              borderRadius: [0, 4, 4, 0],
            },
          })),
      },
    ],
  }
})
const displayed = computed(() => rows.value.filter((r) => showUnavailable.value || r.compatible))
const blockedCount = computed(() => rows.value.filter((r) => !r.compatible).length)
const imageOf = (r) => w.market.find((p) => p.id === r.batch.product_id)?.image_url
function normalize(r) {
  if (mode.value === 'net') return r
  return {
    ...r,
    gross: r.quantity,
    usable: r.usable_quantity,
    evidence: r.yield_rate
      ? {
          rate: r.yield_rate / 100,
          source: r.yield_source,
          process: form.process || '按对应作业记录',
        }
      : null,
    issues: r.issues.map((i) => i.reason),
  }
}
async function calculate() {
  const sent = signature.value
  busy.value = true
  error.value = ''
  try {
    const r = await request.post(
      mode.value === 'net' ? '/workspace/net-preview/' : '/workspace/compare/',
      { ...form, sort: 'net' },
      { timeout: 30000 },
    )
    rows.value = r.data.rows.map(normalize)
    selected.value = selected.value.filter((id) => rows.value.some((r) => r.batch.id === id))
    reviewed.value = sent
  } catch (e) {
    error.value = e.response?.data?.detail || '比较未完成，请核对条件后重试'
  } finally {
    busy.value = false
  }
}
function select(id) {
  selected.value = selected.value.includes(id)
    ? selected.value.filter((x) => x !== id)
    : [...selected.value.slice(-2), id]
}
function purpose(k) {
  form.purpose = k
  form.min_size = k === 'fresh' ? 70 : 0
  form.tolerance = k === 'fresh' ? 5 : 10
  form.process = ''
}
function add(r) {
  if (stale.value) return ElMessage.warning('条件已变化，请更新比较')
  const p = w.market.find((p) => p.id === r.batch.product_id)
  if (p)
    w.addCart(
      p,
      r.batch,
      r.gross,
      mode.value === 'net'
        ? {
            purpose: form.purpose,
            process: r.evidence.process,
            required_usable: form.required_usable,
            yield_record_id: r.evidence.id,
            yield_rate: r.evidence.rate,
          }
        : {},
    )
  else ElMessage.warning('货源资料正在同步，请稍后再试')
}
function toSheet(r) {
  if (stale.value) return ElMessage.warning('请先更新比较')
  const draft = {
    ...form,
    quantity: r.gross,
    required_usable: mode.value === 'net' ? form.required_usable : null,
    process: r.evidence?.process || form.process,
    reference: r.batch.code,
    confirmed: true,
  }
  router.push('/purchase-plans?draft=' + encodeURIComponent(JSON.stringify(draft)))
}
let handled = ''
watch(
  [() => route.query.draft, () => route.query.demand, () => w.state.demands],
  () => {
    const key = String(route.query.draft || route.query.demand || '')
    if (!key || handled === key) return
    if (route.query.draft) {
      try {
        Object.assign(form, JSON.parse(route.query.draft))
        handled = key
        calculate()
      } catch {
        /* Optional state or user cancellation; keep the current business record. */
      }
    } else {
      const d = w.state.demands.find((x) => x.id === Number(route.query.demand))
      if (d) {
        Object.assign(form, d, { deadline: d.deadline })
        mode.value = d.required_usable ? 'net' : 'gross'
        handled = key
        calculate()
      }
    }
  },
  { immediate: true },
)
onMounted(() => calculate())
</script>

<template>
  <div class="page purchase-focus">
    <div class="page-head">
      <div>
        <h1>用途采购</h1>
        <p>比较实际可用量与到货成本，选择合适的批次。</p>
      </div>
      <el-radio-group v-model="mode" aria-label="采购数量口径"
        ><el-radio-button value="net">按净用量</el-radio-button
        ><el-radio-button value="gross">按毛料量</el-radio-button></el-radio-group
      >
    </div>
    <section class="purchase-search" aria-label="采购条件">
      <el-form label-position="top" @submit.prevent="calculate">
        <el-form-item label="品种"
          ><el-input
            v-model="form.keyword"
            clearable
            placeholder="例如苹果"
            @keyup.enter="calculate"
        /></el-form-item>
        <el-form-item :label="mode === 'net' ? '需要净用量' : '采购毛料量'" class="search-quantity"
          ><div>
            <el-input-number
              v-if="mode === 'net'"
              v-model="form.required_usable"
              :min="0.01"
              :precision="2"
              :controls="false"
            /><el-input-number
              v-else
              v-model="form.quantity"
              :min="0.01"
              :precision="2"
              :controls="false"
            /><el-select v-model="form.unit"
              ><el-option
                v-for="u in mode === 'net' ? ['kg', '斤'] : ['kg', '斤', '箱', '件']"
                :key="u"
                :value="u"
            /></el-select></div
        ></el-form-item>
        <el-form-item label="使用用途"
          ><el-select :model-value="form.purpose" @change="purpose"
            ><el-option v-for="(v, k) in purposes" :key="k" :value="k" :label="v[0]" /></el-select
        ></el-form-item>
        <el-form-item label="要求到货日"
          ><el-date-picker
            v-model="form.deadline"
            type="date"
            value-format="YYYY-MM-DD"
            :clearable="false"
        /></el-form-item>
        <div class="search-actions">
          <el-button type="primary" :loading="busy" icon="Search" @click="calculate"
            >比较货源</el-button
          ><el-button text icon="Operation" @click="advanced = true">更多条件</el-button>
        </div>
      </el-form>
    </section>
    <div v-if="error" class="business-error">
      {{ error }}<el-button link @click="calculate">重试</el-button>
    </div>
    <div v-if="stale" class="purchase-changed">
      <el-icon><InfoFilled /></el-icon>条件已变化，请重新比较后采购。<el-button
        link
        @click="calculate"
        >更新结果</el-button
      >
    </div>
    <section class="purchase-results" v-loading="busy">
      <div class="results-top">
        <div>
          <h2>货源比较</h2>
          <span>{{ rows.filter((r) => r.compatible).length }} 个符合条件的批次</span>
        </div>
        <el-button :disabled="chosen.length < 2" @click="comparing = true"
          >对比已选{{ chosen.length ? ' (' + chosen.length + ')' : '' }}</el-button
        >
      </div>
      <div class="purchase-columns">
        <span>批次与供货方</span><span>建议毛料量</span><span>预计净可用量</span
        ><span>每净可用{{ form.unit }}成本</span><span>操作</span>
      </div>
      <article
        v-for="r in displayed"
        :key="r.batch.id"
        class="purchase-row"
        :class="{ chosen: selected.includes(r.batch.id), unavailable: !r.compatible }"
      >
        <div class="purchase-product">
          <el-checkbox
            :model-value="selected.includes(r.batch.id)"
            :disabled="!selected.includes(r.batch.id) && selected.length >= 3"
            :aria-label="'对比' + r.batch.code"
            @change="select(r.batch.id)"
          /><el-image v-if="imageOf(r)" :src="imageOf(r)" fit="cover" /><span
            v-else
            class="purchase-image-fallback"
            ><el-icon><Goods /></el-icon
          ></span>
          <div>
            <h3>
              {{ r.batch.product_name }}
              <span v-if="r.batch.is_demo" class="demo-inline">演示</span>
            </h3>
            <p>
              {{ r.batch.code }}<span>{{ r.batch.grade }}</span>
            </p>
            <small>{{ r.batch.supplier }}</small>
          </div>
        </div>
        <div class="purchase-value">
          <span class="mobile-field-name">建议毛料</span
          ><b
            >{{ r.gross == null ? '—' : qty(r.gross) }}<small>{{ form.unit }}</small></b
          ><span>{{ r.batch.packaging || '包装待核对' }}</span>
        </div>
        <div class="purchase-value">
          <span class="mobile-field-name">预计可用</span
          ><b
            >{{ r.usable == null ? '—' : qty(r.usable) }}<small>{{ form.unit }}</small></b
          ><button class="yield-evidence" @click="evidence = r">
            {{ r.evidence ? '净得率 ' + (r.evidence.rate * 100).toFixed(1) + '%' : '依据待补录' }}
          </button>
        </div>
        <div class="purchase-value purchase-cost">
          <span class="mobile-field-name">净可用成本</span
          ><b>{{ r.net_cost == null ? '待核实' : '¥' + money(r.net_cost) }}</b
          ><span v-if="r.evidence">{{ r.evidence.source }}</span
          ><span v-else>缺少称重依据</span>
        </div>
        <div class="purchase-row-action">
          <el-button
            v-if="r.compatible && w.isBuyer"
            type="primary"
            link
            :disabled="stale"
            @click="detail = r"
            >查看与采购 <el-icon><ArrowRight /></el-icon></el-button
          ><el-button v-else link @click="detail = r"
            >{{ r.compatible ? '查看详情' : '查看原因' }} <el-icon><ArrowRight /></el-icon
          ></el-button>
        </div>
      </article>
      <div v-if="!displayed.length && !busy" class="purchase-empty">
        <el-icon><Search /></el-icon>
        <h3>暂无符合条件的批次</h3>
        <p>调整采购条件，或查看未匹配批次的具体原因。</p>
        <el-button @click="advanced = true">调整条件</el-button>
      </div>
      <div class="purchase-results-foot">
        <span>最多选择 3 批对比，净得率来源可查看。</span
        ><el-button v-if="blockedCount" text @click="showUnavailable = !showUnavailable"
          >{{ showUnavailable ? '收起' : '查看' }}未匹配批次 ({{ blockedCount }})
          <el-icon><component :is="showUnavailable ? 'ArrowUp' : 'ArrowDown'" /></el-icon
        ></el-button>
      </div>
    </section>
    <el-drawer v-model="advanced" title="更多采购条件" :size="'min(440px, 100vw)'"
      ><el-form label-position="top" class="advanced-purchase-form"
        ><el-form-item label="加工方式"
          ><el-input v-model="form.process" placeholder="例如：去皮去核" /><small
            >留空时采用对应用途的最新称重记录。</small
          ></el-form-item
        ><el-form-item label="商品单价预算 / 元"
          ><el-input-number v-model="form.budget" :min="0.01" :precision="2" /></el-form-item
        ><el-form-item label="最小尺寸 / mm"
          ><el-input-number v-model="form.min_size" :min="0" :max="2000" /></el-form-item
        ><el-form-item label="外观瑕疵率上限 / %"
          ><el-input-number v-model="form.tolerance" :min="0" :max="100" /></el-form-item
        ><el-form-item label="等级要求"
          ><el-input v-model="form.grade" placeholder="可选" /></el-form-item
        ><el-form-item label="包装要求"
          ><el-input v-model="form.packaging" placeholder="可选" /></el-form-item></el-form
      ><template #footer
        ><el-button @click="advanced = false">返回</el-button
        ><el-button
          type="primary"
          :loading="busy"
          @click="
            async () => {
              await calculate()
              advanced = false
            }
          "
          >应用并比较</el-button
        ></template
      ></el-drawer
    >
    <el-drawer
      :model-value="!!detail"
      @close="detail = null"
      title="批次采购详情"
      :size="'min(490px, 100vw)'"
      ><template v-if="detail"
        ><div class="purchase-detail-title">
          <span>{{ detail.batch.code }}</span>
          <h2>{{ detail.batch.product_name }}</h2>
          <p>
            {{ detail.batch.grade }} · {{ detail.batch.packaging }} · {{ detail.batch.supplier }}
          </p>
        </div>
        <div class="purchase-detail-values">
          <div>
            <span>采购毛料</span
            ><b
              >{{ detail.gross == null ? '—' : qty(detail.gross) }}
              <small>{{ form.unit }}</small></b
            >
          </div>
          <el-icon><Right /></el-icon>
          <div>
            <span>预计净可用</span
            ><b
              >{{ detail.usable == null ? '—' : qty(detail.usable) }}
              <small>{{ form.unit }}</small></b
            >
          </div>
        </div>
        <div v-if="detail.pricing" class="purchase-price-details">
          <div class="kv">
            <span>商品金额</span><b>¥{{ money(detail.pricing.goods) }}</b>
          </div>
          <div class="kv">
            <span>包装费 / 运费</span
            ><b>¥{{ money(detail.pricing.packaging) }} / ¥{{ money(detail.pricing.freight) }}</b>
          </div>
          <div class="kv price-total">
            <span>本次到货成本</span><b>¥{{ money(detail.pricing.total) }}</b>
          </div>
        </div>
        <div class="purchase-evidence-summary">
          <span class="source-label">{{ detail.evidence?.source || '缺少用途称重依据' }}</span>
          <p>{{ detail.evidence?.process || '尚无对应用途记录' }}</p>
          <el-button link @click="evidence = detail"
            >查看称重依据 <el-icon><ArrowRight /></el-icon
          ></el-button>
        </div>
        <div v-if="detail.issues?.length" class="purchase-issues">
          <h3>未满足的条件</h3>
          <p v-for="reason in detail.issues" :key="reason">
            <el-icon><Warning /></el-icon>{{ reason }}
          </p>
        </div>
        <p v-if="detail.overage > 0" class="data-note section-gap">
          按包装增量取整，预计多出 {{ qty(detail.overage) }} {{ form.unit }} 净可用量。
        </p>
        <p class="data-note section-gap">
          样本称重用于估算，演示参数单独标识。实际可用量以验收为准。
        </p></template
      ><template #footer
        ><template v-if="detail?.compatible && w.isBuyer"
          ><el-button :disabled="stale" @click="toSheet(detail)">加入集采草稿</el-button
          ><el-button
            type="primary"
            :disabled="stale"
            @click="
              () => {
                add(detail)
                detail = null
              }
            "
            >加入采购清单</el-button
          ></template
        ><el-button v-else-if="detail" @click="router.push('/product/' + detail.batch.product_id)"
          >查看货源详情</el-button
        ></template
      ></el-drawer
    >
    <el-dialog v-model="comparing" title="已选批次对比" :width="'min(920px, 94vw)'"
      ><div class="selected-comparison">
        <article v-for="r in chosen" :key="r.batch.id">
          <h3>{{ r.batch.code }}</h3>
          <p>{{ r.batch.grade }} · {{ r.batch.supplier }}</p>
          <b
            >¥{{ money(r.net_cost) }}<small>/ 净可用{{ form.unit }}</small></b
          >
          <div class="kv">
            <span>采购毛料</span><b>{{ qty(r.gross) }} {{ form.unit }}</b>
          </div>
          <div class="kv">
            <span>净得率</span
            ><b>{{ r.evidence ? (r.evidence.rate * 100).toFixed(1) + '%' : '待核实' }}</b>
          </div>
          <div class="kv">
            <span>预计可用</span><b>{{ qty(r.usable) }} {{ form.unit }}</b>
          </div>
          <el-button v-if="w.isBuyer && r.compatible" :disabled="stale" @click="add(r)"
            >加入采购清单</el-button
          >
        </article>
      </div>
      <BusinessChart v-if="chosen.length" :option="chart" height="230px"
    /></el-dialog>
    <el-drawer
      :model-value="!!evidence"
      @close="evidence = null"
      title="本次采购使用的称重依据"
      :size="'min(490px, 100vw)'"
      ><template v-if="evidence"
        ><h2>{{ evidence.batch.code }}</h2>
        <div v-if="evidence.evidence" class="evidence-details">
          <div class="kv">
            <span>用途</span><b>{{ purposes[form.purpose][0] }}</b>
          </div>
          <div class="kv">
            <span>加工方式</span><b>{{ evidence.evidence.process }}</b>
          </div>
          <div class="kv">
            <span>记录来源</span><b>{{ evidence.evidence.source }}</b>
          </div>
          <div class="kv">
            <span>实际投入 / 可用</span
            ><b
              >{{ qty(evidence.evidence.input_weight) }} /
              {{ qty(evidence.evidence.usable_weight) }} {{ form.unit }}</b
            >
          </div>
          <div class="kv">
            <span>记录时间</span><b>{{ dateText(evidence.evidence.created_at) }}</b>
          </div>
          <p class="data-note section-gap">{{ evidence.evidence.note }}</p>
        </div>
        <el-empty v-else description="尚无该用途的独立称重依据" /><el-button
          class="section-gap"
          @click="router.push(w.isBuyer ? '/product/' + evidence.batch.product_id : '/grading')"
          >{{ w.isBuyer ? '查看货源详情' : '补充用途称重' }}</el-button
        ></template
      ></el-drawer
    >
  </div>
</template>
<style scoped>
.purchase-search {
  background: #fff;
  border: 1px solid #e4e9f0;
  border-radius: 12px;
  padding: 23px 24px;
  margin-bottom: 28px;
}
.purchase-search > .el-form {
  display: grid;
  grid-template-columns: minmax(120px, 0.9fr) minmax(200px, 1.25fr) minmax(135px, 0.95fr) minmax(
      145px,
      1fr
    ) auto;
  gap: 20px;
  align-items: end;
}
.purchase-search .el-form-item {
  margin: 0;
  min-width: 0;
}
.purchase-search .el-form-item :deep(.el-form-item__label) {
  font-size: 13px;
  color: #64748b;
  margin-bottom: 9px;
  height: auto;
  line-height: 1.5;
}
.purchase-search :deep(.el-input-number),
.purchase-search :deep(.el-date-editor) {
  width: 100%;
}
.search-quantity > :deep(.el-form-item__content) > div {
  display: flex;
  width: 100%;
  gap: 8px;
  flex-wrap: nowrap;
}
.search-quantity .el-select {
  width: 76px;
  flex-shrink: 0;
}
.search-quantity .el-input-number {
  flex: 1;
  min-width: 0;
  width: auto;
}
.search-actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-self: end;
}
.search-actions .el-button {
  margin: 0;
  min-height: 36px;
}
.search-actions > .el-button.is-text {
  font-size: 12px;
  min-height: 24px;
  height: 24px;
  padding: 0;
}
.purchase-changed {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  color: #8e692f;
  background: #fff7e6;
  padding: 12px 17px;
  margin-bottom: 20px;
  border-radius: 8px;
}
.purchase-results {
  border: 1px solid #e3e9f0;
  border-radius: 12px;
  background: #fff;
  overflow: hidden;
}
.results-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 24px;
}
.results-top > div {
  display: flex;
  align-items: center;
  gap: 18px;
}
.results-top h2 {
  font-size: 17px;
  color: #253c56;
  font-weight: 600;
}
.results-top span {
  font-size: 13px;
  color: #718096;
}
.purchase-columns,
.purchase-row {
  display: grid;
  grid-template-columns: minmax(280px, 2.1fr) minmax(120px, 0.85fr) minmax(130px, 0.95fr) minmax(
      140px,
      1fr
    ) 112px;
  gap: 20px;
  align-items: center;
  padding: 0 24px;
}
.purchase-columns {
  background: #f8fafc;
  padding-top: 14px;
  padding-bottom: 14px;
  color: #6c7e95;
  font-size: 12px;
  border-top: 1px solid #ecf0f5;
  border-bottom: 1px solid #ecf0f5;
}
.purchase-columns > span:last-child {
  text-align: right;
}
.purchase-row {
  min-height: 132px;
  padding-top: 26px;
  padding-bottom: 26px;
  border-bottom: 1px solid #edf0f5;
}
.purchase-row.chosen {
  background: #f7faff;
}
.purchase-row:hover {
  background: #f8faff;
}
.purchase-product {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}
.purchase-product > .el-checkbox {
  height: 26px;
  flex-shrink: 0;
  margin: 0;
}
.purchase-product > .el-image,
.purchase-image-fallback {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  flex-shrink: 0;
}
.purchase-image-fallback {
  display: grid;
  place-items: center;
  background: #f1f5fa;
  color: #8d9fb6;
  font-size: 24px;
}
.purchase-product > div:last-child {
  min-width: 0;
}
.purchase-product h3 {
  font-size: 14px;
  line-height: 1.65;
  font-weight: 600;
  color: #2c415b;
  overflow-wrap: anywhere;
}
.purchase-product p {
  font-size: 12px;
  color: #687e98;
  margin-top: 6px;
  line-height: 1.7;
  overflow-wrap: anywhere;
}
.purchase-product p span {
  margin-left: 9px;
}
.purchase-product small {
  display: block;
  margin-top: 3px;
  font-size: 12px;
  color: #7b8aa0;
}
.demo-inline {
  font-size: 11px;
  font-weight: 400;
  color: #937036;
  white-space: nowrap;
  margin-left: 5px;
}
.purchase-value {
  min-width: 0;
  font-variant-numeric: tabular-nums;
}
.purchase-value > b {
  display: block;
  font-size: 18px;
  font-weight: 550;
  color: #334e70;
  line-height: 1.5;
  white-space: nowrap;
}
.purchase-value > b small {
  font-size: 12px;
  color: #6f8098;
  font-weight: 400;
  margin-left: 5px;
}
.purchase-value > span:not(.mobile-field-name),
.yield-evidence {
  display: block;
  font-size: 12px;
  line-height: 1.8;
  color: #77869a;
  margin-top: 5px;
}
.yield-evidence {
  padding: 0;
  background: transparent;
  border: 0;
  color: #4f729a;
  cursor: pointer;
  text-align: left;
}
.yield-evidence:hover {
  color: #365ee9;
  text-decoration: underline;
}
.purchase-cost > b {
  font-size: 23px;
  color: #2d50bd;
  letter-spacing: -0.5px;
}
.purchase-row-action {
  justify-self: end;
}
.purchase-row-action > .el-button {
  font-size: 13px;
  white-space: nowrap;
}
.purchase-results-foot {
  padding: 16px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  font-size: 12px;
  color: #74859b;
}
.purchase-results-foot .el-button {
  font-size: 12px;
}
.purchase-empty {
  padding: 70px 24px;
  text-align: center;
}
.purchase-empty > .el-icon {
  font-size: 30px;
  color: #8da2bf;
}
.purchase-empty h3 {
  font-size: 16px;
  font-weight: 500;
  color: #3b5675;
  margin: 18px 0 10px;
}
.purchase-empty p {
  font-size: 13px;
  line-height: 1.8;
  color: #71839a;
  margin-bottom: 22px;
}
.mobile-field-name {
  display: none;
}
.advanced-purchase-form .el-form-item {
  margin-bottom: 25px;
}
.advanced-purchase-form small {
  display: block;
  line-height: 1.8;
  color: #70839c;
  font-size: 12px;
  margin-top: 8px;
}
.advanced-purchase-form .el-input-number {
  width: 100%;
}
.purchase-detail-title > span {
  font-size: 12px;
  color: #7189a7;
}
.purchase-detail-title h2 {
  font-size: 23px;
  line-height: 1.6;
  color: #273e5a;
  margin-top: 12px;
}
.purchase-detail-title p {
  font-size: 13px;
  color: #71829a;
  margin-top: 10px;
  line-height: 1.8;
}
.purchase-detail-values {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  margin: 30px 0;
  background: #f6f8fc;
  padding: 24px;
  border-radius: 10px;
}
.purchase-detail-values > div > span {
  font-size: 12px;
  color: #71849c;
}
.purchase-detail-values b {
  display: block;
  font-size: 28px;
  color: #385d8b;
  font-weight: 550;
  margin-top: 12px;
}
.purchase-detail-values b small {
  font-size: 13px;
  color: #71849c;
  font-weight: 400;
}
.purchase-detail-values > .el-icon {
  color: #99adc7;
}
.purchase-price-details .kv {
  font-size: 13px;
}
.purchase-price-details .price-total {
  margin-top: 10px;
  padding-top: 20px;
}
.price-total b {
  font-size: 23px;
  color: #2c50c4;
}
.purchase-evidence-summary {
  margin-top: 28px;
  padding-top: 22px;
  border-top: 1px solid #e6ebf2;
}
.purchase-evidence-summary p {
  font-size: 13px;
  color: #6c809b;
  margin: 13px 0;
}
.purchase-issues {
  margin-top: 24px;
}
.purchase-issues h3 {
  font-size: 14px;
  color: #7a5c2c;
  margin-bottom: 12px;
}
.purchase-issues p {
  display: flex;
  gap: 9px;
  font-size: 13px;
  line-height: 1.8;
  color: #8b733f;
  margin: 8px 0;
}
.purchase-issues .el-icon {
  margin-top: 5px;
  flex-shrink: 0;
}
.selected-comparison {
  display: flex;
  gap: 24px;
}
.selected-comparison > article {
  flex: 1;
  min-width: 0;
  padding: 15px 0;
}
.selected-comparison h3 {
  font-size: 16px;
  color: #304b6e;
  overflow-wrap: anywhere;
}
.selected-comparison p {
  font-size: 12px;
  color: #71829a;
  line-height: 1.8;
  margin: 8px 0;
}
.selected-comparison > article > b {
  font-size: 28px;
  color: #365ee9;
  font-weight: 550;
  display: block;
  margin: 25px 0;
}
.selected-comparison > article > b small {
  font-size: 12px;
  font-weight: 400;
  color: #7286a1;
  margin-left: 6px;
}
.selected-comparison .kv {
  font-size: 13px;
  gap: 12px;
}
.selected-comparison .el-button {
  margin-top: 18px;
}
.evidence-details .kv {
  font-size: 13px;
  gap: 20px;
}
.evidence-details .kv > b {
  text-align: right;
}
@media (max-width: 1350px) {
  .purchase-search > .el-form {
    grid-template-columns: minmax(100px, 1fr) minmax(170px, 1.3fr) minmax(110px, 1fr) minmax(
        130px,
        1fr
      );
    gap: 18px;
  }
  .search-actions {
    grid-column: 1/-1;
    flex-direction: row;
    align-items: center;
    gap: 20px;
  }
  .search-actions > .el-button.is-text {
    height: 36px;
    min-height: 36px;
  }
  .purchase-columns,
  .purchase-row {
    grid-template-columns: minmax(230px, 1.8fr) 100px 110px 130px 100px;
    gap: 16px;
  }
  .purchase-product {
    gap: 10px;
  }
  .purchase-product > .el-image {
    width: 40px;
    height: 40px;
  }
}
@media (max-width: 1150px) {
  .purchase-columns,
  .purchase-row {
    grid-template-columns: minmax(200px, 1.8fr) 85px 100px 115px;
    gap: 15px;
  }
  .purchase-columns > span:last-child {
    display: none;
  }
  .purchase-row-action {
    grid-column: 4;
    justify-self: start;
  }
  .purchase-row {
    row-gap: 12px;
  }
  .purchase-product {
    grid-row: 1/3;
  }
  .purchase-value {
    grid-row: 1;
  }
  .purchase-cost {
    grid-column: 4;
  }
  .purchase-value > b {
    font-size: 17px;
  }
  .purchase-cost > b {
    font-size: 22px;
  }
  .purchase-value > span:not(.mobile-field-name) {
    font-size: 11px;
  }
}
@media (max-width: 760px) {
  .purchase-search {
    padding: 19px;
    margin-bottom: 23px;
  }
  .purchase-search > .el-form {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    gap: 17px 14px;
  }
  .search-quantity > :deep(.el-form-item__content) > div {
    gap: 5px;
  }
  .search-quantity .el-select {
    width: 62px;
  }
  .search-actions {
    justify-content: space-between;
    gap: 12px;
  }
  .search-actions > .el-button:first-child {
    flex: 1;
  }
  .results-top {
    padding: 20px 17px;
    gap: 10px;
  }
  .results-top > div {
    display: block;
  }
  .results-top h2 {
    font-size: 16px;
  }
  .results-top span {
    display: block;
    margin-top: 7px;
    font-size: 12px;
  }
  .results-top > .el-button {
    font-size: 12px;
  }
  .purchase-columns {
    display: none;
  }
  .purchase-row {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 20px 8px;
    padding: 22px 17px;
    min-height: 0;
  }
  .purchase-product {
    grid-row: 1;
    grid-column: 1/-1;
    gap: 12px;
  }
  .purchase-product > .el-image {
    width: 42px;
    height: 42px;
  }
  .purchase-product > div:last-child {
    min-width: 0;
  }
  .purchase-product h3 {
    font-size: 14px;
  }
  .purchase-product p {
    margin-top: 3px;
  }
  .purchase-product small {
    display: none;
  }
  .purchase-value {
    grid-row: 2;
    grid-column: auto !important;
  }
  .purchase-value > span.mobile-field-name {
    display: block;
    font-size: 11px;
    color: #70839a;
    margin: 0 0 8px;
  }
  .purchase-value > b {
    font-size: 18px;
  }
  .purchase-value > b small {
    font-size: 11px;
    margin-left: 3px;
  }
  .purchase-cost > b {
    font-size: 20px;
  }
  .purchase-value > span:not(.mobile-field-name),
  .yield-evidence {
    font-size: 11px;
    line-height: 1.7;
  }
  .purchase-row-action {
    grid-row: 3;
    grid-column: 1/-1;
    justify-self: end;
    padding-top: 2px;
  }
  .purchase-results-foot {
    padding: 15px 17px;
    flex-wrap: wrap;
    gap: 6px;
  }
  .purchase-results-foot > span {
    font-size: 11px;
  }
  .purchase-search .el-form-item :deep(.el-form-item__label) {
    font-size: 12px;
  }
  .selected-comparison {
    gap: 15px;
    overflow-x: auto;
  }
  .selected-comparison > article {
    min-width: 145px;
  }
  .selected-comparison > article > b {
    font-size: 24px;
  }
  .selected-comparison > article > b small {
    display: block;
    margin: 6px 0 0;
  }
  .purchase-changed {
    font-size: 12px;
    align-items: flex-start;
  }
  .purchase-changed > .el-button {
    flex-shrink: 0;
  }
  .purchase-focus > .page-head .el-radio-group {
    margin-top: 2px;
  }
}
</style>
