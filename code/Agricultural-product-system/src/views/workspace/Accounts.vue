<script setup>
defineOptions({ name: 'BusinessAccounts' })
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { useWorkspace, money, qty, dateText } from '@/stores/workspace'
import { useBusinessFeed } from '@/composables/useBusinessFeed'
import request from '@/utils/request'
const route = useRoute()
const w = useWorkspace(),
  router = useRouter(),
  tab = ref('weight'),
  data = ref({ reconciliations: [], supplier_settlements: [], cases: [], summary: {} }),
  filter = ref('pending'),
  submitting = ref(null)
const { busy, error, refresh } = useBusinessFeed(async () => {
  data.value = (
    await request.get('/workspace/accounts/', { timeout: 30000, params: route.query })
  ).data
})
const states = {
  pending: '待核对',
  disputed: '需要补充依据',
  confirmed: '已核对',
  accepted: '待实际执行',
  executed: '待接收方核对',
  recorded: '已登记付款',
  proposed: '待接受方案',
  rejected: '未接受',
  cancelled: '已取消',
}
const names = {
  discount: '折让退款',
  refund: '退款',
  replacement: '补发',
  return: '退货',
  supplement: '追加款',
}
const managed = computed(() => w.state.user.managed_supplier_ids || [w.state.user.id])
const rows = computed(() =>
  data.value.reconciliations.filter((r) => filter.value === 'all' || r.status !== 'confirmed'),
)
async function confirm(r, action) {
  try {
    let note = ''
    if (['reject', 'resubmit'].includes(action)) {
      const p = await ElMessageBox.prompt(
        action === 'resubmit'
          ? '请补充称重凭证、设备编号或核对依据。原验收数量保留供双方核对。'
          : '请填写需要重新核对的重量或证据',
        '补充对账依据',
        { inputType: 'textarea', inputValidator: (v) => !!v?.trim() || '请填写依据' },
      )
      note = p.value
    } else
      await ElMessageBox.confirm(
        `约定 ${qty(r.expected)} ${r.unit}，合格实收 ${qty(r.accepted)} ${r.unit}，按成交单价形成尾差 ¥${money(r.difference)}。确认后生成待执行处理单。`,
        '核对实际重量',
        { confirmButtonText: '确认重量与差额', cancelButtonText: '继续核对' },
      )
    submitting.value = r.id
    await w.act(
      `accounts/${r.id}/`,
      { action, note },
      action === 'confirm' ? '实际重量已核对，尾差处理单已建立' : '核对依据已记录',
    )
    await refresh()
  } catch {
    // Operation errors are shown by the shared workspace action; dialog cancellation is intentional.
  } finally {
    submitting.value = null
  }
}
async function supply(s, action) {
  try {
    let reference = ''
    if (action === 'record') {
      const p = await ElMessageBox.prompt(
        `向 ${s.supplier} 实际支付 ¥${money(s.amount)} 后，填写凭证。系统不会自动划款。`,
        '登记实际供货付款',
        { inputValidator: (v) => v?.trim().length >= 4 || '请输入至少4个字符的实际凭证' },
      )
      reference = p.value
    } else
      await ElMessageBox.confirm(
        `请确认已收到 ${s.payer} 的实际供货款 ¥${money(s.amount)}。`,
        '核对实际到账',
        { confirmButtonText: '已核对到账', cancelButtonText: '继续核对' },
      )
    submitting.value = s.id
    await w.act(`supplier-payments/${s.id}/`, { action, reference }, '供货款核对状态已同步')
    await refresh()
  } catch {
    // Operation errors are shown by the shared workspace action; dialog cancellation is intentional.
  } finally {
    submitting.value = null
  }
}
</script>
<template>
  <div class="page" v-loading="busy && !data.reconciliations.length">
    <div class="page-head">
      <div>
        <h1>实重与资金对账</h1>
        <p>让每一笔差额，都能对应实际数量、成交价格和执行凭证。</p>
      </div>
      <el-button icon="Refresh" @click="refresh()">同步对账记录</el-button>
    </div>
    <div v-if="error" class="business-error">
      {{ error }}<el-button link @click="refresh()">重试</el-button>
    </div>
    <section class="panel section-gap">
      <div class="toolbar">
        <div class="pill-tabs">
          <button :class="{ active: tab === 'weight' }" @click="tab = 'weight'">
            实重验收对账
            <span class="tab-counter">{{ data.summary.weight_pending || 0 }}</span></button
          ><button :class="{ active: tab === 'cases' }" @click="tab = 'cases'">
            退款与补款处理
            <span class="tab-counter">{{ data.summary.cases_pending || 0 }}</span></button
          ><button :class="{ active: tab === 'supply' }" @click="tab = 'supply'">
            替代供货对账 <span class="tab-counter">{{ data.summary.supply_pending || 0 }}</span>
          </button>
        </div>
        <el-radio-group v-if="tab === 'weight'" v-model="filter" size="small"
          ><el-radio-button value="pending">待核对</el-radio-button
          ><el-radio-button value="all">全部记录</el-radio-button></el-radio-group
        >
      </div>
      <template v-if="tab === 'weight'"
        ><article v-for="r in rows" :key="r.id" class="weight-account">
          <div class="weight-account-head">
            <div>
              <b>{{ r.product }}</b
              ><small
                >订单 #{{ r.order_id }} · 实重对账 #{{ r.id }} · {{ dateText(r.created_at) }}</small
              >
            </div>
            <span class="status-badge" :class="r.status === 'confirmed' ? 'confirmed' : 'issue'">{{
              states[r.status]
            }}</span>
          </div>
          <div class="weight-account-values">
            <div>
              <span>约定数量</span
              ><b
                >{{ qty(r.expected) }}<small>{{ r.unit }}</small></b
              >
            </div>
            <el-icon><ArrowRight /></el-icon>
            <div>
              <span>实际收货</span
              ><b
                >{{ qty(r.received) }}<small>{{ r.unit }}</small></b
              >
            </div>
            <el-icon><ArrowRight /></el-icon>
            <div>
              <span>合格实收</span
              ><b
                >{{ qty(r.accepted) }}<small>{{ r.unit }}</small></b
              >
            </div>
            <div class="weight-difference">
              <span>按成交单价的尾差</span
              ><b :class="r.difference > 0 ? 'warn' : 'good'"
                >{{ r.difference > 0 ? '+' : '' }}¥{{ money(r.difference) }}</b
              >
            </div>
          </div>
          <p class="weight-account-note">{{ r.note }}</p>
          <div class="weight-account-actions">
            <el-button link type="primary" @click="router.push('/orders?order=' + r.order_id)"
              >查看订单、验收与凭证</el-button
            >
            <div v-if="r.status === 'pending' && (w.isAdmin || managed.includes(r.seller_id))">
              <el-button plain size="small" @click="confirm(r, 'reject')">需要补充依据</el-button
              ><el-button
                type="primary"
                size="small"
                :loading="submitting === r.id"
                @click="confirm(r, 'confirm')"
                >核对并确认差额</el-button
              >
            </div>
            <el-button
              v-else-if="
                r.status === 'disputed' &&
                (w.state.user.managed_buyer_ids || [w.state.user.id]).includes(r.buyer_id)
              "
              type="primary"
              size="small"
              :loading="submitting === r.id"
              @click="confirm(r, 'resubmit')"
              >补充称重依据并重提</el-button
            ><span v-else-if="r.case_id" class="small good">已生成处理单 #{{ r.case_id }}</span
            ><span v-else-if="r.status !== 'confirmed'" class="small muted"
              >等待交易供货方核对实际验收</span
            >
          </div>
        </article>
        <div v-if="!rows.length" class="empty-business">
          <el-icon size="30"><CircleCheck /></el-icon>
          <p>当前没有待核对的实重记录</p>
          <small>选择“按合格实重结算”的订单验收后，自动生成对账记录。</small>
        </div></template
      >
      <template v-if="tab === 'cases'"
        ><div class="account-table-row account-table-head">
          <span>订单与事项</span><span>金额 / 数量</span><span>处理进度</span><span>下一步</span>
        </div>
        <article v-for="c in data.cases" :key="c.id" class="account-table-row">
          <div>
            <b>{{ c.product }}</b>
            <p>{{ names[c.kind] }} #{{ c.id }} · 订单 #{{ c.order_id }}</p>
          </div>
          <div>
            <b>¥{{ money(c.amount) }}</b
            ><small v-if="c.quantity">约定数量 {{ qty(c.quantity) }}</small>
          </div>
          <span class="status-badge" :class="c.status === 'confirmed' ? 'confirmed' : 'pending'">{{
            states[c.status]
          }}</span
          ><el-button link type="primary" @click="router.push('/orders?order=' + c.order_id)"
            >进入订单处理</el-button
          >
        </article>
        <div v-if="!data.cases.length" class="empty-business">
          当前没有退款、折让、补款或货物处理单。
        </div></template
      >
      <template v-if="tab === 'supply'"
        ><div class="supply-account-intro">
          <el-icon><Connection /></el-icon>
          <p>
            跨供货方补配执行后，原交易方与实际履约方在这里分别登记付款、核对到账。实际履约方核对后，可从作业中心发运。
          </p>
        </div>
        <article v-for="s in data.supplier_settlements" :key="s.id" class="supply-account">
          <div class="supply-parties">
            <div>
              <span>付款主体</span><b>{{ s.payer }}</b>
            </div>
            <el-icon><ArrowRight /></el-icon>
            <div>
              <span>实际履约方</span><b>{{ s.supplier }}</b>
            </div>
            <div class="supply-price">
              <span>约定供货金额</span><b>¥{{ money(s.amount) }}</b>
            </div>
          </div>
          <div class="supply-account-footer">
            <div>
              <span class="status-badge">{{ states[s.status] }}</span
              ><small
                >订单 #{{ s.order_id
                }}<template v-if="s.reference"> · 凭证 {{ s.reference }}</template></small
              >
            </div>
            <el-button
              v-if="s.status === 'pending' && managed.includes(s.payer_id)"
              type="primary"
              :loading="submitting === s.id"
              @click="supply(s, 'record')"
              >登记实际付款</el-button
            ><el-button
              v-else-if="s.status === 'recorded' && managed.includes(s.supplier_id)"
              type="primary"
              :loading="submitting === s.id"
              @click="supply(s, 'confirm')"
              >核对实际到账</el-button
            ><el-button v-else link @click="router.push('/orders?order=' + s.order_id)"
              >查看关联订单</el-button
            >
          </div>
        </article>
        <div v-if="!data.supplier_settlements.length" class="empty-business">
          当前没有跨供货主体的待对账记录。
        </div></template
      >
    </section>
    <p class="data-note section-gap">
      本系统记录实际凭证与双方确认，不自动扣款、划款或退款。包装、运费依原约定，实重尾差使用成交价格快照。
    </p>
  </div>
</template>
<style scoped>
.weight-account {
  padding: 25px 27px;
  border-bottom: 1px solid #e6edf6;
}
.weight-account-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
}
.weight-account-head b {
  font-size: 15px;
  color: #3b587b;
}
.weight-account-head small {
  display: block;
  font-size: 12px;
  color: #687d97;
  margin-top: 9px;
}
.weight-account-values {
  display: grid;
  grid-template-columns: 1fr 28px 1fr 28px 1fr 1.3fr;
  align-items: center;
  gap: 16px;
  padding: 26px 0;
}
.weight-account-values > div > span {
  font-size: 12px;
  color: #647b96;
}
.weight-account-values b {
  font-size: 27px;
  color: #345476;
  display: block;
  font-weight: 550;
  margin-top: 12px;
  font-variant-numeric: tabular-nums;
}
.weight-account-values b small {
  font-size: 12px;
  color: #9babc0;
  margin-left: 7px;
  font-weight: 400;
}
.weight-account-values > .el-icon {
  color: #bccde2;
  font-size: 19px;
}
.weight-difference {
  text-align: right;
}
.weight-difference > b {
  font-size: 26px;
}
.weight-difference > b.good {
  color: #18927f;
}
.weight-difference > b.warn {
  color: #b18542;
}
.weight-account-note {
  font-size: 12px;
  color: #667e9a;
  line-height: 1.9;
  background: #f7f9fc;
  border-radius: 7px;
  padding: 12px 15px;
}
.weight-account-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 15px;
  margin-top: 17px;
}
.account-table-row {
  display: grid;
  grid-template-columns: minmax(220px, 1.5fr) minmax(120px, 1fr) 160px 140px;
  align-items: center;
  gap: 20px;
  padding: 22px 25px;
  border-bottom: 1px solid #edf1f7;
}
.account-table-head {
  font-size: 12px;
  color: #8fa3bf;
  background: #f8fafd;
  padding-top: 13px;
  padding-bottom: 13px;
}
.account-table-row b {
  font-size: 13px;
  color: #446183;
}
.account-table-row p,
.account-table-row small {
  display: block;
  font-size: 12px;
  color: #8fa3bf;
  margin-top: 8px;
  line-height: 1.8;
}
.account-table-row > .status-badge {
  justify-self: start;
  font-size: 12px;
}
.supply-account-intro {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 25px;
  background: #f5f9fd;
  color: #7892b2;
  font-size: 13px;
  line-height: 1.9;
}
.supply-account-intro > .el-icon {
  font-size: 23px;
  flex-shrink: 0;
}
.supply-account {
  padding: 27px;
  border-bottom: 1px solid #e5edf8;
}
.supply-parties {
  display: flex;
  align-items: center;
  gap: 35px;
}
.supply-parties > div > span {
  display: block;
  font-size: 12px;
  color: #647b96;
  margin-bottom: 13px;
}
.supply-parties b {
  font-size: 18px;
  font-weight: 550;
  color: #405f85;
}
.supply-parties > .el-icon {
  color: #b5c6de;
}
.supply-price {
  margin-left: auto;
  text-align: right;
}
.supply-price > b {
  font-size: 26px;
  color: #345a98;
}
.supply-account-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  border-top: 1px solid #edf1f7;
  margin-top: 24px;
  padding-top: 17px;
}
.supply-account-footer small {
  font-size: 12px;
  color: #697d96;
  margin-left: 13px;
}
@media (max-width: 1250px) {
  .weight-account-values {
    gap: 12px;
  }
  .account-table-row {
    grid-template-columns: 1.3fr 100px 140px 120px;
    gap: 10px;
  }
}
@media (max-width: 760px) {
  .weight-account {
    padding: 20px 18px;
  }
  .weight-account-values {
    grid-template-columns: 1fr 1fr 1fr;
    gap: 20px;
    padding: 23px 0;
  }
  .weight-account-values > .el-icon {
    display: none;
  }
  .weight-account-values b {
    font-size: 25px;
  }
  .weight-difference {
    grid-column: 1/-1;
    text-align: left;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .weight-difference > b {
    font-size: 24px;
    margin: 0;
  }
  .weight-account-actions {
    flex-wrap: wrap;
  }
  .weight-account-actions > .el-button {
    font-size: 12px;
  }
  .account-table-head {
    display: none;
  }
  .account-table-row {
    grid-template-columns: minmax(0, 1fr) 100px;
    padding: 19px;
    gap: 16px;
  }
  .account-table-row > .status-badge {
    grid-column: 1;
    grid-row: 2;
  }
  .account-table-row > .el-button {
    grid-column: 2;
    grid-row: 2;
  }
  .supply-account {
    padding: 22px 19px;
  }
  .supply-parties {
    gap: 16px;
    flex-wrap: wrap;
  }
  .supply-parties b {
    font-size: 15px;
  }
  .supply-price {
    width: 100%;
    text-align: left;
    margin: 12px 0 0;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .supply-price > span {
    margin: 0 !important;
  }
  .supply-price > b {
    font-size: 25px;
  }
  .supply-account-footer {
    flex-wrap: wrap;
  }
  .supply-account-footer small {
    display: block;
    margin: 11px 0 0;
  }
}

.tab-counter {
  margin-left: 8px;
  font-size: 12px;
  color: #718098;
}
.weight-account {
  padding: 28px;
}
.weight-account-values {
  padding: 25px 0;
  gap: 20px;
}
.weight-account-note {
  background: transparent;
  padding: 0;
  font-size: 12px;
  color: #6b7d93;
}
.weight-account-head small {
  font-size: 12px;
}
.weight-account-values b {
  font-size: 25px;
}
.weight-account-actions {
  margin-top: 22px;
}
.account-table-row p,
.account-table-row small {
  font-size: 12px;
}
</style>
