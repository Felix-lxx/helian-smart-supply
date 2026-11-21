<script setup>
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
const props = defineProps({ option: Object, height: { type: String, default: '300px' } })
const emit = defineEmits(['select'])
const root = ref()
let chart, observer
const draw = () => {
  if (chart && props.option) chart.setOption(props.option, true)
}
onMounted(async () => {
  await nextTick()
  chart = echarts.init(root.value)
  chart.on('click', (event) => emit('select', event.data))
  draw()
  observer = new ResizeObserver(() => chart?.resize())
  observer.observe(root.value)
})
watch(() => props.option, draw, { deep: true })
onBeforeUnmount(() => {
  observer?.disconnect()
  chart?.dispose()
})
</script>
<template>
  <div ref="root" :style="{ height, width: '100%' }" role="img" aria-label="业务数据图表"></div>
</template>
