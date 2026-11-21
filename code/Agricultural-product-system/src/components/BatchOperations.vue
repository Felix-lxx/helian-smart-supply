<script setup>
import { ref, reactive, computed } from 'vue'
import { useWorkspace, qty, money, dateText } from '@/stores/workspace'
const props = defineProps({ batch: Object }),
  w = useWorkspace(),
  tab = ref('weight'),
  busy = ref(false)
const weight = reactive({ input_weight: undefined, usable_weight: undefined, note: '' }),
  stock = reactive({ kind: 'loss', quantity: undefined, grade: '', note: '' })
const ledger = computed(() => w.collaboration.ledger.filter((x) => x.batch_id === props.batch?.id))
const yieldRate = computed(() =>
  weight.input_weight && weight.usable_weight != null
    ? (100 * weight.usable_weight) / weight.input_weight
    : null,
)
async function saveWeight() {
  busy.value = true
  try {
    await w.act(
      `batches/${props.batch.id}/measure/`,
      { ...weight, version: props.batch.version },
      '分拣实称已保存，可用于净可用成本比较',
    )
  } catch {
  } finally {
    busy.value = false
  }
}
async function saveStock() {
  busy.value = true
  try {
    await w.act(
      `batches/${props.batch.id}/stock/`,
      stock,
      stock.kind === 'split' ? '已按数量守恒拆出待检子批次' : '损耗已登记，库存已同步',
    )
    stock.quantity = undefined
    stock.note = ''
  } catch {
  } finally {
    busy.value = false
  }
}
const names = {
  reserve: '下单预留',
  release: '取消释放',
  dispatch: '发运出库',
  inbound: '录入入库',
  inspect: '人工复核',
  review: '复检处置',
  weigh: '分拣称重',
  loss: '损耗登记',
  split: '拆批移出',
  split_in: '子批入库',
  incident: '异常隔离',
  recovery_release: '补配释放',
  recovery_reserve: '补配预留',
  replacement: '补发出库',
}
</script>
<template>
  <div v-if="batch">
    <div class="pill-tabs" style="margin-bottom: 20px">
      <button :class="{ active: tab === 'weight' }" @click="tab = 'weight'">分拣实称</button
      ><button :class="{ active: tab === 'stock' }" @click="tab = 'stock'">库存作业</button
      ><button :class="{ active: tab === 'ledger' }" @click="tab = 'ledger'">库存流水</button>
    </div>
    <div class="info-strip">
      {{ batch.code }} / {{ batch.product_name }} / 可售 {{ qty(batch.available) }}
      {{ batch.unit }} / 已预留 {{ qty(batch.reserved) }} {{ batch.unit }}
    </div>
    <el-form v-if="tab === 'weight'" label-position="top" class="section-gap"
      ><div class="mobile-form-row">
        <el-form-item :label="'本次投入重量 / ' + batch.unit"
          ><el-input-number
            v-model="weight.input_weight"
            :min="0.01"
            :precision="2" /></el-form-item
        ><el-form-item :label="'本次可用重量 / ' + batch.unit"
          ><el-input-number
            v-model="weight.usable_weight"
            :min="0"
            :max="weight.input_weight || 1000000"
            :precision="2"
        /></el-form-item>
      </div>
      <el-form-item label="用途、覆盖范围与剔除依据"
        ><el-input
          v-model="weight.note"
          type="textarea"
          :rows="3"
          placeholder="例如：厨房加工，随机抽取5箱，去除外观与尺寸不符合部分；称重设备…"
      /></el-form-item>
      <div class="sample-bars">
        <span class="usable" :style="{ width: (yieldRate || 0) + '%' }"></span
        ><span class="rejected" style="flex: 1"></span>
      </div>
      <p class="data-note">
        本次净得率
        {{
          yieldRate == null ? '待录入' : yieldRate.toFixed(2) + '%'
        }}。仅保存实际输入，不改变实物库存。
      </p>
      <div v-if="batch.input_weight" class="kv">
        <span>最近实称记录</span
        ><b>{{ qty(batch.usable_weight) }} / {{ qty(batch.input_weight) }} {{ batch.unit }}</b>
      </div>
      <el-button
        type="primary"
        :loading="busy"
        :disabled="!['kg', '斤'].includes(batch.unit)"
        @click="saveWeight"
        >保存称重依据</el-button
      ></el-form
    >
    <el-form v-if="tab === 'stock'" label-position="top" class="section-gap"
      ><el-form-item label="作业方式"
        ><el-radio-group v-model="stock.kind"
          ><el-radio-button value="loss">登记未预留损耗</el-radio-button
          ><el-radio-button value="split">分级拆批</el-radio-button></el-radio-group
        ></el-form-item
      ><el-form-item :label="'操作数量 / ' + batch.unit"
        ><el-input-number
          v-model="stock.quantity"
          :min="0.01"
          :max="Math.max(0, batch.quantity - batch.reserved)"
          :precision="2" /></el-form-item
      ><el-form-item v-if="stock.kind === 'split'" label="子批次等级"
        ><el-input v-model="stock.grade" placeholder="例如：加工级，需单独复核" /></el-form-item
      ><el-form-item label="实际作业依据"
        ><el-input v-model="stock.note" type="textarea" :rows="3"
      /></el-form-item>
      <p class="data-note">
        拆批从原批次扣减等量数量，新子批次保持待检。涉及已预留货物的短缺，请从异常补配登记，不能直接扣减。
      </p>
      <el-button type="primary" :loading="busy" @click="saveStock">{{
        stock.kind === 'split' ? '拆出待检子批次' : '保存损耗流水'
      }}</el-button></el-form
    >
    <div v-if="tab === 'ledger'" class="section-gap">
      <el-table :data="ledger"
        ><el-table-column label="业务动作"
          ><template #default="{ row }"
            >{{ names[row.kind] || row.kind
            }}<small class="muted" style="display: block">{{
              dateText(row.created_at)
            }}</small></template
          ></el-table-column
        ><el-table-column label="实物变化"
          ><template #default="{ row }"
            >{{ row.quantity > 0 ? '+' : '' }}{{ qty(row.quantity) }}</template
          ></el-table-column
        ><el-table-column label="预留变化"
          ><template #default="{ row }"
            >{{ row.reserved_delta > 0 ? '+' : '' }}{{ qty(row.reserved_delta) }}</template
          ></el-table-column
        ><el-table-column label="实物 / 预留余额"
          ><template #default="{ row }"
            >{{ qty(row.balance) }} / {{ qty(row.reserved_balance) }}</template
          ></el-table-column
        ><el-table-column prop="actor" label="操作人"
      /></el-table>
      <p class="data-note">流水从本次升级后的实际操作开始记录，不补造历史入库。</p>
    </div>
  </div>
</template>
