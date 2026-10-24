# hhanclubrescueseed 前端（模块联邦）

插件的 MoviePilot V3 联邦前端源码：Vue 3 + Vuetify 3.7.3 + `@originjs/vite-plugin-federation`。

## 结构

- `src/components/Page.vue`：联邦 expose `./Page`（下载记录列表、筛选、批量删除）
- `src/components/Config.vue`：联邦 expose `./Config`（插件配置表单）
- `src/App.vue`：本地开发壳（`api` 为 mock），仅 `npm run dev` 预览用，不进产物
- `src/vuetify/`：开发壳的 Vuetify theme/defaults（与示例工程一致）
- `dist/`：构建产物，随仓库提交（远程 MP 通过插件市场安装后无 node_modules，必须有 dist 才能加载前端）

## 构建

```bash
cd frontend
npm install
npm run build
```

构建后 `dist/assets/` 只保留运行必需的 4 个文件，其余（`index-*.js`、`index-*.css`、`date-*.js`、`__federation_shared_*`、`index.html`）是开发壳产物，删除：

- `remoteEntry.js`
- `__federation_fn_import-*.js`
- `__federation_expose_Page-*.js`
- `__federation_expose_Config-*.js`

引用链：`remoteEntry.js → expose ×2 → fn_import`，`shared` 配置 `generate: false`，vue/vuetify 全部取自宿主。

## 与反编译原版的差异

- `Page.vue` 的 Toast 改用宿主 `inject('moviepilot:toast')`，不内联 vue-toastification（规范禁止插件自建 Toast 容器；产物从 75KB 降到 21KB）。
- `Config.vue` 的 `defaultConfig` 含 `max_pages`（本次迁移新增的抓取页数配置，后端对应）。
- `VCronField` 为宿主全局组件，模板直接使用。
