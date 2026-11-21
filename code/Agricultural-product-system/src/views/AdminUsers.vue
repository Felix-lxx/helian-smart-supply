<template>
  <div class="admin-page">
    <el-card class="page-card">
      <template #header>
        <div class="card-header">
          <span>用户权限管理</span>
          <el-button @click="fetchUsers" icon="Refresh">刷新列表</el-button>
        </div>
      </template>

      <el-table :data="users" v-loading="loading" border stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="username" label="用户名" min-width="160" />
        <el-table-column prop="role" label="角色" width="140">
          <template #default="{ row }">
            <el-tag effect="plain">{{ roleMap[row.role] || row.role }}</el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="is_active" label="账号状态" width="120">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'" effect="dark">
              {{ row.is_active ? '可用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="phone" label="手机号" min-width="160" />

        <el-table-column label="监管操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-popconfirm
              :title="row.is_active ? '确定要禁用该账号吗？' : '确定要激活该账号吗？'"
              @confirm="toggleUserStatus(row)"
            >
              <template #reference>
                <el-button
                  :type="row.is_active ? 'danger' : 'success'"
                  size="small"
                >
                  {{ row.is_active ? '禁用账号' : '激活账号' }}
                </el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'

const users = ref([])
const loading = ref(false)

const roleMap = {
  retail: '普通零售用户',
  wholesale: '大宗采购商',
  supplier: '源头供应商',
  admin: '管理员'
}

// 获取用户列表
const fetchUsers = async () => {
  loading.value = true
  try {
    const res = await request.get('/admin/users/')
    users.value = res.data
  } catch (error) {
    ElMessage.error('获取用户列表失败')
  } finally {
    loading.value = false
  }
}

// 切换用户状态
const toggleUserStatus = async (user) => {
  try {
    // 调用后端切换接口
    await request.post(`/admin/users/${user.id}/toggle-status/`)
    ElMessage.success(user.is_active ? '账号已禁用' : '账号已激活')
    fetchUsers() // 刷新列表
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

onMounted(fetchUsers)
</script>

<style scoped>
.admin-page { padding: 20px; }
.page-card { border-radius: 12px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
</style>
