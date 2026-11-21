<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import * as echarts from 'echarts'
import china from '@/assets/map/China.compact.json'
const props = defineProps({
  products: { type: Array, default: () => [] },
  height: { type: String, default: '400px' },
  selected: Number,
  dark: Boolean,
})
const emit = defineEmits(['select'])
const root = ref()
let chart, observer
function draw() {
  if (!chart) return
  const camera = chart.getOption()?.geo?.[0]
  const points = props.products
    .filter(
      (p) => Array.isArray(p.coords) && p.coords.length === 2 && p.coords.every(Number.isFinite),
    )
    .map((p) => ({
      name: p.name,
      value: [...p.coords, p.stock || 0],
      productId: p.id,
      origin: p.origin,
      unit: p.unit,
      kind: p.kind,
      symbol: p.kind === 'site' ? 'roundRect' : 'circle',
      itemStyle:
        p.id === props.selected
          ? { color: '#e4bf76', borderColor: '#fff', borderWidth: 3 }
          : undefined,
    }))
  chart.setOption(
    {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'item',
        renderMode: 'richText',
        formatter: (p) =>
          p.data
            ? `${p.name}\n${p.data.origin}` +
              (p.data.kind === 'site'
                ? '\n业务站点 · 非实时运输位置'
                : `\n${p.data.unit === '项货源' ? '关联' : '可售'} ${p.value[2]} ${p.data.unit}`)
            : '',
      },
      geo: {
        map: 'hualian-china',
        roam: true,
        zoom: camera?.zoom ?? 1.12,
        center: camera?.center,
        layoutCenter: ['50%', '51%'],
        layoutSize: '98%',
        itemStyle: {
          areaColor: props.dark ? '#244a3d' : '#e8efea',
          borderColor: props.dark ? '#4b6d5b' : '#fff',
          borderWidth: 1,
        },
        emphasis: {
          label: { show: false },
          itemStyle: { areaColor: props.dark ? '#365f49' : '#cfdfd2' },
        },
        label: { show: false },
      },
      series: [
        {
          type: 'scatter',
          coordinateSystem: 'geo',
          data: points,
          symbolSize: (p) => Math.min(20, 9 + Math.sqrt(p[2] || 0) / 4),
          itemStyle: {
            color: props.dark ? '#d1e8a9' : '#248363',
            borderColor: props.dark ? '#9fbf7e' : '#fff',
            borderWidth: 2,
          },
          emphasis: { scale: 1.5 },
          label: { show: false },
          z: 3,
        },
      ],
    },
    true,
  )
}
onMounted(() => {
  echarts.registerMap('hualian-china', china)
  chart = echarts.init(root.value)
  draw()
  chart.on('click', (p) => {
    if (p.data?.productId) emit('select', p.data.productId)
  })
  observer = new ResizeObserver(() => chart?.resize())
  observer.observe(root.value)
})
watch(() => [props.products, props.dark, props.selected], draw, { deep: true })
onBeforeUnmount(() => {
  observer?.disconnect()
  chart?.dispose()
})
</script>
<template>
  <div
    ref="root"
    :style="{ height, width: '100%' }"
    role="img"
    aria-label="中国农产品产地地图，散点为已录入坐标的货源，可点击查看"
  ></div>
</template>
