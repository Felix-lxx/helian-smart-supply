<template>
  <div class="audit-page">
    <el-card class="audit-card">
      <template #header>
        <div class="card-header">
          <span>实名认证审核</span>
          <el-button @click="fetchPendingList" icon="Refresh">刷新列表</el-button>
        </div>
      </template>

      <el-table :data="records" v-loading="loading" border stripe>
        <el-table-column prop="username" label="用户名" width="140" />
        <el-table-column prop="real_name" label="真实姓名" width="140" />
        <el-table-column prop="id_card_masked" label="身份证号" min-width="180" />

        <el-table-column label="人脸照片" min-width="120">
          <template #default="{ row }">
            <el-image
              v-if="row.face_image_url"
              style="width: 60px; height: 60px; border-radius: 4px; cursor: pointer"
              :src="row.face_image_url"
              :preview-src-list="[row.face_image_url]"
              preview-teleported
              fit="cover"
            >
              <template #error>
                <div class="image-slot">加载失败</div>
              </template>
            </el-image>
            <span v-else style="color: #909399">未提供</span>
          </template>
        </el-table-column>

        <el-table-column prop="submitted_at" label="提交时间" min-width="180">
          <template #default="{ row }">
            {{ formatDate(row.submitted_at) }}
          </template>
        </el-table-column>

        <el-table-column label="操作" min-width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="success" size="small" @click="approveRecord(row)">
              通过
            </el-button>
            <el-button type="danger" size="small" @click="openRejectDialog(row)">
              驳回
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="!loading && records.length === 0" class="empty-tip">
        暂无待审核实名认证记录
      </div>
    </el-card>

    <el-dialog v-model="rejectDialogVisible" title="驳回实名认证" width="500px">
      <el-form label-width="90px">
        <el-form-item label="用户名">
          <span style="font-weight: bold">{{ currentRecord?.username }}</span>
        </el-form-item>
        <el-form-item label="驳回原因">
          <el-input
            v-model="rejectReason"
            type="textarea"
            :rows="4"
            placeholder="请详细说明驳回原因，例如：照片模糊、信息不符等"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="rejectDialogVisible = false">取消</el-button>
        <el-button type="danger" :loading="rejecting" @click="confirmReject">
          确认驳回
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'

const router = useRouter()
const loading = ref(false)
const rejecting = ref(false)
const records = ref([])

const rejectDialogVisible = ref(false)
const currentRecord = ref(null)
const rejectReason = ref('')

// 🚀 定时器变量
let timer = null

// 权限检查逻辑
const checkRole = () => {
  const role = localStorage.getItem('user_role')
  if (role !== 'admin') {
    ElMessage.error('只有管理员可以访问实名认证审核页面')
    router.replace('/home')
  }
}

// 时间格式化
const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return isNaN(date.getTime()) ? dateStr : date.toLocaleString()
}

// 获取待审核列表
const fetchPendingList = async () => {
  // 仅在手动刷新时显示全屏 loading，静默轮询时不显示以提升体验
  if (records.value.length === 0) loading.value = true
  try {
    const res = await request.get('/admin/realname/pending/')
    records.value = res.data
  } catch (error) {
    console.error('获取列表失败', error)
  } finally {
    loading.value = false
  }
}

// 审核通过逻辑
const approveRecord = async (row) => {
  try {
    await request.post(`/admin/realname/${row.id}/approve/`)
    ElMessage.success(`用户 ${row.username} 已通过实名认证`)
    fetchPendingList()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '审核操作失败')
  }
}

const openRejectDialog = (row) => {
  currentRecord.value = row
  rejectReason.value = ''
  rejectDialogVisible.value = true
}

// 审核驳回逻辑
const confirmReject = async () => {
  if (!currentRecord.value) return
  rejecting.value = true
  try {
    await request.post(`/admin/realname/${currentRecord.value.id}/reject/`, {
      reason: rejectReason.value || '资料不符合要求'
    })
    ElMessage.success('已驳回该申请')
    rejectDialogVisible.value = false
    fetchPendingList()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '驳回操作失败')
  } finally {
    rejecting.value = false
  }
}

onMounted(() => {
  checkRole()
  fetchPendingList()
  // 开启轮询：每 10 秒自动同步一次最新审核数据 [cite: 13, 15]
  timer = setInterval(fetchPendingList, 10000)
})

onBeforeUnmount(() => {
  // 销毁页面时必须清除定时器
  if (timer) {
    clearInterval(timer)
    timer = null
  }
})
</script>

<script>
// 为了匹配图标组件
import { Refresh } from '@element-plus/icons-vue'
export default {
  components: { Refresh }
}
</script>

<style scoped>
.audit-page { padding: 20px; }
.audit-card { border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
.card-header { display: flex; justify-content: space-between; align-items: center; font-size: 18px; font-weight: bold; }
.image-slot { display: flex; justify-content: center; align-items: center; width: 100%; height: 100%; background: #f5f7fa; color: #909399; font-size: 12px; }
.empty-tip { margin-top: 30px; text-align: center; color: #909399; padding-bottom: 20px; }
</style>
