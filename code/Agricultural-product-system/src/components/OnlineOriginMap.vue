<script setup>
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
const props = defineProps({
  products: { type: Array, default: () => [] },
  tileUrl: String,
  selected: Number,
  height: { type: String, default: '580px' },
  links: { type: Array, default: () => [] },
})
const emit = defineEmits(['select', 'unavailable'])
const root = ref(),
  loaded = ref(false),
  failed = ref(false)
let map, markers, routes, observer, tiles, fittedKind, fallbackTimer
function points() {
  return props.products.filter(
    (p) =>
      Array.isArray(p.coords) &&
      p.coords.length === 2 &&
      p.coords.every(Number.isFinite) &&
      Math.abs(p.coords[0]) <= 180 &&
      Math.abs(p.coords[1]) <= 85,
  )
}
function fit() {
  if (!map) return
  const list = points()
  if (list.length > 1)
    map.fitBounds(L.latLngBounds(list.map((p) => [p.coords[1], p.coords[0]])), {
      padding: [40, 40],
      maxZoom: 12,
      animate: false,
    })
  else if (list.length === 1)
    map.setView([list[0].coords[1], list[0].coords[0]], list[0].kind === 'site' ? 12 : 7, {
      animate: false,
    })
  else map.setView([34, 105], 4)
}
function draw() {
  if (!map) return
  markers.clearLayers()
  routes?.clearLayers()
  const byId = new Map(points().map((p) => [p.id, p]))
  for (const link of props.links) {
    const from = byId.get(link.source),
      to = byId.get(link.target)
    if (!from || !to) continue
    const line = L.polyline(
      [
        [from.coords[1], from.coords[0]],
        [to.coords[1], to.coords[0]],
      ],
      {
        color: link.status === 'issue' ? '#dd9b45' : '#3f83d4',
        weight: 2,
        opacity: 0.6,
        dashArray: '6 8',
      },
    )
    const tip = document.createElement('span')
    tip.textContent = (link.label || '履约关联') + '；关联示意，非道路路线或车辆位置'
    line.bindTooltip(tip)
    line.addTo(routes)
  }
  for (const p of points()) {
    const selected = p.id === props.selected
    const ll = [p.coords[1], p.coords[0]]
    let marker
    if (p.kind === 'site') {
      marker = L.marker(ll, {
        icon: L.divIcon({
          className: 'business-site-marker' + (selected ? ' selected' : ''),
          html: '<span></span>',
          iconSize: [18, 18],
          iconAnchor: [9, 9],
        }),
        keyboard: true,
        title: p.name,
      })
    } else
      marker = L.circleMarker(ll, {
        radius: selected ? 10 : 7,
        color: '#fff',
        weight: 2,
        fillColor: selected ? '#b87921' : '#176e51',
        fillOpacity: 0.95,
      })
    const content = document.createElement('div')
    const title = document.createElement('strong')
    title.textContent = p.name
    content.appendChild(title)
    const info = document.createElement('p')
    info.textContent = p.origin || '位置来自业务资料'
    info.style.cssText = 'margin:7px 0;line-height:1.7'
    content.appendChild(info)
    const note = document.createElement('small')
    note.textContent =
      p.kind === 'site'
        ? '业务站点，非实时运输位置'
        : `${p.unit === '项货源' ? '关联' : '可售'} ${p.stock || 0} ${p.unit || ''}`
    content.appendChild(note)
    marker.bindTooltip(content, { direction: 'top' })
    marker.on('click', () => emit('select', p.id))
    marker.addTo(markers)
  }
}
onMounted(async () => {
  await nextTick()
  if (!root.value) return
  map = L.map(root.value, {
    minZoom: 3,
    maxZoom: 18,
    zoomControl: false,
    attributionControl: false,
    preferCanvas: true,
    zoomAnimation: false,
    fadeAnimation: false,
    markerZoomAnimation: false,
  }).setView([34, 105], 4)
  L.control
    .zoom({ position: 'topright', zoomInTitle: '放大地图', zoomOutTitle: '缩小地图' })
    .addTo(map)
  L.control.scale({ imperial: false, position: 'bottomleft' }).addTo(map)
  L.control
    .attribution({ prefix: false })
    .addAttribution(
      '底图 © <a href="https://www.tianditu.gov.cn/" target="_blank" rel="noopener noreferrer">天地图</a>',
    )
    .addTo(map)
  routes = L.layerGroup().addTo(map)
  markers = L.layerGroup().addTo(map)
  for (const layer of ['vec', 'cva']) {
    const t = L.tileLayer(props.tileUrl.replace('{layer}', layer), {
      maxZoom: 18,
      minZoom: 3,
      keepBuffer: 1,
      updateWhenIdle: true,
    })
    t.on('tileload', () => (loaded.value = true))
    t.on('tileerror', () => {
      failed.value = true
    })
    t.addTo(map)
    if (layer === 'vec') tiles = t
  }
  draw()
  fit()
  fallbackTimer = setTimeout(() => {
    if (!loaded.value) emit('unavailable')
  }, 7000)
  fittedKind = points()
    .map((p) => `${p.id}:${p.coords}`)
    .join('|')
  observer = new ResizeObserver(() => map?.invalidateSize({ pan: false }))
  observer.observe(root.value)
})
watch(
  () => props.links,
  () => draw(),
  { deep: true },
)
watch(
  () => props.products,
  () => {
    draw()
    const kind = points()
      .map((p) => `${p.id}:${p.coords}`)
      .join('|')
    if (map && points().length && kind !== fittedKind) {
      fittedKind = kind
      fit()
    }
  },
  { deep: true },
)
watch(
  () => props.selected,
  (id) => {
    draw()
    const p = points().find((x) => x.id === id)
    if (p) map?.panTo([p.coords[1], p.coords[0]], { animate: false })
  },
)
onBeforeUnmount(() => {
  clearTimeout(fallbackTimer)
  observer?.disconnect()
  map?.remove()
  map = null
})
</script>
<template>
  <div class="online-map-wrap" :style="{ height }">
    <div
      ref="root"
      class="online-map"
      role="region"
      aria-label="天地图业务位置地图，可缩放、拖动并选择点位"
    ></div>
    <button class="map-fit-button" @click="fit">显示全部业务点</button>
    <div v-if="!loaded && !failed" class="map-load-status">正在加载天地图底图…</div>
    <div v-if="failed" class="map-load-status warning">
      部分底图暂不可用 <button @click="emit('unavailable')">使用离线概览</button>
    </div>
  </div>
</template>
<style>
.online-map-wrap {
  position: relative;
  width: 100%;
  background: #e8eeea;
}
.online-map {
  height: 100%;
  width: 100%;
  z-index: 0;
  font-family: inherit;
}
.map-fit-button {
  position: absolute;
  top: 14px;
  left: 14px;
  z-index: 500;
  background: #fff;
  color: #245941;
  border: 1px solid #cad8cf;
  border-radius: 6px;
  padding: 8px 12px;
  font-size: 12px;
  box-shadow: 0 2px 8px #17382a12;
}
.map-load-status {
  position: absolute;
  bottom: 28px;
  left: 14px;
  right: 14px;
  z-index: 500;
  background: #fffffff0;
  border-radius: 6px;
  padding: 10px 12px;
  color: #37584a;
  font-size: 12px;
}
.map-load-status.warning {
  color: #855c26;
  background: #fffaed;
}
.map-load-status button {
  border: 0;
  background: none;
  color: #22674e;
  text-decoration: underline;
  margin-left: 10px;
}
.business-site-marker {
  background: transparent;
  border: 0;
}
.business-site-marker span {
  display: block;
  width: 15px;
  height: 15px;
  background: #206b50;
  border: 2px solid white;
  border-radius: 3px;
  box-shadow: 0 2px 6px #173c3260;
}
.business-site-marker.selected span {
  background: #b87921;
}
.leaflet-tooltip {
  font-family: inherit;
  font-size: 12px;
  border: 1px solid #d7e2da;
  border-radius: 7px;
  padding: 12px 14px;
  box-shadow: 0 4px 16px #163c2818;
}
.leaflet-control-attribution {
  font-size: 10px !important;
  padding: 3px 7px !important;
}
.leaflet-control-scale-line {
  font-size: 10px !important;
}
</style>
