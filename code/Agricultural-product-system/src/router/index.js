import { createRouter, createWebHistory } from 'vue-router'
const routes = [
  { path: '/login', component: () => import('../views/Login.vue'), meta: { title: '登录' } },
  {
    path: '/',
    component: () => import('../views/Layout.vue'),
    children: [
      {
        path: 'procurement',
        component: () => import('../views/workspace/Purpose.vue'),
        meta: { title: '用途采购' },
      },
      {
        path: 'reviews',
        component: () => import('../views/workspace/Reviews.vue'),
        meta: { title: '复检任务', roles: ['supplier', 'admin'] },
      },
      {
        path: 'recovery',
        component: () => import('../views/workspace/Recovery.vue'),
        meta: { title: '异常补配' },
      },
      {
        path: 'workboard',
        component: () => import('../views/workspace/Workboard.vue'),
        meta: { title: '交付作业' },
      },
      {
        path: 'companies',
        component: () => import('../views/workspace/Companies.vue'),
        meta: { title: '企业与站点' },
      },
      { path: '', redirect: '/home' },
      {
        path: 'home',
        component: () => import('../views/workspace/Dashboard.vue'),
        meta: { title: '工作台' },
      },
      {
        path: 'products',
        component: () => import('../views/workspace/Market.vue'),
        meta: { title: '货源市场' },
      },
      {
        path: 'product/:id',
        component: () => import('../views/workspace/Product.vue'),
        meta: { title: '货源详情' },
      },
      {
        path: 'cart',
        component: () => import('../views/workspace/Checkout.vue'),
        meta: { title: '采购清单', roles: ['retail'] },
      },
      {
        path: 'orders',
        component: () => import('../views/workspace/Orders.vue'),
        meta: { title: '订单履约' },
      },
      {
        path: 'demands',
        component: () => import('../views/workspace/Demands.vue'),
        meta: { title: '采购需求' },
      },
      {
        path: 'supply',
        component: () => import('../views/workspace/Supply.vue'),
        meta: { title: '商品与批次', roles: ['supplier', 'admin'] },
      },
      {
        path: 'allocation',
        component: () => import('../views/workspace/Allocation.vue'),
        meta: { title: '分货实验室', roles: ['supplier', 'admin'] },
      },
      {
        path: 'quality',
        component: () => import('../views/workspace/Quality.vue'),
        meta: { title: '品质工作台', roles: ['supplier', 'admin'] },
      },
      {
        path: 'origins',
        component: () => import('../views/workspace/Origins.vue'),
        meta: { title: '产地网络' },
      },
      {
        path: 'operations',
        component: () => import('../views/workspace/Operations.vue'),
        meta: { title: '运营中心', roles: ['admin'] },
      },
      {
        path: 'devices',
        component: () => import('../views/workspace/Devices.vue'),
        meta: { title: '设备接入', roles: ['admin'] },
      },
      {
        path: 'profile',
        component: () => import('../views/workspace/Settings.vue'),
        meta: { title: '账户设置' },
      },
      {
        path: 'realname-auth',
        component: () => import('../views/workspace/Settings.vue'),
        meta: { title: '主体认证' },
      },
      { path: 'my-products', redirect: '/supply' },
      { path: 'publish', redirect: '/supply?create=1' },
      { path: 'dashboard', redirect: '/origins' },
      { path: 'admin-dashboard', redirect: '/home' },
      { path: 'admin-orders', redirect: '/orders' },
      { path: 'admin-products', redirect: '/supply' },
      { path: 'admin-users', redirect: '/operations' },
      { path: 'admin-realname-audit', redirect: '/operations' },
      { path: 'admin-device-monitor', redirect: '/devices' },
      { path: 'admin-quality-audit', redirect: '/quality' },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/home' },
]
const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})
router.beforeEach((to) => {
  document.title = `${to.meta.title || '工作台'} · 禾链智配`
  if (to.path != '/login' && !localStorage.getItem('access_token')) return '/login'
  if (to.meta.roles && !to.meta.roles.includes(localStorage.getItem('user_role'))) return '/home'
})
export default router
