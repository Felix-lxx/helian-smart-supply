<script setup>
defineOptions({ name: 'BusinessGrading' })
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useWorkspace, qty, money, dateText } from '@/stores/workspace'
import request from '@/utils/request'
const w = useWorkspace(),
  router = useRouter(),
  selected = ref(null),
  tab = ref('yield'),
  records = ref([]),
  busy = ref(false),
  result = ref(null),
  search = ref('')
const purposes = { fresh: '门店鲜销', kitchen: '厨房加工', juice: '榨汁加工' }
const form = reactive({
  purpose: 'kitchen',
  process: '去皮去核',
  scope: 'sample',
  input_weight: undefined,
  usable_weight: undefined,
  note: '',
})
const split = reactive({
  input_quantity: undefined,
  loss_quantity: 0,
  note: '',
  outputs: [
    {
      key: crypto.randomUUID(),
      grade: '鲜销级',
      purpose: 'fresh',
      quantity: undefined,
      price: undefined,
    },
    {
      key: crypto.randomUUID(),
      grade: '加工级',
      purpose: 'kitchen',
      quantity: undefined,
      price: undefined,
    },
  ],
})
const batch = computed(() => w.state.batches.find((b) => b.id === selected.value)),
  batches = computed(() =>
    w.state.batches.filter((b) => (b.product_name + b.code).includes(search.value)),
  )
const rate = computed(() =>
  form.input_weight > 0 && form.usable_weight != null
    ? Math.min(100, (form.usable_weight / form.input_weight) * 100)
    : null,
)
const outputsTotal = computed(() => split.outputs.reduce((n, r) => n + Number(r.quantity || 0), 0)),
  balance = computed(
    () => Number(split.input_quantity || 0) - outputsTotal.value - Number(split.loss_quantity || 0),
  )
const estimated = computed(() =>
  split.outputs.reduce((n, r) => n + Number(r.quantity || 0) * Number(r.price || 0), 0),
)
async function load() {
  if (!selected.value) return
  try {
    records.value = (await request.get(`/workspace/batches/${selected.value}/yields/`)).data
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '用途称重记录无法读取')
  }
}
watch(
  () => w.state.batches,
  (bs) => {
    if (!selected.value && bs.length) selected.value = bs[0].id
  },
  { immediate: true },
)
watch(selected, () => {
  result.value = null
  records.value = []
  form.input_weight = undefined
  form.usable_weight = undefined
  form.note = ''
  split.input_quantity = undefined
  split.loss_quantity = 0
  split.note = ''
  split.outputs.forEach((r) => {
    r.quantity = undefined
    r.price = batch.value?.price
  })
  load()
})
onMounted(() => {
  w.refresh(true)
  load()
})
async function weigh() {
  if (!batch.value) return
  busy.value = true
  try {
    await w.act(
      `batches/${batch.value.id}/yields/`,
      form,
      '用途称重依据已保存，净量采购与供货排程可使用',
    )
    await load()
    form.input_weight = undefined
    form.usable_weight = undefined
    form.note = ''
  } catch {
    // Operation errors are shown by the shared workspace action; dialog cancellation is intentional.
  } finally {
    busy.value = false
  }
}
async function grade() {
  if (!batch.value) return
  if (Math.abs(balance.value) > 0.005) return ElMessage.warning('分级量加损耗须等于投入量')
  busy.value = true
  try {
    result.value = await w.act(
      `batches/${batch.value.id}/grading/`,
      { ...split, version: batch.value.version },
      '分级已入账，子批次待品质复核',
    )
    split.input_quantity = undefined
    split.outputs.forEach((r) => (r.quantity = undefined))
  } catch {
    // Operation errors are shown by the shared workspace action; dialog cancellation is intentional.
  } finally {
    busy.value = false
  }
}
function choose(id) {
  selected.value = id
}
</script>
<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1>分级与用途称重</h1>
        <p>把实际分拣结果变成可采购、可追溯的批次依据。</p>
      </div>
      <el-button
        icon="Refresh"
        @click="
          async () => {
            await w.refresh()
            await load()
          }
        "
        >同步批次</el-button
      >
    </div>
    <div class="grading-layout">
      <aside class="panel grading-batches">
        <div class="panel-head">
          <h2>作业批次</h2>
          <span class="small muted">{{ batches.length }} 批</span>
        </div>
        <div class="panel-body">
          <el-input v-model="search" clearable placeholder="搜索批次与货品" prefix-icon="Search" />
        </div>
        <button
          v-for="b in batches"
          :key="b.id"
          class="grading-batch"
          :class="{ active: selected === b.id }"
          @click="choose(b.id)"
        >
          <div>
            <b>{{ b.product_name }}</b
            ><span v-if="b.parent_id" class="source-label">分级子批</span>
          </div>
          <p>{{ b.code }}</p>
          <small
            >未预留 {{ qty(b.quantity - b.reserved) }} {{ b.unit
            }}<em v-if="b.is_demo">演示</em></small
          >
        </button>
        <div v-if="!batches.length" class="empty-business">先入库商品批次，再记录分级与称重。</div>
      </aside>
      <div v-if="batch">
        <section class="grading-batch-hero">
          <div>
            <span>{{ batch.code }} <em v-if="batch.is_demo">演示批次</em></span>
            <h2>{{ batch.product_name }}</h2>
            <p>{{ batch.origin }} · {{ batch.grade }} · {{ batch.packaging }}</p>
          </div>
          <div>
            <small>当前未预留数量</small
            ><b
              >{{ qty(batch.quantity - batch.reserved) }} <span>{{ batch.unit }}</span></b
            >
            <p>已预留 {{ qty(batch.reserved) }} {{ batch.unit }}</p>
          </div>
        </section>
        <div class="grading-tabs">
          <button :class="{ active: tab === 'yield' }" @click="tab = 'yield'">
            <el-icon><ScaleToOriginal /></el-icon>按用途记录净得率</button
          ><button :class="{ active: tab === 'split' }" @click="tab = 'split'">
            <el-icon><SetUp /></el-icon>实际分级与拆批
          </button>
        </div>
        <div v-if="tab === 'yield'" class="yield-layout">
          <section class="panel">
            <div class="panel-head">
              <h2>本次实际称重</h2>
              <span class="small muted">{{ batch.unit }}</span>
            </div>
            <el-form label-position="top" class="panel-body"
              ><div class="yield-form-grid">
                <el-form-item label="使用用途"
                  ><el-select v-model="form.purpose"
                    ><el-option
                      v-for="(n, k) in purposes"
                      :key="k"
                      :label="n"
                      :value="k" /></el-select></el-form-item
                ><el-form-item label="加工或分拣方式"
                  ><el-input v-model="form.process" placeholder="例如：去皮去核" /></el-form-item
                ><el-form-item :label="'实际投入 / ' + batch.unit"
                  ><el-input-number
                    v-model="form.input_weight"
                    :min="0.01"
                    :max="batch.quantity"
                    :precision="2"
                    placeholder="称重后录入" /></el-form-item
                ><el-form-item :label="'实际可用 / ' + batch.unit"
                  ><el-input-number
                    v-model="form.usable_weight"
                    :min="0"
                    :max="form.input_weight || batch.quantity"
                    :precision="2"
                    placeholder="称重后录入"
                /></el-form-item>
              </div>
              <el-form-item label="记录范围"
                ><el-radio-group v-model="form.scope"
                  ><el-radio value="sample">样本实称，用于估算</el-radio
                  ><el-radio value="whole">整批实际作业</el-radio></el-radio-group
                ></el-form-item
              ><el-form-item label="实际作业依据"
                ><el-input
                  v-model="form.note"
                  type="textarea"
                  :rows="3"
                  placeholder="记录取样范围、剔除原因和称重方式，避免把样本当作整批事实"
              /></el-form-item>
              <div class="yield-submit">
                <span>用途与加工方式共同决定这份记录的适用范围</span
                ><el-button type="primary" :loading="busy" @click="weigh">保存实际称重</el-button>
              </div></el-form
            >
          </section>
          <section class="yield-preview">
            <span>本次记录预览</span>
            <h2>{{ purposes[form.purpose] }}</h2>
            <p>{{ form.process || '请填写加工方式' }}</p>
            <div class="yield-ratio">
              <b>{{ rate == null ? '—' : rate.toFixed(1) }}<small v-if="rate != null">%</small></b
              ><span>净得率</span>
            </div>
            <div class="yield-weight-bar"><i :style="{ width: (rate || 0) + '%' }"></i></div>
            <div class="yield-weight-label">
              <span>可用 {{ qty(form.usable_weight) }} {{ batch.unit }}</span
              ><span>投入 {{ qty(form.input_weight) }} {{ batch.unit }}</span>
            </div>
            <p class="yield-note">
              {{
                form.scope === 'whole'
                  ? '整批投入量须与当前批次数量一致。'
                  : '该记录为样本实称，采购反算会明确标注估算来源。'
              }}未提交前不会改变现有依据。
            </p>
            <el-button plain @click="router.push('/procurement')">打开净量采购</el-button>
          </section>
        </div>
        <details v-if="tab === 'yield'" class="panel section-gap yield-history">
          <summary>
            称重历史 <span>{{ records.length }} 条记录</span><el-icon><ArrowDown /></el-icon>
          </summary>
          <div v-for="r in records" :key="r.id" class="yield-record">
            <div>
              <b>{{ purposes[r.purpose] }}</b
              ><span>{{ r.process }}</span
              ><small>{{ dateText(r.created_at) }} · {{ r.actor }}</small>
            </div>
            <div class="yield-record-measure">
              <b>{{ r.rate }}%</b
              ><small
                >{{ qty(r.usable_weight) }} / {{ qty(r.input_weight) }} {{ batch.unit }}</small
              >
            </div>
            <div>
              <span class="source-label">{{
                r.is_demo ? '演示参数' : r.scope === 'whole' ? '整批实称' : '样本估算'
              }}</span>
              <p>{{ r.note }}</p>
            </div>
          </div>
          <div v-if="!records.length" class="empty-business">
            该批次还没有分用途的称重依据。<br />请完成实际作业后记录。
          </div>
        </details>
        <template v-if="tab === 'split'"
          ><section class="panel">
            <div class="panel-head">
              <h2>分级草稿</h2>
              <span class="small muted">提交后按实物数量生成待检子批次</span>
            </div>
            <div class="panel-body">
              <div class="split-inputs">
                <el-form-item :label="'实际投入 / ' + batch.unit"
                  ><el-input-number
                    v-model="split.input_quantity"
                    :min="0.01"
                    :max="batch.quantity - batch.reserved"
                    :precision="2" /></el-form-item
                ><el-form-item :label="'实际损耗 / ' + batch.unit"
                  ><el-input-number
                    v-model="split.loss_quantity"
                    :min="0"
                    :max="split.input_quantity || batch.quantity"
                    :precision="2"
                /></el-form-item>
              </div>
              <div class="grading-flow">
                <div class="grading-source">
                  <el-icon><Box /></el-icon
                  ><strong>{{ qty(split.input_quantity) }} {{ batch.unit }}</strong
                  ><span>原批次实际投入</span>
                </div>
                <div class="grading-connect">
                  <el-icon><Right /></el-icon>
                </div>
                <div class="grading-destinations">
                  <div v-for="r in split.outputs" :key="r.key">
                    <span>{{ r.grade || '待填等级' }}</span
                    ><b>{{ qty(r.quantity) }} {{ batch.unit }}</b
                    ><i
                      :style="{
                        width:
                          Math.min(
                            100,
                            (Number(r.quantity || 0) / Math.max(1, split.input_quantity || 0)) *
                              100,
                          ) + '%',
                      }"
                    ></i>
                  </div>
                  <div class="loss-output">
                    <span>实际剔除 / 损耗</span
                    ><b>{{ qty(split.loss_quantity) }} {{ batch.unit }}</b>
                  </div>
                </div>
              </div>
              <div class="split-result-strip">
                <span :class="{ danger: Math.abs(balance) > 0.005 }"
                  >数量差 {{ qty(balance) }} {{ batch.unit }}</span
                ><span>分级报价试算 ¥{{ money(estimated) }}</span
                ><span
                  >原批次等量报价 ¥{{
                    money(Number(split.input_quantity || 0) * batch.price)
                  }}</span
                >
              </div>
              <div v-for="(r, i) in split.outputs" :key="r.key" class="split-edit-row">
                <el-input v-model="r.grade" placeholder="等级" /><el-select v-model="r.purpose"
                  ><el-option
                    v-for="(n, k) in purposes"
                    :key="k"
                    :label="n"
                    :value="k" /></el-select
                ><el-input-number
                  v-model="r.quantity"
                  :min="0.01"
                  :precision="2"
                  placeholder="分级数量"
                /><el-input-number
                  v-model="r.price"
                  :min="0.01"
                  :precision="2"
                  placeholder="每单位报价"
                /><el-button
                  v-if="split.outputs.length > 1"
                  link
                  type="danger"
                  @click="split.outputs.splice(i, 1)"
                  aria-label="移除分级结果"
                  ><el-icon><Delete /></el-icon
                ></el-button>
              </div>
              <el-button
                link
                type="primary"
                icon="Plus"
                @click="
                  split.outputs.push({
                    key: crypto.randomUUID(),
                    grade: '',
                    purpose: 'fresh',
                    quantity: undefined,
                    price: batch.price,
                  })
                "
                >增加分级结果</el-button
              ><el-input
                v-model="split.note"
                type="textarea"
                :rows="2"
                placeholder="实际分级、损耗依据；分级不能代替品质复核"
                class="section-gap"
              />
              <div class="split-submit">
                <p>子批次分别报价，复核放行后进入交易。报价试算不代表已成交金额。</p>
                <el-button
                  type="primary"
                  :disabled="Math.abs(balance) > 0.005 || !split.input_quantity"
                  :loading="busy"
                  @click="grade"
                  >确认实际分级并入账</el-button
                >
              </div>
            </div>
          </section>
          <section v-if="result" class="panel section-gap">
            <div class="panel-head">
              <h2>已生成待检子批次</h2>
              <span class="good">数量守恒已核对</span>
            </div>
            <div class="grading-created" v-for="r in result.outputs" :key="r.batch_id">
              <div>
                <b>{{ r.code }}</b>
                <p>
                  {{ r.grade }} / {{ purposes[r.purpose] }} · {{ qty(r.quantity) }}
                  {{ batch.unit }} · ¥{{ money(r.price) }}
                </p>
              </div>
              <el-button plain type="primary" @click="router.push('/quality?batch=' + r.batch_id)"
                >进入品质复核</el-button
              >
            </div>
          </section></template
        >
      </div>
      <section v-else class="panel empty-business">选择一个实际批次开始作业。</section>
    </div>
  </div>
</template>
<style scoped>
.grading-layout {
  display: grid;
  grid-template-columns: 270px minmax(0, 1fr);
  gap: 25px;
  align-items: start;
}
.grading-batches {
  max-height: calc(100vh - 180px);
  overflow: auto;
}
.grading-batch {
  display: block;
  width: 100%;
  text-align: left;
  border: 0;
  background: white;
  border-bottom: 1px solid #edf1f7;
  padding: 19px 22px;
}
.grading-batch.active {
  background: #f0f5ff;
}
.grading-batch > div {
  display: flex;
  justify-content: space-between;
  gap: 9px;
  align-items: center;
}
.grading-batch b {
  font-size: 13px;
  color: #385679;
}
.grading-batch p {
  font-size: 12px;
  color: #869bb7;
  margin: 9px 0;
}
.grading-batch small {
  font-size: 12px;
  color: #8ba1b9;
}
.grading-batch em {
  font-size: 12px;
  font-style: normal;
  color: #b28e4a;
  margin-left: 8px;
}
.grading-batch-hero {
  padding: 26px 29px;
  background: #173559;
  border-radius: 12px;
  color: white;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 25px;
}
.grading-batch-hero > div > span {
  font-size: 12px;
  color: #a3bddb;
}
.grading-batch-hero em {
  font-style: normal;
  font-size: 12px;
  color: #d4bf8c;
  margin-left: 8px;
}
.grading-batch-hero h2 {
  font-size: 24px;
  margin: 12px 0;
  color: #edf5ff;
}
.grading-batch-hero p {
  font-size: 12px;
  color: #97b4d4;
  line-height: 1.9;
}
.grading-batch-hero > div:last-child {
  text-align: right;
  flex-shrink: 0;
}
.grading-batch-hero small {
  font-size: 12px;
  color: #9bb6d7;
}
.grading-batch-hero b {
  display: block;
  font-size: 30px;
  margin: 10px 0;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.grading-batch-hero b span {
  font-size: 13px;
  font-weight: 400;
}
.grading-tabs {
  display: flex;
  gap: 14px;
  margin: 24px 0 19px;
  border-bottom: 1px solid #dce4f0;
}
.grading-tabs button {
  border: 0;
  background: transparent;
  padding: 0 10px 15px;
  display: flex;
  align-items: center;
  gap: 9px;
  color: #8c9eb7;
  font-size: 13px;
  position: relative;
}
.grading-tabs button.active {
  color: #3b62d7;
  font-weight: 600;
}
.grading-tabs button.active:after {
  content: '';
  position: absolute;
  bottom: -1px;
  left: 10px;
  right: 10px;
  height: 2px;
  background: #3b62d7;
}
.yield-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(235px, 1fr);
  gap: 23px;
}
.yield-form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 18px;
}
.yield-form-grid .el-input-number {
  width: 100%;
}
.yield-submit {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
}
.yield-submit span {
  font-size: 12px;
  line-height: 1.8;
  color: #9aabc0;
  max-width: 200px;
}
.yield-preview {
  padding: 27px;
  background: #eaf3f6;
  border-radius: 12px;
  color: #376c78;
}
.yield-preview > span {
  font-size: 12px;
  color: #6a929a;
}
.yield-preview h2 {
  font-size: 20px;
  margin: 14px 0 9px;
}
.yield-preview > p {
  font-size: 13px;
  color: #82a1a7;
}
.yield-ratio {
  margin: 30px 0 21px;
}
.yield-ratio b {
  font-size: 49px;
  color: #188e89;
  font-weight: 600;
  letter-spacing: -1px;
  font-variant-numeric: tabular-nums;
}
.yield-ratio small {
  font-size: 23px;
  margin-left: 4px;
  font-weight: 400;
}
.yield-ratio span {
  display: block;
  font-size: 12px;
  color: #6e969e;
  margin-top: 7px;
}
.yield-weight-bar {
  height: 9px;
  background: #d7e8ed;
  border-radius: 5px;
  overflow: hidden;
}
.yield-weight-bar i {
  height: 100%;
  display: block;
  background: #34a9a2;
  border-radius: 5px;
}
.yield-weight-label {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  font-size: 12px;
  color: #6e969e;
  margin: 11px 0 22px;
}
.yield-preview .yield-note {
  font-size: 12px;
  line-height: 1.9;
  color: #7e9b9f;
}
.yield-preview .el-button {
  margin-top: 20px;
  background: white;
  border-color: #d3e4e8;
  color: #4b858c;
}
.yield-record {
  display: grid;
  grid-template-columns: 1fr 130px 1.5fr;
  align-items: center;
  gap: 20px;
  padding: 22px;
  border-bottom: 1px solid #edf1f7;
}
.yield-record > div:first-child > b {
  font-size: 13px;
  color: #4a6383;
}
.yield-record > div:first-child > span {
  display: block;
  color: #7d93ad;
  font-size: 12px;
  margin-top: 8px;
}
.yield-record small {
  font-size: 12px;
  color: #9cabc0;
  display: block;
  margin-top: 9px;
}
.yield-record-measure b {
  font-size: 24px;
  font-weight: 600;
  color: #269e91;
}
.yield-record p {
  font-size: 12px;
  color: #91a3b9;
  line-height: 1.8;
  margin-top: 9px;
}
.split-inputs {
  display: flex;
  gap: 25px;
}
.split-inputs .el-form-item {
  display: block;
}
.split-inputs:deep(.el-form-item__label) {
  display: block;
  font-size: 13px;
  color: #7f95b1;
  margin-bottom: 8px;
}
.grading-flow {
  display: grid;
  grid-template-columns: 160px 50px 1fr;
  gap: 18px;
  align-items: center;
  padding: 26px;
  background: #f4f7fc;
  border-radius: 10px;
  margin: 15px 0 0;
}
.grading-source {
  text-align: center;
  padding: 23px 13px;
  border: 1px solid #dbe6f5;
  background: white;
  border-radius: 10px;
}
.grading-source > .el-icon {
  font-size: 30px;
  color: #7296cd;
}
.grading-source strong {
  display: block;
  color: #345b8b;
  font-size: 23px;
  margin: 12px 0 9px;
}
.grading-source > span {
  font-size: 12px;
  color: #92a7c3;
}
.grading-connect {
  font-size: 25px;
  color: #b2c5e1;
  text-align: center;
}
.grading-destinations {
  display: grid;
  gap: 14px;
}
.grading-destinations > div {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 15px;
  padding: 15px 17px;
  background: white;
  border: 1px solid #e0e8f4;
  border-radius: 8px;
  overflow: hidden;
}
.grading-destinations span {
  font-size: 13px;
  color: #527194;
}
.grading-destinations b {
  font-size: 17px;
  color: #537bbb;
  font-weight: 550;
}
.grading-destinations i {
  position: absolute;
  left: 0;
  bottom: 0;
  height: 3px;
  background: #70a4e4;
}
.grading-destinations > div:nth-child(2) i {
  background: #64beb2;
}
.grading-destinations .loss-output {
  background: transparent;
  border-style: dashed;
}
.grading-destinations .loss-output b {
  font-size: 14px;
  color: #b19465;
}
.split-result-strip {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
  color: #8498b2;
  font-size: 12px;
  padding: 17px 4px 25px;
}
.split-edit-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr 1fr 30px;
  gap: 12px;
  margin-bottom: 15px;
}
.split-edit-row .el-input-number {
  width: 100%;
}
.split-submit {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: center;
  margin-top: 22px;
}
.split-submit p {
  font-size: 12px;
  line-height: 1.9;
  color: #93a5bd;
  max-width: 400px;
}
.grading-created {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 22px;
  border-bottom: 1px solid #edf1f7;
}
.grading-created b {
  font-size: 13px;
  color: #4f6b8e;
}
.grading-created p {
  font-size: 12px;
  color: #8a9fb9;
  margin-top: 9px;
}
@media (max-width: 1250px) {
  .grading-layout {
    grid-template-columns: 240px minmax(0, 1fr);
  }
  .yield-layout {
    grid-template-columns: 1fr;
  }
  .yield-preview {
    display: none;
  }
  .yield-record {
    grid-template-columns: 1fr 100px;
  }
  .yield-record > div:last-child {
    grid-column: 1/-1;
  }
  .grading-flow {
    grid-template-columns: 140px 25px 1fr;
    gap: 10px;
    padding: 20px;
  }
  .split-edit-row {
    grid-template-columns: 1fr 1fr;
    position: relative;
    padding-right: 35px;
  }
  .split-edit-row > .el-button {
    position: absolute;
    right: 0;
    top: 18px;
  }
}
@media (max-width: 760px) {
  .grading-layout {
    grid-template-columns: 1fr;
    gap: 19px;
  }
  .grading-batches {
    max-height: 245px;
  }
  .grading-batch {
    padding: 16px 20px;
  }
  .grading-batch-hero {
    padding: 23px;
    gap: 16px;
  }
  .grading-batch-hero h2 {
    font-size: 20px;
  }
  .grading-batch-hero b {
    font-size: 25px;
  }
  .grading-batch-hero > div:last-child {
    max-width: 105px;
  }
  .grading-batch-hero > div > span {
    font-size: 12px;
  }
  .grading-tabs {
    gap: 12px;
  }
  .grading-tabs button {
    font-size: 13px;
    padding-left: 3px;
    padding-right: 3px;
  }
  .yield-form-grid {
    grid-template-columns: 1fr;
  }
  .yield-submit {
    flex-wrap: wrap;
  }
  .yield-submit span {
    max-width: none;
  }
  .split-inputs {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 15px;
  }
  .split-inputs .el-input-number {
    width: 100%;
  }
  .grading-flow {
    grid-template-columns: 105px 15px 1fr;
    padding: 14px;
    gap: 8px;
  }
  .grading-source {
    padding: 20px 8px;
  }
  .grading-source strong {
    font-size: 18px;
  }
  .grading-destinations > div {
    padding: 12px 11px;
  }
  .grading-destinations b {
    font-size: 14px;
  }
  .grading-destinations span {
    font-size: 12px;
  }
  .split-submit {
    flex-wrap: wrap;
  }
  .grading-created {
    align-items: flex-start;
    flex-wrap: wrap;
  }
  .yield-record {
    padding: 20px;
    gap: 13px;
  }
}

.yield-history > summary {
  display: flex;
  align-items: center;
  gap: 14px;
  cursor: pointer;
  list-style: none;
  padding: 21px 24px;
  color: #36516f;
  font-size: 14px;
}
.yield-history > summary::-webkit-details-marker {
  display: none;
}
.yield-history > summary > span {
  font-size: 12px;
  color: #7689a1;
}
.yield-history > summary > .el-icon {
  margin-left: auto;
  font-size: 13px;
}
.yield-history[open] > summary {
  border-bottom: 1px solid #e7edf4;
}
.yield-history[open] > summary > .el-icon {
  transform: rotate(180deg);
}
.grading-batch-hero {
  background: #fff;
  border: 1px solid #e3e9f1;
  padding: 25px 28px;
  color: #344f70;
}
.grading-batch-hero h2 {
  color: #2b4669;
  font-size: 23px;
}
.grading-batch-hero p,
.grading-batch-hero span,
.grading-batch-hero small {
  color: #71859f;
  font-size: 12px;
}
.grading-batch-hero > div:last-child > b {
  color: #345d8e;
  font-size: 32px;
}
.grading-batch-hero > div:last-child > b span {
  font-size: 12px;
}

.grading-batch-hero > div > span,
.grading-batch-hero b span {
  color: #71859f;
  font-size: 12px;
}
</style>
