 <template>
    <div class="admin-layout">
      <!-- 左侧菜单 -->
      <el-aside width="250px" class="admin-aside">
        <div class="logo">
          <span>管理员后台</span>
        </div>
        <el-menu
          router
          :default-active="activeMenu"
          class="admin-menu"
          background-color="#1F2D3D"
          text-color="#BFC7D5"
          active-text-color="#ffffff"
        >
          <el-menu-item index="/admin-dashboard">
            <el-icon><House /></el-icon>
            <span>仪表盘</span>
          </el-menu-item>
          <el-menu-item index="/admin-realname-audit">
            <el-icon><UserFilled /></el-icon>
            <span>实名认证审核</span>
          </el-menu-item>
          <el-menu-item index="/admin-users">
            <el-icon><User /></el-icon>
            <span>用户管理</span>
          </el-menu-item>
          <el-menu-item index="/admin-products">
            <el-icon><ShoppingBag /></el-icon>
            <span>商品管理</span>
          </el-menu-item>
          <el-menu-item index="/admin-orders">
            <el-icon><Document /></el-icon>
            <span>订单管理</span>
          </el-menu-item>
          <el-menu-item index="/admin-device-monitor">
            <el-icon><Odometer /></el-icon>
            <span>设备监控</span>
          </el-menu-item>
        </el-menu>
      </el-aside>

      <!-- 右侧主体区域 -->
      <el-container>
        <el-header class="admin-header">
          <el-dropdown @command="handleCommand">
            <span class="admin-dropdown">
              管理员
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </el-header>

        <!-- 主体区域，显示具体的内容 -->
        <el-main class="admin-main">
          <router-view />
        </el-main>
      </el-container>
    </div>
  </template>

  <script setup>
  import { ref, computed, onMounted } from 'vue'
  import { useRoute, useRouter } from 'vue-router'
  import { ElMessage } from 'element-plus'
  import { House, UserFilled, User, ShoppingBag, Document, Odometer, ArrowDown } from '@element-plus/icons-vue'

  const router = useRouter()
  const route = useRoute()

  const userRole = ref(localStorage.getItem('user_role'))

  const activeMenu = computed(() => route.path)

  // 登出处理
  const handleCommand = (command) => {
    if (command === 'logout') {
      localStorage.removeItem('access_token')
      localStorage.removeItem('user_role')
      localStorage.removeItem('username')
      router.push('/login')
    }
  }

  onMounted(() => {
    if (userRole.value !== 'admin') {
      ElMessage.error('只有管理员可以访问此页面')
      router.push('/home')
    }
  })
  </script>

  <style scoped>
  .admin-layout {
    display: flex;
    height: 100vh;
  }

  .admin-aside {
    background-color: #2F3A4E;
    color: #fff;
  }

  .admin-header {
    background-color: #fff;
    padding: 0 20px;
    display: flex;
    justify-content: flex-end;
    align-items: center;
  }

  .admin-dropdown {
    cursor: pointer;
    padding: 5px;
    color: #409EFF;
  }

  .admin-main {
    padding: 20px;
    flex-grow: 1;
    background-color: #f5f7fa;
  }
  </style>
