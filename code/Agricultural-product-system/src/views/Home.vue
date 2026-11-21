<template>
  <div class="dashboard-container">
    <el-row :gutter="20" class="stat-row">
      <el-col :span="6" v-for="card in statCards" :key="card.title">
        <div class="data-card" :class="card.type">
          <div class="card-inner">
            <div class="card-info">
              <div class="label">{{ card.title }}</div>
              <div class="value-wrapper">
                <span class="unit" v-if="card.prefix">{{ card.prefix }}</span>
                <span class="count">{{ card.value }}</span>
              </div>
            </div>
            <div class="card-icon">
              <el-icon><component :is="card.icon" /></el-icon>
            </div>
          </div>
          <div class="card-footer">
            <span class="trend" :class="card.trend > 0 ? 'up' : 'down'">
              {{ card.trend >= 0 ? '↑' : '↓' }} {{ Math.abs(card.trend) }}%
            </span>
            <span class="sub-label">较上月同期</span>
          </div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="main-row">
      <el-col :span="24">
        <el-card shadow="never" class="recommend-card">
          <template #header>
            <div class="card-header">
              <span class="title-with-icon">
                <el-icon><Star /></el-icon> {{ recommendData.title }}
              </span>
              <el-tooltip v-if="recommendData.advice" :content="recommendData.advice" placement="top">
                <el-icon class="info-icon" style="margin-left: 8px; cursor: pointer; color: #909399;"><InfoFilled /></el-icon>
              </el-tooltip>
              <el-tag v-if="recommendData.type === 'competitor'" type="warning" size="small" style="margin-left: 10px">商业情报</el-tag>
            </div>
          </template>
          <el-row :gutter="20">
            <el-col :span="4" v-for="item in recommendData.data" :key="item.id">
              <div class="prod-recommend-item" @click="$router.push(`/product/${item.id}`)">
                <div class="comp-badge" v-if="recommendData.type === 'competitor'">竞品分析</div>
                <el-image :src="item.image_url" fit="cover" class="recommend-img">
                  <template #error><div class="image-slot"><el-icon><Picture /></el-icon></div></template>
                </el-image>
                <div class="recommend-info">
                  <div class="name-text">{{ item.name }}</div>
                  <div class="meta-text">
                    <span class="price-tag">￥{{ item.retail_price }}</span>
                    <span class="sales-tag">销量: {{ item.sales_count || 0 }}</span>
                  </div>
                </div>
              </div>
            </el-col>
          </el-row>
          <el-empty v-if="recommendData.data.length === 0" description="算法正在为您计算最优策略..." :image-size="60" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="main-row">
      <el-col :span="24">
        <el-card class="quality-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span class="title-with-icon">
                <el-icon><Monitor /></el-icon> 平台 AI 视觉审计实时动态 (YOLOv5 驱动)
              </span>
              <el-tag type="danger" effect="dark" class="blink">LIVE</el-tag>
            </div>
          </template>
          <div class="quality-scroll-wrapper">
            <div v-for="log in qualityLogs" :key="log.id" class="quality-item">
              <div class="log-info">
                <el-tag size="small" :type="log.bad_count === 0 ? 'success' : 'warning'">
                  {{ log.bad_count === 0 ? '检测合格' : '发现瑕疵' }}
                </el-tag>
                <span class="time">[{{ formatTime(log.created_at) }}]</span>
                <span class="desc">
                  系统对商品 <b>#{{ log.product || '样本' }}</b> 完成 AI 抽检，
                  识别出坏果位点: <span :class="log.bad_count > 0 ? 'text-danger' : 'text-success'">{{ log.bad_count }}</span> 个。
                </span>
              </div>
              <el-button type="primary" link @click="viewAuditDetail(log)">查看审计快照</el-button>
            </div>
            <el-empty v-if="qualityLogs.length === 0" :image-size="40" description="AI 审计引擎待命中..." />
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="main-row">
      <el-col :span="16">
        <el-card class="map-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span><el-icon><Location /></el-icon> 全国源头产地全量追溯 (实时更新)</span>
              <el-tag type="success" effect="dark" size="small">全网覆盖</el-tag>
            </div>
          </template>
          <div ref="mapChartRef" class="map-viz"></div>
          <div class="map-legend">
            <div class="legend-item"><span class="dot orange"></span> 核心供应基地</div>
            <div class="legend-item"><span class="dot blue"></span> 实时物流节点</div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card class="status-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span><el-icon><Bell /></el-icon> 实时采购动态流水</span>
            </div>
          </template>
          <div class="scroll-wrapper">
            <div class="scroll-content">
              <div v-for="item in purchaseLogs" :key="item.id" class="log-item">
                <div class="log-dot"></div>
                <div class="log-text">
                  <span class="time">{{ formatLogTime(item.created_at) }}</span>
                  <span class="buyer">{{ item.buyer_name }}</span>
                  采购了 <span class="prod">{{ getProductName(item) }}</span>
                </div>
                <el-tag size="small" :type="getDisplayStatus(item.status).type">
                  {{ getDisplayStatus(item.status).text }}
                </el-tag>
              </div>
              <el-empty v-if="purchaseLogs.length === 0" description="暂无近期流水" :image-size="60" />
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="bottom-row">
      <el-col :span="12">
        <el-card class="monitor-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span><el-icon><Cpu /></el-icon> 边缘节点：RDK X5 实时算力示波器</span>
              <el-tag :type="warningMsg === 'Offline' ? 'info' : 'danger'" class="blink">
                {{ warningMsg === 'Offline' ? 'OFFLINE' : 'ONLINE' }}
              </el-tag>
            </div>
          </template>
          <div class="monitor-body">
            <div class="monitor-stats">
              <div class="m-item">
                <div class="m-label">NPU 负载</div>
                <div class="m-value">{{ npuLoad }}%</div>
              </div>
              <div class="m-item">
                <div class="m-label">推理延迟</div>
                <div class="m-value tech">{{ yoloDelay }}ms</div>
              </div>
            </div>
            <div ref="npuWaveRef" class="wave-chart"></div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card class="chart-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span><el-icon><TrendCharts /></el-icon> 采购品类权重分析</span>
            </div>
          </template>
          <div ref="pieChartRef" class="echart-container"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-dialog v-model="auditDialogVisible" title="YOLOv5 AI 审计结果快照" width="50%">
      <div v-if="selectedLog" class="audit-detail">
        <el-image :src="selectedLog.processed_image" fit="contain">
          <template #error><div class="image-slot">快照加载失败</div></template>
        </el-image>
        <div class="audit-summary mt-10">
          <el-descriptions border :column="2">
            <el-descriptions-item label="检出异常数">{{ selectedLog.bad_count }} 个</el-descriptions-item>
            <el-descriptions-item label="检测结论">{{ selectedLog.summary }}</el-descriptions-item>
            <el-descriptions-item label="操作员">系统自动审计 (Admin)</el-descriptions-item>
          </el-descriptions>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick, markRaw } from 'vue'
import * as echarts from 'echarts'
import dayjs from 'dayjs'
import {
  Wallet, User, Location, Cpu, Bell, TrendCharts,
  Monitor, Star, InfoFilled, Picture
} from '@element-plus/icons-vue'
import chinaMap from '../assets/map/china.json'
import request from '../utils/request'

// --- 状态定义 ---
const npuLoad = ref(0)
const yoloDelay = ref(0)
const warningMsg = ref('Offline')
const purchaseLogs = ref([])
const qualityLogs = ref([])
const productDict = ref({})
const auditDialogVisible = ref(false)
const selectedLog = ref(null)

// 响应式推荐数据
const recommendData = ref({ type: 'buyer', title: '猜你喜欢：优质农产推荐', data: [], advice: '' })

const statCards = ref([
  { title: '平台总交易额', value: '0', prefix: '￥', trend: 0, icon: markRaw(Wallet), type: 'primary', key: 'total_revenue' },
  { title: '用户', value: '5', trend: 0, icon: markRaw(User), type: 'success', key: 'total_users' },
  { title: '活跃供应基地', value: '0', trend: 0, icon: markRaw(Location), type: 'warning', key: 'supplier_count' },
  { title: '边缘计算节点', value: '0', trend: 0, icon: markRaw(Cpu), type: 'danger', key: 'device_count' }
])

const CATEGORY_MAP = {
  'fruits_vegs': '生鲜果蔬', 'grains': '米面粮油', 'meat': '肉禽蛋奶', 'dry': '干货菌菇'
}

// --- 业务函数 ---
const formatLogTime = (t) => dayjs(t).format('M/D HH:mm')
const formatTime = (t) => dayjs(t).format('HH:mm:ss')

const getDisplayStatus = (status) => {
  if (status === 'shipped') return { text: '已发车', type: 'success' }
  if (status === 'paid') return { text: '待发货', type: 'warning' }
  return { text: '处理中', type: 'info' }
}

const getProductName = (row) => {
  if (row.product_name) return row.product_name
  const pId = row.product?.id || row.product
  return productDict.value[pId]?.name || '未记录货品'
}

const viewAuditDetail = (log) => {
  selectedLog.value = log
  auditDialogVisible.value = true
}

// --- 数据同步逻辑 ---

// 首页推荐入口：后端会根据角色返回“竞品”或“猜你喜欢”两种结构。
const fetchRecommendations = async () => {
  try {
    const res = await request.get('/recommend/')
    // 处理后端返回的数据结构：既支持纯数组也支持带元数据的对象
    recommendData.value = {
      type: res.data.type || 'buyer',
      title: res.data.title || (res.data.type === 'competitor' ? '竞品情报：同类目热销商品' : '猜你喜欢：优质农产推荐'),
      advice: res.data.advice || '',
      data: res.data.data || res.data
    }
  } catch (e) {
    console.error('推荐算法加载失败', e)
  }
}

// 质检流水用于首页滚动展示与审计弹窗。
const fetchQualityLogs = async () => {
  try {
    const res = await request.get('/quality/logs/')
    qualityLogs.value = res.data.results || res.data
  } catch (e) { console.error('质检日志更新失败', e) }
}

// 并行拉取商品和订单，再驱动地图/饼图联动刷新。
const fetchLiveDate = async () => {
  try {
    const userRole = localStorage.getItem('user_role')
    const orderApi =
      userRole === 'admin'
        ? '/orders/all/'
        : userRole === 'supplier'
          ? '/orders/supplier/'
          : '/orders/'

    const [prodRes, orderRes] = await Promise.all([
      request.get('/products/'),
      request.get(orderApi)
    ])
    const prods = prodRes.data.results || prodRes.data
    prods.forEach(p => productDict.value[p.id] = p)
    purchaseLogs.value = orderRes.data.results || orderRes.data
    updateMapScatter(); updatePieChart()
  } catch (e) { console.error('首页数据更新失败', e) }
}

const fetchSystemStats = async () => {
  try {
    const res = await request.get('/sys/stats/')
    const data = res.data
    statCards.value[0].value = data.total_revenue.toLocaleString()
    statCards.value[1].value = data.total_users
    statCards.value[2].value = data.supplier_count
    statCards.value[3].value = data.device_count
    statCards.value[0].trend = data.trends.revenue
    statCards.value[1].trend = data.trends.wholesale
    statCards.value[2].trend = data.trends.supplier
  } catch (e) { console.error('统计数据更新失败', e) }
}

const fetchDeviceData = async () => {
  try {
    const res = await request.get('/device/report/')
    npuLoad.value = res.data.npu_load
    yoloDelay.value = res.data.yolo_delay
    warningMsg.value = res.data.status === 'offline' ? 'Offline' : 'Normal'
    updateWave()
  } catch (e) { warningMsg.value = 'Offline' }
}

// --- ECharts 配置 ---
const mapChartRef = ref(null); const pieChartRef = ref(null); const npuWaveRef = ref(null)
let mapChart, pieChart, waveChart
const waveData = new Array(20).fill(0)

const updateWave = () => {
  waveData.shift(); waveData.push(npuLoad.value)
  waveChart?.setOption({ series: [{ data: waveData }] })
}

// 将商品产地坐标转换为地图散点数据。
const updateMapScatter = () => {
  if (!mapChart) return
  const scatterData = Object.values(productDict.value)
    .filter(p => p && p.location && p.location.includes(','))
    .map(p => {
      const coords = p.location.split(',').map(Number)
      return { name: p.name, value: [coords[0], coords[1], 100], origin: p.origin }
    })
  mapChart.setOption({ series: [{ data: scatterData }] })
}

// 统计当前商品池的分类分布，更新饼图。
const updatePieChart = () => {
  if (!pieChart) return
  const stats = { fruits_vegs: 0, grains: 0, meat: 0, dry: 0 }
  Object.values(productDict.value).forEach(p => {
    if (p && stats.hasOwnProperty(p.category)) stats[p.category]++
  })
  const pieData = Object.entries(CATEGORY_MAP).map(([key, label]) => ({
    value: stats[key], name: label
  }))
  pieChart.setOption({ series: [{ data: pieData }] })
}

const initCharts = () => {
  echarts.registerMap('china', chinaMap)
  mapChart = echarts.init(mapChartRef.value)
  mapChart.setOption({
    geo: { map: 'china', roam: true, zoom: 1.2, itemStyle: { areaColor: '#f3f6f9', borderColor: '#ced4da' } },
    tooltip: { trigger: 'item', formatter: (p) => `${p.name}<br/>产地: ${p.data.origin}` },
    series: [{ type: 'effectScatter', coordinateSystem: 'geo', symbolSize: 10, rippleEffect: { scale: 4 }, itemStyle: { color: '#ff5000' }, data: [] }]
  })
  pieChart = echarts.init(pieChartRef.value)
  pieChart.setOption({
    tooltip: { trigger: 'item' },
    series: [{ type: 'pie', radius: ['50%', '70%'], itemStyle: { borderRadius: 8, borderColor: '#fff', borderWidth: 2 }, data: [] }]
  })
  waveChart = echarts.init(npuWaveRef.value)
  waveChart.setOption({
    grid: { left: 0, right: 0, top: 0, bottom: 0 },
    xAxis: { type: 'category', show: false },
    yAxis: { type: 'value', min: 0, max: 100, show: false },
    series: [{ type: 'line', smooth: true, areaStyle: { color: 'rgba(245,108,108,0.2)' }, lineStyle: { color: '#f56c6c' }, data: waveData }]
  })
}

// --- 生命周期 ---
let pollingTimer, logRefreshTimer
onMounted(async () => {
  await nextTick(); initCharts()
  fetchSystemStats(); fetchLiveDate(); fetchDeviceData(); fetchQualityLogs()
  fetchRecommendations() // 首次加载推荐

  pollingTimer = setInterval(fetchDeviceData, 2000)
  logRefreshTimer = setInterval(() => {
    fetchLiveDate(); fetchSystemStats(); fetchQualityLogs(); fetchRecommendations()
  }, 10000)
  window.addEventListener('resize', () => { mapChart?.resize(); pieChart?.resize(); waveChart?.resize() })
})

onBeforeUnmount(() => { clearInterval(pollingTimer); clearInterval(logRefreshTimer) })
</script>

<style scoped>
.dashboard-container { padding: 20px; background-color: #f8f9fa; }
.stat-row, .main-row, .bottom-row { margin-bottom: 20px; }
.data-card { background: white; border-radius: 12px; padding: 20px; border-left: 4px solid #ddd; transition: 0.3s; }
.primary { border-left-color: #409EFF; }
.success { border-left-color: #67C23A; }
.warning { border-left-color: #E6A23C; }
.danger { border-left-color: #F56C6C; }
.count { font-size: 26px; font-weight: bold; }
.card-inner { display: flex; justify-content: space-between; align-items: center; }

/* 推荐板块样式 */
.recommend-card { border-radius: 12px; }
.prod-recommend-item {
  background: #fff; border-radius: 8px; border: 1px solid #f0f0f0; padding: 10px; cursor: pointer; transition: 0.3s; position: relative; overflow: hidden;
}
.prod-recommend-item:hover { transform: translateY(-5px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); border-color: #409eff; }
.comp-badge {
  position: absolute; top: 0; right: 0; background: #e6a23c; color: #fff; font-size: 10px; padding: 2px 6px; border-bottom-left-radius: 8px; z-index: 10;
}
.recommend-img { width: 100%; height: 120px; border-radius: 4px; }
.recommend-info { margin-top: 10px; }
.name-text { font-size: 13px; font-weight: bold; color: #333; margin-bottom: 5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.meta-text { display: flex; justify-content: space-between; align-items: center; }
.price-tag { color: #f56c6c; font-weight: bold; font-size: 14px; }
.sales-tag { color: #999; font-size: 11px; }

/* 质检动态滚动条样式 */
.quality-card { border-radius: 12px; }
.quality-scroll-wrapper { height: 120px; overflow-y: auto; scrollbar-width: none; }
.quality-item { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px dashed #eee; font-size: 13px; }
.time { color: #999; margin: 0 10px; font-family: monospace; }
.text-danger { color: #F56C6C; font-weight: bold; }
.text-success { color: #67C23A; font-weight: bold; }
.blink { animation: blink 2s infinite; }
@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }

.map-viz { height: 450px; }
.scroll-wrapper { height: 460px; overflow-y: auto; }
.log-item { display: flex; align-items: center; padding: 12px 0; border-bottom: 1px solid #f0f0f0; }
.monitor-body { height: 180px; display: flex; }
.wave-chart { flex: 1; height: 100%; }
.echart-container { height: 180px; }
.mt-10 { margin-top: 10px; }
.mt-20 { margin-top: 20px; }
</style>
