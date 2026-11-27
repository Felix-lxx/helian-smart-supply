# 禾链智配前端

完整安装与演示见[根 README](../../README.md)，模块分工见[系统架构](../../docs/ARCHITECTURE.md)。

```sh
npm ci
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
npm run build
```

本地后端默认为 `http://127.0.0.1:8000/api`。复制 `.env.example` 为 `.env.local` 可设置公开的 `VITE_API_BASE_URL`；任何 `VITE_*` 变量都不允许存储机密。

路由入口 `src/router/index.js`，当前页面 `src/views/workspace/`，共享组件 `src/components/`，工作区状态 `src/stores/workspace.js`。历史页面已退出源码，旧地址通过路由重定向保留。
