# MediaServerEnhance 插件上下文（AI 交接文档）

面向后续维护本插件的 AI agent / 开发者，只记录结构与维护边界。

## 1. 插件概览

`MediaServerEnhance`（展示名「媒体服务器增强」）是 MoviePilot V3 原生插件，聚合媒体服务器 API 域的四个模块，后端为 Python 服务层，前端为 Vue 联邦组件（`__init__.py::get_render_mode()` 返回 `("vue", "dist/assets")`）。

- 源码目录：`plugins.v3/mediaserverenhance/`
- 前端源码：`frontend.v3/mediaserverenhance/`（构建产物输出到插件目录 `dist/`）
- 市场元数据：仓库根 `package.v3.json` 的 `MediaServerEnhance` 条目
- 插件身份：`plugin_name="媒体服务器增强"`、`plugin_config_prefix="mediaserverenhance_"`、`plugin_order=30`、`auth_level=1`
- 渲染产物：`plugins.v3/mediaserverenhance/dist/`（联邦入口 `dist/assets/remoteEntry.js`）

四个模块（口径与 `__init__.py::plugin_desc`、`package.v3.json` description 一致）：

| # | 模块 | 一句话职责 | 主要实现文件 |
| --- | --- | --- | --- |
| 1 | 刷新编排 | 整库/指定库刷新、整理入库事件触发、防抖合并、待刷新队列手动提交 | `modules/refresh/service.py`、`modules/refresh/events.py` |
| 2 | 媒体库体检 | 只读巡检：缺集（服务器季集查询）、重复条目、空目录、孤立旁车、缺封面（服务器复核）、失效路径 | `modules/audit/service.py` |
| 3 | 封面工坊 | CoverGen 迁移的轻量版：三种风格渲染、预览、回传服务器（`covers_upload` 双开关） | `modules/covers/service.py`、`core/style/` |
| 4 | 服务端能力 | Emby/Jellyfin 插件探测与关键词匹配（如 StrmAssistant 神医、弹幕、Playback Reporting） | `modules/capabilities/service.py` |

另有 `modules/diagnostics/` 提供运行诊断（配置摘要、模块开关、数据目录、功能重叠插件、最近 webhook 事件）。

v1.1.0 新增行为：

- **观察模式**（`observe_only`，默认关）：开启后体检等只读检查照常运行，但所有刷新请求与封面上传被跳过，任务时间线 status 记 `observed`（见 `modules/refresh/service.py::_execute_refresh`、`modules/covers/service.py` 上传分支）。
- **Webhook 登记**：订阅宿主 `WebhookMessage` 事件，只记录渠道/事件名/摘要到 `WebhookEvents` 持久化键（上限 50 条）供诊断页展示；删除类事件（`deleted/removed/删除` 关键词）额外打日志显式留痕「不联动删除」，插件不基于 webhook 执行任何破坏性动作（`controller/events.py::handle_webhook_event`）。
- **CoverGen 互斥**：封面模块启用时若检测到本机已装并启用 `CoverGen` 插件，cover 相关执行直接拒绝并在 job 记录冲突原因，避免两个插件重复生成/上传封面。

## 2. 边界（不做项）

- **不删除任何文件**：体检只读，无删除动作；删除权在 DownloadManagerLocal。
- **不做 STRM 生成**：归 StrmManage。
- **不做服务器实例增删**：实例列表完全复用宿主「设定 → 媒体服务器」配置（`MediaServerHelper`），插件只有启用过滤。
- **不做用户管理、播放记录、转码、代理**等宿主/服务器本体能力。

## 3. 目录结构

```
plugins.v3/mediaserverenhance/
├── __init__.py                # 入口：身份/生命周期/事件注册/命令声明/薄委托
├── AGENTS.md                  # 本文件
├── adapter/
│   └── mediaserver.py         # MediaServerHelper 封装：列表/库/条目遍历、刷新、季集、图片上传
├── controller/
│   ├── api.py                 # build_api_routes(plugin)：14 条路由声明（overview/servers/.../history_clear）
│   ├── handlers.py            # Handlers 静态方法集，endpoint 用 partial(Handlers.x, plugin)
│   └── events.py              # 宿主事件订阅声明（TransferComplete 入库触发 / PluginAction 命令 / WebhookMessage 只记录）
│   ├── lifecycle.py           # initialize_plugin：先停旧运行时再写新配置
│   ├── scheduler.py           # cron 注册（refresh_cron/audit_cron/covers_cron/capabilities_cron）
│   └── style/                 # 封面渲染风格实现
├── model/
│   └── api.py                 # pydantic 请求/响应模型（AuditRequest.servers 等为复数命名）
├── modules/
│   ├── refresh/  audit/  covers/  capabilities/  diagnostics/
├── utils/
│   ├── runtime.py             # 配置键→ `_xxx` 运行属性映射（CONFIG_ATTR_MAP）与归一化
│   └── store.py               # 插件持久化（JOBS_KEY/AUDIT_REPORT_KEY/CAPABILITIES_KEY 等）
└── dist/                      # 前端联邦构建产物（不要手改，由 frontend.v3 工程构建）
```

## 4. 关键约定

- **配置键**：`covers_upload`、`covers_limit` 等复数前缀；`utils/runtime.py::CONFIG_ATTR_MAP` 一一映射到 `_cover_upload` 等实例属性。新增配置必须同步 `__init__.py` 类属性声明、runtime 映射、`get_form` 默认值和前端 Config.vue。
- **上传双开关**：封面回传需要配置 `covers_upload=true` **且** 请求体 `upload=true`，二者缺一不上传。
- **API 路径**：动态路由为下划线风格（`/audit_run`、`/cover_run`、`/capabilities_probe`），不是斜杠子路径。
- **类型归一**：Emby/Jellyfin 条目 `item_type` 可能是 `Movie/Series`（服务器原值）或宿主中文值，统一经 `modules/audit/service.py::_item_kind` 归一为 `movie/tv` 再判定。
- **缺集检查**：`item.seasoninfo` 不可信（宿主遍历不返回季集），必须走 `adapter/mediaserver.py::fetch_season_episodes` 实时向服务器查询，该方法吞异常返回空映射。
- **缺封面复核**：本地目录无图片不直接报问题，先经 `adapter/mediaserver.py::fetch_primary_image`（缩略 240px）向服务器复核，服务端抓图条目本地常无图片文件。
- **封面迁移来源**：`core/style/` 迁自 `plugins.v2/covergen`（业务精简版，去掉 UI/API 层与库过滤逻辑）；原插件继续独立维护。
- **事件数据展开**：宿主事件 `event_data` 形态不一：dict（宿主直接传字典时）、扁平 pydantic 模型（WebhookMessage → `WebhookEventInfo`，`_event_data(event, dump_models=True)` 展开）、嵌套模型（TransferComplete → `TransferResultContractData`，**不要 dump**，浅层 dump 会破坏嵌套 `mediainfo`/`transferinfo` 的取值；`modules/refresh/service.py::build_payload_from_event` 内的 `_get` 同时兼容属性与字典）。新增事件处理一律走 `controller/events.py::_event_data`，不要直接 `event.event_data.get(...)`。
- **Webhook 真实报文**：宿主 webhook 端点 `POST /api/v1/webhook/?token=<API_TOKEN>&source=<实例名>` 只接受 **multipart form 的 `data` 字段**（JSON，必须有 `Event` 键），JSON body 会被静默忽略（Emby 解析器 form.get("data")）。
- **插件日志**：插件 logger（`app.sdk.logging`）按实例写入 `config/logs/plugins/mediaserverenhance.log`，不在主 `moviepilot.log` 里。

## 5. 验证要点

- 后端语法：`python -c "import ast; ast.parse(...)"` 逐文件。
- 本地运行验证（MockEmby：`D:/tmp/mse_mock_emby.py`，端口 18096，含假库/条目/季集端点 `/emby/Shows/{id}/Episodes` 与单条目端点 `/emby/Users/{uid}/Items/{id}`）：
  1. `POST /api/v1/system/setting/MediaServers`（**POST** 不是 PUT，body 为配置数组）接入实例；
  2. `GET /api/v1/plugin/MediaServerEnhance/overview` 确认在线；
  3. `POST .../audit_run` → `GET .../audit` 看问题明细（Test Show S1 应缺 2 集：3、5）；
  4. `POST .../cover_preview` / `cover_run`（`upload:true`）确认生成与上传；
  5. `POST .../capabilities_probe` → `GET .../capabilities`；
  6. `GET .../jobs/1/20` 任务时间线；
  7. webhook 登记：`curl -F 'data={"Event":"item.markplayed","Item":{...}}' ".../api/v1/webhook/?token=<API_TOKEN>&source=<实例名>"` → `GET .../diagnostics` 看 webhooks 记录；观察模式开 `observe_only` 后 `POST .../refresh` 应返回 `status: observed`。
- reload 用类名 id：`POST /api/v1/plugin/reload/MediaServerEnhance`。
