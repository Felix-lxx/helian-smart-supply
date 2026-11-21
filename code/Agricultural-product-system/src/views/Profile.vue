<template>
  <div class="profile-page">
    <el-card class="profile-card">
      <template #header>
        <div class="card-header">
          <span>个人中心</span>
        </div>
      </template>

      <div class="user-profile-header">
        <div class="avatar-wrapper">
          <el-avatar :size="100" :src="userInfo.avatar || defaultAvatar" />
          <el-upload
            class="avatar-uploader"
            action="http://127.0.0.1:8000/api/user/profile/"
            :headers="authHeaders"
            :show-file-list="false"
            :on-success="handleAvatarSuccess"
            method="PATCH"
            name="avatar"
          >
            <el-button size="small" type="primary" plain>更换头像</el-button>
          </el-upload>
        </div>
        <div class="user-meta">
          <h2 class="username">{{ userInfo.username }}</h2>
          <el-tag :type="userInfo.role === 'supplier' ? 'warning' : 'success'">
            {{ roleMap[userInfo.role] }}
          </el-tag>
          <p class="motto-text">{{ userInfo.motto || '这个家伙很懒，什么都没留下...' }}</p>
        </div>
      </div>

      <el-divider />

      <el-form :model="userInfo" label-width="100px" class="profile-detail-form">
        <el-form-item label="实名状态">
          <el-tag :type="statusTag">{{ statusText }}</el-tag>
          <el-button v-if="realnameInfo.status !== 'approved'" type="primary" link @click="goRealname" class="ml-10">
            去认证/查看记录
          </el-button>
        </el-form-item>

        <el-form-item label="社交绑定">
          <div class="bind-icons">
            <el-tooltip :content="userInfo.qq_bound ? 'QQ已绑定' : '未绑定QQ'">
              <el-icon :size="28" :class="{ 'is-active': userInfo.qq_bound }" @click="handleBind('qq')">
                <ChatDotRound />
              </el-icon>
            </el-tooltip>
            <el-tooltip :content="userInfo.email_bound ? '邮箱已绑定' : '未绑定邮箱'">
              <el-icon :size="28" :class="{ 'is-active': userInfo.email_bound }" @click="handleBind('email')">
                <Message />
              </el-icon>
            </el-tooltip>
          </div>
        </el-form-item>

        <el-form-item label="个性签名">
          <el-input v-model="userInfo.motto" placeholder="用一句话介绍自己" maxlength="50" show-word-limit />
        </el-form-item>

        <el-form-item label="联系电话">
          <el-input v-model="userInfo.phone" placeholder="请输入手机号" />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="saveProfile" :loading="saving">保存个人资料</el-button>
        </el-form-item>
      </el-form>

      <div v-if="realnameInfo.reject_reason" class="reject-alert mt-20">
        <el-alert :title="'认证驳回原因：' + realnameInfo.reject_reason" type="error" :closable="false" show-icon />
      </div>
    </el-card>

    <!-- 模拟绑定弹窗 -->
    <el-dialog v-model="bindDialogVisible" :title="bindTitle" width="400px">
      <el-form label-width="80px">
        <el-form-item label="账号">
          <el-input v-model="bindAccount" placeholder="请输入账号" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="bindPassword" type="password" placeholder="请输入密码" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="bindDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmBind" :loading="binding">确认绑定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import request from '../utils/request'
import { ChatDotRound, Message } from '@element-plus/icons-vue'

const router = useRouter()
const userInfo = ref({
  username: '',
  role: '',
  phone: '',
  avatar: '',
  motto: '',
  qq_bound: false,
  email_bound: false
})
const realnameInfo = ref({ status: 'unverified', reject_reason: '' })
const saving = ref(false)
const defaultAvatar = 'https://cube.elemecdn.com/3/7c/3ea6beec64369c2642b92c6726f1epng.png'

const roleMap = { retail: '普通零售用户', wholesale: '大宗采购商', supplier: '源头供应商', admin: '管理员' }

const authHeaders = computed(() => ({
  Authorization: `Bearer ${localStorage.getItem('access_token')}`
}))

// 获取用户详细资料
const fetchProfile = async () => {
  try {
    const res = await request.get('/user/profile/')
    userInfo.value = res.data
  } catch (error) {
    ElMessage.error('获取资料失败')
  }
}

// 获取实名状态
const fetchStatus = async () => {
  try {
    const res = await request.get('/realname/status/')
    realnameInfo.value = res.data
  } catch (e) {}
}

const saveProfile = async () => {
  saving.value = true
  try {
    // 注意：原代码中 userInfo.userInfo.motto 是错误写法，修正为 userInfo.value.motto
    await request.patch('/user/profile/', {
      motto: userInfo.value.motto,
      phone: userInfo.value.phone
    })
    ElMessage.success('资料更新成功')
    fetchProfile()
  } catch (error) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

const handleAvatarSuccess = () => {
  ElMessage.success('头像上传成功')
  fetchProfile()
}

const statusText = computed(() =>
  ({ unverified: '未认证', pending: '待审核', approved: '已通过', rejected: '已驳回' }[realnameInfo.value.status] || '未知')
)
const statusTag = computed(() =>
  ({ unverified: 'info', pending: 'warning', approved: 'success', rejected: 'danger' }[realnameInfo.value.status] || 'info')
)

const goRealname = () => router.push('/realname-auth')

// ==================== 模拟绑定相关 ====================
const bindDialogVisible = ref(false)
const bindType = ref('')      // 'qq' 或 'email'
const bindAccount = ref('')
const bindPassword = ref('')
const binding = ref(false)

const bindTitle = computed(() => bindType.value === 'qq' ? '绑定QQ' : '绑定邮箱')

// 点击图标触发
const handleBind = (type) => {
  if (type === 'qq' && userInfo.value.qq_bound) {
    ElMessage.info('QQ已绑定，无需重复绑定')
    return
  }
  if (type === 'email' && userInfo.value.email_bound) {
    ElMessage.info('邮箱已绑定，无需重复绑定')
    return
  }
  bindType.value = type
  bindAccount.value = ''
  bindPassword.value = ''
  bindDialogVisible.value = true
}

// 确认绑定（模拟）
const confirmBind = () => {
  if (!bindAccount.value || !bindPassword.value) {
    ElMessage.warning('请填写完整账号和密码')
    return
  }
  binding.value = true
  // 模拟异步操作
  setTimeout(() => {
    if (bindType.value === 'qq') {
      userInfo.value.qq_bound = true
    } else if (bindType.value === 'email') {
      userInfo.value.email_bound = true
    }
    bindDialogVisible.value = false
    ElMessage.success(`${bindType.value === 'qq' ? 'QQ' : '邮箱'}绑定成功（模拟）`)
    binding.value = false
  }, 500)
}
// =====================================================

onMounted(() => {
  fetchProfile()
  fetchStatus()
})
</script>

<style scoped>
.profile-page { padding: 20px; background-color: #f5f7fa; min-height: 80vh; }
.profile-card { max-width: 800px; margin: 0 auto; border-radius: 16px; }
.user-profile-header { display: flex; align-items: center; gap: 30px; padding: 10px 0; }
.avatar-wrapper { display: flex; flex-direction: column; align-items: center; gap: 10px; }
.user-meta .username { margin: 0 0 8px 0; color: #303133; }
.motto-text { color: #909399; font-size: 14px; margin-top: 10px; font-style: italic; }
.bind-icons { display: flex; gap: 15px; align-items: center; color: #C0C4CC; }
.bind-icons .el-icon { cursor: pointer; transition: all 0.3s; }
.bind-icons .el-icon:hover { transform: scale(1.1); }
.is-active { color: #409EFF; }
.ml-10 { margin-left: 10px; }
.mt-20 { margin-top: 20px; }
</style>
