<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useWorkspace, qty, money, todayPlus, dateText } from '@/stores/workspace'
import { useBusinessFeed } from '@/composables/useBusinessFeed'
import request from '@/utils/request'
const w = useWorkspace(),
  router = useRouter(),
  route = useRoute(),
  sheets = ref([]),
  companies = ref([]),
  selected = ref(Number(useRoute().query.sheet) || null),
  editing = ref(false),
  saving = ref(false),
  checking = ref(null),
  preview = ref(null),
  lineView = ref('open')
const purposes = { fresh: '门店鲜销', kitchen: '厨房加工', juice: '榨汁加工' }
const form = reactive({
  title: '',
  delivery_date: todayPlus(1),
  company_id: null,
  cutoff_at: '',
  template: false,
  note: '',
  lines: [],
})
let submissionKey = crypto.randomUUID()
const { busy, error, refresh } = useBusinessFeed(async () => {
  const [a, b] = await Promise.all([
    request.get('/workspace/sheets/', { timeout: 30000 }),
    request.get('/workspace/companies/'),
  ])
  sheets.value = a.data.items
  companies.value = b.data.filter(
    (c) => c.owner_role === 'retail' || (c.owner_role == null && c.owner_id === w.state.user.id),
  )
  if (!selected.value && sheets.value.length) selected.value = sheets.value[0].id
})
const company = computed(() => companies.value.find((c) => c.id === form.company_id)),
  sites = computed(() => company.value?.sites || []),
  active = computed(() => sheets.value.find((s) => s.id === selected.value))
const visibleLines = computed(() =>
  (active.value?.lines || []).filter(
    (l) =>
      lineView.value === 'all' ||
      (lineView.value === 'open' ? l.status === 'open' : l.status === 'ordered'),
  ),
)
const summaries = computed(() => {
  const map = {}
  for (const l of active.value?.lines || []) map[l.unit] = (map[l.unit] || 0) + l.quantity
  return map
})
function line(seed = {}) {
  return {
    key: crypto.randomUUID(),
    site_id: sites.value[0]?.id || null,
    keyword: '',
    quantity: 100,
    unit: 'kg',
    purpose: 'fresh',
    budget: 10,
    mode: 'gross',
    required_usable: 80,
    process: '去皮去核',
    confirmed: false,
    min_size: 0,
    packaging: '',
    arrival_window: '',
    ...seed,
  }
}
function create(source = null) {
  form.company_id = source?.company_id || companies.value[0]?.id || null
  Object.assign(form, {
    title: source ? source.title + ' · 复用' : '',
    delivery_date: todayPlus(1),
    cutoff_at: '',
    template: false,
    note: '',
    lines: [],
  })
  form.lines = source
    ? source.lines.map((l) =>
        line({ ...l, mode: l.required_usable ? 'net' : 'gross', confirmed: false }),
      )
    : [line()]
  submissionKey = crypto.randomUUID()
  editing.value = true
  preview.value = null
}
watch(
  () => form.company_id,
  () => {
    for (const l of form.lines)
      if (!sites.value.some((s) => s.id === l.site_id)) l.site_id = sites.value[0]?.id || null
  },
)
let openedCreate = false
watch(
  [() => route.query.create, () => companies.value.length],
  () => {
    if (route.query.create === '1' && !openedCreate && companies.value.length && w.isBuyer) {
      openedCreate = true
      create()
    }
  },
  { immediate: true },
)
let consumedDraft = ''
watch(
  [() => route.query.draft, () => companies.value.length],
  () => {
    if (
      !route.query.draft ||
      consumedDraft === route.query.draft ||
      !companies.value.length ||
      !w.isBuyer
    )
      return
    try {
      const draft = JSON.parse(route.query.draft)
      create()
      form.lines = [
        line({ ...draft, mode: draft.required_usable ? 'net' : 'gross', confirmed: true }),
      ]
      consumedDraft = route.query.draft
    } catch {
      /* Optional state or user cancellation; keep the current business record. */
    }
  },
  { immediate: true },
)
async function calculate(l) {
  if (!l.keyword) return ElMessage.warning('先填写品种')
  checking.value = l.key
  try {
    const r = await request.post(
      '/workspace/net-preview/',
      { ...l, deadline: form.delivery_date },
      { timeout: 30000 },
    )
    preview.value = { line: l, rows: r.data.rows }
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '反算未完成')
  } finally {
    checking.value = null
  }
}
function adopt(r) {
  preview.value.line.quantity = r.gross
  preview.value.line.confirmed = true
  preview.value.line.reference = r.batch.code
  preview.value = null
}
async function save() {
  if (!form.lines.length) return ElMessage.warning('请添加采购明细')
  if (form.lines.some((l) => l.mode === 'net' && !l.confirmed))
    return ElMessage.warning('请先对净用量明细反算并核对毛料采购量')
  saving.value = true
  try {
    const result = await w.act(
      'sheets/',
      {
        ...form,
        submission_key: submissionKey,
        lines: form.lines.map((l) => ({
          ...l,
          required_usable: l.mode === 'net' ? l.required_usable : null,
        })),
      },
      '门店集采单已发布，供应端可响应报价',
    )
    editing.value = false
    await refresh()
    selected.value = result.id
  } catch {
    // Operation errors are shown by the shared workspace action; dialog cancellation is intentional.
  } finally {
    saving.value = false
  }
}
function templateCSV() {
  const blob = new Blob(
    ['\ufeff品种,毛量,单位,用途,单价预算,门店\r\n苹果,100,kg,门店鲜销,8,填写已建门店名称\r\n'],
    { type: 'text/csv;charset=utf-8' },
  )
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = '门店集采导入模板.csv'
  a.click()
  URL.revokeObjectURL(a.href)
}
async function importCSV(event) {
  const file = event.target.files?.[0]
  if (!file) return
  if (file.size > 1024 * 1024) return ElMessage.warning('请选择1MB以内CSV')
  const text = (await file.text()).replace(/^\uFEFF/, '')
  const rows = []
  let fields = [],
    value = '',
    quoted = false
  for (let i = 0; i < text.length; i++) {
    const c = text[i]
    if (c === '"') {
      if (quoted && text[i + 1] === '"') {
        value += '"'
        i++
      } else quoted = !quoted
    } else if (c === ',' && !quoted) {
      fields.push(value)
      value = ''
    } else if ((c === '\n' || c === '\r') && !quoted) {
      if (c === '\r' && text[i + 1] === '\n') i++
      fields.push(value)
      if (fields.some(Boolean)) rows.push(fields)
      fields = []
      value = ''
    } else value += c
  }
  if (value || fields.length) {
    fields.push(value)
    rows.push(fields)
  }
  if (quoted) return ElMessage.warning('CSV引号未闭合')
  if (rows.length > 101) return ElMessage.warning('一次最多导入100项')
  const parsed = rows.slice(1).map((r) =>
    line({
      keyword: r[0]?.trim(),
      quantity: Number(r[1]),
      unit: r[2] || 'kg',
      purpose: Object.keys(purposes).find((k) => purposes[k] === r[3]) || r[3] || 'fresh',
      budget: Number(r[4]),
      site_id: sites.value.find((s) => s.name === r[5]?.trim())?.id || null,
    }),
  )
  if (
    !parsed.length ||
    parsed.some(
      (l) =>
        !l.keyword ||
        !Number.isFinite(l.quantity) ||
        l.quantity <= 0 ||
        !Number.isFinite(l.budget) ||
        l.budget <= 0 ||
        !['kg', '斤', '箱', '件'].includes(l.unit) ||
        !purposes[l.purpose],
    )
  )
    return ElMessage.warning('CSV中存在无效品种、数量、单位、用途或预算')
  form.lines = parsed
  ElMessage.success('已导入草稿，请逐项核对门店与数量')
  event.target.value = ''
}
</script>
<template>
  <div class="page purchase-plans" v-loading="busy && !sheets.length">
    <div class="page-head">
      <div>
        <h1>{{ editing ? '编制门店集采单' : '门店集采单' }}</h1>
        <p>
          {{
            editing
              ? '把多个门店的品项、用途和到货要求放在一张单里。'
              : '从门店需求开始，贯通报价、拆单与实际交付。'
          }}
        </p>
      </div>
      <div class="head-actions">
        <el-button v-if="editing" @click="editing = false">返回采购单</el-button
        ><el-button v-if="!editing && w.isBuyer" type="primary" icon="Plus" @click="create()"
          >新建集采单</el-button
        ><el-button v-if="editing" type="primary" :loading="saving" @click="save()"
          >发布采购需求</el-button
        >
      </div>
    </div>
    <div v-if="error" class="business-error">
      {{ error }}<el-button link @click="refresh()">重试</el-button>
    </div>
    <template v-if="editing"
      ><section class="panel">
        <div class="panel-head">
          <h2>采购主体与到货安排</h2>
          <span class="small muted">发布前核对收货点与实际数量</span>
        </div>
        <div class="panel-body sheet-basics">
          <el-form-item label="采购主体"
            ><el-select v-model="form.company_id" placeholder="选择已建立主体"
              ><el-option
                v-for="c in companies"
                :key="c.id"
                :value="c.id"
                :label="c.name" /></el-select></el-form-item
          ><el-form-item label="采购单名称"
            ><el-input v-model="form.title" placeholder="例如：周一门店与厨房集采" /></el-form-item
          ><el-form-item label="约定到货日"
            ><el-date-picker
              v-model="form.delivery_date"
              type="date"
              value-format="YYYY-MM-DD"
              :clearable="false" /></el-form-item
          ><el-form-item label="报价截单时间"
            ><el-date-picker
              v-model="form.cutoff_at"
              type="datetime"
              value-format="YYYY-MM-DDTHH:mm:ss"
              placeholder="可选，按实际约定填写"
          /></el-form-item>
        </div>
      </section>
      <section class="panel section-gap">
        <div class="panel-head">
          <h2>
            门店 × 品项明细 <span class="small muted">{{ form.lines.length }} 项</span>
          </h2>
          <div class="record-actions">
            <el-button link @click="templateCSV" icon="Download">模板</el-button
            ><label class="csv-import"
              ><el-icon><Upload /></el-icon>导入CSV<input
                type="file"
                accept=".csv,text/csv"
                @change="importCSV" /></label
            ><el-button size="small" icon="Plus" @click="form.lines.push(line())"
              >增加品项</el-button
            >
          </div>
        </div>
        <div v-if="!sites.length" class="sheet-tip">
          先在“企业与岗位”建立收货门店，或在明细展开项填写收货地址。<router-link to="/companies"
            >维护企业与站点</router-link
          >
        </div>
        <div class="sheet-line" v-for="(l, i) in form.lines" :key="l.key">
          <div class="sheet-line-heading">
            <b>品项 {{ i + 1 }}</b
            ><span v-if="l.mode === 'net' && l.confirmed" class="source-label"
              >毛量依据：{{ l.reference }}</span
            ><el-button
              v-if="form.lines.length > 1"
              link
              type="danger"
              @click="form.lines.splice(i, 1)"
              >移除</el-button
            >
          </div>
          <div class="sheet-line-grid">
            <el-form-item label="收货门店"
              ><el-select v-model="l.site_id" placeholder="选择门店"
                ><el-option
                  v-for="s in sites"
                  :key="s.id"
                  :value="s.id"
                  :label="s.name" /></el-select></el-form-item
            ><el-form-item label="采购品种"
              ><el-input
                v-model="l.keyword"
                placeholder="苹果 / 黄瓜"
                @input="l.confirmed = false" /></el-form-item
            ><el-form-item label="用途"
              ><el-select v-model="l.purpose" @change="l.confirmed = false"
                ><el-option
                  v-for="(n, k) in purposes"
                  :key="k"
                  :value="k"
                  :label="n" /></el-select></el-form-item
            ><el-form-item label="数量口径"
              ><el-select v-model="l.mode" @change="l.confirmed = false"
                ><el-option value="gross" label="毛料采购量" /><el-option
                  value="net"
                  label="净可用量" /></el-select></el-form-item
            ><el-form-item :label="l.mode === 'net' ? '需要净用量' : '采购数量'"
              ><el-input-number
                v-if="l.mode === 'net'"
                v-model="l.required_usable"
                :min="0.01"
                :precision="2"
                @change="l.confirmed = false" /><el-input-number
                v-else
                v-model="l.quantity"
                :min="0.01"
                :precision="2" /></el-form-item
            ><el-form-item label="单位"
              ><el-select v-model="l.unit" @change="l.confirmed = false"
                ><el-option
                  v-for="u in ['kg', '斤', '箱', '件']"
                  :key="u"
                  :value="u" /></el-select></el-form-item
            ><el-form-item label="商品单价预算 / 元"
              ><el-input-number v-model="l.budget" :min="0.01" :precision="2"
            /></el-form-item>
          </div>
          <div class="sheet-line-extra">
            <el-input
              v-if="!l.site_id"
              v-model="l.destination"
              placeholder="收货地址"
              style="max-width: 320px"
            /><el-input
              v-model="l.arrival_window"
              placeholder="到货时段，例如 07:00—09:00"
              style="max-width: 250px"
            /><template v-if="l.mode === 'net'"
              ><el-input
                v-model="l.process"
                placeholder="加工方式"
                style="max-width: 190px"
                @input="l.confirmed = false"
              /><el-button
                plain
                type="primary"
                :loading="checking === l.key"
                @click="calculate(l)"
                >{{ l.confirmed ? '重新反算' : '反算并核对毛量' }}</el-button
              ><span class="small muted" v-if="l.confirmed"
                >参考采购 {{ qty(l.quantity) }} {{ l.unit }}</span
              ></template
            >
          </div>
        </div>
        <div class="sheet-editor-footer">
          <el-checkbox v-model="form.template">保留为可复用采购模板</el-checkbox
          ><el-input v-model="form.note" placeholder="本单其他交付约定" style="max-width: 430px" />
        </div></section
    ></template>
    <div v-else class="sheet-layout">
      <aside class="panel sheet-list">
        <div class="panel-head">
          <h2>采购单记录</h2>
          <span class="small muted">{{ sheets.length }} 张</span>
        </div>
        <button
          v-for="s in sheets"
          :key="s.id"
          class="sheet-list-item"
          :class="{ active: selected === s.id }"
          @click="selected = s.id"
        >
          <div>
            <b>{{ s.title }}</b
            ><span>{{ s.delivery_date }}</span>
          </div>
          <p>{{ s.company }}</p>
          <small
            >{{ s.lines.length }} 个品项 · {{ s.order_count }} 笔关联订单
            <em v-if="s.template">可复用</em></small
          >
        </button>
        <div v-if="!sheets.length" class="empty-business">
          还没有集采单<br />从一张门店采购单开始
        </div>
      </aside>
      <div v-if="active">
        <section class="sheet-summary">
          <div>
            <span>{{ active.company }}</span>
            <h2>{{ active.title }}</h2>
            <p>
              约定到货 {{ active.delivery_date
              }}<template v-if="active.cutoff_at">
                · 截单 {{ dateText(active.cutoff_at) }}</template
              >
            </p>
          </div>
          <el-button v-if="w.isBuyer" icon="CopyDocument" @click="create(active)"
            >复用采购单</el-button
          >
          <div class="sheet-summary-numbers">
            <div>
              <span>采购品项</span><b>{{ active.lines.length }}<small>项</small></b>
            </div>
            <div>
              <span>关联订单</span><b>{{ active.order_count }}<small>笔</small></b>
            </div>
            <div>
              <span>已形成订单金额</span><b>¥{{ money(active.amount) }}</b>
            </div>
          </div>
        </section>
        <section class="panel section-gap">
          <div class="panel-head">
            <h2>品项与报价进展</h2>
            <div class="business-meta">
              <span v-for="(v, u) in summaries" :key="u">毛料 {{ qty(v) }} {{ u }}</span>
            </div>
          </div>
          <div class="sheet-line-tabs">
            <button :class="{ active: lineView === 'open' }" @click="lineView = 'open'">
              待报价 / 承接</button
            ><button :class="{ active: lineView === 'ordered' }" @click="lineView = 'ordered'">
              已承接</button
            ><button :class="{ active: lineView === 'all' }" @click="lineView = 'all'">
              全部品项
            </button>
          </div>
          <div v-if="!visibleLines.length" class="empty-business">
            当前分类下没有采购品项，可切换查看全部。
          </div>
          <div class="sheet-demand" v-for="l in visibleLines" :key="l.id">
            <div>
              <span class="sheet-store"
                ><el-icon><Location /></el-icon>{{ l.site || l.destination }}</span
              >
              <h3>
                {{ l.keyword }} <small>{{ purposes[l.purpose] }}</small>
              </h3>
              <p v-if="l.required_usable">
                需要净用量 {{ qty(l.required_usable) }} {{ l.unit }} · {{ l.process }}
              </p>
              <p v-else>
                采购 {{ qty(l.quantity) }} {{ l.unit }} · 单价预算 ¥{{ money(l.budget) }}
              </p>
            </div>
            <div class="sheet-demand-state">
              <b>{{ l.quotes.length }} 份报价</b
              ><small>毛料待承接 {{ qty(l.remaining) }} {{ l.unit }}</small
              ><el-button link type="primary" @click="router.push('/demands?demand=' + l.id)"
                >核对报价<el-icon><ArrowRight /></el-icon
              ></el-button>
            </div>
          </div>
        </section>
        <div v-if="active.order_ids.length" class="sheet-orders-entry">
          <span>{{ active.order_count }} 笔关联订单</span
          ><el-button link @click="router.push('/orders?sheet=' + active.id)"
            >查看关联履约 <el-icon><ArrowRight /></el-icon
          ></el-button>
        </div>
      </div>
      <section v-else class="panel empty-business">
        选择左侧采购单查看品项、报价和履约记录。
      </section>
    </div>
    <el-drawer
      :model-value="!!preview"
      @close="preview = null"
      title="按用途反算毛料采购量"
      size="600px"
      ><template v-if="preview"
        ><p class="data-note">
          {{ preview.line.keyword }} · 需要净用量 {{ preview.line.required_usable }}
          {{ preview.line.unit }} · {{ preview.line.process }}
        </p>
        <article v-for="r in preview.rows" :key="r.batch.id" class="net-preview-option">
          <div>
            <b>{{ r.batch.code }} / {{ r.batch.grade }}</b
            ><span class="source-label">{{ r.evidence?.source || '缺少对应用途记录' }}</span>
          </div>
          <p v-if="r.gross">
            采购 {{ qty(r.gross) }} {{ preview.line.unit }} → 可用约 {{ qty(r.usable) }}
            {{ preview.line.unit }}
          </p>
          <p v-if="r.net_cost">每净可用单位成本 ¥{{ money(r.net_cost) }}</p>
          <p v-for="reason in r.issues" :key="reason" class="warn small">{{ reason }}</p>
          <el-button v-if="r.compatible" type="primary" plain @click="adopt(r)"
            >采用此依据核对毛量</el-button
          >
        </article>
        <el-empty v-if="!preview.rows.length" description="暂无符合品种和单位的货源" /></template
    ></el-drawer>
  </div>
</template>
<style scoped>
.sheet-layout {
  display: grid;
  grid-template-columns: 290px minmax(0, 1fr);
  gap: 24px;
  align-items: start;
}
.sheet-list-item {
  display: block;
  width: 100%;
  text-align: left;
  border: 0;
  background: white;
  padding: 21px;
  border-bottom: 1px solid #edf1f7;
}
.sheet-list-item.active {
  background: #f0f5ff;
}
.sheet-list-item > div {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: start;
}
.sheet-list-item b {
  font-size: 13px;
  color: #365271;
  line-height: 1.7;
}
.sheet-list-item span {
  font-size: 12px;
  color: #8d9fb7;
  white-space: nowrap;
  margin-top: 4px;
}
.sheet-list-item p {
  font-size: 12px;
  color: #8195af;
  margin: 10px 0;
}
.sheet-list-item small {
  font-size: 12px;
  color: #98a9bf;
}
.sheet-list-item em {
  font-size: 12px;
  font-style: normal;
  color: #62927f;
  margin-left: 6px;
}
.sheet-summary {
  background: #162e53;
  color: white;
  border-radius: 12px;
  padding: 27px 29px;
  display: flex;
  flex-wrap: wrap;
  align-items: start;
  justify-content: space-between;
  gap: 20px;
}
.sheet-summary > div > span {
  font-size: 12px;
  color: #92aed3;
}
.sheet-summary h2 {
  font-size: 23px;
  color: #eff5ff;
  margin: 13px 0;
}
.sheet-summary p {
  font-size: 12px;
  color: #a4bbd9;
  line-height: 1.8;
}
.sheet-summary .el-button {
  background: #274774;
  border-color: #456790;
  color: #c9ddf8;
}
.sheet-summary-numbers {
  display: flex;
  width: 100%;
  gap: 45px;
  border-top: 1px solid #344d70;
  padding-top: 22px;
}
.sheet-summary-numbers span {
  font-size: 12px;
  color: #9eb5d3;
  display: block;
}
.sheet-summary-numbers b {
  display: block;
  font-size: 25px;
  margin-top: 11px;
  letter-spacing: -0.5px;
  font-weight: 550;
}
.sheet-summary-numbers small {
  font-size: 12px;
  font-weight: 400;
  margin-left: 7px;
  color: #9db4d4;
}
.sheet-demand {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 23px;
  border-bottom: 1px solid #edf1f7;
}
.sheet-store {
  display: flex;
  gap: 6px;
  align-items: center;
  color: #91a2b9;
  font-size: 12px;
}
.sheet-demand h3 {
  font-size: 16px;
  margin: 11px 0;
  color: #2d4b6e;
}
.sheet-demand h3 small {
  font-size: 12px;
  color: #8b9fb9;
  margin-left: 9px;
  font-weight: 400;
}
.sheet-demand p {
  font-size: 12px;
  line-height: 1.8;
  color: #7e94af;
}
.sheet-demand-state {
  text-align: right;
  min-width: 140px;
}
.sheet-demand-state b {
  display: block;
  color: #5576ac;
  font-size: 13px;
}
.sheet-demand-state small {
  display: block;
  color: #92a5bd;
  font-size: 12px;
  margin: 9px 0;
}
.sheet-basics {
  display: grid;
  grid-template-columns: 1fr 1.5fr 1fr 1.2fr;
  gap: 20px;
}
.sheet-basics .el-form-item {
  display: block;
}
.sheet-basics .el-form-item:deep(.el-form-item__label) {
  display: block;
  font-size: 13px;
  color: #7e92ad;
  margin-bottom: 8px;
}
.sheet-basics:deep(.el-date-editor) {
  width: 100%;
}
.sheet-line {
  padding: 22px;
  border-bottom: 1px solid #edf1f7;
}
.sheet-line-heading {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 18px;
}
.sheet-line-heading > b {
  font-size: 13px;
  color: #5f789a;
}
.sheet-line-heading > .el-button {
  margin-left: auto;
}
.sheet-line-grid {
  display: grid;
  grid-template-columns: 1.2fr 1fr 1fr 1fr 1fr 0.6fr 1fr;
  gap: 13px;
}
.sheet-line-grid .el-form-item {
  display: block;
  margin-bottom: 0;
}
.sheet-line-grid:deep(.el-form-item__label) {
  font-size: 12px;
  color: #8a9cb4;
  display: block;
  margin-bottom: 5px;
}
.sheet-line-grid:deep(.el-input-number) {
  width: 100%;
}
.sheet-line-extra {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 18px;
}
.sheet-tip {
  padding: 14px 22px;
  background: #fff8e9;
  color: #a3844f;
  font-size: 13px;
  line-height: 1.9;
}
.sheet-tip a {
  color: #547cbb;
  margin-left: 14px;
}
.sheet-editor-footer {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: center;
  flex-wrap: wrap;
  padding: 20px 22px;
}
.csv-import {
  display: flex;
  gap: 6px;
  align-items: center;
  cursor: pointer;
  color: #6e88ab;
  font-size: 13px;
}
.csv-import input {
  display: none;
}
.net-preview-option {
  padding: 20px 0;
  border-bottom: 1px solid #e7edf5;
}
.net-preview-option > div {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 13px;
  font-size: 13px;
}
.net-preview-option p {
  font-size: 13px;
  color: #7b91ac;
  line-height: 1.9;
  margin: 7px 0;
}
.net-preview-option .el-button {
  margin-top: 10px;
}
@media (max-width: 1350px) {
  .sheet-basics {
    grid-template-columns: 1fr 1fr;
  }
  .sheet-line-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
  .sheet-layout {
    grid-template-columns: 260px minmax(0, 1fr);
  }
}
@media (max-width: 800px) {
  .sheet-layout {
    grid-template-columns: 1fr;
  }
  .sheet-list {
    max-height: 270px;
    overflow-y: auto;
  }
  .sheet-summary {
    padding: 24px;
  }
  .sheet-summary-numbers {
    gap: 25px;
    flex-wrap: wrap;
  }
  .sheet-summary-numbers b {
    font-size: 23px;
  }
  .sheet-demand {
    padding: 20px 18px;
    gap: 12px;
  }
  .sheet-demand-state {
    min-width: 100px;
  }
  .sheet-demand-state small {
    font-size: 12px;
  }
  .sheet-basics {
    grid-template-columns: 1fr;
    padding-bottom: 10px;
  }
  .sheet-line-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .sheet-line {
    padding: 20px 17px;
  }
  .sheet-line-extra > .el-input {
    max-width: 100% !important;
  }
  .sheet-demand h3 {
    font-size: 15px;
  }
}

.sheet-summary {
  background: #fff;
  border: 1px solid #e4e9f0;
  color: #344c69;
  padding: 26px;
  border-radius: 12px;
}
.sheet-summary h2 {
  color: #243d5d;
  font-size: 23px;
  margin-top: 10px;
}
.sheet-summary p,
.sheet-summary > div > span {
  color: #6b7f98;
  font-size: 13px;
}
.sheet-summary-numbers {
  margin-top: 22px;
  padding-top: 20px;
  border-color: #e7ecf3;
  gap: 30px;
}
.sheet-summary-numbers > div > span {
  color: #74849a;
  font-size: 12px;
}
.sheet-summary-numbers b {
  color: #2b476a;
  font-size: 22px;
}
.sheet-summary-numbers small {
  color: #7b8ba0;
  font-size: 12px;
}
.sheet-line-tabs {
  display: flex;
  gap: 24px;
  padding: 0 24px;
  border-bottom: 1px solid #e8edf4;
}
.sheet-line-tabs button {
  background: transparent;
  border: 0;
  color: #71829a;
  padding: 18px 0;
  font-size: 13px;
  border-bottom: 2px solid transparent;
  cursor: pointer;
}
.sheet-line-tabs button.active {
  color: #365ee9;
  border-bottom-color: #365ee9;
}
.sheet-orders-entry {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
  color: #71839a;
  margin-top: 20px;
  padding: 0 2px;
}
.sheet-demand {
  padding: 22px 25px;
}
.sheet-line-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 20px;
}
@media (max-width: 760px) {
  .sheet-summary {
    padding: 22px;
  }
  .sheet-summary h2 {
    font-size: 20px;
  }
  .sheet-summary-numbers {
    gap: 20px;
    flex-wrap: wrap;
  }
  .sheet-line-grid {
    grid-template-columns: 1fr 1fr;
    gap: 16px;
  }
  .sheet-line-tabs {
    padding: 0 18px;
    gap: 19px;
  }
}

.sheet-summary .el-button {
  background: #fff;
  color: #527297;
  border-color: #dce5f0;
}
.sheet-summary-numbers span {
  color: #74849a;
}
</style>
