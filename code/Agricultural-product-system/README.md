# 禾链智配 · 前端

Vue 3、Vite、Element Plus、Pinia、ECharts 与 Leaflet 构建的采购、供应和运营工作区。完整功能、截图、后端安装和数据库初始化见[根目录 README](../../README.md)。

## Recommended IDE Setup

[VS Code](https://code.visualstudio.com/) + [Vue (Official)](https://marketplace.visualstudio.com/items?itemName=Vue.volar) (and disable Vetur).

## Recommended Browser Setup

- Chromium-based browsers (Chrome, Edge, Brave, etc.):
  - [Vue.js devtools](https://chromewebstore.google.com/detail/vuejs-devtools/nhdogjmejiglipccpnnnanhbledajbpd)
  - [Turn on Custom Object Formatter in Chrome DevTools](http://bit.ly/object-formatters)
- Firefox:
  - [Vue.js devtools](https://addons.mozilla.org/en-US/firefox/addon/vue-js-devtools/)
  - [Turn on Custom Object Formatter in Firefox DevTools](https://fxdx.dev/firefox-devtools-custom-object-formatters/)

## Customize configuration

See [Vite Configuration Reference](https://vite.dev/config/).

## Project Setup

```sh
npm ci
```

### Compile and Hot-Reload for Development

```sh
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

### Compile and Minify for Production

需要 Node.js `^20.19.0 || >=22.12.0`。后端需运行在 `http://127.0.0.1:8000`，当前请求地址见 `src/utils/request.js`。Vue 使用 beta 版本，以锁文件为准。

```sh
npm run build
```

### Lint with [ESLint](https://eslint.org/)

```sh
npm run lint
```

`npm run lint` 会自动修复文件，运行前请保存或提交已有修改。当前业务页面在 `src/views/workspace/`，旧页面路由已统一重定向。DeepSeek 和地图密钥只配置在后端，不写入前端或 `VITE_*` 构建变量。
