<template>
    <div class="admin-dashboard">
      <el-row :gutter="20">
        <el-col :span="6">
          <el-card class="stat-card" shadow="hover">
            <div class="card-title">总订单数</div>
            <div class="card-value">{{ totalOrders }}</div>
          </el-card>
        </el-col>

        <el-col :span="6">
          <el-card class="stat-card" shadow="hover">
            <div class="card-title">总用户数</div>
            <div class="card-value">{{ totalUsers }}</div>
          </el-card>
        </el-col>

        <el-col :span="6">
          <el-card class="stat-card" shadow="hover">
            <div class="card-title">总商品数</div>
            <div class="card-value">{{ totalProducts }}</div>
          </el-card>
        </el-col>

        <el-col :span="6">
          <el-card class="stat-card" shadow="hover">
            <div class="card-title">设备在线数</div>
            <div class="card-value">{{ deviceCount }}</div>
          </el-card>
        </el-col>
      </el-row>
    </div>
  </template>

  <script setup>
  import { ref, onMounted, onBeforeUnmount } from 'vue'
  import request from '@/utils/request'

  // 定义定时器变量
  let timer = null

  const totalOrders = ref(0)
  const totalUsers = ref(0)
  const totalProducts = ref(0)
  const deviceCount = ref(0)

  const getStats = async () => {
  try {
    const res = await request.get('/sys/stats/') // 确保路径是 /sys/stats/
    totalOrders.value = res.data.total_orders
    totalUsers.value = res.data.total_users
    totalProducts.value = res.data.total_products
    deviceCount.value = res.data.device_count
    } catch (error) {
      console.error('获取统计数据失败', error)
    }
  }

  onMounted(() => {
    getStats()
    // 开启轮询：每 5 秒刷新一次数据，增强演示动态感
    timer = setInterval(() => {
      getStats()
    }, 5000)
  })

  onBeforeUnmount(() => {
  // 页面销毁前必须清除定时器，防止内存泄漏
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  })
  </script>

  <style scoped>
  .admin-dashboard {
    display: flex;
    flex-wrap: wrap;
    gap: 20px;
  }

  .stat-card {
    text-align: center;
  }

  .card-title {
    font-size: 18px;
    color: #409eff;
  }

  .card-value {
    font-size: 30px;
    font-weight: bold;
    color: #2c3e50;
  }
  </style>
