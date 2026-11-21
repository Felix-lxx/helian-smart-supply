<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useWorkspace, money, qty, dateText, todayPlus } from '@/stores/workspace'
import StatusBadge from '@/components/StatusBadge.vue'
import BatchOperations from '@/components/BatchOperations.vue'
import request from '@/utils/request'
import { ElMessage } from 'element-plus'
const w = useWorkspace(),
  route = useRoute(),
  router = useRouter(),
  tab = ref('products'),
  search = ref(''),
  productDialog = ref(false),
  batchDialog = ref(false),
  busy = ref(false),
  editing = ref(null)
const operationsId = ref(null),
  operationsBatch = computed(() => w.state.batches.find((b) => b.id === operationsId.value))
const form = reactive({}),
  batch = reactive({}),
  products = computed(() =>
    w.state.products.filter((p) => (p.name + p.origin + p.supplier).includes(search.value)),
  ),
  batches = computed(() =>
    w.state.batches.filter((b) => (b.product_name + b.code + b.origin).includes(search.value)),
  )
function edit(p) {
  editing.value = p?.id || null
  Object.assign(
    form,
    {
      name: '',
      category: 'fruits_vegs',
      origin: '',
      location: '',
      variety: '',
      grade: '标准级',
      packaging: '散装',
      retail_price: 5,
      packaging_fee: 0,
      freight_fee: 0,
      quantity_step: 1,
      unit: 'kg',
      min_order: 10,
      delivery_days: 2,
      image_url: '',
      description: '',
      price_tiers: [],
    },
    p ? JSON.parse(JSON.stringify(p)) : {},
  )
  productDialog.value = true
}
function newBatch(p) {
  Object.assign(batch, {
    product_id: p?.id || w.state.products[0]?.id,
    quantity: 100,
    grade: p?.grade || '标准级',
    packaging: p?.packaging || '散装',
    size_mm: 0,
    harvest_date: todayPlus(0),
    available_date: todayPlus(0),
    removal_date: '',
    storage_condition: '',
    note: '',
  })
  batchDialog.value = true
}
async function save() {
  busy.value = true
  try {
    await w.act(
      editing.value ? `products/${editing.value}/save/` : 'products/save/',
      form,
      editing.value ? '商品资料已更新' : '商品草稿已创建，请入库批次并复核',
    )
    productDialog.value = false
  } catch {
  } finally {
    busy.value = false
  }
}
async function saveBatch() {
  busy.value = true
  try {
    await w.act('batches/', batch, '批次已入库，等待品质复核')
    batchDialog.value = false
    tab.value = 'batches'
  } catch {
  } finally {
    busy.value = false
  }
}
async function toggle(p) {
  try {
    await w.act(
      `products/${p.id}/status/`,
      { status: p.status === 'on_sale' ? 'off_shelf' : 'on_sale', reason: '供货调整' },
      p.status === 'on_sale' ? '商品已下架' : '商品已上架',
    )
  } catch {}
}
async function upload({ file, onSuccess, onError }) {
  const data = new FormData()
  data.append('file', file)
  try {
    form.image_url = (await request.post('/workspace/upload/', data, { timeout: 20000 })).data.url
    onSuccess({})
    ElMessage.success('图片已上传')
  } catch (e) {
    onError(e)
    ElMessage.error('上传失败，请选择8MB以内的JPG/PNG')
  }
}
onMounted(() => {
  if (route.query.create) edit()
})
</script>
<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1>商品与批次</h1>
        <p>商品定义规格与价格，批次记录实际供给。入库、复核、上架后才可采购。</p>
      </div>
      <div class="head-actions">
        <el-button icon="Box" :disabled="!w.state.products.length" @click="newBatch()"
          >新增入库批次</el-button
        ><el-button type="primary" icon="Plus" @click="edit()">创建商品</el-button>
      </div>
    </div>
    <div class="metrics">
      <div class="metric">
        <div class="metric-label">商品总量</div>
        <div class="metric-value">{{ w.state.products.length }}</div>
        <div class="metric-foot">当前账号可管理的商品</div>
      </div>
      <div class="metric">
        <div class="metric-label">在售商品</div>
        <div class="metric-value">
          {{ w.state.products.filter((p) => p.status === 'on_sale').length }}
        </div>
        <div class="metric-foot">具备放行批次的可售货源</div>
      </div>
      <div class="metric">
        <div class="metric-label">库存批次</div>
        <div class="metric-value">{{ w.state.batches.length }}</div>
        <div class="metric-foot">按批次跟踪数量与品质</div>
      </div>
      <div class="metric">
        <div class="metric-label">待检与隔离</div>
        <div class="metric-value warn">
          {{ w.state.batches.filter((b) => b.status !== 'released').length }}
        </div>
        <div class="metric-foot">复核前不进入可售库存</div>
      </div>
    </div>
    <section class="panel">
      <div class="toolbar">
        <div class="pill-tabs">
          <button :class="{ active: tab === 'products' }" @click="tab = 'products'">商品目录</button
          ><button :class="{ active: tab === 'batches' }" @click="tab = 'batches'">批次库存</button>
        </div>
        <el-input
          v-model="search"
          clearable
          placeholder="搜索商品、产地或批次"
          prefix-icon="Search"
        />
      </div>
      <el-table v-if="tab === 'products'" :data="products"
        ><el-table-column label="商品" min-width="230"
          ><template #default="{ row }"
            ><div class="table-product">
              <el-image :src="row.image_url" fit="cover" class="thumb" />
              <div>
                <strong>{{ row.name }} <span v-if="row.is_demo" class="demo-tag">演示</span></strong
                ><small>{{ row.origin }}</small>
              </div>
            </div></template
          ></el-table-column
        ><el-table-column label="规格" min-width="140"
          ><template #default="{ row }"
            >{{ row.grade }} · {{ row.packaging }}</template
          ></el-table-column
        ><el-table-column label="单价" width="120"
          ><template #default="{ row }"
            >¥{{ money(row.retail_price) }}/{{ row.unit }}</template
          ></el-table-column
        ><el-table-column label="可售库存" width="115"
          ><template #default="{ row }"
            >{{ qty(row.stock) }} {{ row.unit }}</template
          ></el-table-column
        ><el-table-column label="状态" width="100"
          ><template #default="{ row }"
            ><StatusBadge :value="row.status" /></template></el-table-column
        ><el-table-column label="操作" width="220" fixed="right"
          ><template #default="{ row }"
            ><el-button link type="primary" @click="edit(row)">编辑</el-button
            ><el-button link @click="newBatch(row)">入库</el-button
            ><el-button
              link
              :type="row.status === 'on_sale' ? 'warning' : 'success'"
              @click="toggle(row)"
              >{{ row.status === 'on_sale' ? '下架' : '上架' }}</el-button
            ></template
          ></el-table-column
        ></el-table
      >
      <el-table v-else :data="batches"
        ><el-table-column label="批次 / 商品" min-width="220"
          ><template #default="{ row }"
            ><strong>{{ row.code }}</strong>
            <div class="small muted" style="margin-top: 5px">
              {{ row.product_name }} · {{ row.grade }}
            </div></template
          ></el-table-column
        ><el-table-column label="实物库存" width="125"
          ><template #default="{ row }"
            >{{ qty(row.quantity) }} {{ row.unit }}</template
          ></el-table-column
        ><el-table-column label="已预留" width="100"
          ><template #default="{ row }">{{ qty(row.reserved) }}</template></el-table-column
        ><el-table-column label="可分配" width="100"
          ><template #default="{ row }"
            ><b class="good">{{ qty(row.available) }}</b></template
          ></el-table-column
        ><el-table-column label="采收日期" prop="harvest_date" width="125" /><el-table-column
          label="复核状态"
          width="145"
          ><template #default="{ row }"
            ><StatusBadge :value="row.status" /></template></el-table-column
        ><el-table-column label="操作" width="230"
          ><template #default="{ row }"
            ><el-button link type="primary" @click="router.push('/quality?batch=' + row.id)"
              >检查与复核</el-button
            ><el-button link @click="operationsId = row.id">称重与库存</el-button></template
          ></el-table-column
        ></el-table
      >
    </section>
    <p class="data-note">
      可分配量 = 放行批次实物库存 −
      已预留量。未放行批次不可采购；历史库存无批次时需核实后重新入库，系统不会自动将旧数值当成实物。
    </p>
    <el-dialog
      v-model="productDialog"
      :title="editing ? '编辑商品资料' : '创建商品草稿'"
      width="760px"
      ><el-form label-position="top"
        ><div class="form-grid">
          <el-form-item label="商品名称"
            ><el-input v-model="form.name" maxlength="100" /></el-form-item
          ><el-form-item label="品种 / 匹配关键词"
            ><el-input v-model="form.variety" placeholder="例如：苹果、红富士" /></el-form-item
          ><el-form-item label="分类"
            ><el-select v-model="form.category" style="width: 100%"
              ><el-option label="果蔬" value="fruits_vegs" /><el-option
                label="米面粮油"
                value="grains" /><el-option label="肉禽蛋奶" value="meat" /><el-option
                label="干货菌菇"
                value="dry" /></el-select></el-form-item
          ><el-form-item label="产地名称"
            ><el-input v-model="form.origin" placeholder="省 / 市 / 县" /></el-form-item
          ><el-form-item label="产地坐标（经度,纬度）"
            ><el-input
              v-model="form.location"
              placeholder="例如 109.432,35.762；未知可留空" /></el-form-item
          ><el-form-item label="等级"
            ><el-select v-model="form.grade" style="width: 100%"
              ><el-option
                v-for="g in ['优选级', '标准级']"
                :key="g"
                :label="g"
                :value="g" /></el-select></el-form-item
          ><el-form-item label="包装规格"
            ><el-input v-model="form.packaging" placeholder="散装 / 5kg箱装" /></el-form-item
          ><el-form-item label="计量单位"
            ><el-select v-model="form.unit" style="width: 100%"
              ><el-option
                v-for="u in ['kg', '斤', '箱', '件']"
                :key="u"
                :value="u"
                :label="u" /></el-select></el-form-item
          ><el-form-item label="基础单价 / 元"
            ><el-input-number
              v-model="form.retail_price"
              :min="0.01"
              :precision="2" /></el-form-item
          ><el-form-item label="起订数量"
            ><el-input-number v-model="form.min_order" :min="1" /></el-form-item
          ><el-form-item label="确认收款后发运 / 天"
            ><el-input-number v-model="form.delivery_days" :min="0" :max="90" /></el-form-item
          ><el-form-item label="包装费 / 每计量单位"
            ><el-input-number v-model="form.packaging_fee" :min="0" :precision="2" /></el-form-item
          ><el-form-item label="运费 / 每批次订单"
            ><el-input-number v-model="form.freight_fee" :min="0" :precision="2" /></el-form-item
          ><el-form-item label="采购数量增量"
            ><el-input-number
              v-model="form.quantity_step"
              :min="0.01"
              :precision="2" /></el-form-item
          ><el-form-item label="商品图片"
            ><el-upload :http-request="upload" :show-file-list="false" accept="image/png,image/jpeg"
              ><el-button>上传实拍图片</el-button></el-upload
            ><el-image
              v-if="form.image_url"
              :src="form.image_url"
              style="width: 60px; height: 45px; margin-left: 10px"
              fit="cover" /></el-form-item
          ><el-form-item label="图片地址" class="wide"
            ><el-input
              v-model="form.image_url"
              placeholder="也可填写可访问的图片地址" /></el-form-item
          ><el-form-item label="供货说明" class="wide"
            ><el-input
              v-model="form.description"
              type="textarea"
              :rows="3"
              maxlength="2000" /></el-form-item
          ><el-form-item label="批发阶梯价" class="wide"
            ><div style="width: 100%">
              <div
                v-for="(t, i) in form.price_tiers"
                :key="i"
                class="row-actions"
                style="margin-bottom: 10px"
              >
                <span>满</span
                ><el-input-number v-model="t.min_quantity" :min="1" size="small" /><span
                  >{{ form.unit }}，单价</span
                ><el-input-number
                  v-model="t.price"
                  :min="0.01"
                  :precision="2"
                  size="small"
                /><el-button link type="danger" @click="form.price_tiers.splice(i, 1)"
                  >移除</el-button
                >
              </div>
              <el-button
                link
                type="primary"
                :disabled="form.price_tiers?.length >= 8"
                @click="form.price_tiers.push({ min_quantity: 100, price: form.retail_price })"
                >＋ 添加价格档位</el-button
              >
            </div></el-form-item
          >
        </div></el-form
      ><template #footer
        ><el-button @click="productDialog = false">取消</el-button
        ><el-button type="primary" :loading="busy" @click="save">{{
          editing ? '保存修改' : '创建草稿'
        }}</el-button></template
      ></el-dialog
    >
    <el-dialog v-model="batchDialog" title="新增库存批次" width="600px"
      ><div class="info-strip" style="margin-bottom: 20px">
        新批次默认为待检。完成抽样与人工复核后，再放行供货。
      </div>
      <el-form label-position="top"
        ><div class="form-grid">
          <el-form-item label="关联商品" class="wide"
            ><el-select
              v-model="batch.product_id"
              filterable
              style="width: 100%"
              @change="
                (id) => {
                  const p = w.state.products.find((x) => x.id === id)
                  batch.grade = p.grade
                  batch.packaging = p.packaging
                }
              "
              ><el-option
                v-for="p in w.state.products"
                :key="p.id"
                :label="p.name + ' · ' + p.grade + ' / ' + p.unit"
                :value="p.id" /></el-select></el-form-item
          ><el-form-item label="实际入库数量"
            ><el-input-number v-model="batch.quantity" :min="0.01" :precision="2" /></el-form-item
          ><el-form-item label="尺寸 / mm（未知填0）"
            ><el-input-number v-model="batch.size_mm" :min="0" :max="2000" /></el-form-item
          ><el-form-item label="等级"><el-input v-model="batch.grade" /></el-form-item
          ><el-form-item label="包装"><el-input v-model="batch.packaging" /></el-form-item
          ><el-form-item label="存储条件"
            ><el-input
              v-model="batch.storage_condition"
              placeholder="填写实际要求，不由采收日推断" /></el-form-item
          ><el-form-item label="移出日期 / 有依据时录入"
            ><el-date-picker
              v-model="batch.removal_date"
              value-format="YYYY-MM-DD"
              style="width: 100%" /></el-form-item
          ><el-form-item label="采收日期"
            ><el-date-picker
              v-model="batch.harvest_date"
              value-format="YYYY-MM-DD"
              style="width: 100%" /></el-form-item
          ><el-form-item label="可供货日期"
            ><el-date-picker
              v-model="batch.available_date"
              value-format="YYYY-MM-DD"
              style="width: 100%" /></el-form-item
          ><el-form-item label="入库备注" class="wide"
            ><el-input v-model="batch.note" type="textarea"
          /></el-form-item></div></el-form
      ><template #footer
        ><el-button @click="batchDialog = false">取消</el-button
        ><el-button type="primary" :loading="busy" @click="saveBatch"
          >确认入库，进入待检</el-button
        ></template
      ></el-dialog
    >
  </div>
  <el-drawer
    :model-value="!!operationsBatch"
    title="分拣称重与库存作业"
    size="680px"
    @close="operationsId = null"
    ><BatchOperations v-if="operationsBatch" :key="operationsBatch.id" :batch="operationsBatch"
  /></el-drawer>
</template>
