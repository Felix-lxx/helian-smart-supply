import { ref, onMounted, onBeforeUnmount } from 'vue'

export function useBusinessFeed(load, interval = 20000) {
  const busy = ref(false),
    error = ref(''),
    updated = ref(null)
  let pending = false,
    timer
  async function refresh(silent = false) {
    if (pending) return
    pending = true
    if (!silent) busy.value = true
    try {
      await load()
      error.value = ''
      updated.value = new Date()
    } catch (e) {
      error.value = e.response?.data?.detail || '数据暂时无法同步，请重试'
    } finally {
      pending = false
      busy.value = false
    }
  }
  const changed = () => refresh(true)
  onMounted(() => {
    refresh()
    timer = setInterval(() => {
      if (!document.hidden) refresh(true)
    }, interval)
    window.addEventListener('hl-business-change', changed)
  })
  onBeforeUnmount(() => {
    clearInterval(timer)
    window.removeEventListener('hl-business-change', changed)
  })
  return { busy, error, updated, refresh }
}
