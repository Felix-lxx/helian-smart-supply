<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useWorkspace, qty, dateText } from '@/stores/workspace'
import StatusBadge from '@/components/StatusBadge.vue'
import request from '@/utils/request'
import { ElMessage } from 'element-plus'
const w = useWorkspace(),
  route = useRoute(),
  selectedId = ref(Number(route.query.batch) || null),
  filter = ref('all'),
  search = ref(''),
  busy = ref(false),
  visionBusy = ref(false),
  vision = ref(null),
  form = reactive({
    sample_size: undefined,
    defect_count: undefined,
    status: 'pending',
    note: '',
    position: '',
    metrics: { rot: 0, size: 0 },
  })
const dirty = ref(false),
  sourceChanged = ref(false),
  editVersion = ref(null)
let synchronizing = false,
  editingBatch = null
const draftKey = (id) => `hl-quality-${w.state.user.id}-${id}`
function loadEvidence(b, ignoreDraft = false) {
  synchronizing = true
  editingBatch = b.id
  editVersion.value = b.version
  Object.assign(form, {
    sample_size: b.sample_size || undefined,
    defect_count: b.sample_size ? b.defect_count : undefined,
    status: b.status,
    note: b.note,
    position: '',
    metrics: { rot: 0, size: 0 },
  })
  dirty.value = false
  sourceChanged.value = false
  try {
    const saved = !ignoreDraft && JSON.parse(localStorage.getItem(draftKey(b.id)) || 'null')
    if (saved) {
      Object.assign(form, saved.form)
      editVersion.value = saved.version
      dirty.value = true
      sourceChanged.value = saved.version !== b.version
    }
  } catch {}
  synchronizing = false
}
watch(
  form,
  () => {
    if (!synchronizing && editingBatch) {
      dirty.value = true
      localStorage.setItem(
        draftKey(editingBatch),
        JSON.stringify({ form, version: editVersion.value }),
      )
    }
  },
  { deep: true, flush: 'sync' },
)
function reloadEvidence() {
  if (selected.value) {
    localStorage.removeItem(draftKey(selected.value.id))
    loadEvidence(selected.value, true)
  }
}
const list = computed(() =>
  w.state.batches.filter(
    (b) =>
      (b.product_name + b.code).includes(search.value) &&
      (filter.value === 'all' || b.status === filter.value),
  ),
)
const selected = computed(() => w.state.batches.find((b) => b.id === selectedId.value))
watch(
  () => w.state.batches,
  (bs) => {
    if (!selectedId.value && bs.length) selectedId.value = bs[0].id
  },
  { immediate: true },
)
watch(
  selected,
  (b) => {
    if (b) {
      if (b.id !== editingBatch || !dirty.value) loadEvidence(b)
      else if (editVersion.value !== b.version) sourceChanged.value = true
      vision.value = [...b.inspections].reverse().find((x) => x.image_url) || null
    }
  },
  { immediate: true },
)
function interval(n, k) {
  if (!n || !Number.isFinite(k)) return [0, 100]
  const z = 1.95996398454,
    p = k / n,
    den = 1 + (z * z) / n,
    c = (p + (z * z) / 2 / n) / den,
    h = (z * Math.sqrt((p * (1 - p)) / n + (z * z) / 4 / n / n)) / den
  return [Math.max(0, c - h) * 100, Math.min(1, c + h) * 100]
}
const ci = computed(() =>
    interval(form.sample_size, Math.min(form.defect_count, form.sample_size)),
  ),
  threshold = ref(5),
  history = computed(() => [...(selected.value?.inspections || [])].reverse())
async function save() {
  busy.value = true
  try {
    await w.act(
      `batches/${selectedId.value}/inspect/`,
      { ...form, version: editVersion.value },
      '复核记录已保存，库存与受影响订单已同步',
    )
    reloadEvidence()
  } catch {
  } finally {
    busy.value = false
  }
}
async function upload({ file, onSuccess, onError }) {
  visionBusy.value = true
  const d = new FormData()
  d.append('image', file)
  try {
    vision.value = (
      await request.post(`/workspace/batches/${selectedId.value}/vision/`, d, { timeout: 90000 })
    ).data
    await w.refresh(true)
    onSuccess({})
    ElMessage.success('视觉结果已保存，请人工核对后填写抽样记录')
  } catch (e) {
    onError(e)
    ElMessage.error(e.response?.data?.detail || '视觉检测不可用，请继续人工抽样')
  } finally {
    visionBusy.value = false
  }
}
</script>
<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1>品质工作台</h1>
        <p>图像提供线索，抽样提供证据，人工复核决定库存处置。</p>
      </div>
      <div class="row-actions">
        <span class="status-badge released"><i></i>批次与订单联动</span
        ><el-button icon="Refresh" @click="w.refresh()">同步批次</el-button>
      </div>
    </div>
    <div class="quality-layout">
      <aside class="panel batch-list">
        <div class="panel-head">
          <h2>检查任务</h2>
          <span class="small muted">{{ list.length }} 批</span>
        </div>
        <div class="panel-body">
          <el-input
            v-model="search"
            placeholder="搜索批次或商品"
            prefix-icon="Search"
            clearable
          /><el-select v-model="filter" style="width: 100%; margin-top: 12px"
            ><el-option label="全部批次" value="all" /><el-option
              label="待检查"
              value="pending" /><el-option label="已放行" value="released" /><el-option
              label="隔离待复核"
              value="quarantine"
          /></el-select>
        </div>
        <button
          v-for="b in list"
          :key="b.id"
          class="batch-task"
          :class="{ selected: b.id === selectedId }"
          @click="selectedId = b.id"
        >
          <div>
            <strong>{{ b.product_name }}</strong
            ><small>{{ b.code }} · {{ b.grade }}</small>
          </div>
          <StatusBadge :value="b.status" /></button
        ><el-empty v-if="!list.length" description="暂无检查任务" :image-size="60" />
      </aside>
      <div v-if="selected">
        <section class="panel">
          <div class="panel-head">
            <div>
              <h2>
                {{ selected.product_name }}
                <span v-if="selected.is_demo" class="demo-tag">演示记录</span>
              </h2>
              <p class="small muted" style="margin-top: 7px">
                {{ selected.code }} · {{ selected.supplier }} · 库存 {{ qty(selected.quantity)
                }}{{ selected.unit }}
              </p>
            </div>
            <StatusBadge :value="selected.status" />
          </div>
          <div class="panel-body">
            <div class="vision-layout">
              <el-upload
                drag
                :http-request="upload"
                :show-file-list="false"
                accept="image/jpeg,image/png"
                :disabled="visionBusy"
                ><div class="vision-upload">
                  <el-icon size="30"><Camera /></el-icon>
                  <h3>{{ visionBusy ? '正在分析图像…' : '上传批次实拍图' }}</h3>
                  <p>JPG / PNG，最多8MB<br />本地YOLO辅助发现疑似外观异常</p>
                </div></el-upload
              >
              <div class="vision-output" v-loading="visionBusy">
                <el-image
                  v-if="vision?.image_url"
                  :src="vision.image_url"
                  fit="contain"
                  :preview-src-list="[vision.image_url]"
                  preview-teleported
                />
                <div v-else class="vision-empty">
                  <el-icon size="32"><Picture /></el-icon><span>标注结果将在这里展示</span>
                </div>
                <div v-if="vision" class="vision-result">
                  疑似异常目标 <b>{{ vision.bad_count ?? vision.defect_count }}</b> 个 · 待人工核实
                </div>
              </div>
            </div>
            <div class="info-strip warning section-gap">
              当前模型仅辅助发现外观异常，不自动确定抽样总数、商品等级或食品安全。未检出异常也不代表整批合格。
            </div>
          </div>
        </section>
        <section class="panel section-gap">
          <div class="panel-head">
            <h2>抽样证据与人工复核</h2>
            <span class="small muted">记录本次代表性抽样，历史保留</span>
          </div>
          <div class="panel-body">
            <div v-if="dirty" class="info-strip section-gap" :class="{ warning: sourceChanged }">
              {{
                sourceChanged
                  ? '后台已有新版本，你的草稿已保留；提交前需载入新记录并核对。'
                  : '正在编辑的草稿已保存在此设备，后台刷新不会覆盖。'
              }}<el-button link @click="reloadEvidence">放弃草稿并载入最新</el-button>
            </div>
            <el-form label-position="top"
              ><div class="form-grid">
                <el-form-item label="人工确认抽样总数 / 个"
                  ><el-input-number
                    v-model="form.sample_size"
                    :min="1"
                    :max="100000"
                    style="width: 100%" /></el-form-item
                ><el-form-item label="人工确认外观缺陷数 / 个"
                  ><el-input-number
                    v-model="form.defect_count"
                    :min="0"
                    :max="form.sample_size"
                    style="width: 100%"
                /></el-form-item></div
            ></el-form>
            <div class="sampling-visual">
              <div class="sample-summary">
                <div>
                  <span>观察缺陷率</span
                  ><b
                    >{{
                      form.sample_size && form.defect_count != null
                        ? ((form.defect_count / form.sample_size) * 100).toFixed(2)
                        : '—'
                    }}<small>%</small></b
                  >
                </div>
                <div>
                  <span>95% Wilson区间</span
                  ><b>{{ ci[0].toFixed(2) }}—{{ ci[1].toFixed(2) }}<small>%</small></b>
                </div>
                <div>
                  <span>比较要求上限 / %</span
                  ><el-input-number v-model="threshold" :min="0" :max="100" size="small" />
                </div>
              </div>
              <div
                class="interval-track"
                role="img"
                :aria-label="'缺陷率区间' + ci[0].toFixed(2) + '至' + ci[1].toFixed(2) + '%'"
              >
                <div
                  class="interval-range"
                  :style="{ left: ci[0] + '%', width: Math.max(0.4, ci[1] - ci[0]) + '%' }"
                ></div>
                <div class="interval-limit" :style="{ left: threshold + '%' }"></div>
              </div>
              <div class="interval-axis">
                <span>0%</span><span>25%</span><span>50%</span><span>75%</span><span>100%</span>
              </div>
              <p class="small" :class="ci[1] <= threshold ? 'good' : 'warn'">
                {{
                  ci[1] <= threshold
                    ? '此项区间上界未超过比较阈值；仍需核对其他验收条件。'
                    : '此项证据尚不足以支持所设阈值，可追加随机抽样或保持待复核。'
                }}
              </p>
            </div>
            <el-form label-position="top" class="section-gap"
              ><el-form-item label="人工处置"
                ><el-radio-group v-model="form.status"
                  ><el-radio-button value="pending">保持待检</el-radio-button
                  ><el-radio-button value="released">复核放行</el-radio-button
                  ><el-radio-button value="quarantine">隔离复核</el-radio-button></el-radio-group
                ></el-form-item
              ><el-form-item label="实际抽样位置 / 箱次"
                ><el-input v-model="form.position" placeholder="请记录实际覆盖位置"
              /></el-form-item>
              <div class="mobile-form-row">
                <el-form-item label="人工发现腐坏目标数"
                  ><el-input-number
                    v-model="form.metrics.rot"
                    :min="0"
                    :max="form.sample_size || 100000" /></el-form-item
                ><el-form-item label="人工确认尺寸偏差数"
                  ><el-input-number
                    v-model="form.metrics.size"
                    :min="0"
                    :max="form.sample_size || 100000"
                /></el-form-item>
              </div>
              <el-form-item label="抽样方法、覆盖箱次及处理说明"
                ><el-input
                  v-model="form.note"
                  type="textarea"
                  :rows="3"
                  placeholder="请说明抽样覆盖、人工确认依据和放行/隔离原因"
                  maxlength="2000" /></el-form-item
              ><el-button type="primary" :loading="busy" @click="save"
                >保存复核，并同步库存</el-button
              ></el-form
            >
            <p class="data-note">
              Wilson区间基于二项抽样假设。选择性拍照、漏检或箱间差异不能由该区间消除；人工应确认抽样代表性。
            </p>
          </div>
        </section>
        <section class="panel section-gap">
          <div class="panel-head">
            <h2>检查记录</h2>
            <span class="small muted">保留每次记录，不覆盖历史</span>
          </div>
          <div class="panel-body">
            <div class="timeline">
              <div v-for="(h, i) in history" :key="i" class="timeline-item">
                <b>{{
                  h.type === 'vision'
                    ? '视觉辅助检查'
                    : '人工复核 · ' +
                      (h.status === 'released'
                        ? '放行'
                        : h.status === 'quarantine'
                          ? '隔离'
                          : '待检')
                }}</b>
                <p class="muted">{{ h.note }}</p>
                <small
                  >{{ h.actor }} · {{ dateText(h.time) }}
                  <span v-if="h.sample_size"
                    >· 抽样{{ h.sample_size }} / 缺陷{{ h.defect_count }}</span
                  ></small
                >
              </div>
            </div>
            <p v-if="!history.length" class="small muted">
              当前为批次初始记录，下一次检查将写入时间线。
            </p>
          </div>
        </section>
      </div>
      <div v-else class="panel empty-state">选择一个批次开始检查，或先在商品与批次中创建库存。</div>
    </div>
  </div>
</template>
<style scoped>
.quality-layout {
  display: grid;
  grid-template-columns: 285px minmax(0, 1fr);
  gap: 22px;
  align-items: start;
}
.batch-list {
  position: sticky;
  top: 90px;
}
.batch-task {
  width: 100%;
  border: 0;
  border-top: 1px solid var(--line);
  background: white;
  padding: 18px;
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
  text-align: left;
  color: inherit;
}
.batch-task.selected {
  background: #edf5ee;
}
.batch-task strong {
  font-size: 12px;
  font-weight: 500;
}
.batch-task small {
  font-size: 10px;
  color: var(--muted);
  display: block;
  margin-top: 8px;
}
.batch-task .status-badge {
  font-size: 10px;
  padding: 3px 5px;
}
.vision-layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}
.vision-upload {
  height: 190px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
  color: #5b7d65;
}
.vision-upload p {
  font-size: 11px;
  line-height: 1.9;
  color: var(--muted);
}
.vision-layout :deep(.el-upload-dragger) {
  padding: 15px;
}
.vision-output {
  min-height: 220px;
  border-radius: 8px;
  overflow: hidden;
  background: #f0f4ef;
  position: relative;
}
.vision-output > .el-image {
  width: 100%;
  height: 220px;
}
.vision-empty {
  height: 220px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 15px;
  color: #8a9d8b;
  font-size: 12px;
}
.vision-result {
  background: #e4ede2;
  padding: 10px 15px;
  font-size: 12px;
}
.sampling-visual {
  background: #f7faf6;
  border-radius: 9px;
  padding: 22px;
}
.sample-summary {
  display: flex;
  gap: 20px;
  justify-content: space-between;
  flex-wrap: wrap;
}
.sample-summary > div {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.sample-summary span {
  font-size: 11px;
  color: var(--muted);
}
.sample-summary b {
  font-size: 23px;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}
.sample-summary small {
  font-size: 12px;
  color: var(--muted);
}
.interval-track {
  position: relative;
  height: 15px;
  background: #e2e9df;
  margin: 25px 0 8px;
  border-radius: 3px;
}
.interval-range {
  position: absolute;
  height: 15px;
  background: #5a9a6c;
  border-radius: 3px;
}
.interval-limit {
  position: absolute;
  top: -5px;
  height: 25px;
  width: 2px;
  background: #b78a39;
}
.interval-axis {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  color: #758774;
  margin-bottom: 18px;
}
@media (max-width: 1150px) {
  .quality-layout {
    grid-template-columns: 230px minmax(0, 1fr);
  }
  .vision-layout {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 800px) {
  .quality-layout {
    grid-template-columns: 1fr;
  }
  .batch-list {
    position: static;
    max-height: 320px;
    overflow: auto;
  }
  .sample-summary b {
    font-size: 19px;
  }
}
</style>
