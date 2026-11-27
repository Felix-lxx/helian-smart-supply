<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { useWorkspace, money, qty, todayPlus } from '@/stores/workspace'
import StatusBadge from '@/components/StatusBadge.vue'
const w = useWorkspace(),
  search = ref(''),
  status = ref('all'),
  createVisible = ref(false),
  quoteVisible = ref(false),
  detailVisible = ref(false),
  selectedId = ref(null),
  busy = ref(false),
  form = reactive({}),
  quote = reactive({})
const route = useRoute(),
  acceptedDifferences = reactive({}),
  purposes = { fresh: '门店鲜销', kitchen: '厨房加工', juice: '榨汁采购' }
watch(
  [() => route.query.demand, () => w.state.demands],
  () => {
    const id = Number(route.query.demand)
    if (w.state.demands.some((d) => d.id === id)) {
      selectedId.value = id
      detailVisible.value = true
    }
  },
  { immediate: true },
)
const selected = computed(() => w.state.demands.find((d) => d.id === selectedId.value)),
  rows = computed(() =>
    w.state.demands.filter(
      (d) =>
        (!route.query.date || d.deadline === route.query.date) &&
        (!route.query.site || d.site_id === Number(route.query.site)) &&
        (!route.query.unit || d.unit === route.query.unit) &&
        (route.query.exclude_demo !== '1' || !d.is_demo) &&
        (d.title + d.keyword + d.destination).includes(search.value) &&
        (status.value === 'all' || d.status === status.value),
    ),
  )
const quoteBatches = computed(() =>
  w.state.batches.filter(
    (b) => b.status === 'released' && b.available > 0 && b.unit === selected.value?.unit,
  ),
)
function create() {
  Object.assign(form, {
    title: '',
    keyword: '',
    quantity: 100,
    unit: 'kg',
    budget: 6,
    min_size: 0,
    grade: '',
    packaging: '',
    tolerance: 10,
    deadline: todayPlus(5),
    destination: '',
    location: '',
    note: '',
    purpose: 'fresh',
    flexible_fields: [],
    priority: 1,
    arrival_window: '',
  })
  createVisible.value = true
}
async function save() {
  busy.value = true
  try {
    await w.act('demands/', form, '采购需求已发布，供应商可查看并报价')
    createVisible.value = false
  } catch {
  } finally {
    busy.value = false
  }
}
function open(d) {
  selectedId.value = d.id
  detailVisible.value = true
}
function startQuote(d) {
  selectedId.value = d.id
  Object.assign(quote, {
    batch_id: null,
    price: d.budget,
    quantity: d.remaining || d.quantity,
    note: '',
  })
  quoteVisible.value = true
}
async function sendQuote() {
  busy.value = true
  try {
    await w.act(`demands/${selected.value.id}/quote/`, quote, '报价已发送，待采购商确认')
    quoteVisible.value = false
  } catch {
  } finally {
    busy.value = false
  }
}
async function accept(q) {
  try {
    await ElMessageBox.confirm(
      `确认接受 ${q.supplier} 的报价，单价 ¥${money(q.price)}，本次承接 ${qty(selected.value.required_usable ? q.quantity : Math.min(q.quantity, selected.value.remaining))} ${selected.value.unit}？${q.terms?.committed_usable ? '约定预计净用量 ' + qty(q.terms.committed_usable) + ' ' + selected.value.unit + '。' : ''}${q.deviations?.length ? '你同时接受已列出的规格偏差。' : ''}包装费和运费以报价明细为准。`,
      '接受报价',
      { confirmButtonText: '接受并创建订单', cancelButtonText: '再比较一下' },
    )
    await w.act(
      `quotes/${q.id}/accept/`,
      { accept_deviations: acceptedDifferences[q.id] === true },
      '已创建采购订单，请前往订单中心确认付款',
    )
  } catch {}
}
</script>
<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1>{{ w.isBuyer ? '我的采购需求' : '采购需求与商机' }}</h1>
        <p>先明确规格、数量和到货窗口，再比较可履约的报价。接受部分报价后保留未满足数量。</p>
      </div>
      <el-button v-if="w.isBuyer" type="primary" icon="Plus" @click="create">发布采购需求</el-button
      ><router-link v-else to="/allocation"
        ><el-button type="primary" icon="Connection">查看匹配与分货</el-button></router-link
      >
    </div>
    <div class="metrics">
      <div class="metric">
        <span class="metric-label">采购需求</span>
        <div class="metric-value">{{ w.state.demands.length }}</div>
        <span class="metric-foot">当前账号可见范围</span>
      </div>
      <div class="metric">
        <span class="metric-label">正在征集</span>
        <div class="metric-value">
          {{ w.state.demands.filter((d) => d.status === 'open').length }}
        </div>
        <span class="metric-foot">可继续响应报价</span>
      </div>
      <div class="metric">
        <span class="metric-label">已收到报价</span>
        <div class="metric-value">
          {{ w.state.demands.reduce((s, d) => s + d.quotes.length, 0) }}
        </div>
        <span class="metric-foot">供应方仅见自己的报价</span>
      </div>
      <div class="metric">
        <span class="metric-label">需求已满足</span>
        <div class="metric-value">
          {{ w.state.demands.filter((d) => d.status === 'ordered').length }}
        </div>
        <span class="metric-foot">已确认报价并转为订单</span>
      </div>
    </div>
    <section class="panel">
      <div class="toolbar">
        <div class="pill-tabs">
          <button
            v-for="[s, n] in [
              ['all', '全部需求'],
              ['open', '征集中'],
              ['ordered', '已转订单'],
            ]"
            :key="s"
            :class="{ active: status === s }"
            @click="status = s"
          >
            {{ n }}
          </button>
        </div>
        <el-input
          v-model="search"
          prefix-icon="Search"
          placeholder="搜索品种、需求或目的地"
          clearable
        />
      </div>
      <el-table :data="rows" @row-click="open" style="cursor: pointer"
        ><el-table-column label="采购需求" min-width="230"
          ><template #default="{ row }"
            ><strong>{{ row.title }} <span v-if="row.is_demo" class="demo-tag">演示</span></strong>
            <div class="small muted" style="margin-top: 7px">
              {{ row.keyword }} · {{ row.grade || '等级不限' }} ·
              {{ row.packaging || '包装可协商' }}
            </div></template
          ></el-table-column
        ><el-table-column label="待满足 / 总需求" width="150"
          ><template #default="{ row }"
            ><b class="good">{{ qty(row.remaining) }}</b> / {{ qty(row.quantity) }} {{ row.unit
            }}<small v-if="row.required_usable" class="data-note" style="display: block"
              >毛量参考；净缺口 {{ qty(row.remaining_usable) }} {{ row.unit }}</small
            ></template
          ></el-table-column
        ><el-table-column label="单价预算" width="125"
          ><template #default="{ row }"
            >¥{{ money(row.budget) }}/{{ row.unit }}</template
          ></el-table-column
        ><el-table-column label="到货期限" prop="deadline" width="120" /><el-table-column
          label="进度"
          width="105"
          ><template #default="{ row }"
            ><StatusBadge :value="row.status" /></template></el-table-column
        ><el-table-column label="操作" width="145" fixed="right"
          ><template #default="{ row }"
            ><div @click.stop>
              <el-button
                v-if="w.isSupplier && row.status === 'open'"
                type="primary"
                link
                @click="startQuote(row)"
                >提交报价</el-button
              ><el-button link @click="open(row)">{{ w.isBuyer ? '查看报价' : '详情' }}</el-button>
            </div></template
          ></el-table-column
        ></el-table
      >
    </section>
    <el-dialog v-model="createVisible" title="发布采购需求" width="720px"
      ><el-form label-position="top"
        ><div class="form-grid">
          <el-form-item label="需求标题" class="wide"
            ><el-input
              v-model="form.title"
              placeholder="例如：门店周配 · 优选苹果"
              maxlength="160" /></el-form-item
          ><el-form-item label="采购用途"
            ><el-select v-model="form.purpose"
              ><el-option
                v-for="(v, k) in purposes"
                :key="k"
                :value="k"
                :label="v" /></el-select></el-form-item
          ><el-form-item label="需求优先级"
            ><el-select v-model="form.priority"
              ><el-option :value="1" label="日常采购" /><el-option
                :value="2"
                label="较紧急" /><el-option :value="3" label="优先保障" /></el-select></el-form-item
          ><el-form-item label="约定到货时段"
            ><el-input v-model="form.arrival_window" placeholder="例如 08:00—11:00" /></el-form-item
          ><el-form-item label="可协商条件"
            ><el-checkbox-group v-model="form.flexible_fields"
              ><el-checkbox value="size">尺寸</el-checkbox
              ><el-checkbox value="grade">等级</el-checkbox
              ><el-checkbox value="packaging">包装</el-checkbox></el-checkbox-group
            ></el-form-item
          ><el-form-item label="品种关键词"
            ><el-input v-model="form.keyword" placeholder="例如：苹果" /></el-form-item
          ><el-form-item label="数量"
            ><el-input-number v-model="form.quantity" :min="0.01" :precision="2" /></el-form-item
          ><el-form-item label="计量单位"
            ><el-select v-model="form.unit" style="width: 100%"
              ><el-option
                v-for="u in ['kg', '斤', '箱', '件']"
                :key="u"
                :value="u" /></el-select></el-form-item
          ><el-form-item label="最高单价 / 元"
            ><el-input-number v-model="form.budget" :min="0.01" :precision="2" /></el-form-item
          ><el-form-item label="最低尺寸 / mm（不限填0）"
            ><el-input-number v-model="form.min_size" :min="0" /></el-form-item
          ><el-form-item label="等级要求"
            ><el-select v-model="form.grade" style="width: 100%"
              ><el-option label="等级不限" value="" /><el-option
                label="优选级"
                value="优选级" /><el-option
                label="标准级"
                value="标准级" /></el-select></el-form-item
          ><el-form-item label="包装要求（留空可协商）"
            ><el-input
              v-model="form.packaging"
              placeholder="例如：5kg箱装，需与货源一致" /></el-form-item
          ><el-form-item label="约定外观缺陷率上限 / %"
            ><el-input-number
              v-model="form.tolerance"
              :min="0"
              :max="100"
              :precision="1" /></el-form-item
          ><el-form-item label="到货期限"
            ><el-date-picker
              v-model="form.deadline"
              value-format="YYYY-MM-DD"
              style="width: 100%" /></el-form-item
          ><el-form-item label="收货目的地"><el-input v-model="form.destination" /></el-form-item
          ><el-form-item label="验收与交付说明" class="wide"
            ><el-input
              v-model="form.note"
              type="textarea"
              :rows="3"
              placeholder="说明抽样、时间窗口与允许的替代条件"
          /></el-form-item></div></el-form
      ><template #footer
        ><el-button @click="createVisible = false">取消</el-button
        ><el-button type="primary" :loading="busy" @click="save">确认发布</el-button></template
      ></el-dialog
    >
    <el-dialog v-model="quoteVisible" title="提交供货报价" width="560px"
      ><div class="info-strip" style="margin-bottom: 20px">
        {{ selected?.title }} · 未满足 {{ qty(selected?.remaining) }} {{ selected?.unit }}
      </div>
      <el-form label-position="top"
        ><el-form-item label="选择放行批次"
          ><el-select
            v-model="quote.batch_id"
            style="width: 100%"
            @change="
              (id) => {
                const b = quoteBatches.find((x) => x.id === id)
                quote.price = b.price
                quote.quantity = Math.min(quote.quantity, b.available)
              }
            "
            ><el-option
              v-for="b in quoteBatches"
              :key="b.id"
              :label="b.code + ' · ' + b.product_name + ' · 可用' + b.available + b.unit"
              :value="b.id" /></el-select
        ></el-form-item>
        <div class="form-grid">
          <el-form-item label="报价单价 / 元"
            ><el-input-number v-model="quote.price" :min="0.01" :precision="2" /></el-form-item
          ><el-form-item label="可供数量"
            ><el-input-number v-model="quote.quantity" :min="0.01" :precision="2"
          /></el-form-item>
        </div>
        <el-form-item label="供货与交期说明"
          ><el-input v-model="quote.note" type="textarea" :rows="3" /></el-form-item
      ></el-form>
      <p class="data-note">
        报价暂不预占库存。采购商接受时重新校验可用量，报价单位必须与需求一致。
      </p>
      <template #footer
        ><el-button @click="quoteVisible = false">取消</el-button
        ><el-button type="primary" :loading="busy" :disabled="!quote.batch_id" @click="sendQuote"
          >发送给采购商</el-button
        ></template
      ></el-dialog
    >
    <el-drawer v-model="detailVisible" title="需求详情与报价" size="600px"
      ><template v-if="selected"
        ><h2>{{ selected.title }}</h2>
        <p class="muted small" style="margin: 10px 0 20px">
          采购方 {{ selected.buyer }} <span v-if="selected.is_demo" class="demo-tag">演示</span>
        </p>
        <div class="kv">
          <span>待满足数量</span
          ><b>{{ qty(selected.remaining) }} / {{ qty(selected.quantity) }} {{ selected.unit }}</b>
        </div>
        <div class="kv">
          <span>预算上限</span><b>¥{{ money(selected.budget) }} / {{ selected.unit }}</b>
        </div>
        <div class="kv">
          <span>规格要求</span
          ><b
            >{{ selected.grade || '等级不限' }} · {{ selected.min_size || '不限' }}mm ·
            {{ selected.packaging || '包装可协商' }}</b
          >
        </div>
        <div class="kv">
          <span>到货期限</span><b>{{ selected.deadline }}</b>
        </div>
        <div class="kv">
          <span>用途 / 到货时段</span
          ><b
            >{{ purposes[selected.purpose] || '门店鲜销' }} /
            {{ selected.arrival_window || '未指定时段' }}</b
          >
        </div>
        <router-link :to="'/procurement?demand=' + selected.id"
          ><el-button type="primary" plain style="margin: 16px 0"
            >按此需求比较可供批次</el-button
          ></router-link
        >
        <div class="kv">
          <span>收货目的地</span><b>{{ selected.destination }}</b>
        </div>
        <div class="info-strip section-gap">
          {{ selected.note || '采购方尚未补充其他说明' }}<br />约定外观缺陷率上限
          {{ selected.tolerance }}%，此项不替代食品安全检验。
        </div>
        <h3 style="margin: 25px 0 10px">供货报价 · {{ selected.quotes.length }} 项</h3>
        <div v-for="q in selected.quotes" :key="q.id" class="quote-card">
          <div class="row-actions">
            <strong>{{ q.supplier }}</strong
            ><StatusBadge :value="q.status" />
          </div>
          <p>{{ q.batch_code }} · {{ qty(q.quantity) }} {{ selected.unit }}</p>
          <p v-if="q.terms?.total">
            含已录入费用总额 ¥{{ money(q.terms.total) }} / 包装 ¥{{ money(q.terms.packaging) }} /
            运费 ¥{{ money(q.terms.freight) }}
          </p>
          <p v-if="q.expires_at">
            报价有效至
            {{
              new Date(q.expires_at).toLocaleString('zh-CN', {
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
              })
            }}
          </p>
          <div v-if="q.deviations?.length" class="constraint-chips">
            <span v-for="x in q.deviations" :key="x.field">{{ x.reason }} · 可协商偏差</span>
          </div>
          <el-checkbox
            v-if="w.isBuyer && q.deviations?.length && q.status === 'pending'"
            v-model="acceptedDifferences[q.id]"
            >我已核对并接受列出的偏差</el-checkbox
          >
          <div class="quote-price">
            <b
              >¥{{ money(q.price) }}<small>/{{ selected.unit }}</small></b
            ><el-button
              v-if="w.isBuyer && q.status === 'pending' && selected.status === 'open'"
              type="primary"
              size="small"
              :disabled="q.deviations?.length && !acceptedDifferences[q.id]"
              @click="accept(q)"
              >接受并转订单</el-button
            ><router-link v-if="q.order_id" :to="'/orders?order=' + q.order_id"
              ><el-button size="small">查看订单</el-button></router-link
            >
          </div>
          <p>{{ q.note || '未补充说明' }}</p>
        </div>
        <el-empty
          v-if="!selected.quotes.length"
          description="暂无报价，供应商响应后会通知你"
          :image-size="70" /></template
    ></el-drawer>
  </div>
</template>
<style scoped>
.quote-card {
  padding: 18px;
  border: 1px solid var(--line);
  border-radius: 9px;
  margin-bottom: 13px;
}
.quote-card strong {
  font-size: 13px;
}
.quote-card p {
  font-size: 12px;
  color: var(--muted);
  margin-top: 10px;
  line-height: 1.8;
}
.quote-price {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 15px;
}
.quote-price > b {
  font-size: 24px;
  color: var(--brand);
  font-weight: 600;
}
.quote-price small {
  font-size: 12px;
  font-weight: 400;
  color: var(--muted);
}
</style>
