<script setup>
import { ref, computed, onMounted, defineAsyncComponent } from 'vue'
import { useRouter } from 'vue-router'
import { useWorkspace, qty, money } from '@/stores/workspace'
import OriginMap from '@/components/OriginMap.vue'
import request from '@/utils/request'
import { ElMessage } from 'element-plus'
const OnlineOriginMap = defineAsyncComponent(() => import('@/components/OnlineOriginMap.vue'))
const mapConfig = ref(null),
  mapMode = ref('offline')
onMounted(async () => {
  try {
    mapConfig.value = (await request.get('/workspace/maps/config/')).data
    if (mapConfig.value.enabled) mapMode.value = 'official'
  } catch {}
})
function offline() {
  mapMode.value = 'offline'
  ElMessage.warning('暂时无法完整加载底图，已切换离线产地概览')
}
const w = useWorkspace(),
  router = useRouter(),
  search = ref(''),
  selected = ref(null),
  layer = ref('supply')
const sites = computed(() =>
  w.collaboration.sites
    .filter((s) => (s.name + s.address + s.company).includes(search.value))
    .map((s) => {
      const a = s.location?.split(',').map(Number)
      return {
        ...s,
        coords:
          a?.length === 2 &&
          a.every(Number.isFinite) &&
          Math.abs(a[0]) <= 180 &&
          Math.abs(a[1]) <= 90
            ? a
            : null,
      }
    }),
)
const products = computed(() => w.market.filter((p) => (p.origin + p.name).includes(search.value)))
const groups = computed(() => {
  if (layer.value === 'sites')
    return sites.value
      .filter((s) => s.coords)
      .map((s) => ({
        id: -s.id,
        name: s.name,
        origin: s.address,
        coords: s.coords,
        stock: 1,
        unit: '个站点',
        kind: 'site',
        items: [],
      }))
  const m = new Map()
  for (const p of products.value) {
    if (!p.coords) continue
    const k = p.coords.join(',')
    if (!m.has(k))
      m.set(k, {
        id: p.id,
        name: p.origin,
        origin: p.origin,
        coords: p.coords,
        stock: 0,
        unit: '项货源',
        items: [],
      })
    m.get(k).items.push(p)
    m.get(k).stock++
  }
  return [...m.values()]
})
const active = computed(() => groups.value.find((g) => g.id === selected.value)),
  visible = computed(() => active.value?.items || products.value)
function select(id) {
  selected.value = selected.value === id ? null : id
}
</script>
<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1>产地网络</h1>
        <p>从地图找到货源，从货源核对批次。每个点都对应已录入的真实经纬度。</p>
      </div>
      <el-input
        v-model="search"
        placeholder="按产地或品种筛选"
        prefix-icon="Search"
        clearable
        style="width: 270px"
        @input="selected = null"
      />
    </div>
    <div class="origin-metrics">
      <span
        ><b>{{ groups.length }}</b> 个已定位{{ layer === 'sites' ? '业务站点' : '产地点' }}</span
      ><span
        ><b>{{ layer === 'sites' ? sites.length : products.length }}</b> 项可见{{
          layer === 'sites' ? '站点' : '货源'
        }}</span
      ><span
        ><b>{{ (layer === 'sites' ? sites : products).filter((p) => !p.coords).length }}</b>
        项尚未录入坐标</span
      ><span class="origin-note"><i></i>散点为供给位置，非实时运输位置</span>
    </div>
    <div class="origin-layout">
      <section class="map-surface">
        <div class="map-heading">
          <h2>{{ layer === 'sites' ? '业务站点分布' : '全国货源分布' }}</h2>
          <el-radio-group v-if="mapConfig?.enabled" v-model="mapMode" size="small"
            ><el-radio-button value="official">天地图</el-radio-button
            ><el-radio-button value="offline">离线概览</el-radio-button></el-radio-group
          ><el-radio-group v-model="layer" size="small" @change="selected = null"
            ><el-radio-button value="supply">产地</el-radio-button
            ><el-radio-button value="sites">站点</el-radio-button></el-radio-group
          >
        </div>
        <OnlineOriginMap
          v-if="mapMode === 'official' && mapConfig?.enabled"
          :products="groups"
          :tile-url="mapConfig.tile_url"
          :selected="selected"
          height="580px"
          @select="select"
          @unavailable="offline"
        /><OriginMap
          v-else
          :products="groups"
          :selected="selected"
          height="580px"
          dark
          @select="select"
        />
        <div class="map-bottom">
          <span>{{
            mapMode === 'official'
              ? '天地图官方底图 / 业务坐标须为 WGS84 或 CGCS2000'
              : '离线产地概览 / 未知坐标不自动定位'
          }}</span
          ><el-button v-if="selected" size="small" @click="selected = null">清除选中</el-button>
        </div>
      </section>
      <section class="panel origin-list">
        <div class="panel-head">
          <h2>{{ layer === 'sites' ? '业务站点' : active ? '产地关联货源' : '可见货源' }}</h2>
          <span class="small muted"
            >{{ layer === 'sites' ? sites.length : visible.length }} 项</span
          >
        </div>
        <div v-if="active" class="active-origin">
          <el-icon><Location /></el-icon>
          <div>
            <b>{{ active.origin }}</b
            ><small>{{ active.coords.join('，') }}</small>
          </div>
        </div>
        <div v-if="layer === 'sites'" class="panel-body">
          <article
            v-for="s in sites.filter((s) => !selected || -s.id === selected)"
            :key="s.id"
            class="site-card"
          >
            <h3>{{ s.name }}</h3>
            <p>
              {{ s.company }}<br />{{ s.address }}<br />{{ s.contact }} {{ s.phone }}<br />{{
                s.location || '坐标待录入'
              }}
            </p>
            <el-button v-if="s.coords" link type="primary" @click="select(-s.id)">{{
              selected === -s.id ? '显示全部站点' : '在地图中选中'
            }}</el-button>
          </article>
          <el-empty
            v-if="!sites.length"
            description="尚无授权可见站点，请在企业与站点中维护"
            :image-size="60"
          />
        </div>
        <template v-else
          ><button
            v-for="p in visible"
            :key="p.id"
            class="origin-product"
            @click="router.push('/product/' + p.id)"
          >
            <el-image :src="p.image_url" fit="cover" class="thumb" />
            <div>
              <b>{{ p.name }}</b
              ><small>{{ p.origin }}</small
              ><span>{{ qty(p.stock) }} {{ p.unit }} 可售 <i v-if="p.is_demo">演示</i></span>
            </div>
            <el-icon><Right /></el-icon></button
          ><el-empty v-if="!visible.length" description="暂无匹配的货源" :image-size="60"
        /></template>
      </section>
    </div>
    <div class="info-strip section-gap">
      地图按已录入经纬度绘制，同一位置的货源合并展示。演示货源使用对应行政区域的示例坐标，不代表真实合作基地或物流覆盖。产地位置不能证明该批次的品质与安全。
    </div>
  </div>
</template>
<style scoped>
.origin-metrics {
  display: flex;
  align-items: center;
  gap: 30px;
  flex-wrap: wrap;
  margin-bottom: 24px;
  font-size: 12px;
  color: var(--muted);
}
.origin-metrics b {
  font-size: 22px;
  color: #31513a;
  font-weight: 500;
  margin-right: 5px;
}
.origin-note {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 10px;
}
.origin-note i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #4b8d5b;
}
.origin-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.8fr) minmax(285px, 1fr);
  gap: 22px;
}
.map-surface {
  background: #173a2e;
  border-radius: 12px;
  overflow: hidden;
  color: #dfeeda;
}
.map-heading {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding-bottom: 18px;
  justify-content: space-between;
  padding: 25px 27px 0;
  align-items: center;
}
.map-heading h2 {
  font-size: 16px;
}
.map-heading span {
  font-size: 10px;
  color: #b7ccba;
}
.map-bottom {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 25px 22px;
  font-size: 10px;
  color: #b6cbb7;
  gap: 15px;
}
.origin-list {
  max-height: 670px;
  overflow: auto;
}
.origin-product {
  display: flex;
  gap: 13px;
  align-items: center;
  width: 100%;
  border: 0;
  border-bottom: 1px solid var(--line);
  background: #fff;
  padding: 20px;
  text-align: left;
  color: inherit;
}
.origin-product:hover {
  background: #f4f8f2;
}
.origin-product > div:not(.el-image) {
  flex: 1;
}
.origin-product .thumb {
  flex: 0 0 44px;
}
.origin-product b {
  font-size: 12px;
  font-weight: 500;
}
.origin-product small {
  display: block;
  font-size: 10px;
  color: var(--muted);
  margin-top: 7px;
}
.origin-product span {
  display: block;
  font-size: 10px;
  color: var(--brand);
  margin-top: 7px;
}
.origin-product i {
  font-style: normal;
  color: #9a7e45;
  margin-left: 10px;
}
.active-origin {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 18px 20px;
  background: #edf5ea;
  color: #417244;
}
.active-origin b {
  font-size: 12px;
}
.active-origin small {
  font-size: 10px;
  display: block;
  margin-top: 7px;
}
@media (max-width: 1100px) {
  .origin-layout {
    grid-template-columns: 1fr;
  }
  .origin-list {
    max-height: 450px;
  }
  .origin-note {
    margin-left: 0;
  }
}
</style>
