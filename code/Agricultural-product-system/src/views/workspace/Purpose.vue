<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useWorkspace, money, qty, todayPlus } from '@/stores/workspace'
import request from '@/utils/request'
const w = useWorkspace(),
  route = useRoute(),
  router = useRouter(),
  busy = ref(false),
  rows = ref([]),
  selected = ref([]),
  scenarios = reactive({}),
  sort = ref('cost'),
  activeDemand = ref(null)
const form = reactive({
  keyword: '苹果',
  quantity: 100,
  unit: 'kg',
  purpose: 'fresh',
  min_size: 70,
  grade: '',
  packaging: '',
  budget: 10,
  tolerance: 10,
  deadline: todayPlus(5),
  flexible_fields: [],
  arrival_window: '',
  destination: '',
})
const labels = { fresh: '门店鲜销', kitchen: '厨房加工', juice: '榨汁采购' }
const chosen = computed(() => rows.value.filter((r) => selected.value.includes(r.batch.id)))
const allCompatible = computed(() => rows.value.filter((r) => r.compatible).length)
function template(v) {
  const x = { fresh: [70, 5], kitchen: [0, 10], juice: [0, 10] }[v]
  form.min_size = x[0]
  form.tolerance = x[1]
}
async function calculate() {
  busy.value = true
  try {
    const r = await request.post(
      '/workspace/compare/',
      { ...form, demand_id: activeDemand.value, sort: sort.value, scenario_yield: scenarios },
      { timeout: 30000 },
    )
    rows.value = r.data.rows
    selected.value = selected.value.filter((id) => rows.value.some((r) => r.batch.id === id))
    if (!selected.value.length) selected.value = rows.value.slice(0, 2).map((r) => r.batch.id)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '比较未完成，请检查采购条件')
  } finally {
    busy.value = false
  }
}
function toggle(id) {
  selected.value = selected.value.includes(id)
    ? selected.value.filter((x) => x !== id)
    : [...selected.value.slice(-2), id]
}
function add(r) {
  const p = w.market.find((x) => x.id === r.batch.product_id)
  if (p) w.addCart(p, r.batch, r.quantity)
}
async function publish() {
  if (!form.destination) return ElMessage.warning('请填写收货地址后再发布需求')
  try {
    await w.act(
      'demands/',
      {
        ...form,
        title: `${labels[form.purpose]} · ${form.keyword}`,
        note: '来自用途采购比较工作区',
      },
      '已发布采购需求，供应商可响应',
    )
    router.push('/demands')
  } catch {}
}
function clearScenario(id) {
  delete scenarios[id]
  calculate()
}
function applyRoute() {
  activeDemand.value = null
  if (route.query.draft) {
    try {
      const d = JSON.parse(String(route.query.draft))
      for (const key of ['keyword', 'quantity', 'unit', 'purpose', 'deadline'])
        if (d[key] != null) form[key] = d[key]
      if (labels[d.purpose]) template(d.purpose)
    } catch {
      ElMessage.warning('采购草稿格式无法识别，请手动填写')
    }
  }
  if (route.query.demand) {
    const d = w.state.demands.find((x) => x.id === Number(route.query.demand))
    if (d) {
      Object.assign(form, d)
      form.quantity = d.remaining > 0 ? d.remaining : d.quantity
      activeDemand.value = d.id
    }
  } else if (route.query.keyword) form.keyword = String(route.query.keyword)
}
onMounted(async () => {
  await w.refresh(true)
  applyRoute()
  await calculate()
})
watch(
  () => route.fullPath,
  async () => {
    applyRoute()
    await calculate()
  },
)
</script>
<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1>用途采购</h1>
        <p>把规格、交付和分拣可用量放在一起比较，找到适合这笔采购的货。</p>
      </div>
      <el-button v-if="w.isBuyer" type="primary" icon="DocumentAdd" @click="publish"
        >保存为采购需求</el-button
      >
    </div>
    <section class="panel">
      <div class="panel-body">
        <el-form label-position="top" class="compact-form">
          <el-form-item label="采购用途"
            ><el-select v-model="form.purpose" @change="template"
              ><el-option v-for="(v, k) in labels" :key="k" :value="k" :label="v" /></el-select
          ></el-form-item>
          <el-form-item label="品种关键词"
            ><el-input v-model="form.keyword" placeholder="例如苹果、黄瓜" clearable
          /></el-form-item>
          <el-form-item label="采购数量"
            ><el-input-number v-model="form.quantity" :min="1" :max="100000" style="width: 100%"
          /></el-form-item>
          <el-form-item label="计量单位"
            ><el-select v-model="form.unit"
              ><el-option v-for="u in ['kg', '斤', '箱', '件']" :key="u" :value="u" /></el-select
          ></el-form-item>
          <el-form-item label="最小尺寸 / mm"
            ><el-input-number v-model="form.min_size" :min="0" :max="2000" style="width: 100%"
          /></el-form-item>
          <el-form-item label="商品单价预算"
            ><el-input-number v-model="form.budget" :min="0.01" :precision="2" style="width: 100%"
          /></el-form-item>
          <el-form-item label="外观缺陷率上限 / %"
            ><el-input-number v-model="form.tolerance" :min="0" :max="100" style="width: 100%"
          /></el-form-item>
          <el-form-item label="要求到货日期"
            ><el-date-picker v-model="form.deadline" value-format="YYYY-MM-DD" style="width: 100%"
          /></el-form-item>
        </el-form>
        <div class="decision-toolbar">
          <div class="row-actions">
            <span class="small muted">允许协商</span
            ><el-checkbox-group v-model="form.flexible_fields"
              ><el-checkbox value="size">尺寸</el-checkbox
              ><el-checkbox value="grade">等级</el-checkbox
              ><el-checkbox value="packaging">包装</el-checkbox></el-checkbox-group
            >
          </div>
          <el-button type="primary" :loading="busy" icon="Search" @click="calculate"
            >比较可供批次</el-button
          >
        </div>
      </div>
    </section>
    <div class="insight-band">
      <el-icon :size="30"><ScaleToOriginal /></el-icon>
      <div>
        <h2>单价相近，可用成本可能不同</h2>
        <p>
          仅用本批分拣称重或你设置的情景参数计算净得率。没有记录时保持“待核实”，不从图片检测数量换算重量。
        </p>
      </div>
    </div>
    <div class="decision-layout">
      <section class="panel" v-loading="busy">
        <div class="panel-head">
          <div>
            <h2>
              批次比较
              <span class="small muted">{{ rows.length }} 项 / {{ allCompatible }} 项严格符合</span>
            </h2>
          </div>
          <el-select v-model="sort" style="width: 160px" @change="calculate"
            ><el-option value="cost" label="按到货成本" /><el-option
              value="net"
              label="按净可用成本"
          /></el-select>
        </div>
        <article
          v-for="r in rows"
          :key="r.batch.id"
          class="comparison-row"
          :class="{ chosen: selected.includes(r.batch.id) }"
        >
          <el-checkbox
            :model-value="selected.includes(r.batch.id)"
            :aria-label="'比较' + r.batch.code"
            @change="toggle(r.batch.id)"
          />
          <el-image
            :src="w.market.find((p) => p.id === r.batch.product_id)?.image_url"
            fit="cover"
          />
          <div>
            <h3>
              {{ r.batch.product_name }} <span v-if="r.batch.is_demo" class="demo-tag">演示</span>
            </h3>
            <div class="fact-line">
              <span>{{ r.batch.code }}</span
              ><span>{{ r.batch.supplier }}</span
              ><span>{{ r.batch.grade }} · {{ r.batch.size_mm }}mm</span
              ><span>{{ r.batch.packaging }}</span>
            </div>
            <div class="constraint-chips">
              <span v-if="r.compatible" class="good">规格与交付条件符合</span
              ><span v-for="i in r.issues" :key="i.field"
                >{{ i.reason }}{{ i.negotiable ? ' · 可协商' : '' }}</span
              >
            </div>
            <div class="fact-line">
              <span>本次可供 {{ qty(r.quantity) }} {{ r.batch.unit }}</span
              ><span>预计 {{ r.arrival }} 到货</span
              ><span v-if="r.shortfall">还缺 {{ qty(r.shortfall) }} {{ form.unit }}</span>
            </div>
            <div class="evidence-source">
              净得率：{{ r.yield_rate == null ? '待核实' : r.yield_rate + '%' }}
              <span v-if="r.yield_source === '情景假设'" class="scenario-label">情景假设</span
              ><span v-else> / {{ r.yield_source }}</span
              ><br v-if="r.batch.weight_note" />{{ r.batch.weight_note }}
            </div>
          </div>
          <div>
            <div class="comparison-price">
              {{ r.net_cost == null ? '待核实' : '¥' + money(r.net_cost)
              }}<small>每 {{ form.unit }} 净可用成本</small>
            </div>
            <p class="small muted" style="text-align: right; margin-top: 10px">
              到货金额 {{ r.pricing ? '¥' + money(r.pricing.total) : '不可报价' }}
            </p>
            <div class="scenario-control">
              <el-input-number
                v-model="scenarios[r.batch.id]"
                :min="1"
                :max="100"
                :controls="false"
                size="small"
                placeholder="情景净得率 %"
              /><el-button size="small" @click="calculate">试算</el-button>
            </div>
            <el-button
              v-if="scenarios[r.batch.id] != null"
              link
              size="small"
              @click="clearScenario(r.batch.id)"
              >恢复实称依据</el-button
            >
          </div>
        </article>
        <el-empty
          v-if="!rows.length && !busy"
          description="没有对应品种货源，调整关键词或发布需求征集报价"
        />
      </section>
      <aside class="decision-aside panel">
        <div class="panel-head">
          <h2>对比已选 {{ chosen.length }} 批</h2>
        </div>
        <div class="panel-body">
          <div v-for="r in chosen" :key="r.batch.id" class="compare-mini">
            <strong>{{ r.batch.code }} / {{ r.batch.grade }}</strong>
            <div class="kv">
              <span>商品款</span><b>¥{{ money(r.pricing?.goods) }}</b>
            </div>
            <div class="kv">
              <span>包装费 / 运费</span
              ><b>¥{{ money(r.pricing?.packaging) }} / {{ money(r.pricing?.freight) }}</b>
            </div>
            <div class="kv">
              <span>净可用量</span
              ><b>{{
                r.usable_quantity == null ? '待核实' : qty(r.usable_quantity) + ' ' + r.batch.unit
              }}</b>
            </div>
            <el-button
              v-if="w.isBuyer"
              type="primary"
              plain
              size="small"
              :disabled="!r.compatible || !r.pricing"
              @click="add(r)"
              >将这批加入采购清单</el-button
            ><router-link :to="'/product/' + r.batch.product_id"
              ><el-button link size="small">核对批次证据</el-button></router-link
            >
          </div>
          <p v-if="!chosen.length" class="muted small">勾选左侧批次，最多同时比较三批。</p>
          <el-form v-if="w.isBuyer" label-position="top" class="section-gap"
            ><el-form-item label="采购需求收货地址"
              ><el-input
                v-model="form.destination"
                type="textarea"
                :rows="2"
                placeholder="发布需求时填写，比较试算可暂留空" /></el-form-item
          ></el-form>
          <p class="data-note">
            用途模板只提供起点，采购条件由你确认。协商偏差须经采购方明确接受；腐坏与未放行状态不能靠降低外观要求绕过。
          </p>
        </div>
      </aside>
    </div>
  </div>
</template>
