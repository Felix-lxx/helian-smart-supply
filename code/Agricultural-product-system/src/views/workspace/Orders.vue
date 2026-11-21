<script setup>
import { ref, computed, reactive, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { useWorkspace, money, qty, dateText, labels } from '@/stores/workspace'
import StatusBadge from '@/components/StatusBadge.vue'
import SettlementPanel from '@/components/SettlementPanel.vue'
const w = useWorkspace(),
  route = useRoute(),
  search = ref(''),
  status = ref(route.query.status || 'all'),
  page = ref(1),
  detailId = ref(null),
  drawer = ref(false),
  dialog = ref(false),
  action = ref(''),
  target = ref(null),
  busy = ref(false),
  form = reactive({
    reference: '',
    carrier: '',
    tracking_number: '',
    accepted_quantity: 0,
    received_quantity: 0,
    quantity: 0,
    delivery_id: null,
    quality_issue: '',
    packaging_issue: '',
    note: '',
  })
watch(
  () => route.query.status,
  (s) => {
    status.value = s || 'all'
    page.value = 1
  },
)
const filtered = computed(() =>
  w.state.orders.filter(
    (o) =>
      (status.value === 'all' || o.status === status.value) &&
      (o.name + o.number + o.buyer + o.supplier).toLowerCase().includes(search.value.toLowerCase()),
  ),
)
const rows = computed(() => filtered.value.slice((page.value - 1) * 10, page.value * 10)),
  detail = computed(() => w.state.orders.find((o) => o.id === detailId.value))
const actionTitles = {
  'submit-payment': '提交付款确认',
  'confirm-payment': '核对收款',
  ship: '登记发运信息',
  receive: '确认到货验收',
  resolve: '提出差异处理方案',
  'accept-resolution': '确认处理结果',
}
function open(o) {
  detailId.value = o.id
  drawer.value = true
}
function openAction(o, a) {
  target.value = o
  action.value = a
  Object.assign(form, {
    reference: '',
    carrier: '',
    tracking_number: '',
    quantity: (o.quantity || 0) - (o.dispatched_quantity || 0),
    delivery_id: o.deliveries?.find((d) => d.status === 'shipped')?.id || null,
    received_quantity:
      o.deliveries?.find((d) => d.status === 'shipped')?.quantity || o.quantity || 0,
    accepted_quantity:
      o.deliveries?.find((d) => d.status === 'shipped')?.quantity || o.quantity || 0,
    quality_issue: '',
    packaging_issue: '',
    note: '',
  })
  dialog.value = true
}
function chooseDelivery(id) {
  const d = target.value.deliveries.find((d) => d.id === id)
  if (d) {
    form.received_quantity = Number(d.quantity)
    form.accepted_quantity = Number(d.quantity)
  }
}
let openedNavigation = ''
watch(
  [() => route.fullPath, () => w.state.orders],
  () => {
    const id = Number(route.query.order)
    const o = w.state.orders.find((x) => x.id === id)
    if (o) {
      detailId.value = id
      drawer.value = true
      const key = route.fullPath
      if (openedNavigation !== key && ['ship', 'receive'].includes(route.query.action)) {
        openedNavigation = key
        openAction(o, route.query.action)
      }
    }
  },
  { immediate: true },
)
async function perform() {
  busy.value = true
  try {
    await w.act(`orders/${target.value.id}/${action.value}/`, form, '订单已更新，相关方已收到通知')
    dialog.value = false
  } catch {
  } finally {
    busy.value = false
  }
}
async function cancel(o) {
  try {
    await ElMessageBox.confirm('取消后将释放预留库存，并保留历史记录。', '取消订单', {
      type: 'warning',
      confirmButtonText: '确认取消',
      cancelButtonText: '继续采购',
    })
    await w.act(`orders/${o.id}/cancel/`, {}, '订单已取消，库存已释放')
  } catch {}
}
function exportOrders() {
  const safe = (v) =>
    '"' +
    String(v ?? '')
      .replace(/^[=+@-]/, "'")
      .replaceAll('"', '""') +
    '"'
  const fields = ['订单号', '货品', '采购方', '供应方', '数量', '单位', '金额', '状态']
  const values = filtered.value.map((o) => [
    o.number,
    o.name,
    o.buyer,
    o.supplier,
    o.quantity,
    o.unit,
    o.total_amount,
    labels[o.status],
  ])
  const csv = '\ufeff' + [fields, ...values].map((r) => r.map(safe).join(',')).join('\r\n')
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8;' }))
  const a = document.createElement('a')
  a.href = url
  a.download = '禾链订单明细.csv'
  a.click()
  URL.revokeObjectURL(url)
}
</script>
<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1>{{ w.isBuyer ? '我的采购订单' : '订单履约' }}</h1>
        <p>
          {{
            w.isBuyer
              ? '从下单到验收，跟进每一笔采购。'
              : '核对收款、登记发运、处理验收差异，保持交付有序。'
          }}
        </p>
      </div>
      <div class="head-actions">
        <el-button icon="Download" @click="exportOrders">导出当前明细</el-button
        ><el-button icon="Refresh" @click="w.refresh()">刷新订单</el-button>
      </div>
    </div>
    <div class="metrics">
      <div class="metric">
        <span class="metric-label">待核对收款</span
        ><b class="metric-value" style="display: block">{{
          w.state.orders.filter((o) => o.payment_status === 'review').length
        }}</b
        ><span class="metric-foot">由收款方核实实际到账</span>
      </div>
      <div class="metric">
        <span class="metric-label">等待发运</span
        ><b class="metric-value" style="display: block">{{ w.state.stats.shipping || 0 }}</b
        ><span class="metric-foot">已确认收款的订单</span>
      </div>
      <div class="metric">
        <span class="metric-label">运输途中</span
        ><b class="metric-value" style="display: block">{{ w.state.stats.transit || 0 }}</b
        ><span class="metric-foot">待采购方验收</span>
      </div>
      <div class="metric">
        <span class="metric-label">验收差异</span
        ><b class="metric-value warn" style="display: block">{{ w.state.stats.issues || 0 }}</b
        ><span class="metric-foot">双方协商后确认完成</span>
      </div>
    </div>
    <section class="panel">
      <div class="toolbar">
        <div class="pill-tabs">
          <button
            v-for="[id, n] in [
              ['all', '全部订单'],
              ['pending', '待付款'],
              ['paid', '待发运'],
              ['shipped', '运输中'],
              ['issue', '验收异常'],
              ['completed', '已完成'],
              ['cancelled', '已取消'],
            ]"
            :key="id"
            :class="{ active: status === id }"
            @click="
              () => {
                status = id
                page = 1
              }
            "
          >
            {{ n }}
          </button>
        </div>
        <el-input
          v-model="search"
          placeholder="搜索订单、货品或交易方"
          prefix-icon="Search"
          clearable
          @input="page = 1"
        />
      </div>
      <el-table :data="rows" @row-click="open" style="cursor: pointer"
        ><el-table-column label="订单 / 货品" min-width="230"
          ><template #default="{ row }"
            ><div class="table-product">
              <el-image :src="row.image_url" fit="cover" class="thumb" />
              <div>
                <strong>{{ row.name }} <span v-if="row.is_demo" class="demo-tag">演示</span></strong
                ><small>{{ row.number }}</small>
              </div>
            </div></template
          ></el-table-column
        ><el-table-column :label="w.isBuyer ? '供应方' : '采购方'" min-width="120"
          ><template #default="{ row }">{{
            w.isBuyer ? row.supplier : row.buyer
          }}</template></el-table-column
        ><el-table-column label="数量" width="105"
          ><template #default="{ row }">{{
            row.quantity === null ? '历史未记录' : qty(row.quantity) + ' ' + row.unit
          }}</template></el-table-column
        ><el-table-column label="订单金额" width="130"
          ><template #default="{ row }"
            ><b class="amount">¥{{ money(row.total_amount) }}</b></template
          ></el-table-column
        ><el-table-column label="收款状态" width="130"
          ><template #default="{ row }"
            ><StatusBadge :value="row.payment_status" /></template></el-table-column
        ><el-table-column label="履约状态" width="115"
          ><template #default="{ row }"
            ><StatusBadge :value="row.status" /></template></el-table-column
        ><el-table-column label="操作" width="165" fixed="right"
          ><template #default="{ row }"
            ><div @click.stop>
              <el-button
                v-if="w.isBuyer && row.status === 'pending' && row.payment_status === 'unpaid'"
                link
                type="primary"
                @click="openAction(row, 'submit-payment')"
                >提交付款</el-button
              ><el-button
                v-if="!w.isBuyer && row.payment_status === 'review'"
                link
                type="primary"
                @click="openAction(row, 'confirm-payment')"
                >核对收款</el-button
              ><el-button
                v-if="!w.isBuyer && row.status === 'paid'"
                link
                type="primary"
                @click="openAction(row, 'ship')"
                >登记发运</el-button
              ><el-button
                v-if="
                  w.isBuyer &&
                  (row.status === 'shipped' || row.deliveries?.some((d) => d.status === 'shipped'))
                "
                link
                type="primary"
                @click="openAction(row, 'receive')"
                >到货验收</el-button
              ><el-button
                v-if="!w.isBuyer && row.status === 'issue'"
                link
                type="primary"
                @click="open(row)"
                >处理差异</el-button
              ><el-button link @click="open(row)">详情</el-button>
            </div></template
          ></el-table-column
        ></el-table
      ><el-pagination
        v-if="filtered.length > 10"
        v-model:current-page="page"
        :total="filtered.length"
        :page-size="10"
        layout="total,prev,pager,next"
      />
    </section>
    <p class="data-note">
      付款以收款方核对记录为准，本系统不会自动扣款或执行退款。{{
        w.state.stats.limited ? '当前工作台展示最近500笔订单。' : ''
      }}
    </p>
    <el-drawer v-model="drawer" title="订单详情与交付时间线" size="560px"
      ><template v-if="detail"
        ><div class="detail-section">
          <div class="row-actions">
            <h2>{{ detail.name }}</h2>
            <StatusBadge :value="detail.status" />
          </div>
          <p class="small muted" style="margin: 9px 0">
            {{ detail.number }} <span v-if="detail.is_demo" class="demo-tag">演示订单</span>
          </p>
          <div class="kv">
            <span>成交规格</span
            ><b
              >{{ detail.snapshot.grade || '历史未记录' }} ·
              {{ detail.snapshot.packaging || '—' }}</b
            >
          </div>
          <div class="kv">
            <span>成交数量与单价</span
            ><b
              >{{ detail.quantity === null ? '未记录' : qty(detail.quantity) }} {{ detail.unit }} ×
              ¥{{ money(detail.unit_price) }}</b
            >
          </div>
          <div class="kv">
            <span>成交金额</span><b>¥{{ money(detail.total_amount) }}</b>
          </div>
          <div v-if="detail.snapshot.pricing" class="kv">
            <span>其中包装费 / 运费</span
            ><b
              >¥{{ money(detail.snapshot.pricing.packaging) }} /
              {{ money(detail.snapshot.pricing.freight) }}</b
            >
          </div>
          <div v-if="detail.allocations?.length" class="detail-section">
            <h3 style="margin: 18px 0 10px">当前履约分配</h3>
            <div v-for="a in detail.allocations" :key="a.id" class="kv">
              <span>{{ a.batch_code }}</span
              ><b>{{ qty(a.quantity) }} {{ detail.unit }} / 已发 {{ qty(a.dispatched) }}</b>
            </div>
            <p v-if="detail.snapshot.recovery_plan" class="data-note">
              已按各方确认的补配方案 #{{
                detail.snapshot.recovery_plan
              }}
              更新履约批次；原成交快照保留，价差在下方处理单核对。
            </p>
          </div>
          <div class="kv">
            <span>供货批次</span><b>{{ detail.batch_code || '历史未关联' }}</b>
          </div>
          <div class="kv">
            <span>交易双方</span><b>{{ detail.buyer }} / {{ detail.supplier }}</b>
          </div>
        </div>
        <div class="detail-section">
          <h3>收货与配送</h3>
          <p class="small" style="line-height: 2">
            {{ detail.receiver_name }} {{ detail.receiver_phone }}<br />{{
              detail.address || '待补充收货信息'
            }}
          </p>
          <div class="kv">
            <span>承运方</span><b>{{ detail.carrier || '尚未发运' }}</b>
          </div>
          <div class="kv">
            <span>运单 / 配送单</span><b>{{ detail.tracking_number || '—' }}</b>
          </div>
          <div class="kv" v-if="detail.payment_reference">
            <span>付款说明</span><b>{{ detail.payment_reference }}</b>
          </div>
        </div>
        <div v-if="detail.issue" class="info-strip warning detail-section">
          <strong>验收差异</strong>
          <p>{{ detail.issue }}</p>
          <p>
            实际接收 {{ qty(detail.accepted_quantity) }} / {{ qty(detail.quantity) }}
            {{ detail.unit }}
          </p>
          <p v-if="detail.resolution">协商方案：{{ detail.resolution }}</p>
        </div>
        <div class="detail-section">
          <h3>业务时间线</h3>
          <div class="timeline">
            <div v-for="(e, i) in detail.events" :key="i" class="timeline-item">
              <b>{{ e.title }}</b>
              <p class="muted">{{ e.note }}</p>
              <small>{{ e.actor }} · {{ dateText(e.time) }}</small>
            </div>
            <p v-if="!detail.events.length" class="muted small">旧版订单尚无详细事件记录。</p>
          </div>
        </div>
        <SettlementPanel :order="detail" />
        <el-button
          v-if="w.isBuyer && detail.status === 'pending' && detail.payment_status === 'unpaid'"
          type="danger"
          plain
          @click="cancel(detail)"
          >取消并释放库存</el-button
        ><router-link v-if="detail.product_id" :to="'/product/' + detail.product_id"
          ><el-button style="margin-left: 10px">查看当前货源</el-button></router-link
        ></template
      ></el-drawer
    >
    <el-dialog v-model="dialog" :title="actionTitles[action]" width="500px"
      ><template v-if="target"
        ><div class="info-strip" style="margin-bottom: 20px">
          {{ target.number }} · {{ target.name }} · ¥{{ money(target.total_amount) }}
        </div>
        <el-form label-position="top"
          ><el-form-item v-if="action === 'submit-payment'" label="转账流水号或付款凭证说明"
            ><el-input
              v-model="form.reference"
              placeholder="填写实际付款信息，等待收款方核实"
              maxlength="200"
          /></el-form-item>
          <div v-if="action === 'confirm-payment'" class="detail-section">
            <p>付款方提交：{{ target.payment_reference }}</p>
            <p class="data-note">请在你的收款账户核实金额与付款方后确认。此操作仅记录核对结果。</p>
          </div>
          <template v-if="action === 'ship'"
            ><el-form-item :label="'本次发运数量 / ' + target.unit"
              ><el-input-number
                v-model="form.quantity"
                :min="0.01"
                :max="target.quantity - target.dispatched_quantity"
                :precision="2" /></el-form-item
            ><el-form-item label="承运方 / 配送负责人"
              ><el-input
                v-model="form.carrier"
                placeholder="例如：本地冷链配送 / 承运公司" /></el-form-item
            ><el-form-item label="运单号 / 配送单号"
              ><el-input v-model="form.tracking_number" /></el-form-item></template
          ><template v-if="action === 'receive'"
            ><el-form-item
              v-if="target.deliveries?.some((d) => d.status === 'shipped')"
              label="本次验收的配送单"
              ><el-select v-model="form.delivery_id" style="width: 100%" @change="chooseDelivery"
                ><el-option
                  v-for="d in target.deliveries.filter((d) => d.status === 'shipped')"
                  :key="d.id"
                  :value="d.id"
                  :label="
                    d.tracking_number + ' / ' + qty(d.quantity) + target.unit
                  " /></el-select></el-form-item
            ><el-form-item :label="'实际到货数量 / ' + target.unit"
              ><el-input-number
                v-model="form.received_quantity"
                :min="0"
                :max="
                  target.deliveries?.find((d) => d.id === form.delivery_id)?.quantity ||
                  target.quantity
                "
                :precision="2" /></el-form-item
            ><el-form-item :label="'符合约定的合格数量 / ' + target.unit"
              ><el-input-number
                v-model="form.accepted_quantity"
                :min="0"
                :max="target.quantity"
                :precision="2" /></el-form-item
            ><el-form-item label="品质差异 / 足量到货也可登记"
              ><el-input
                v-model="form.quality_issue"
                placeholder="例如成熟度、腐坏或规格不符合约定" /></el-form-item
            ><el-form-item label="包装差异"
              ><el-input
                v-model="form.packaging_issue"
                placeholder="破损、包装规格或标识差异" /></el-form-item
            ><el-form-item label="验收备注 / 差异原因"
              ><el-input
                v-model="form.note"
                type="textarea"
                :rows="3"
                placeholder="部分接收时请说明短重、规格或品质差异" /></el-form-item></template
          ><el-form-item v-if="action === 'resolve'" label="双方协商处理方案"
            ><el-input
              v-model="form.note"
              type="textarea"
              :rows="4"
              placeholder="说明补货安排或线下退赔及核对情况，采购商确认后完成"
          /></el-form-item>
          <div v-if="action === 'accept-resolution'" class="info-strip warning">
            供应方方案：{{ target.resolution }}<br />请确认相关补货或线下退赔已落实后再完成。
          </div></el-form
        ></template
      ><template #footer
        ><el-button @click="dialog = false">暂不处理</el-button
        ><el-button type="primary" :loading="busy" @click="perform">{{
          action === 'confirm-payment' ? '已核实到账，确认' : '确认提交'
        }}</el-button></template
      ></el-dialog
    >
  </div>
</template>
