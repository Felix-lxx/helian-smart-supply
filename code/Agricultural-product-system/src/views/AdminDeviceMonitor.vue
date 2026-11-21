<template>
  <div class="admin-page">
    <el-card class="page-card">
      <template #header>
        <div class="card-header">
          <span>边缘节点设备监控</span>
          <div>
            <el-button @click="fetchDeviceStatus">手动拉取</el-button>
            <el-button :type="autoRefresh ? 'success' : 'info'" @click="toggleAutoRefresh">
              {{ autoRefresh ? '3秒高频轮询中 (自动)' : '已暂停轮询' }}
            </el-button>
          </div>
        </div>
      </template>

      <div v-if="deviceStatus.status === 'offline'" class="offline-placeholder">
        <el-empty description="边缘计算节点已离线 / 信号闪断" :image-size="180">
          <template #image>
            <el-icon :size="100" color="#F56C6C" class="offline-icon"><WarningFilled /></el-icon>
          </template>
          <div class="offline-tips">
            <p>由于产地恶劣气象或物理断电，未捕获到 RDK X5 节点的心跳上报。</p>
            <p>系统已启用自修复倒计时，正在等待设备网络重连...</p>
          </div>
        </el-empty>
      </div>

      <el-row :gutter="20" v-else>
        <el-col :span="8">
          <el-card shadow="hover" class="stat-card">
            <div class="stat-title">NPU 瞬时负载</div>
            <div class="stat-value text-primary">
              {{ deviceStatus.npu_load || 0 }} <span class="unit">%</span>
            </div>
            <div class="stat-wave" :style="{ width: (deviceStatus.npu_load || 0) + '%' }"></div>
          </el-card>
        </el-col>

        <el-col :span="8">
          <el-card shadow="hover" class="stat-card">
            <div class="stat-title">YOLOv5 推理延迟</div>
            <div class="stat-value text-warning">
              {{ deviceStatus.yolo_delay || 0 }} <span class="unit">ms</span>
            </div>
          </el-card>
        </el-col>

        <el-col :span="8">
          <el-card shadow="hover" class="stat-card">
            <div class="stat-title">实时异常告警短语</div>
            <div class="stat-value" :class="deviceStatus.warning_msg === 'Normal' ? 'text-success' : 'text-danger'">
              {{ deviceStatus.warning_msg === 'Normal' ? '暂无异常' : deviceStatus.warning_msg }}
            </div>
          </el-card>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { WarningFilled } from '@element-plus/icons-vue'
import request from '@/utils/request'

const deviceStatus = ref({
  npu_load: 0,
  yolo_delay: 0,
  warning_msg: 'Normal',
  status: 'offline' // 默认设为离线，等待第一次请求成功更新
})

const autoRefresh = ref(true)
let timer = null

// 获取设备状态
const fetchDeviceStatus = async () => {
  try {
    const res = await request.get('/device/report/')
    deviceStatus.value = res.data
  } catch (error) {
    // 核心容错处理：接口异常直接降级为离线状态并触发占位图
    deviceStatus.value.status = 'offline'
    console.warn('捕获到边缘设备网络闪断异常')
  }
}

// 自动刷新开关
const toggleAutoRefresh = () => {
  autoRefresh.value = !autoRefresh.value
  if (autoRefresh.value) {
    timer = setInterval(fetchDeviceStatus, 3000)
    ElMessage.success('已开启 3 秒高频轮询')
  } else {
    clearInterval(timer)
    timer = null
    ElMessage.info('已暂停自动刷新')
  }
}

onMounted(() => {
  // 首次主动拉取
  fetchDeviceStatus()
  // 组件挂载即强制启动3秒轮询
  timer = setInterval(fetchDeviceStatus, 3000)
})

onBeforeUnmount(() => {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
})
</script>

<style scoped>
.admin-page {
  padding: 20px;
}
.page-card {
  border-radius: 18px;
  min-height: 400px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: bold;
  font-size: 18px;
}

.stat-card {
  text-align: center;
  padding: 20px 0;
  border-radius: 12px;
  position: relative;
  overflow: hidden;
}
.stat-title {
  font-size: 14px;
  color: #909399;
  margin-bottom: 15px;
}
.stat-value {
  font-size: 36px;
  font-weight: bold;
}
.unit {
  font-size: 16px;
  color: #606266;
  font-weight: normal;
}
.text-primary { color: #409EFF; }
.text-warning { color: #E6A23C; }
.text-success { color: #67C23A; }
.text-danger { color: #F56C6C; animation: blink 1s infinite; }

@keyframes blink {
  0% { opacity: 1; }
  50% { opacity: 0.5; }
  100% { opacity: 1; }
}

/* NPU 负载波形演示条 */
.stat-wave {
  position: absolute;
  bottom: 0;
  left: 0;
  height: 6px;
  background: linear-gradient(90deg, #409EFF, #64ffda);
  transition: width 0.5s ease-in-out;
}

/* 离线占位图样式 */
.offline-placeholder {
  padding: 40px 0;
  animation: fadeIn 0.5s ease;
}
.offline-icon {
  animation: pulse 2s infinite;
}
.offline-tips {
  margin-top: 15px;
  color: #909399;
  font-size: 14px;
  line-height: 1.8;
}

@keyframes pulse {
  0% { transform: scale(1); opacity: 0.8; }
  50% { transform: scale(1.1); opacity: 1; }
  100% { transform: scale(1); opacity: 0.8; }
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
