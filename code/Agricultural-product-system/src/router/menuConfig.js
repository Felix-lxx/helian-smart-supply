export const menuConfig = {
  // 采购商：侧重购物和产地溯源
  retail: [
    { name: '系统首页', path: '/home', icon: 'HomeFilled' },
    { name: '农产商城', path: '/products', icon: 'Goods' },
    { name: '遥感溯源大屏', path: '/dashboard', icon: 'DataBoard' },
    { name: '我的订单', path: '/orders', icon: 'List' }
  ],
  // 商家/管理员：全权限，包含库存管理与监控
  admin: [
    { name: '管理概览', path: '/home', icon: 'HomeFilled' },
    { name: '库存管理', path: '/products', icon: 'Goods' },
    { name: '遥感监测中心', path: '/dashboard', icon: 'DataBoard' },
    { name: '销售订单', path: '/orders', icon: 'List' }
  ]
};
