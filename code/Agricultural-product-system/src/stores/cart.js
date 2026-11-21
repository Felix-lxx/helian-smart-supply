import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useCartStore = defineStore('cart', () => {
  const items = ref([])   // 定义购物车数组

  // 计算购物车总数
  const totalCount = computed(() => items.value.reduce((sum, i) => sum + i.quantity, 0))
  // 计算总价（单价 × 数量，保留两位小数）
  const totalPrice = computed(() => {
    return items.value.reduce((sum, i) => sum + i.retail_price * i.quantity, 0).toFixed(2)
  })

  // 加入购物车逻辑
  function addToCart(product) {
    const existing = items.value.find(i => i.id === product.id)
    if (existing) {
      existing.quantity++
    } else {
      items.value.push({
        id: product.id,
        name: product.name,
        retail_price: product.retail_price,
        image_url: product.image_url,
        origin: product.origin,
        quantity: 1
      })
    }
  }

  // 清空购物车
  function clearCart() { items.value = [] }

  return { items, totalCount, totalPrice, addToCart, clearCart }
})
