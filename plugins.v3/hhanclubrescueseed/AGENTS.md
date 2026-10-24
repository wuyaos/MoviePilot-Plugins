# Hhanclubrescueseed（憨憨保种区）

Fork 自 [Seed680/MoviePilot-Plugins](https://github.com/Seed680/MoviePilot-Plugins/tree/main/plugins.v3/hanhanrescueseeding) 的 `hanhanrescueseeding` v3 2.0.0，迁移至本仓库并更名 `Hhanclubrescueseed`。站点强耦合憨憨 BT（HhanClub），无通用性。

## 结构

- `__init__.py`：插件入口，单类 `Hhanclubrescueseed(_PluginBase)`，约 1040 行
  - 类属性：`domain`（hhanclub.net → hhanclub.top → hhan.club 依次回退）、`plugin_config_prefix = "hhanclubrescueseed_"`
  - `init_plugin()`：读配置、起 `BackgroundScheduler`；`run_once` / `history_rescue_enabled` 触发一次性任务后自动复位
  - `_check_seeding()`：主任务。按 `max_pages`（默认 5，可配置）翻页抓 `rescue.php?page=N`，HTML 解析（lxml etree）筛选做种人数/大小，经 `DownloaderHelper` 下载打标签，记录写入 `save_data("download_records")`
  - `_check_history_seeding()`：历史保种，走用户详情页（无分页）
  - API（`get_api()`，相对路径，V3 envelope）：
    - `GET /config` → `Response(success=True, data={...})`，含 `max_pages`
    - `GET /download_records` → `Response(success=True, data=[...])`
    - `POST /delete_torrents`、`POST /delete_download_records` → `Response`
  - `get_render_mode()` → `("vue", "dist/assets")`，前端为 module federation 构建产物
- `dist/`：Vue 前端构建产物（由 `frontend/` 构建同步，**不手工编辑**）：`assets/remoteEntry.js`（联邦入口，scope `hhanclubrescueseed__`）、`assets/__federation_expose_Config-*.js`、`assets/__federation_expose_Page-*.js`、`assets/__federation_fn_import-*.js`；`vue/vuetify` 不打包（宿主 shared 提供），dev 壳产物（`index-*.js/css`、`index.html`、`_plugin-vue_export-helper-*`）构建后剔除
- `frontend/`：前端源码（Vite + @originjs/vite-plugin-federation，脚手架取自 wuyaos/MoviePilot-Frontend v2 `examples/plugin-component`）。构建：`cd frontend && npm ci --ignore-scripts && npm run build`，产物在 `frontend/dist/`，同步到 `../dist/assets/` 入库（`frontend/dist` 为中间产物不入库）

## 关键契约（踩坑记录）

- 插件 API 路由前缀 = 插件类名（PascalCase）。dist 内所有 `plugin/<id>/...` 字符串必须与类名一致，改类名需同步：Config.js defaultConfig.id、index.js initialConfig.id、Page.js 3 处 URL。
- 前端按 `response.success/response.data` envelope 读取；`GET /config`、`GET /download_records` 必须返回 `Response(success=True, data=...)`，返回裸 dict/裸数组会导致前端恒报「获取配置失败/获取下载记录失败」（原版 bug）。
- 重建后的 `remoteEntry.js` federation scope 为 `hhanclubrescueseed__`（与 `frontend/vite.config.js` 的 `name` 自洽），与插件 id 无关、无需与类名一致。
- 改前端一律走 `frontend/` 源码后重新构建，不再手工编辑 `dist/`（旧手编版已整体替换为构建产物）。

## 配置项

enable / run_once / cron / downloader / seeding_count（如 `1-3`）/ torrent_size（GB 范围）/ download_limit（0 不限）/ save_path / custom_tag / enable_notification / notify_on_zero_torrents / history_rescue_enabled / user_id / force_resume / **max_pages（默认 5）**
