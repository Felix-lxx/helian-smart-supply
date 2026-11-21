<template>
    <div class="remote-sensing-container">
      <el-row :gutter="20">
        <el-col :span="16">
          <el-card shadow="never">
            <template #header>
              <span style="font-weight: bold;">洛川苹果主产区 - 环境指标动态监测图</span>
            </template>
            <div ref="chartRef" style="width: 100%; height: 400px;"></div>
          </el-card>
        </el-col>

        <el-col :span="8">
          <el-card shadow="never" style="height: 100%;">
            <template #header>
              <span style="font-weight: bold;">🌿 系统智能数据解读</span>
            </template>

            <el-alert
              title="作物长势：极佳"
              type="success"
              description="本月植被指数(NDVI)持续上升，说明果树叶片茂盛，光合作用强烈，预计今年果实甜度较高。"
              show-icon
              :closable="false"
              class="mb-15"
            />

            <el-alert
              title="土壤墒情：水分充足"
              type="info"
              description="当前土壤湿度维持在 52%-60% 之间，属于果树膨大期的黄金湿度区间，近期内饭店/超市采购商可放心预订该产区货源，品质有保障。"
              show-icon
              :closable="false"
              class="mb-15"
            />

            <el-alert
              title="灾害预警：安全"
              type="warning"
              description="综合遥感气象云图，未来一周无强降雨或冰雹等极端天气，不影响物流发车与采摘。"
              show-icon
              :closable="false"
            />
          </el-card>
        </el-col>
      </el-row>
    </div>
  </template>

  <script setup>
  import { ref, onMounted } from 'vue'
  import * as echarts from 'echarts'

  const chartRef = ref(null)

  onMounted(() => {
    const myChart = echarts.init(chartRef.value)
    const option = {
      tooltip: { trigger: 'axis' },
      legend: { data: ['土壤湿度 (%)', '植被生长指数'] },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: { type: 'category', boundaryGap: false, data: ['1日', '5日', '10日', '15日', '20日', '25日', '30日'] },
      yAxis: { type: 'value' },
      series: [
        { name: '土壤湿度 (%)', type: 'line', data: [45, 42, 38, 55, 60, 58, 52], smooth: true, areaStyle: { color: 'rgba(64, 158, 255, 0.2)' } },
        { name: '植被生长指数', type: 'line', data: [65, 66, 68, 70, 75, 76, 74], smooth: true, itemStyle: { color: '#67C23A' } }
      ]
    }
    myChart.setOption(option)
    window.addEventListener('resize', () => myChart.resize())
  })
  </script>

  <style scoped>
  .mb-15 { margin-bottom: 15px; }
  </style>
