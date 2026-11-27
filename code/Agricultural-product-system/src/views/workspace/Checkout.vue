<script setup>
import { ref, reactive, computed, onMounted, watch, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useWorkspace, money, todayPlus } from '@/stores/workspace'
import request from '@/utils/request'
import { ElMessage } from 'element-plus'
const w = useWorkspace(),
  router = useRouter(),
  busy = ref(false),
  address = reactive({ receiver_name: '', receiver_phone: '', address: '' }),
  addresses = ref([]),
  addressId = ref(null)
const submissionKey = ref(crypto.randomUUID())
const companies = ref([]),
  siteId = ref(null),
  promised = ref(todayPlus(3)),
  basis = ref('contract'),
  tolerance = ref(0)
const sites = computed(() =>
  companies.value
    .filter((c) => c.owner_role === 'retail')
    .flatMap((c) => c.sites.map((s) => ({ ...s, company: c.name }))),
)
const weightOnly = computed(() => w.cart.every((c) => ['kg', '斤'].includes(c.unit)))
function chooseSite(id) {
  const site = sites.value.find((s) => s.id === id)
  if (site) {
    Object.assign(address, {
      receiver_name: site.contact,
      receiver_phone: site.phone,
      address: site.address,
    })
    addressId.value = null
  }
}
const pricing = ref(null),
  quoting = ref(false),
  priceError = ref('')
const total = computed(() => pricing.value?.total || 0)
const linePrice = (id) => pricing.value?.items.find((x) => x.batch_id === id)
let quoteTimer,
  quoteSequence = 0
async function reprice() {
  const seq = ++quoteSequence
  if (!w.cart.length) {
    pricing.value = null
    return
  }
  quoting.value = true
  priceError.value = ''
  try {
    const r = await request.post('/workspace/pricing/preview/', {
      items: w.cart.map((c) => ({ ...c, batch_id: c.batch_id, quantity: c.quantity })),
    })
    if (seq === quoteSequence) pricing.value = r.data
  } catch (e) {
    if (seq === quoteSequence) {
      pricing.value = null
      priceError.value = e.response?.data?.detail || '核价未完成，请检查库存与数量'
    }
  } finally {
    if (seq === quoteSequence) quoting.value = false
  }
}
watch(
  () => JSON.stringify(w.cart.map((c) => [c.batch_id, c.quantity])),
  () => {
    submissionKey.value = crypto.randomUUID()
    clearTimeout(quoteTimer)
    pricing.value = null
    quoteTimer = setTimeout(reprice, 350)
  },
  { immediate: true },
)
watch(address, () => (submissionKey.value = crypto.randomUUID()), { deep: true })
watch([siteId, promised, basis, tolerance], () => {
  submissionKey.value = crypto.randomUUID()
})
onBeforeUnmount(() => clearTimeout(quoteTimer))
function remove(i) {
  w.cart.splice(i, 1)
  w.persistCart()
}
function choose(id) {
  siteId.value = null
  const a = addresses.value.find((x) => x.id === id)
  if (a)
    Object.assign(address, {
      receiver_name: a.receiver_name,
      receiver_phone: a.receiver_phone,
      address: a.detail_address,
    })
}
async function saveAddress() {
  if (!address.receiver_name || !address.receiver_phone || !address.address)
    return ElMessage.warning('请补全收货信息')
  try {
    await request.post('/addresses/', { ...address, detail_address: address.address })
    ElMessage.success('收货地址已保存')
  } catch {
    ElMessage.error('保存地址失败')
  }
}
async function submit() {
  if (!address.receiver_name || !address.receiver_phone || !address.address)
    return ElMessage.warning('请补全收货信息')
  busy.value = true
  try {
    const reviewed = pricing.value?.signature
    await reprice()
    if (!pricing.value) return
    if (reviewed !== pricing.value.signature) {
      ElMessage.warning('核价已更新，请核对费用后再次确认提交')
      return
    }
    await w.act(
      'checkout/',
      {
        idempotency_key: submissionKey.value,
        pricing_signature: pricing.value.signature,
        items: w.cart.map((c) => ({ ...c, batch_id: c.batch_id, quantity: c.quantity })),
        address,
        site_id: siteId.value,
        promised_date: promised.value,
        settlement_basis: basis.value,
        weight_tolerance_pct: tolerance.value,
      },
      '采购订单已创建，库存已预留',
    )
    w.cart = []
    w.persistCart()
    router.push('/orders')
  } catch {
    // Operation errors are shown by the shared workspace action; dialog cancellation is intentional.
  } finally {
    busy.value = false
  }
}
onMounted(async () => {
  try {
    companies.value = (await request.get('/workspace/companies/')).data
    addresses.value = (await request.get('/addresses/')).data
    const a = addresses.value.find((x) => x.is_default) || addresses.value[0]
    if (a) {
      addressId.value = a.id
      choose(a.id)
    }
  } catch {
    /* Optional state or user cancellation; keep the current business record. */
  }
})
</script>
<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1>采购清单</h1>
        <p>确认批次、数量与收货信息。提交时将重新检查可用库存和阶梯价。</p>
      </div>
      <router-link to="/products"><el-button>继续选货</el-button></router-link>
    </div>
    <div v-if="!w.cart.length" class="panel empty-state">
      <el-icon size="40"><ShoppingCart /></el-icon>
      <h2 style="margin-top: 15px">采购清单还是空的</h2>
      <p>从货源市场选择规格和批次后，加入你的采购清单。</p>
      <router-link to="/products"><el-button type="primary">发现产地货源</el-button></router-link>
    </div>
    <div v-else class="checkout-grid">
      <section class="panel">
        <div class="panel-head">
          <h2>已选货源 · {{ w.cart.length }} 项</h2>
        </div>
        <div class="panel-body">
          <div v-for="(c, i) in w.cart" :key="c.batch_id" class="cart-row">
            <el-image :src="c.image_url" fit="cover" class="cart-photo" />
            <div class="cart-info">
              <h3>{{ c.name }}</h3>
              <p>{{ c.supplier }} · {{ c.code }}</p>
              <b>¥{{ money(linePrice(c.batch_id)?.unit_price ?? c.price) }} / {{ c.unit }}</b>
            </div>
            <el-input-number
              v-model="c.quantity"
              :min="c.min_order || 1"
              :max="c.available"
              :precision="2"
              size="small"
              @change="w.persistCart()"
            />
            <div class="cart-subtotal">
              <b>{{
                linePrice(c.batch_id) ? '¥' + money(linePrice(c.batch_id).total) : '待核价'
              }}</b
              ><el-button link type="danger" @click="remove(i)">移除</el-button>
            </div>
          </div>
          <div class="info-strip section-gap">
            每个批次形成独立订单。阶梯价、包装费和运费已统一核价；提交前费用变化会要求重新确认。
          </div>
        </div>
      </section>
      <section class="panel">
        <div class="panel-head"><h2>交付与金额确认</h2></div>
        <div class="panel-body">
          <el-form-item label="关联门店或收货点">
            <el-select
              v-model="siteId"
              clearable
              placeholder="选择门店，与交付地图和作业关联"
              style="width: 100%"
              @change="chooseSite"
            >
              <el-option
                v-for="s in sites"
                :key="s.id"
                :value="s.id"
                :label="s.name + ' · ' + s.company"
              />
            </el-select>
          </el-form-item>

          <el-select
            v-if="addresses.length"
            v-model="addressId"
            placeholder="选用已保存地址"
            style="width: 100%; margin-bottom: 20px"
            @change="choose"
            ><el-option
              v-for="a in addresses"
              :key="a.id"
              :label="a.receiver_name + ' · ' + a.detail_address"
              :value="a.id" /></el-select
          ><el-form label-position="top"
            ><el-form-item label="收货联系人"
              ><el-input v-model="address.receiver_name" /></el-form-item
            ><el-form-item label="联系电话"
              ><el-input v-model="address.receiver_phone" maxlength="20" /></el-form-item
            ><el-form-item label="详细收货地址"
              ><el-input
                v-model="address.address"
                :readonly="!!siteId"
                type="textarea"
                :rows="3" /></el-form-item></el-form
          ><el-button link type="primary" @click="saveAddress">保存为常用收货地址</el-button>
          <div class="checkout-agreement">
            <el-form-item label="约定到货日"
              ><el-date-picker
                v-model="promised"
                type="date"
                value-format="YYYY-MM-DD"
                :clearable="false"
                style="width: 100%"
            /></el-form-item>
            <el-form-item label="结算口径"
              ><el-select v-model="basis" style="width: 100%"
                ><el-option value="contract" label="依约定数量结算，异常另行处理" /><el-option
                  value="accepted_weight"
                  label="按合格实重核对数量尾差"
                  :disabled="!weightOnly" /></el-select
            ></el-form-item>
            <el-form-item label="双方约定的数量允差 / %"
              ><el-input-number
                v-model="tolerance"
                :min="0"
                :max="10"
                :precision="2"
                style="width: 100%"
            /></el-form-item>
            <p class="data-note" style="font-size: 11px">
              {{
                basis === 'accepted_weight'
                  ? '验收后以成交单价计算数量尾差，供货方核对重量后，双方登记实际退款或补款。'
                  : '当前依成交数量与价格快照结算。'
              }}装车实际净重须在所确认的允差内。
            </p>
          </div>
          <div class="kv section-gap">
            <span>货源项目</span><b>{{ w.cart.length }} 项</b>
          </div>
          <div class="kv">
            <span>服务器核定合计</span
            ><b class="checkout-total">{{ quoting ? '核价中' : '¥' + money(total) }}</b>
          </div>
          <div v-if="pricing" class="kv">
            <span>其中包装 / 运费</span
            ><b
              >¥{{ money(pricing.items.reduce((s, r) => s + r.packaging, 0)) }} /
              {{ money(pricing.items.reduce((s, r) => s + r.freight, 0)) }}</b
            >
          </div>
          <div v-if="priceError" class="info-strip warning">
            {{ priceError }} <el-button link @click="reprice">重新核价</el-button>
          </div>
          <div class="info-strip warning section-gap">
            付款方式为双方线下转账、收款方核对。总额包含已录入的包装费与运费；未录入费用不代表第三方免费配送。
          </div>
          <el-button
            type="primary"
            size="large"
            :loading="busy"
            :disabled="quoting || !pricing"
            style="width: 100%; margin-top: 22px"
            @click="submit"
            >确认提交采购订单</el-button
          >
        </div>
      </section>
    </div>
  </div>
</template>
<style scoped>
.checkout-agreement {
  margin-top: 22px;
  padding-top: 20px;
  border-top: 1px solid var(--line);
}
.checkout-grid {
  display: grid;
  grid-template-columns: 1.8fr 1fr;
  gap: 24px;
  align-items: start;
}
.cart-row {
  display: flex;
  gap: 14px;
  align-items: center;
  padding: 20px 0;
  border-bottom: 1px solid var(--line);
}
.cart-photo {
  width: 68px;
  height: 68px;
  border-radius: 8px;
  flex-shrink: 0;
}
.cart-info {
  flex: 1;
}
.cart-info p {
  font-size: 11px;
  color: var(--muted);
  margin: 7px 0;
}
.cart-info > b {
  font-size: 12px;
  color: var(--brand);
}
.cart-subtotal {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 12px;
  font-size: 14px;
  min-width: 85px;
}
.checkout-total {
  font-size: 25px;
  color: var(--brand);
}
@media (max-width: 1200px) {
  .checkout-grid {
    grid-template-columns: 1fr;
  }
  .cart-row {
    flex-wrap: wrap;
  }
}
</style>
