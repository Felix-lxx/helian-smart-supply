<script setup>
import { ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useWorkspace, money, qty, dateText } from '@/stores/workspace'
import StatusBadge from '@/components/StatusBadge.vue'
import request from '@/utils/request'
import { ElMessage } from 'element-plus'
const route = useRoute(),
  router = useRouter(),
  w = useWorkspace(),
  selected = ref(null),
  amount = ref(10),
  comments = ref([]),
  text = ref(''),
  rating = ref(5),
  posting = ref(false)
const p = computed(
  () =>
    w.market.find((x) => x.id === Number(route.params.id)) ||
    w.state.products.find((x) => x.id === Number(route.params.id)),
)
const batches = computed(
  () => p.value?.batches.filter((b) => b.status === 'released' && b.available > 0) || [],
)
const batch = computed(() => batches.value.find((b) => b.id === selected.value) || batches.value[0])
const price = computed(() => {
  let result = p.value?.retail_price || 0
  for (const t of p.value?.price_tiers || []) if (amount.value >= t.min_quantity) result = t.price
  return result
})
const canReview = computed(() =>
  w.state.orders.some(
    (o) =>
      o.product_id === p.value?.id && o.status === 'completed' && o.buyer_id === w.state.user.id,
  ),
)
watch(
  () => p.value?.id,
  () => {
    amount.value = p.value?.min_order || 1
    selected.value = null
  },
  { immediate: true },
)
async function loadComments() {
  try {
    comments.value = (await request.get(`/products/${route.params.id}/comments/`)).data
  } catch {
    comments.value = []
  }
}
watch(() => route.params.id, loadComments, { immediate: true })
function add(go = false) {
  if (!batch.value) return
  if(!w.addCart(p.value, batch.value, amount.value))return
  if (go) router.push('/cart')
}
async function review() {
  posting.value = true
  try {
    await request.post(`/products/${p.value.id}/comments/`, {
      content: text.value,
      rating: rating.value,
    })
    text.value = ''
    await loadComments()
    ElMessage.success('评价已发布')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '评价未提交')
  } finally {
    posting.value = false
  }
}
</script>
<template>
  <div class="page" v-if="p">
    <div class="page-head">
      <div>
        <el-button link @click="router.push('/products')"
          ><el-icon style="margin-right: 7px"><Back /></el-icon>返回货源市场</el-button
        >
        <h1 style="margin-top: 16px">
          {{ p.name }} <span v-if="p.is_demo" class="demo-tag">演示货源</span>
        </h1>
        <p>{{ p.origin }} · 由 {{ p.supplier }} 提供</p>
      </div>
      <StatusBadge :value="p.status" />
    </div>
    <div class="product-detail-grid">
      <div>
        <section class="panel product-main-photo">
          <el-image :src="p.image_url" fit="cover"
            ><template #error><div class="empty-state">暂无实拍图片</div></template></el-image
          >
          <div class="photo-caption">
            <el-icon><Location /></el-icon>{{ p.origin || '产地未记录'
            }}<router-link to="/origins"
              >产地网络 <el-icon><TopRight /></el-icon
            ></router-link>
          </div>
        </section>
        <section class="panel section-gap">
          <div class="panel-head"><h2>供货说明</h2></div>
          <div class="panel-body">
            <p class="description">
              {{ p.description || '供应商尚未补充供货说明。交易前请确认规格、数量与交付条件。' }}
            </p>
            <div class="kv">
              <span>商品品种</span><b>{{ p.variety || '未记录' }}</b>
            </div>
            <div class="kv">
              <span>规格等级</span><b>{{ p.grade }} · {{ p.packaging }}</b>
            </div>
            <div class="kv">
              <span>预计发运</span><b>确认收款后 {{ p.delivery_days }} 日内</b>
            </div>
          </div>
        </section>
      </div>
      <section class="panel purchase-panel">
        <div class="panel-body">
          <div class="price-line">
            <b>¥{{ money(price) }}</b
            ><span>/ {{ p.unit }}</span
            ><StatusBadge value="on_sale" />
          </div>
          <p class="small muted" style="margin-top: 10px">
            {{ p.min_order }}{{ p.unit }}起订 · 价格随采购数量自动试算
          </p>
          <div class="tier-list" v-if="p.price_tiers.length">
            <div>
              <span>{{ p.min_order }}{{ p.unit }}起</span><b>¥{{ money(p.retail_price) }}</b>
            </div>
            <div
              v-for="t in p.price_tiers"
              :key="t.min_quantity"
              :class="{ selected: amount >= t.min_quantity }"
            >
              <span>{{ t.min_quantity }}{{ p.unit }}起</span><b>¥{{ money(t.price) }}</b>
            </div>
          </div>
          <h3 style="margin: 27px 0 12px">选择放行批次</h3>
          <button
            v-for="b in batches"
            :key="b.id"
            class="batch-choice"
            :class="{ selected: batch?.id === b.id }"
            @click="() => {
              selected = b.id
              amount = Math.min(amount, b.available)
            }"
          >
            <div>
              <b>{{ b.code }}</b
              ><span
                >{{ b.grade }} · {{ b.packaging }}
                {{ b.size_mm ? '· ' + b.size_mm + 'mm' : '' }}</span
              >
            </div>
            <div>
              <b>{{ qty(b.available) }} {{ p.unit }}</b
              ><span>可用库存</span>
            </div>
            <el-icon v-if="batch?.id === b.id"><CircleCheckFilled /></el-icon>
          </button>
          <div v-if="!batches.length" class="info-strip warning">
            暂无放行库存，可发布采购需求或联系供应商。
          </div>
          <template v-if="batch"
            ><div class="small muted" style="margin: 14px 0; line-height: 1.9">
              采收日期 {{ batch.harvest_date || '未记录' }} · 已抽检
              {{ batch.sample_size }} 个，记录外观缺陷
              {{ batch.defect_count }} 个。抽样结果不代表全批次或食品安全证明。
            </div>
            <div class="kv">
              <span>采购数量 / {{ p.unit }}</span
              ><el-input-number
                v-model="amount"
                :min="p.min_order"
                :max="batch.available"
                :precision="2"
                :step="p.quantity_step||1"
              />
            </div>
            <div class="kv">
              <span>商品小计</span><strong class="total-price">¥{{ money(amount * price) }}</strong>
            </div>
            <p class="data-note">
              商品小计按阶梯价计算；包装费 ¥{{money(p.packaging_fee)}} / {{p.unit}}，运费 ¥{{money(p.freight_fee)}} / 批次订单，清单中统一核价。
            </p></template
          >
          <div class="purchase-actions" v-if="w.isBuyer">
            <el-button size="large" :disabled="!batch || amount < p.min_order" @click="add()"
              >加入采购清单</el-button
            ><el-button
              type="primary"
              size="large"
              :disabled="!batch || amount < p.min_order"
              @click="add(true)"
              >确认采购</el-button
            >
          </div>
          <router-link v-else to="/supply"
            ><el-button type="primary" size="large" style="width: 100%; margin-top: 24px"
              >前往供货管理</el-button
            ></router-link
          >
        </div>
      </section>
    </div>
    <section class="panel section-gap">
      <div class="panel-head">
        <h2>采购评价</h2>
        <span class="small muted">仅完成交易的采购方可评价</span>
      </div>
      <div class="panel-body">
        <div v-for="c in comments" :key="c.id" class="list-row">
          <div>
            <h3>
              {{ c.username }}
              <el-rate v-if="c.rating" :model-value="c.rating" disabled size="small" />
            </h3>
            <p>{{ c.content }}</p>
            <p v-for="reply in c.replies" :key="reply.id">
              {{ reply.is_seller_reply ? '供应商回复' : reply.username }}：{{ reply.content }}
            </p>
          </div>
          <small class="muted">{{ dateText(c.created_at) }}</small>
        </div>
        <p v-if="!comments.length" class="muted small">暂无交易评价。</p>
        <div v-if="canReview" class="section-gap">
          <el-rate v-model="rating" /><el-input
            v-model="text"
            type="textarea"
            placeholder="分享这次采购的规格、交付和验收体验"
            maxlength="1000"
          /><el-button
            type="primary"
            :disabled="!text.trim()"
            :loading="posting"
            style="margin-top: 12px"
            @click="review"
            >发布评价</el-button
          >
        </div>
      </div>
    </section>
  </div>
  <div v-else class="page">
    <el-empty description="货源不可用或已下架"
      ><router-link to="/products"
        ><el-button type="primary">返回货源市场</el-button></router-link
      ></el-empty
    >
  </div>
</template>
<style scoped>
.product-detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 25px;
  align-items: start;
}
.product-main-photo > .el-image {
  width: 100%;
  height: 380px;
  display: block;
}
.photo-caption {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 16px 20px;
  font-size: 12px;
  color: var(--muted);
}
.photo-caption a {
  margin-left: auto;
  color: var(--brand);
}
.description {
  font-size: 13px;
  line-height: 2;
  color: #64776a;
  margin-bottom: 15px;
}
.purchase-panel .panel-body {
  padding: 28px;
}
.price-line {
  display: flex;
  align-items: baseline;
  gap: 7px;
}
.price-line > b {
  font-size: 38px;
  font-weight: 600;
  letter-spacing: -1px;
  color: #175f45;
}
.price-line > span {
  font-size: 13px;
  color: var(--muted);
}
.price-line .status-badge {
  margin-left: auto;
}
.tier-list {
  display: flex;
  background: #f5f8f4;
  border-radius: 8px;
  margin-top: 20px;
  padding: 14px 0;
}
.tier-list > div {
  padding: 0 16px;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 12px;
}
.tier-list > div + div {
  border-left: 1px solid var(--line);
}
.tier-list span {
  color: var(--muted);
  font-size: 11px;
}
.tier-list b {
  font-size: 17px;
  font-weight: 500;
}
.tier-list .selected {
  color: var(--brand);
}
.batch-choice {
  width: 100%;
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
  text-align: left;
  background: #fff;
  border: 1px solid var(--line);
  padding: 13px;
  border-radius: 8px;
  margin-bottom: 10px;
  color: inherit;
}
.batch-choice.selected {
  border-color: #3c9272;
  background: #f2f8f3;
}
.batch-choice div:first-child {
  flex: 1;
}
.batch-choice b {
  font-size: 12px;
  font-weight: 500;
  display: block;
}
.batch-choice span {
  font-size: 10px;
  color: var(--muted);
  margin-top: 6px;
  display: block;
}
.batch-choice .el-icon {
  color: var(--brand);
}
.total-price {
  font-size: 26px;
  color: var(--brand);
}
.purchase-actions {
  display: flex;
  gap: 12px;
  margin-top: 25px;
}
.purchase-actions .el-button {
  flex: 1;
  margin: 0;
}
@media (max-width: 1050px) {
  .product-detail-grid {
    grid-template-columns: 1fr;
  }
  .product-main-photo > .el-image {
    height: 330px;
  }
}
</style>
