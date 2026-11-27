<script setup>
import { ref, reactive, computed } from 'vue'
import { ElMessageBox } from 'element-plus'
import { useWorkspace, money, qty, dateText } from '@/stores/workspace'
const props = defineProps({ order: Object }),
  w = useWorkspace(),
  creating = ref(false),
  executing = ref(null),
  busy = ref(false)
const form = reactive({ kind: 'discount', quantity: 0, amount: 0, note: '' }),
  execution = reactive({ reference: '', batch_id: null })
const names = {
  discount: '折让退款',
  refund: '退货退款',
  replacement: '补发货物',
  return: '退货交接',
  supplement: '补配追加款',
}
const states = {
  proposed: '待采购方确认',
  accepted: '待实际执行',
  executed: '待接收方核对',
  confirmed: '已核对完成',
  rejected: '未接受',
}
const buyer = computed(() => (w.state.user.managed_buyer_ids || [w.state.user.id]).includes(props.order.buyer_id)),
  seller = computed(
    () =>
      w.isAdmin ||
      (w.state.user.managed_supplier_ids || [w.state.user.id]).includes(
        props.order.snapshot?.supplier_id,
      ),
  )
const active = computed(() =>
  props.order.cases?.some((c) => !['confirmed', 'rejected'].includes(c.status)),
)
function canExecute(c) {
  return c.status === 'accepted' && (['supplement','return'].includes(c.kind) ? buyer.value : seller.value)
}
function canConfirm(c) {
  return c.status === 'executed' && (['supplement','return'].includes(c.kind) ? seller.value : buyer.value)
}
async function propose() {
  busy.value = true
  try {
    await w.act(`orders/${props.order.id}/resolve/`, form, '处理方案已发送，等待采购方确认')
    creating.value = false
  } catch {
  } finally {
    busy.value = false
  }
}
async function act(c, action) {
  try {
    if (action === 'confirm')
      await ElMessageBox.confirm(
        '请确认你已核对实际退款、追加款项、货物或交接结果。系统只保存双方记录，不自动划款。',
        '核对实际执行结果',
        { confirmButtonText: '已核对，确认', cancelButtonText: '继续核对' },
      )
    await w.act(`cases/${c.id}/`, { action }, '处理单进度已同步')
  } catch {}
}
function openExecution(c) {
  executing.value = c
  execution.reference = ''
  execution.batch_id = null
}
async function execute() {
  try {
    await w.act(
      `cases/${executing.value.id}/`,
      { action: 'execute', ...execution },
      '执行凭证已登记，等待接收方核对',
    )
    executing.value = null
  } catch {}
}
</script>
<template>
  <section class="detail-section">
    <div class="case-title">
      <h3>异常处理与价差凭证</h3>
      <el-button
        v-if="seller && order.status === 'issue' && !active"
        type="primary"
        plain
        size="small"
        @click="creating = true"
        >提出处理方案</el-button
      >
    </div>
    <div v-for="c in order.cases || []" :key="c.id" class="case-row">
      <div class="case-title">
        <b>{{ names[c.kind] }} #{{ c.id }}</b
        ><span class="status-badge">{{ states[c.status] }}</span>
      </div>
      <p>
        {{ c.note }}<br />数量 {{ qty(c.quantity) }} {{ order.unit }} / 金额 ¥{{ money(c.amount)
        }}<br v-if="c.reference" /><span v-if="c.reference">实际执行凭证：{{ c.reference }}</span>
      </p>
      <div class="case-actions">
        <template v-if="c.status === 'proposed' && buyer"
          ><el-button size="small" @click="act(c, 'reject')">不接受</el-button
          ><el-button type="primary" size="small" @click="act(c, 'accept')"
            >接受处理条件</el-button
          ></template
        ><el-button v-if="canExecute(c)" type="primary" size="small" @click="openExecution(c)"
          >登记实际执行凭证</el-button
        ><el-button v-if="canConfirm(c)" type="primary" size="small" @click="act(c, 'confirm')"
          >核对执行结果</el-button
        >
      </div>
    </div>
    <p v-if="!order.cases?.length" class="data-note">
      暂无处理单。有验收差异时，由供货方提出明确数量、金额和执行方式，双方逐步确认。
    </p>
    <el-dialog v-model="creating" title="提出可核对的处理方案" width="520px" append-to-body
      ><el-form label-position="top"
        ><el-form-item label="处理方式"
          ><el-select v-model="form.kind"
            ><el-option
              v-for="k in ['discount', 'refund', 'replacement', 'return']"
              :key="k"
              :value="k"
              :label="names[k]" /></el-select
        ></el-form-item>
        <div class="mobile-form-row">
          <el-form-item label="处理数量"
            ><el-input-number
              v-model="form.quantity"
              :min="0"
              :max="order.quantity"
              :precision="2" /></el-form-item
          ><el-form-item label="实际处理金额 / 元"
            ><el-input-number
              v-model="form.amount"
              :min="0"
              :max="order.total_amount"
              :precision="2"
          /></el-form-item>
        </div>
        <el-form-item label="依据、责任和约定执行时间"
          ><el-input v-model="form.note" type="textarea" :rows="4" /></el-form-item></el-form
      ><template #footer
        ><el-button @click="creating = false">取消</el-button
        ><el-button :loading="busy" type="primary" @click="propose"
          >发送采购方确认</el-button
        ></template
      ></el-dialog
    >
    <el-dialog
      :model-value="!!executing"
      title="登记真实执行凭证"
      width="500px"
      append-to-body
      @close="executing = null"
      ><el-form label-position="top"
        ><el-form-item v-if="executing?.kind === 'replacement'" label="本次补发批次"
          ><el-select v-model="execution.batch_id" style="width: 100%"
            ><el-option
              v-for="b in w.state.batches.filter(
                (b) => b.product_id === order.product_id && b.status === 'released',
              )"
              :key="b.id"
              :value="b.id"
              :label="b.code + ' / 可售 ' + qty(b.available)" /></el-select></el-form-item
        ><el-form-item label="实际流水号、配送单号或交接凭证"
          ><el-input v-model="execution.reference" maxlength="200" /></el-form-item
      ></el-form>
      <p class="data-note">
        退款或追加款项在双方账户实际处理后登记。本操作不自动扣款；补发会扣减所选批次的真实可用库存。
      </p>
      <template #footer
        ><el-button @click="executing = null">取消</el-button
        ><el-button type="primary" @click="execute">保存执行凭证</el-button></template
      ></el-dialog
    >
  </section>
</template>
