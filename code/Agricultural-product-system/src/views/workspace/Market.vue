<script setup>
import { ref, computed, reactive } from 'vue'
import { useWorkspace, money, qty } from '@/stores/workspace'
const w = useWorkspace(),
  search = ref(''),
  sort = ref('default'),
  category = ref('all'),
  onlyStock = ref(false),
  page = ref(1)
const mode = ref('cards'),
  batchChoices = reactive({}),
  quantities = reactive({})
function batchFor(p) {
  return (
    p.batches.find((b) => b.id === batchChoices[p.id]) ||
    p.batches.find((b) => b.status === 'released' && b.available > 0)
  )
}
function quickAdd(p) {
  const b = batchFor(p)
  if (b) w.addCart(p, b, quantities[p.id] || p.min_order)
}
const rows = computed(() => {
  let a = w.market.filter(
    (p) =>
      (p.name + p.origin + p.variety).toLowerCase().includes(search.value.toLowerCase()) &&
      (category.value === 'all' || p.category === category.value) &&
      (!onlyStock.value || p.stock > 0),
  )
  if (sort.value === 'price') a = [...a].sort((a, b) => a.retail_price - b.retail_price)
  if (sort.value === 'stock') a = [...a].sort((a, b) => b.stock - a.stock)
  return a
})
const paged = computed(() => rows.value.slice((page.value - 1) * 12, page.value * 12))
const categories = [
  ['all', '全部货源'],
  ['fruits_vegs', '当季果蔬'],
  ['grains', '米面粮油'],
  ['meat', '肉禽蛋奶'],
  ['dry', '干货菌菇'],
]
</script>
<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1>货源市场</h1>
        <p>发现产地好货，按规格、批次与交期做采购决定。</p>
      </div>
      <router-link to="/demands"
        ><el-button type="primary"
          >{{ w.isBuyer ? '发布采购需求' : '查看需求商机'
          }}<el-icon style="margin-left: 8px"><Right /></el-icon></el-button
      ></router-link>
    </div>
    <div class="market-banner">
      <div>
        <span class="banner-season">当季产地直供</span>
        <h2>选好每一批，交付每一程。</h2>
        <p>规格明确 · 批次可查 · 按量核价</p>
      </div>
      <div class="banner-counter">
        <b>{{ w.market.filter((p) => p.stock > 0).length }}</b
        ><span>项货源可采购</span>
      </div>
      <el-icon class="banner-decoration"><Connection /></el-icon>
    </div>
    <div class="panel market-controls">
      <div class="toolbar">
        <div class="pill-tabs">
          <button
            v-for="[id, n] in categories"
            :key="id"
            :class="{ active: category === id }"
            @click="
              () => {
                category = id
                page = 1
              }
            "
          >
            {{ n }}
          </button>
        </div>
        <span class="small muted">{{ rows.length }} 项货源</span>
      </div>
      <div class="toolbar" style="border: 0">
        <el-input
          v-model="search"
          placeholder="搜索品种、产地或商品"
          prefix-icon="Search"
          clearable
          @input="page = 1"
        />
        <div class="row-actions">
          <el-radio-group v-model="mode" size="small"
            ><el-radio-button value="cards">看图选货</el-radio-button
            ><el-radio-button value="list">批量采购</el-radio-button></el-radio-group
          >
          <el-checkbox v-model="onlyStock" @change="page = 1">仅看有货</el-checkbox
          ><el-select v-model="sort" style="width: 140px"
            ><el-option label="默认排序" value="default" /><el-option
              label="价格从低到高"
              value="price" /><el-option label="可售量优先" value="stock"
          /></el-select>
        </div>
      </div>
    </div>
    <section v-if="mode === 'list'" class="panel">
      <el-table :data="paged"
        ><el-table-column label="商品 / 规格" min-width="210"
          ><template #default="{ row }"
            ><router-link :to="'/product/' + row.id"
              ><b>{{ row.name }}</b></router-link
            >
            <p class="small muted" style="margin-top: 6px">
              {{ row.variety }} / {{ row.origin }}
            </p></template
          ></el-table-column
        ><el-table-column label="放行批次" min-width="230"
          ><template #default="{ row }"
            ><el-select
              :model-value="batchFor(row)?.id"
              @update:model-value="(v) => (batchChoices[row.id] = v)"
              style="width: 100%"
              ><el-option
                v-for="b in row.batches.filter((b) => b.status === 'released' && b.available > 0)"
                :key="b.id"
                :value="b.id"
                :label="
                  b.code + ' / ' + b.grade + ' / ' + qty(b.available) + row.unit
                " /></el-select></template></el-table-column
        ><el-table-column label="起订 / 参考单价" min-width="140"
          ><template #default="{ row }"
            >{{ row.min_order }}{{ row.unit }}起订<br />¥{{ money(row.retail_price) }} /
            {{ row.unit }}</template
          ></el-table-column
        ><el-table-column v-if="w.isBuyer" label="本次采购量" width="170"
          ><template #default="{ row }"
            ><el-input-number
              v-model="quantities[row.id]"
              :min="row.min_order"
              :max="batchFor(row)?.available || row.min_order"
              :step="row.quantity_step || 1"
              :precision="2"
              size="small"
              style="width: 145px"
              :placeholder="String(row.min_order)" /></template></el-table-column
        ><el-table-column v-if="w.isBuyer" label="采购" width="110" fixed="right"
          ><template #default="{ row }"
            ><el-button link type="primary" :disabled="!batchFor(row)" @click="quickAdd(row)"
              >加入清单</el-button
            ></template
          ></el-table-column
        ></el-table
      >
      <div class="panel-body">
        <p class="data-note">
          多项货源在同页选择数量。阶梯价、包装费和运费在采购清单中由服务器核定；不同单位分别下单。
        </p>
      </div>
    </section>
    <div v-else class="product-grid">
      <router-link v-for="p in paged" :key="p.id" :to="'/product/' + p.id" class="product-tile"
        ><div class="product-image">
          <el-image :src="p.image_url" fit="cover"
            ><template #error
              ><div class="photo-placeholder">
                <el-icon><Picture /></el-icon><span>{{ p.variety || p.name }}</span>
              </div></template
            ></el-image
          ><span v-if="p.is_demo" class="demo-tag">演示货源</span
          ><span class="stock-chip" :class="{ out: !p.stock }">{{
            p.stock ? '可订购' : '暂无放行库存'
          }}</span>
        </div>
        <div class="product-copy">
          <div class="product-origin">
            <el-icon><Location /></el-icon>{{ p.origin || '产地待补充' }}
          </div>
          <h3>{{ p.name }}</h3>
          <div class="product-spec">
            <span>{{ p.grade }}</span
            ><span>{{ p.packaging }}</span>
          </div>
          <div class="product-price">
            <strong
              >¥{{ money(p.retail_price) }}<small>/{{ p.unit }}</small></strong
            ><span>{{ p.min_order }}{{ p.unit }}起订</span>
          </div>
          <div class="product-bottom">
            <span>可售 {{ qty(p.stock) }}{{ p.unit }}</span
            ><span
              >{{ p.delivery_days }}日内发运 <el-icon><Right /></el-icon
            ></span>
          </div></div
      ></router-link>
    </div>
    <div class="empty-state" v-if="!rows.length">
      没有符合条件的货源，试试其他关键词或发布采购需求。
    </div>
    <el-pagination
      v-if="rows.length > 12"
      v-model:current-page="page"
      :total="rows.length"
      :page-size="12"
      layout="prev,pager,next"
    />
  </div>
</template>
<style scoped>
.market-banner {
  position: relative;
  overflow: hidden;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #e7eedf;
  border-radius: 12px;
  padding: 30px 38px;
  margin-bottom: 22px;
  color: #25432f;
}
.banner-season {
  font-size: 11px;
  color: #5b795a;
}
.market-banner h2 {
  font-size: 25px;
  margin: 10px 0;
  letter-spacing: -0.4px;
}
.market-banner p {
  font-size: 12px;
  color: #6a7f64;
}
.banner-counter {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  margin-right: 30px;
  z-index: 1;
}
.banner-counter b {
  font-size: 42px;
  font-weight: 500;
}
.banner-counter span {
  font-size: 11px;
  color: #60775a;
}
.banner-decoration {
  position: absolute;
  font-size: 200px;
  right: 190px;
  bottom: -70px;
  opacity: 0.06;
}
.market-controls {
  margin-bottom: 24px;
}
.product-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 22px;
}
.product-tile {
  border: 1px solid var(--line);
  border-radius: 11px;
  overflow: hidden;
  background: #fff;
  transition:
    transform 0.2s,
    border-color 0.2s;
}
.product-tile:hover {
  transform: translateY(-4px);
  border-color: #a6c6af;
}
.product-image {
  position: relative;
  aspect-ratio: 1.38;
  overflow: hidden;
}
.product-image .el-image {
  width: 100%;
  height: 100%;
  transition: transform 0.4s;
}
.product-tile:hover .el-image {
  transform: scale(1.04);
}
.product-image > .demo-tag {
  position: absolute;
  top: 12px;
  left: 12px;
}
.stock-chip {
  position: absolute;
  right: 11px;
  bottom: 11px;
  background: #fffef6;
  color: #28613a;
  font-size: 10px;
  padding: 5px 8px;
  border-radius: 4px;
}
.stock-chip.out {
  color: #966a2d;
}
.product-copy {
  padding: 17px;
}
.product-origin {
  font-size: 10px;
  color: #78877c;
  display: flex;
  gap: 4px;
  align-items: center;
  white-space: nowrap;
  overflow: hidden;
}
.product-copy h3 {
  font-size: 15px;
  margin: 10px 0;
}
.product-spec {
  display: flex;
  gap: 7px;
  font-size: 10px;
  color: #627768;
}
.product-spec span {
  background: #f0f4ef;
  padding: 3px 6px;
  border-radius: 3px;
}
.product-price {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin: 18px 0 16px;
  gap: 8px;
}
.product-price strong {
  font-size: 21px;
  color: #1c6447;
  font-weight: 600;
}
.product-price small {
  font-size: 10px;
  color: #78877c;
  font-weight: 400;
  margin-left: 3px;
}
.product-price > span {
  font-size: 10px;
  color: #849087;
}
.product-bottom {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  border-top: 1px solid var(--line);
  padding-top: 12px;
  color: #7a8b7d;
}
.photo-placeholder {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  background: #e4ede0;
  color: #6b8867;
}
.photo-placeholder .el-icon {
  font-size: 35px;
}
@media (max-width: 1300px) {
  .product-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
@media (max-width: 900px) {
  .product-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 15px;
  }
  .market-banner {
    padding: 25px;
  }
  .market-banner h2 {
    font-size: 21px;
  }
}
@media (max-width: 480px) {
  .product-grid {
    gap: 10px;
  }
  .product-copy {
    padding: 12px;
  }
  .product-copy h3 {
    font-size: 13px;
  }
  .product-price {
    align-items: flex-start;
    flex-direction: column;
    gap: 4px;
  }
  .product-bottom {
    gap: 7px;
    flex-direction: column;
  }
  .banner-counter {
    display: none;
  }
}
</style>
