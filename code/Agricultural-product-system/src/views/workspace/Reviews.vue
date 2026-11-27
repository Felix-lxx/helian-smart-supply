<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useWorkspace, qty, dateText } from '@/stores/workspace'
import request from '@/utils/request'
const w = useWorkspace(),
  route = useRoute(),
  router = useRouter(),
  priorities = ref([]),
  selected = ref(null),
  tab = ref('priority'),
  busy = ref(false),
  creating = ref(false),
  editing = ref(null)
const task = reactive({
  batch_id: null,
  metric: 'appearance',
  target_sample: 50,
  estimated_minutes: 15,
  sample_cost: undefined,
  note: '',
  position: '',
})
const result = reactive({
  sample_size: undefined,
  defect_count: undefined,
  position: '',
  note: '',
  status: 'pending',
})
const metrics = { appearance: '外观瑕疵', rot: '腐坏目标', size: '尺寸偏差' }
const active = computed(() => priorities.value.find((x) => x.batch_id === selected.value)),
  batch = computed(() => w.state.batches.find((x) => x.id === selected.value))
const openTasks = computed(() => w.collaboration.tasks.filter((x) => x.status === 'open'))
async function load() {
  busy.value = true
  try {
    await w.refresh(true)
    const r = await request.get('/workspace/collaboration/?priorities=1', { timeout: 30000 })
    priorities.value = r.data.priorities
    if (!selected.value) selected.value = priorities.value[0]?.batch_id
    if (route.query.task) {
      const t = w.collaboration.tasks.find((x) => x.id === Number(route.query.task))
      if (t) selected.value = t.batch_id
    }
  } catch {
    ElMessage.error('检查任务暂时无法同步，请重试')
  } finally {
    busy.value = false
  }
}
function schedule(id) {
  task.batch_id = id
  task.metric = 'appearance'
  task.target_sample = Math.max(
    50,
    Math.min(
      100000,
      priorities.value.find((p) => p.batch_id === id)?.minimum_zero_defect_sample || 50,
    ),
  )
  task.note = ''
  task.position = ''
  creating.value = true
}
async function create() {
  try {
    await w.act('reviews/', task, '复检任务已建立，供货方可执行')
    creating.value = false
    await load()
  } catch {}
}
function open(t) {
  editing.value = t
  Object.assign(result, {
    sample_size: undefined,
    defect_count: undefined,
    position: t.position,
    note: '',
    status: 'pending',
  })
}
async function complete() {
  try {
    await w.act(`reviews/${editing.value.id}/`, result, '复检已记录，匹配与订单证据已同步')
    editing.value = null
    await load()
  } catch {}
}
onMounted(load)
</script>
<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1>复检任务</h1>
        <p>先检查会影响采购决定的批次，让每次抽样有明确去向。</p>
      </div>
      <el-button icon="Refresh" :loading="busy" @click="load">同步任务与影响范围</el-button>
    </div>
    <div class="insight-band">
      <el-icon :size="30"><Aim /></el-icon>
      <div>
        <h2>{{ openTasks.length }} 项复检待执行</h2>
        <p>
          排序综合受影响采购预算、交期紧迫度、证据区间与预计检查耗时。每次复检独立保留样本记录，不把连续选择性复查当作固定置信保证。
        </p>
      </div>
    </div>
    <div class="priority-layout">
      <section class="panel">
        <div class="panel-head">
          <div class="pill-tabs">
            <button :class="{ active: tab === 'priority' }" @click="tab = 'priority'">
              建议顺序</button
            ><button :class="{ active: tab === 'tasks' }" @click="tab = 'tasks'">
              待办 {{ openTasks.length }}
            </button>
          </div>
        </div>
        <template v-if="tab === 'priority'"
          ><button
            v-for="p in priorities"
            :key="p.batch_id"
            class="task-list-item"
            :class="{ active: selected === p.batch_id }"
            @click="selected = p.batch_id"
          >
            <div class="task-meta">
              <b>{{ p.code }}</b
              ><span class="status-badge" :class="p.priority > 0 ? 'warning' : ''"
                >{{ p.blocked_demands.length }} 项需求</span
              >
            </div>
            <strong>{{ p.product }}</strong>
            <p>
              {{ p.sample_size }} 个已记录样本 / 外观区间 {{ p.interval[0] }}—{{ p.interval[1] }}%
            </p>
            <p>优先顺序值 {{ p.priority.toFixed(2) }}</p>
          </button></template
        >
        <template v-else
          ><button v-for="t in openTasks" :key="t.id" class="task-list-item" @click="open(t)">
            <div class="task-meta">
              <b>{{ t.batch_code }}</b
              ><span class="small muted">#{{ t.id }}</span>
            </div>
            <strong>{{ metrics[t.metric] }} / 计划 {{ t.target_sample }} 个</strong>
            <p>{{ t.note || '待补充抽样说明' }}</p>
            <p>{{ dateText(t.created_at) }}</p>
          </button>
          <div v-if="!openTasks.length" class="compact-empty">
            目前没有待执行复检。<br />可从建议顺序中安排检查。
          </div></template
        >
      </section>
      <div v-if="active && batch">
        <section class="panel">
          <div class="panel-head">
            <div>
              <h2>{{ active.product }}</h2>
              <p class="small muted" style="margin-top: 6px">
                {{ active.code }} / {{ batch.supplier }}
              </p>
            </div>
            <el-button type="primary" icon="Plus" @click="schedule(active.batch_id)"
              >安排复检</el-button
            >
          </div>
          <div class="panel-body">
            <div class="interval-evidence">
              <b>{{ active.interval[0] }}—{{ active.interval[1] }}<small>%</small></b>
              <p>
                外观指标 95% Wilson 区间<br />{{ active.sample_size }} 个样本，{{
                  active.defect_count
                }}
                个外观缺陷
              </p>
            </div>
            <div class="sample-bars">
              <span
                class="usable"
                :style="{
                  width:
                    (active.sample_size
                      ? 100 * (1 - active.defect_count / active.sample_size)
                      : 0) + '%',
                }"
              ></span
              ><span class="rejected" style="flex: 1"></span>
            </div>
            <div class="fact-line" style="margin-top: 12px">
              <span
                >当前状态
                {{
                  batch.status === 'released'
                    ? '已放行'
                    : batch.status === 'quarantine'
                      ? '隔离复核'
                      : '待检'
                }}</span
              ><span>可用 {{ qty(batch.available) }} {{ batch.unit }}</span>
            </div>
            <div class="review-decision-facts">
              <span v-for="(amount, u) in active.influence_by_unit" :key="u"
                >可能影响 {{ qty(amount) }} {{ u }}</span
              >
              <span>预计检查 {{ active.estimated_minutes }} 分钟</span>
              <span v-if="active.minimum_zero_defect_sample"
                >零缺陷时至少
                {{ active.minimum_zero_defect_sample }} 个样本才可能低于当前最严阈值</span
              >
            </div>
            <p class="data-note">
              {{ active.reason }}。区间只针对代表性外观抽样，不等同于食品安全结论。
            </p>
            <router-link :to="'/quality?batch=' + batch.id"
              ><el-button plain>查看图像与历史证据</el-button></router-link
            >
          </div>
        </section>
        <section class="panel section-gap">
          <div class="panel-head">
            <h2>检查结果可能影响的采购需求</h2>
            <span class="small muted">规格和交期先符合，再比较证据</span>
          </div>
          <div class="panel-body">
            <ul class="impact-list">
              <li v-for="d in active.blocked_demands" :key="d.id">
                <div>
                  <b>{{ d.title }}</b
                  ><small
                    >待采购 {{ qty(d.quantity) }} {{ d.unit }} / 外观阈值 {{ d.tolerance }}% /
                    {{ d.deadline }} 前到货</small
                  >
                </div>
                <router-link :to="'/demands?demand=' + d.id"
                  ><el-button link type="primary">核对需求</el-button></router-link
                >
              </li>
            </ul>
            <el-empty
              v-if="!active.blocked_demands.length"
              description="目前没有仅受此项证据阻挡的采购需求"
              :image-size="65"
            />
          </div>
        </section>
        <section class="panel section-gap">
          <div class="panel-head"><h2>任务记录</h2></div>
          <el-table :data="w.collaboration.tasks.filter((t) => t.batch_id === batch.id)"
            ><el-table-column prop="id" label="任务" width="65" /><el-table-column label="指标"
              ><template #default="{ row }">{{ metrics[row.metric] }}</template></el-table-column
            ><el-table-column label="执行状态"
              ><template #default="{ row }"
                ><span class="status-badge">{{
                  row.status === 'completed' ? '已完成' : '待执行'
                }}</span></template
              ></el-table-column
            ><el-table-column label="结果"
              ><template #default="{ row }">{{
                row.result?.sample_size
                  ? row.result.defect_count + ' / ' + row.result.sample_size
                  : '尚未检查'
              }}</template></el-table-column
            ><el-table-column width="90"
              ><template #default="{ row }"
                ><el-button v-if="row.status === 'open'" link type="primary" @click="open(row)"
                  >执行任务</el-button
                ></template
              ></el-table-column
            ></el-table
          >
        </section>
      </div>
      <el-empty v-else description="暂无可检查的批次，先录入商品库存" />
    </div>
    <el-dialog v-model="creating" title="安排代表性复检" width="520px"
      ><el-form label-position="top"
        ><el-form-item label="检查指标"
          ><el-select v-model="task.metric"
            ><el-option
              v-for="(v, k) in metrics"
              :key="k"
              :value="k"
              :label="v" /></el-select></el-form-item
        ><el-form-item label="计划抽样数 / 个"
          ><el-input-number v-model="task.target_sample" :min="1" :max="100000" /></el-form-item
        ><el-form-item label="预计检查分钟"
          ><el-input-number v-model="task.estimated_minutes" :min="1" :max="1440"
        /></el-form-item>
        <el-form-item label="本次抽样成本 / 元（可选）"
          ><el-input-number v-model="task.sample_cost" :min="0" :precision="2"
        /></el-form-item>
        <el-form-item label="抽样位置或箱次"
          ><el-input
            v-model="task.position"
            placeholder="例如前、中、后段各随机选取包装" /></el-form-item
        ><el-form-item label="检查目的"
          ><el-input v-model="task.note" type="textarea" :rows="3" /></el-form-item></el-form
      ><template #footer
        ><el-button @click="creating = false">取消</el-button
        ><el-button type="primary" @click="create">建立任务</el-button></template
      ></el-dialog
    >
    <el-dialog
      :model-value="!!editing"
      title="登记实际复检结果"
      width="560px"
      @close="editing = null"
      ><template v-if="editing"
        ><div class="info-strip">
          {{ editing.batch_code }} / {{ metrics[editing.metric] }} / 计划抽样
          {{ editing.target_sample }} 个。请填写实际样本，不以计划数替代。
        </div>
        <el-form label-position="top" class="section-gap"
          ><div class="mobile-form-row">
            <el-form-item label="实际抽样总数"
              ><el-input-number v-model="result.sample_size" :min="1" :max="100000" /></el-form-item
            ><el-form-item label="本项实际缺陷数"
              ><el-input-number
                v-model="result.defect_count"
                :min="0"
                :max="result.sample_size || 100000"
            /></el-form-item>
          </div>
          <el-form-item label="实际抽样位置 / 箱次"
            ><el-input v-model="result.position" /></el-form-item
          ><el-form-item label="记录与处置依据"
            ><el-input v-model="result.note" type="textarea" :rows="3" /></el-form-item
          ><el-form-item label="人工处置"
            ><el-radio-group v-model="result.status"
              ><el-radio-button value="pending">待复核</el-radio-button
              ><el-radio-button value="released">放行</el-radio-button
              ><el-radio-button value="quarantine">隔离</el-radio-button></el-radio-group
            ></el-form-item
          ></el-form
        ></template
      ><template #footer
        ><el-button @click="editing = null">保留待办</el-button
        ><el-button type="primary" @click="complete">保存实际结果</el-button></template
      ></el-dialog
    >
  </div>
</template>
<style scoped>
.review-decision-facts {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin: 18px 0;
}
.review-decision-facts > span {
  padding: 10px 13px;
  background: #f1f5fd;
  border: 1px solid #e2eafa;
  color: #3b5b83;
  border-radius: 7px;
  font-size: 13px;
  line-height: 1.8;
}
</style>
