<script setup>
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useWorkspace, dateText } from '@/stores/workspace'
import AiAssistant from '@/components/AiAssistant.vue'
const w = useWorkspace(),
  route = useRoute(),
  router = useRouter()
const mobileOpen = ref(false),
  collapsed = ref(false),
  inbox = ref(false),
  expanded = ref(null)
const wall = computed(() => route.meta.wall)
const roleName = computed(() =>
  w.isBuyer ? '采购工作区' : w.isAdmin ? '运营工作区' : '供应工作区',
)
const nav = computed(() => [
  {
    title: '工作区',
    icon: 'Grid',
    direct: true,
    items: [
      ['/home', '工作台', 'Grid'],
      ['/control', '履约调度', 'DataBoard'],
    ],
  },
  ...(w.isBuyer
    ? [
        {
          title: '采购',
          icon: 'ShoppingBag',
          items: [
            ['/purchase-plans', '门店集采', 'Tickets'],
            ['/products', '货源市场', 'Shop'],
            ['/procurement', '用途采购', 'ScaleToOriginal'],
            ['/demands', '需求与报价', 'Document'],
          ],
        },
      ]
    : []),
  {
    title: '交易与履约',
    icon: 'Box',
    items: [
      ['/orders', '订单履约', 'Box'],
      ['/workboard', w.isBuyer ? '到货验收' : '现场作业', 'Van'],
      ['/recovery', '异常补配', 'Switch'],
      ['/accounts', '对账中心', 'Wallet'],
    ],
  },
  ...(!w.isBuyer
    ? [
        {
          title: '供给与品质',
          icon: 'Goods',
          items: [
            ['/products', '货源市场', 'Shop'],
            ['/supply', '商品与批次', 'Goods'],
            ['/grading', '分级与称重', 'SetUp'],
            ['/allocation', '供货排程', 'Connection'],
            ['/quality', '品质工作台', 'CircleCheck'],
            ['/reviews', '复检任务', 'Aim'],
            ['/demands', '需求商机', 'Document'],
            ['/procurement', '用途比较', 'ScaleToOriginal'],
          ],
        },
      ]
    : []),
  {
    title: '业务网络',
    icon: 'OfficeBuilding',
    items: [
      ['/origins', '产地与站点', 'Location'],
      ['/companies', '企业与岗位', 'OfficeBuilding'],
      ...(w.isAdmin
        ? [
            ['/operations', '经营分析', 'TrendCharts'],
            ['/devices', '设备采集', 'Monitor'],
          ]
        : []),
    ],
  },
])
const currentGroup = computed(
  () => nav.value.find((g) => g.items.some((x) => x[0] === route.path))?.title,
)
function isOpen(group) {
  return (
    !collapsed.value &&
    (expanded.value === group.title ||
      (expanded.value === null && currentGroup.value === group.title))
  )
}
function toggleGroup(group) {
  if (collapsed.value) collapsed.value = false
  expanded.value = isOpen(group) ? '' : group.title
}
function navigate(path) {
  router.push(path)
  mobileOpen.value = false
}
function openNotice(n) {
  navigate(n.route)
  inbox.value = false
}
watch(
  () => route.path,
  () => {
    if (!nav.value.find((g) => g.title === expanded.value)?.items.some((x) => x[0] === route.path))
      expanded.value = null
    mobileOpen.value = false
  },
)
let timer
onMounted(() => {
  w.refresh()
  timer = setInterval(() => {
    if (!document.hidden) w.refresh(true)
  }, 20000)
})
onBeforeUnmount(() => clearInterval(timer))
</script>
<template>
  <div class="hl-shell" :class="{ 'is-collapsed': collapsed, 'is-wall': wall }">
    <button
      v-if="mobileOpen && !wall"
      class="nav-scrim"
      aria-label="关闭导航"
      @click="mobileOpen = false"
    />
    <aside v-if="!wall" class="hl-sidebar" :class="{ 'mobile-open': mobileOpen }">
      <router-link to="/home" class="hl-brand"
        ><span class="hl-logo"
          ><el-icon><Connection /></el-icon
        ></span>
        <div><b>禾链智配</b><small>集采与履约协同</small></div></router-link
      >
      <div class="hl-space">
        <span>{{ roleName }}</span
        ><small>{{ w.state.user.username }}</small>
      </div>
      <nav class="hl-nav" aria-label="业务导航">
        <section
          v-for="group in nav"
          :key="group.title"
          :class="{ 'nav-direct': group.direct, 'group-current': currentGroup === group.title }"
        >
          <button
            v-if="!group.direct"
            class="nav-group-trigger"
            :title="group.title"
            :aria-expanded="isOpen(group)"
            @click="toggleGroup(group)"
          >
            <el-icon><component :is="group.icon" /></el-icon><span>{{ group.title }}</span
            ><el-icon class="group-chevron" :class="{ opened: isOpen(group) }"
              ><ArrowRight
            /></el-icon>
          </button>
          <div
            v-if="group.direct || isOpen(group)"
            class="nav-items"
            :class="{ 'nav-subitems': !group.direct }"
          >
            <button
              v-for="[path, title, icon] in group.items"
              :key="path"
              :class="{ active: route.path === path }"
              :aria-current="route.path === path ? 'page' : undefined"
              :title="title"
              @click="navigate(path)"
            >
              <el-icon><component :is="icon" /></el-icon><span>{{ title }}</span
              ><i
                v-if="path === '/recovery' && w.state.stats.issues"
                class="nav-alert-dot"
                aria-label="有待处理异常"
              />
            </button>
          </div>
        </section>
      </nav>
      <div class="sidebar-tail">
        <router-link to="/profile" title="账户与设置"
          ><el-icon><Setting /></el-icon><span>账户与设置</span></router-link
        ><button @click="w.logout()" title="退出工作区">
          <el-icon><SwitchButton /></el-icon><span>退出登录</span>
        </button>
        <p>
          <i :class="{ offline: w.error }" /><span>{{
            w.error ? '同步暂不可用' : '业务数据已连接'
          }}</span>
        </p>
      </div>
    </aside>
    <div class="hl-main">
      <header v-if="!wall" class="hl-topbar">
        <div class="topbar-start">
          <button
            class="nav-fold desktop-fold"
            aria-label="折叠导航"
            :aria-expanded="!collapsed"
            @click="collapsed = !collapsed"
          >
            <el-icon><Fold /></el-icon></button
          ><button
            class="nav-fold mobile-fold"
            aria-label="打开导航"
            :aria-expanded="mobileOpen"
            @click="mobileOpen = !mobileOpen"
          >
            <el-icon><Expand /></el-icon></button
          ><span class="hl-breadcrumb"
            ><span>{{ roleName }}</span
            ><el-icon><ArrowRight /></el-icon><b>{{ route.meta.title }}</b></span
          >
        </div>
        <div class="topbar-end">
          <router-link v-if="w.isBuyer" to="/cart" class="cart-shortcut" aria-label="采购清单"
            ><el-icon><ShoppingCart /></el-icon><span>采购清单</span
            ><b v-if="w.cart.length">{{ w.cart.length }}</b></router-link
          ><AiAssistant /><el-badge :value="w.unread" :hidden="!w.unread" :max="99"
            ><button class="nav-fold" aria-label="打开业务消息" @click="inbox = true">
              <el-icon><Bell /></el-icon></button></el-badge
          ><router-link to="/profile" class="hl-avatar" aria-label="账户资料">{{
            w.state.user.username?.slice(0, 1)?.toUpperCase() || 'H'
          }}</router-link>
        </div>
      </header>
      <div v-if="w.error && !wall" class="business-error shell-error">
        {{ w.error }}<el-button link @click="w.refresh()">重新同步</el-button>
      </div>
      <main class="hl-content"><router-view /></main>
      <footer v-if="!wall" class="hl-footer">
        <span>禾链智配</span><span>演示数据仅用于流程体验</span>
      </footer>
    </div>
    <el-drawer v-model="inbox" title="业务消息" :size="'min(420px, 100vw)'"
      ><div class="inbox-top">
        <span>{{ w.unread }} 条未读</span
        ><el-button link @click="w.act('notifications/', {}, '消息已读')">全部标记已读</el-button>
      </div>
      <button
        v-for="n in w.state.notifications"
        :key="n.id"
        class="inbox-message"
        :class="{ unread: !n.read }"
        @click="openNotice(n)"
      >
        <span class="inbox-state" :class="{ done: n.resolved }" />
        <div>
          <b>{{ n.title }}</b>
          <p>{{ n.content }}</p>
          <small>{{ dateText(n.created_at) }}{{ n.resolved ? ' · 关联任务已完成' : '' }}</small>
        </div>
        <el-icon><ArrowRight /></el-icon></button
      ><el-empty v-if="!w.state.notifications.length" description="暂无业务消息"
    /></el-drawer>
  </div>
</template>
<style scoped>
.hl-shell {
  --sidebar-width: 224px;
  display: grid;
  grid-template-columns: var(--sidebar-width) minmax(0, 1fr);
  min-height: 100vh;
  background: #f5f7fa;
}
.hl-sidebar {
  position: fixed;
  inset: 0 auto 0 0;
  width: var(--sidebar-width);
  background: #111f35;
  color: #9cacc4;
  display: flex;
  flex-direction: column;
  z-index: 90;
  transition: width 0.18s ease;
}
.hl-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 30px 25px 24px;
  text-decoration: none;
  min-height: 100px;
}
.hl-logo {
  display: grid;
  place-items: center;
  width: 35px;
  height: 35px;
  color: #d6e3ff;
  background: #365ac1;
  border-radius: 10px;
  font-size: 22px;
  flex-shrink: 0;
}
.hl-brand b {
  color: #f2f6ff;
  font-weight: 650;
  font-size: 20px;
  letter-spacing: 0.5px;
  white-space: nowrap;
}
.hl-brand small {
  display: block;
  font-size: 11px;
  color: #93a7c7;
  margin-top: 5px;
  white-space: nowrap;
}
.hl-space {
  padding: 0 25px 27px;
  display: flex;
  flex-direction: column;
  gap: 7px;
  font-size: 12px;
  color: #a9bad3;
}
.hl-space small {
  font-size: 12px;
  color: #758eaf;
  overflow-wrap: anywhere;
}
.hl-nav {
  flex: 1;
  overflow-y: auto;
  padding: 0 14px 22px;
  scrollbar-width: thin;
  scrollbar-color: #3c4b63 transparent;
}
.hl-nav section + section {
  margin-top: 10px;
}
.nav-direct {
  margin-bottom: 30px;
}
.nav-items {
  display: grid;
  gap: 4px;
}
.hl-nav button {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 12px 13px;
  background: transparent;
  border: 0;
  border-radius: 7px;
  text-align: left;
  color: #acbad0;
  cursor: pointer;
  min-height: 43px;
  font-size: 13px;
  transition:
    background 0.13s ease,
    color 0.13s ease;
  position: relative;
}
.hl-nav button:hover {
  color: #f1f5ff;
  background: #1c2d48;
}
.hl-nav button > .el-icon:first-child {
  font-size: 17px;
  flex-shrink: 0;
  color: #8098ba;
}
.hl-nav button.active {
  background: #263e65;
  color: #f1f5ff;
  font-weight: 550;
}
.hl-nav button.active > .el-icon {
  color: #b1caff;
}
.hl-nav .nav-group-trigger {
  font-size: 13px;
  color: #bdc9da;
}
.nav-group-trigger > span {
  flex: 1;
}
.nav-group-trigger > .group-chevron {
  font-size: 11px;
  color: #778da9;
  transition: transform 0.14s ease;
}
.nav-group-trigger > .group-chevron.opened {
  transform: rotate(90deg);
}
.nav-subitems {
  margin-top: 5px;
  padding-left: 19px;
}
.hl-nav .nav-subitems > button {
  padding: 10px 12px;
  min-height: 39px;
  font-size: 13px;
  gap: 10px;
}
.nav-subitems > button > .el-icon:first-child {
  font-size: 15px;
  color: #748dae;
}
.nav-alert-dot {
  margin-left: auto;
  width: 5px;
  height: 5px;
  background: #dca75e;
  border-radius: 50%;
  flex-shrink: 0;
}
.sidebar-tail {
  padding: 19px 25px 24px;
  border-top: 1px solid #28374d;
}
.sidebar-tail > a,
.sidebar-tail > button {
  display: flex;
  align-items: center;
  gap: 12px;
  text-decoration: none;
  background: none;
  border: 0;
  color: #9fb1cb;
  font-size: 12px;
  padding: 10px 0;
  white-space: nowrap;
  width: 100%;
  cursor: pointer;
}
.sidebar-tail .el-icon {
  font-size: 15px;
  flex-shrink: 0;
}
.sidebar-tail p {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 11px;
  color: #748eae;
  margin-top: 17px;
  white-space: nowrap;
}
.sidebar-tail p i {
  width: 5px;
  height: 5px;
  background: #48b5a4;
  border-radius: 50%;
  flex-shrink: 0;
}
.sidebar-tail p i.offline {
  background: #c89a55;
}
.hl-main {
  grid-column: 2;
  min-width: 0;
}
.hl-topbar {
  position: sticky;
  top: 0;
  z-index: 70;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 0 34px;
  background: #fff;
  border-bottom: 1px solid #e7ecf2;
}
.topbar-start,
.topbar-end {
  display: flex;
  align-items: center;
  gap: 19px;
}
.topbar-start {
  min-width: 0;
}
.nav-fold {
  display: grid;
  place-items: center;
  border: 0;
  background: transparent;
  color: #75849a;
  font-size: 18px;
  width: 30px;
  height: 34px;
  cursor: pointer;
  border-radius: 6px;
}
.nav-fold:hover {
  background: #f0f3f9;
  color: #3b5682;
}
.hl-breadcrumb {
  display: flex;
  align-items: center;
  gap: 13px;
  font-size: 12px;
  color: #7e8da1;
  min-width: 0;
}
.hl-breadcrumb > .el-icon {
  font-size: 11px;
  color: #9aa9bd;
  flex-shrink: 0;
}
.hl-breadcrumb > b {
  font-size: 13px;
  color: #465e7b;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.topbar-end {
  gap: 20px;
  flex-shrink: 0;
}
.topbar-end > .el-badge {
  margin-right: 7px;
}
.cart-shortcut {
  display: flex;
  gap: 8px;
  align-items: center;
  text-decoration: none;
  font-size: 12px;
  color: #637896;
  white-space: nowrap;
}
.cart-shortcut > .el-icon {
  font-size: 17px;
}
.cart-shortcut > b {
  font-size: 11px;
  background: #edf2ff;
  color: #4869c8;
  min-width: 20px;
  height: 20px;
  display: grid;
  place-items: center;
  border-radius: 5px;
}
.hl-avatar {
  height: 31px;
  width: 31px;
  display: grid;
  place-items: center;
  background: #edf2fb;
  border-radius: 50%;
  font-size: 12px;
  color: #4e6cb2;
  text-decoration: none;
  font-weight: 600;
}
.hl-content {
  min-height: calc(100vh - 118px);
}
.hl-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 18px 38px;
  font-size: 11px;
  color: #8b98aa;
}
.shell-error {
  margin: 20px 36px 0;
}
.is-collapsed {
  --sidebar-width: 76px;
}
.is-collapsed .hl-brand {
  padding: 30px 20px 24px;
}
.is-collapsed .hl-brand > div,
.is-collapsed .hl-space,
.is-collapsed .hl-nav button > span,
.is-collapsed .group-chevron,
.is-collapsed .sidebar-tail span,
.is-collapsed .sidebar-tail p {
  display: none;
}
.is-collapsed .hl-nav {
  padding: 0 13px 22px;
}
.is-collapsed .hl-nav button {
  justify-content: center;
  padding: 12px 0;
}
.is-collapsed .sidebar-tail {
  padding: 17px 30px;
}
.is-collapsed .nav-direct {
  margin-bottom: 27px;
}
.mobile-fold,
.nav-scrim {
  display: none;
}
.is-wall {
  display: block;
  background: #0c192c;
}
.is-wall .hl-main {
  grid-column: auto;
}
.is-wall .hl-content {
  min-height: 100vh;
}
.inbox-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
  color: #718199;
  padding-bottom: 14px;
  border-bottom: 1px solid #e7edf4;
}
.inbox-message {
  display: flex;
  gap: 13px;
  align-items: flex-start;
  width: 100%;
  padding: 22px 0;
  border: 0;
  border-bottom: 1px solid #e8edf4;
  background: none;
  text-align: left;
  cursor: pointer;
}
.inbox-message > div {
  flex: 1;
  min-width: 0;
}
.inbox-message b {
  font-size: 14px;
  color: #334d6d;
  line-height: 1.7;
  font-weight: 550;
}
.inbox-message p {
  font-size: 13px;
  color: #71839a;
  line-height: 1.8;
  margin: 8px 0;
}
.inbox-message small {
  display: block;
  font-size: 12px;
  color: #8797ac;
}
.inbox-message > .el-icon {
  color: #8ca1bc;
  margin-top: 6px;
}
.inbox-state {
  width: 5px;
  height: 5px;
  flex-shrink: 0;
  border-radius: 50%;
  background: #ced7e5;
  margin-top: 9px;
}
.inbox-message.unread .inbox-state {
  background: #547ad7;
}
.inbox-state.done {
  background: #39a48e;
}
@media (max-width: 1100px) {
  .hl-topbar {
    padding: 0 26px;
  }
  .topbar-end {
    gap: 14px;
  }
}
@media (max-width: 900px) {
  .hl-shell {
    display: block;
    --sidebar-width: 224px;
  }
  .hl-sidebar {
    transform: translateX(-100%);
    transition: transform 0.18s ease;
  }
  .hl-sidebar.mobile-open {
    transform: translateX(0);
  }
  .hl-main {
    grid-column: auto;
  }
  .desktop-fold {
    display: none;
  }
  .mobile-fold {
    display: grid;
  }
  .hl-topbar {
    height: 60px;
    padding: 0 20px;
  }
  .hl-content {
    min-height: calc(100vh - 114px);
  }
  .nav-scrim {
    display: block;
    position: fixed;
    inset: 0;
    background: #08172b66;
    z-index: 85;
    border: 0;
  }
  .is-collapsed .hl-sidebar .hl-brand > div,
  .is-collapsed .hl-sidebar .hl-space,
  .is-collapsed .hl-sidebar .hl-nav button > span,
  .is-collapsed .hl-sidebar .sidebar-tail span,
  .is-collapsed .hl-sidebar .sidebar-tail p {
    display: revert;
  }
  .is-collapsed .hl-sidebar .hl-brand {
    padding: 30px 25px 24px;
  }
  .is-collapsed .hl-sidebar .hl-nav button {
    justify-content: flex-start;
    padding: 12px 13px;
  }
  .is-collapsed .hl-sidebar .sidebar-tail {
    padding: 19px 25px 24px;
  }
  .hl-footer {
    padding: 18px 23px;
  }
  .shell-error {
    margin: 16px 22px 0;
  }
}
@media (max-width: 520px) {
  .hl-topbar {
    padding: 0 16px;
    gap: 10px;
  }
  .topbar-start {
    gap: 11px;
  }
  .hl-breadcrumb {
    gap: 7px;
  }
  .hl-breadcrumb > span,
  .hl-breadcrumb > .el-icon {
    display: none;
  }
  .topbar-end {
    gap: 12px;
  }
  .cart-shortcut span {
    display: none;
  }
  .hl-avatar {
    display: none;
  }
  .hl-footer {
    padding: 17px 20px;
    font-size: 10px;
    gap: 12px;
  }
  .topbar-end :deep(.assistant-trigger > span) {
    display: none;
  }
}
</style>
