# hhanclubrescueseed 前端（模块联邦）

MoviePilot V3 联邦前端源码：Vue 3 + Vuetify 3.7.3 + `@originjs/vite-plugin-federation`。

## 结构

- `src/components/Page.vue`：联邦 expose `./Page`（下载记录列表、筛选、批量删除）
- `src/components/Config.vue`：联邦 expose `./Config`（26 键白名单配置表单）
- `src/App.vue`：本地开发壳（`api` 为 mock），仅 `npm run dev` 预览用，不进产物
- `src/vuetify/`：开发壳的 Vuetify theme/defaults
- `dist/`：同一次构建后同步的联邦运行产物

## 构建与产物

```bash
rm -rf dist
npm install
npm run build
```

将同一次构建的 `dist/assets/` 中运行必需的 **7 个文件**整体同步到插件根 `dist/assets/`：

- `remoteEntry.js`
- `__federation_fn_import-*.js`
- `_plugin-vue_export-helper-*.js`
- `__federation_expose_Page-*.js` 与同名 `.css`
- `__federation_expose_Config-*.js` 与同名 `.css`

其余 `index-*.js/css`、`date-*.js`、`__federation_shared_*`、`index.html` 是开发壳产物，不要混入部署目录。`remoteEntry.js → expose ×2 → fn_import` 是引用链，`shared` 配置 `generate: false`，vue/vuetify 取自宿主。

## 前端行为

配置保存只投影 26 个后端配置键，旧的 `user_id`、`min_seeders`、`max_torrent_size_gb` 和辅助 `all_downloaders` 不会由表单回写。获取规则分为列表页粗筛和详情页下载者精筛；详情精筛为空时不会请求 `viewpeerlist.php`，启用时每轮详情请求预算为 15。详情响应可能因大雷种子被服务端截断（`data` 数量小于 `count`），该 partial 边界由后端按已返回行判定并写 debug 日志；历史任务保持独立，不纳入普通任务精筛。

`Page.vue` 只保留顶部统计区刷新按钮，下载记录标题区不重复提供刷新。
