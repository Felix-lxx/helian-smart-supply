<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useWorkspace, labels, dateText } from '@/stores/workspace'
import AiAssistant from '@/components/AiAssistant.vue'
const w = useWorkspace(),
  route = useRoute(),
  router = useRouter(),
  collapsed = ref(false),
  notifications = ref(false)
let timer
const nav = computed(() => [
  {
    title: '业务工作区',
    items: [
      ['/home', '工作台', 'House'],
      ['/products', '货源市场', 'Shop'],
      ['/procurement', '用途采购', 'ScaleToOriginal'],
      ['/demands', w.isBuyer ? '我的采购需求' : '需求商机', 'Document'],
      ['/orders', w.isBuyer ? '我的采购订单' : '订单履约', 'Box'],
      ['/workboard', w.isBuyer ? '到货与验收' : '交付作业', 'Van'],
      ['/recovery', '异常补配', 'RefreshRight'],
    ],
  },
  ...(!w.isBuyer
    ? [
        {
          title: '供给与决策',
          items: [
            ['/supply', '商品与批次', 'Goods'],
            ['/allocation', '分货实验室', 'Connection'],
            ['/quality', '品质工作台', 'CircleCheck'],
            ['/reviews', '复检任务', 'Aim'],
          ],
        },
      ]
    : []),
  {
    title: '网络与运营',
    items: [
      ['/origins', '产地网络', 'Location'],
      ['/companies', '企业与站点', 'OfficeBuilding'],
      ...(w.isAdmin
        ? [
            ['/operations', '运营中心', 'Operation'],
            ['/devices', '设备接入', 'Monitor'],
          ]
        : []),
    ],
  },
])
onMounted(() => {
  w.refresh()
  timer = setInterval(() => {
    if (!document.hidden) w.refresh(true)
  }, 20000)
})
onBeforeUnmount(() => clearInterval(timer))
</script>
<template>
  <div class="app-shell" :class="{ collapsed }">
    <aside class="sidebar">
      <router-link to="/home" class="brand"
        ><span class="brand-mark"
          ><el-icon><Connection /></el-icon></span
        ><span class="brand-words">禾链智配<small>农产品协同工作空间</small></span></router-link
      >
      <div class="workspace-id">
        <span class="workspace-avatar">{{ w.state.user.username?.[0]?.toUpperCase() || 'H' }}</span>
        <div>
          <b>{{ labels[w.role] }}工作区</b><small>{{ w.state.user.username }}</small>
        </div>
        <el-icon><OfficeBuilding /></el-icon>
      </div>
      <nav>
        <div v-for="group in nav" :key="group.title" class="nav-group">
          <span class="nav-caption">{{ group.title }}</span
          ><router-link
            v-for="[path, title, icon] in group.items"
            :key="path"
            :to="path"
            class="nav-item"
            :class="{ active: route.path === path }"
            ><el-icon><component :is="icon" /></el-icon><span>{{ title }}</span
            ><span v-if="path === '/orders' && w.state.stats.issues" class="nav-count">{{
              w.state.stats.issues
            }}</span></router-link
          >
        </div>
      </nav>
      <div class="sidebar-bottom">
        <div class="connection-status">
          <i></i><span>{{ w.error ? '同步暂不可用' : '工作空间已连接' }}</span>
        </div>
        <router-link to="/profile" class="nav-item"
          ><el-icon><Setting /></el-icon><span>账户与设置</span></router-link
        ><button class="nav-item logout" @click="w.logout">
          <el-icon><SwitchButton /></el-icon><span>退出当前账号</span>
        </button>
      </div>
    </aside>
    <div class="workspace-main">
      <header class="topbar">
        <div class="top-left">
          <button class="icon-button" aria-label="折叠菜单" @click="collapsed = !collapsed">
            <el-icon><Fold /></el-icon></button
          ><span class="breadcrumb"
            >工作空间 <span>/</span> <b>{{ route.meta.title }}</b></span
          >
        </div>
        <div class="top-right">
          <span class="sync-text">{{
            w.lastSync ? '更新于 ' + dateText(w.lastSync) : '连接中'
          }}</span
          ><router-link v-if="w.isBuyer" to="/cart" class="cart-link"
            ><el-icon><ShoppingCart /></el-icon><span>采购清单</span
            ><b>{{ w.cart.length }}</b></router-link
          ><AiAssistant /><el-badge :value="w.unread" :hidden="!w.unread"
            ><button class="icon-button" aria-label="消息中心" @click="notifications = true">
              <el-icon><Bell /></el-icon></button></el-badge
          ><router-link to="/profile" class="user-avatar">{{
            w.state.user.username?.slice(0, 1)?.toUpperCase()
          }}</router-link>
        </div>
      </header>
      <div v-if="w.error" class="sync-error">
        {{ w.error }} <el-button link @click="w.refresh()">重新同步</el-button>
      </div>
      <main class="workspace-content"><router-view /></main>
      <footer class="workspace-footer">
        <span>禾链智配 · 让每一批货，找到合适的订单</span
        ><span>标记“演示”的货源、检测与交易仅用于体验</span>
      </footer>
    </div>
    <el-drawer v-model="notifications" title="消息与业务待办" size="400px"
      ><el-button
        v-if="w.unread"
        link
        type="primary"
        @click="w.act('notifications/', {}, '已标记已读')"
        >全部已读</el-button
      >
      <div
        v-for="n in w.state.notifications"
        :key="n.id"
        class="message-row"
        @click="
          () => {
            router.push(n.route)
            notifications = false
          }
        "
      >
        <strong>{{ n.title }}</strong>
        <p>{{ n.content }}</p>
        <small>{{ dateText(n.created_at) }}</small
        ><i v-if="!n.read"></i>
      </div>
      <el-empty v-if="!w.state.notifications.length" description="暂无消息，业务变化会显示在这里"
    /></el-drawer>
  </div>
</template>
<style scoped>
.app-shell {
  display: flex;
  min-height: 100vh;
}
.sidebar {
  width: 238px;
  background: #172a25;
  color: #b7c8bf;
  position: fixed;
  inset: 0 auto 0 0;
  z-index: 60;
  display: flex;
  flex-direction: column;
  transition: width 0.2s;
}
.brand {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 29px 24px 26px;
  color: #fff;
}
.brand-mark {
  width: 35px;
  height: 35px;
  background: #c6e9b1;
  color: #183b2c;
  border-radius: 9px;
  display: grid;
  place-items: center;
  font-size: 23px;
}
.brand-words {
  font-size: 20px;
  font-weight: 650;
  white-space: nowrap;
  letter-spacing: 1px;
}
.brand-words small {
  display: block;
  font-size: 10px;
  color: #a6bfb0;
  font-weight: 400;
  letter-spacing: 1px;
  margin-top: 5px;
}
.workspace-id {
  margin: 0 15px 21px;
  border: 1px solid #3b4d43;
  border-radius: 8px;
  padding: 11px;
  display: flex;
  gap: 10px;
  align-items: center;
}
.workspace-id div {
  flex: 1;
}
.workspace-id b {
  display: block;
  color: #e6eee8;
  font-size: 12px;
  font-weight: 500;
}
.workspace-id small {
  font-size: 10px;
  display: block;
  margin-top: 4px;
}
.workspace-avatar {
  height: 30px;
  width: 30px;
  background: #344a3d;
  color: #d8e7d9;
  border-radius: 6px;
  display: grid;
  place-items: center;
}
.nav-group {
  margin-bottom: 21px;
}
.nav-caption {
  display: block;
  font-size: 10px;
  color: #91a89b;
  padding: 0 26px 10px;
  letter-spacing: 0.5px;
}
.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13px;
  margin: 3px 13px;
  padding: 11px 14px;
  border-radius: 6px;
  transition: background 0.15s;
}
.nav-item > .el-icon {
  font-size: 17px;
}
.nav-item:hover {
  background: #263e32;
  color: white;
}
.nav-item.active {
  background: #c9e8b5;
  color: #1d3929;
  font-weight: 600;
}
.nav-count {
  margin-left: auto;
  font-size: 11px;
}
.sidebar nav {
  overflow: auto;
}
.sidebar-bottom {
  margin-top: auto;
  padding: 18px 0 16px;
}
.connection-status {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 0 26px 17px;
  font-size: 10px;
  color: #a7bcae;
}
.connection-status i {
  background: #9ed393;
  width: 5px;
  height: 5px;
  border-radius: 50%;
}
.logout {
  border: 0;
  background: transparent;
  color: inherit;
  width: calc(100% - 26px);
}
.workspace-main {
  margin-left: 238px;
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  transition: margin 0.2s;
}
.topbar {
  height: 68px;
  position: sticky;
  top: 0;
  background: #ffffffed;
  z-index: 40;
  border-bottom: 1px solid var(--line);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 32px;
  gap: 16px;
}
.top-left,
.top-right {
  display: flex;
  align-items: center;
  gap: 22px;
}
.icon-button {
  height: 32px;
  width: 32px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: #55685c;
  display: grid;
  place-items: center;
  font-size: 19px;
}
.icon-button:hover {
  background: #edf3ef;
}
.breadcrumb {
  font-size: 12px;
  color: #7a897f;
}
.breadcrumb span {
  margin: 0 16px;
  color: #c0cbc4;
}
.breadcrumb b {
  color: #263c30;
  font-weight: 500;
}
.sync-text {
  font-size: 10px;
  color: #74847a;
}
.cart-link {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 12px;
}
.cart-link b {
  background: #e7eee8;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 10px;
}
.user-avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: #ede4d3;
  color: #6b5838;
  display: grid;
  place-items: center;
  font-size: 12px;
}
.workspace-content {
  flex: 1;
}
.workspace-footer {
  padding: 15px 34px;
  display: flex;
  justify-content: space-between;
  color: #7d8b82;
  font-size: 10px;
  border-top: 1px solid var(--line);
  gap: 15px;
}
.message-row {
  padding: 20px 2px;
  border-bottom: 1px solid var(--line);
  cursor: pointer;
  position: relative;
}
.message-row strong {
  font-size: 13px;
  font-weight: 500;
}
.message-row p,
.message-row small {
  color: var(--muted);
  font-size: 12px;
  line-height: 1.8;
  margin-top: 7px;
}
.message-row i {
  position: absolute;
  right: 0;
  top: 23px;
  width: 6px;
  height: 6px;
  background: var(--brand);
  border-radius: 50%;
}
.sync-error {
  padding: 10px 30px;
  background: #fff0de;
  color: #8d602c;
  font-size: 13px;
}
.collapsed .sidebar {
  width: 76px;
}
.collapsed .workspace-main {
  margin-left: 76px;
}
.collapsed .brand {
  padding: 27px 20px;
}
.collapsed .brand-words,
.collapsed .workspace-id,
.collapsed .nav-caption,
.collapsed .nav-item span,
.collapsed .connection-status {
  display: none;
}
.collapsed .nav-item {
  justify-content: center;
  padding: 13px;
}
.collapsed .nav-group {
  margin-bottom: 10px;
}
@media (max-width: 1000px) {
  .sidebar {
    width: 76px;
  }
  .workspace-main {
    margin-left: 76px;
  }
  .brand {
    padding: 27px 20px;
  }
  .brand-words,
  .workspace-id,
  .nav-caption,
  .nav-item span,
  .connection-status {
    display: none;
  }
  .nav-item {
    justify-content: center;
    padding: 13px;
  }
  .nav-group {
    margin-bottom: 10px;
  }
  .topbar {
    padding: 0 20px;
  }
  .sync-text {
    display: none;
  }
}
@media (max-width: 600px) {
  .sidebar {
    width: 58px;
  }
  .workspace-main {
    margin-left: 58px;
  }
  .brand {
    padding: 23px 12px;
  }
  .brand-mark {
    width: 32px;
    height: 32px;
  }
  .nav-item {
    margin: 3px 7px;
    padding: 11px 6px;
  }
  .topbar {
    padding: 0 12px;
    height: 58px;
  }
  .top-left,
  .top-right {
    gap: 8px;
  }
  .breadcrumb {
    font-size: 11px;
  }
  .breadcrumb span {
    margin: 0 6px;
  }
  .cart-link span {
    display: none;
  }
  .workspace-footer {
    padding: 15px;
    flex-direction: column;
  }
  .sidebar-bottom {
    padding-bottom: 8px;
  }
}
</style>
