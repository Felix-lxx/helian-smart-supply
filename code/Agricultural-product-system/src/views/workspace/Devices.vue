<script setup>
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'
import request from '@/utils/request'
import { dateText } from '@/stores/workspace'
import BusinessChart from '@/components/BusinessChart.vue'
import { ElMessage } from 'element-plus'
const devices = ref([]),
  selectedId = ref(null),
  busy = ref(false)
let timer
const selected = computed(
  () => devices.value.find((d) => d.id === selectedId.value) || devices.value[0],
)
async function load() {
  busy.value = true
  try {
    devices.value = (await request.get('/workspace/devices/')).data
  } catch {
    ElMessage.error('设备状态暂不可用')
  } finally {
    busy.value = false
  }
}
const chart = computed(() => ({
  color: ['#378060', '#ba9a59'],
  tooltip: { trigger: 'axis' },
  legend: { data: ['负载 / %', '延迟 / ms'], bottom: 0 },
  grid: { top: 30, left: 50, right: 50, bottom: 55 },
  xAxis: {
    type: 'category',
    data: selected.value?.history.map((h) => dateText(h.timestamp)) || [],
    axisLabel: { show: false },
  },
  yAxis: [
    { type: 'value', name: '负载 / %', max: 100, splitLine: { lineStyle: { color: '#edf1ee' } } },
    { type: 'value', name: '延迟 / ms', splitLine: { show: false } },
  ],
  series: [
    {
      name: '负载 / %',
      type: 'line',
      smooth: true,
      data: selected.value?.history.map((h) => h.npu_load) || [],
    },
    {
      name: '延迟 / ms',
      type: 'line',
      yAxisIndex: 1,
      smooth: true,
      data: selected.value?.history.map((h) => h.yolo_delay) || [],
    },
  ],
}))
onMounted(() => {
  load()
  timer = setInterval(() => {
    if (!document.hidden) load()
  }, 15000)
})
onBeforeUnmount(() => clearInterval(timer))
</script>
<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1>设备接入</h1>
        <p>每台设备独立记录心跳与观测数据。离线只表示近期没有上报，不推断断电或气象原因。</p>
      </div>
      <el-button icon="Refresh" :loading="busy" @click="load">刷新状态</el-button>
    </div>
    <div class="metrics">
      <div class="metric">
        <div class="metric-label">已登记节点</div>
        <div class="metric-value">{{ devices.length }}</div>
        <div class="metric-foot">来自实际设备登记记录</div>
      </div>
      <div class="metric">
        <div class="metric-label">近期在线</div>
        <div class="metric-value good">{{ devices.filter((d) => d.online).length }}</div>
        <div class="metric-foot">30秒内收到有效上报</div>
      </div>
      <div class="metric">
        <div class="metric-label">未收到近期心跳</div>
        <div class="metric-value">{{ devices.filter((d) => !d.online).length }}</div>
        <div class="metric-foot">不等同于硬件故障</div>
      </div>
      <div class="metric">
        <div class="metric-label">显示历史点</div>
        <div class="metric-value">{{ selected?.history.length || 0 }}</div>
        <div class="metric-foot">所选设备最近24条记录</div>
      </div>
    </div>
    <div class="grid-equal">
      <section class="panel">
        <div class="panel-head"><h2>节点列表</h2></div>
        <el-table :data="devices" highlight-current-row @row-click="(d) => (selectedId = d.id)"
          ><el-table-column label="设备编号" prop="device_id" min-width="170" /><el-table-column
            label="位置"
            prop="location"
            min-width="120"
          /><el-table-column label="状态" width="100"
            ><template #default="{ row }"
              ><span :class="row.online ? 'good' : 'muted'">{{
                row.online ? '在线' : '未在线'
              }}</span></template
            ></el-table-column
          ></el-table
        >
        <div v-if="!devices.length" class="empty-state">
          <el-icon size="35"><Monitor /></el-icon>
          <h3 style="margin-top: 15px">尚未接入设备</h3>
          <p>软件业务可独立运行。连接真实摄像头、称重或监测设备后，在这里查看上报。</p>
        </div>
      </section>
      <section class="panel">
        <div class="panel-head">
          <h2>{{ selected?.device_id || '节点观测趋势' }}</h2>
          <span class="small muted">{{
            selected?.last_seen ? dateText(selected.last_seen) : '暂无数据'
          }}</span>
        </div>
        <BusinessChart v-if="selected" :option="chart" height="300px" />
        <div v-if="selected" class="panel-body"><div v-if="selected.is_mock" class="info-strip warning">此节点为 MOCK 模拟遥测，不能作为真实设备性能或品质证据。</div><div class="row-actions"><router-link v-if="selected.batch_id" :to="'/quality?batch='+selected.batch_id"><el-button type="primary" plain>查看关联批次</el-button></router-link><router-link v-if="selected.task_id" :to="'/reviews?task='+selected.task_id"><el-button plain>打开检查任务</el-button></router-link></div><p v-if="Object.keys(selected.observations||{}).length" class="data-note">原始观测待人工核实：{{JSON.stringify(selected.observations)}}</p></div>
        <div v-else class="empty-state">设备数据到达后显示趋势，不生成模拟波形。</div>
      </section>
    </div>
    <div class="info-strip warning section-gap">
      旧版 mock_x5.py
      为随机模拟上报程序，其数据不能作为真实设备性能证明。旧上报通道需要设备令牌，工作台不对任意匿名数据开放写入。
    </div>
  </div>
</template>
