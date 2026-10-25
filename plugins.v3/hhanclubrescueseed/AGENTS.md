# Hhanclubrescueseed（憨憨保种区）

Fork 自 [Seed680/MoviePilot-Plugins](https://github.com/Seed680/MoviePilot-Plugins/tree/main/plugins.v3/hanhanrescueseeding) 的 `hanhanrescueseeding` v3 2.0.0，迁移至本仓库并更名 `Hhanclubrescueseed`。站点强耦合憨憨 BT（HhanClub），无通用性。

## 结构

- `__init__.py`：插件入口，单类 `Hhanclubrescueseed(_PluginBase)`，约 1400 行
  - 类属性：`domain`（hhanclub.net → hhanclub.top → hhan.club 依次回退）、`plugin_config_prefix = "hhanclubrescueseed_"`；内置治理常数（`DISK_QUOTA_TARGET_RATIO=0.9`、`NO_UPLOAD_AVG_SPEED=1024`、`MAX_REMOVE_PER_RUN=5`）集中一处
  - `init_plugin()`：读配置、起 `BackgroundScheduler`；`run_once` / `history_rescue_enabled` 触发一次性任务后自动复位
  - `get_service()`：**双任务注册**
    - `Hhanclubrescueseed` 保种区获取（`cron`，默认 `*/20 14-15 * * *`）→ `_check_seeding()`
    - `HhanclubrescueseedMonitor` 种子监控（`monitor_cron`，默认 `*/30 * * * *`，留空禁用）→ `_maintenance()`
  - `_check_seeding()`：获取任务。按 `max_pages`（默认 5）翻页抓 `rescue.php?page=N`，`_prefilter_row()` 列表页预筛（免费/做种数/下载数/完成率/发布时间/体积范围，字段全部来自列表 DOM，无详情页二次请求），经 `DownloaderHelper` 下载打 `custom_tag` 标签，记录写入 `save_data("download_records")`
  - `_maintenance()`：监控任务。仅依赖下载器状态：① 达标打标（做种满 `reward_hours` 且完成 → 加 `reward_tag`）→ ② 配额删除（总体积 > `disk_quota_gb` 触发，删回 `disk_quota_gb * 0.9`，达标优先/平均上传低优先/做种久优先）→ ③ 卡死清理（超 `stuck_days` 天未完成）。两类删除单轮各限 `MAX_REMOVE_PER_RUN=5` 个；仅在发生删除时发通知
  - `_delete_torrent_by_hash()`：统一删除入口。**先按 hash+标签反查圈定复核**（不带 `custom_tag` 的种子拒绝删除），qb 用 `delete_torrents(ids=, delete_file=)`、tr 用 `remove_torrents(hashs=, delete_file=)`
  - `_get_torrent_stats()`：qb(dict)/tr(属性) 统一翻译 `{name, hash, size_gb, uploaded, avg_upspeed, progress, seeding_hours, added_days, tags, state}`；平均上传速度 = 累计上传/活动时长
  - `_check_history_seeding()`：历史保种，走用户详情页（无分页）
  - `_event`（stop_service 置位）在页面/配额/卡死循环中检查，禁用插件可及时叫停
  - API（`get_api()`，相对路径，V3 envelope）：
    - `GET /config` → `Response(success=True, data={...})`
    - `GET /download_records` → `Response(success=True, data={records, auto_delete_enabled, disk_quota_gb})`
    - `POST /delete_torrents`（body 裸数组 hashes）、`POST /delete_download_records`（body 裸数组 titles）→ `Response`
  - `get_render_mode()` → `("vue", "dist/assets")`，前端为 module federation 构建产物
- `dist/`：Vue 前端构建产物（由 `frontend/` 构建同步，**不手工编辑**）。入库白名单（联邦规范）：`remoteEntry.js`、`__federation_fn_import-*.js`、`__federation_expose_Page/Config-*.js` **及同名 `-*.css`**（自定义样式在 expose css 里，宿主会加载）、`_plugin-vue_export-helper-*.js`；dev 壳产物（`index-*.js/css`、`date-*.js`、`index.html`、`__federation_shared_vuetify/`）构建后剔除
- `frontend/`：前端源码（Vite + @originjs/vite-plugin-federation，脚手架取自 wuyaos/MoviePilot-Frontend v2 `examples/plugin-component`）。构建：`cd frontend && npm ci --ignore-scripts && npm run build`，产物在 `frontend/dist/`，同步到 `../dist/assets/` 入库（`frontend/dist` 为中间产物不入库）

## 关键契约（踩坑记录）

- 插件 API 路由前缀 = 插件类名（PascalCase）。**宿主 `$pluginApi` 是裸 axios 实例（baseURL `api/v1/`，不自动拼插件段）**：相对路径必须写 `` `plugin/${props.pluginId}/<name>` ``（下划线命名，如 `download_records`）；路由参数是 FastAPI 直注（`titles: List[str]` 收**裸数组 body**），漏前缀会打到宿主全局同名接口（405）或宿主配置接口（假成功）
- 前端按 `response.success/response.data` envelope 读取；`GET /config`、`GET /download_records` 必须返回 `Response(success=True, data=...)`，返回裸 dict/裸数组会导致前端恒报「获取配置失败/获取下载记录失败」（原版 bug）
- 重建后的 `remoteEntry.js` federation scope 为 `hhanclubrescueseed__`（与 `frontend/vite.config.js` 的 `name` 自洽），与插件 id 无关、无需与类名一致
- 保种区列表页为 Tailwind div 布局（无 table.torrents）：行容器 `//*[@id="mainContent"]/div[1]/div[2]/div[3]/div`；做种 `div[3]/div/div[3]/a`、下载 `div[3]/div/div[4]/a`、完成 `div[3]/div/div[5]/a`、体积 `div[3]/div/div[1]`、发布时间 `div[3]/div/div[2]/span/@title`（精确时间）、免费标记 `div[2]/div/div[2]/div` 含「免费」文本。站点改版需同步 `_prefilter_row`
- MP 本地实例 `app/plugins/<id>` 可能是拷贝目录而非 junction（某次复制部署会打断 junction），改仓库后必须手动同步 `dist/assets` + `__init__.py` 并 reload，勿假设自动生效
- **`dist/assets` 必须是同一次构建的完整白名单 7 文件**：`remoteEntry.js`、`__federation_fn_import-*.js`、`_plugin-vue_export-helper-*.js`、`__federation_expose_{Page,Config}-*.js` + 两个同名 `.css`。缺 fn_import/export_helper 会「组件加载错误 无法加载组件」（expose js 相对 import 404）
- **`frontend/dist` 是 vite outDir 在 root 外的多构建堆积场**（vite 不清空 root 外 outDir）：同步前先 `rm -rf frontend/dist` 全新构建，再从 `frontend/dist/assets` 整体复制白名单 7 文件；从堆积目录挑单文件会拿到互不配套的组合（remoteEntry 引 A 批 expose、文件却是 B 批）
- 浏览器对 `remoteEntry.js` 的 HTTP 启发式缓存极顽固（旧文件 mtime 老时 reload 也不 revalidate），验证修复用 `fetch(url, {cache:'reload'})` 全部 7 文件后 `location.reload()`，或浏览器硬刷新
- `dist/` 被 `.gitignore` 的 `dist/` 全局规则忽略、**不入库**——部署必须从工作区文件打包；工作区 `dist/assets` 一旦损坏，git 恢复不了
- 改前端一律走 `frontend/` 源码后重新构建，不再手工编辑 `dist/`

## 配置项

enable / run_once / cron / monitor_cron / downloader / save_path / custom_tag / enable_notification / notify_on_zero_torrents / force_resume / history_rescue_enabled / user_id / reward_tag / reward_hours（默认 18）/ disk_quota_gb / stuck_days（默认 7）/ seeding_count（如 `1-3`）/ torrent_size（GB 范围）/ min_seeders / min_downloaders / max_torrent_size_gb / completion_ratio_max（%，0-100）/ connect_time_max_hours（小时）/ download_limit（0 不限）/ max_downloading（默认 3）/ **max_pages（默认 5）**；`free` 为「仅下载免费种子」开关（默认关，开启后预筛仅保留免费种子）
