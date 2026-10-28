# DownloadManagerLocal 插件上下文（AI 交接文档）

面向后续维护本插件的 AI agent / 开发者。只记录代码不能可靠推断的事实、真实路径与边界；版本、路径、键名以当前工作树代码为准；配置平铺键共 111 个（`utils/config.py::build_plugin_config_defaults` 实测）。

## 1. 插件概览

`DownloadManagerLocal`（展示名「下载中心」）是 MoviePilot V3 原生插件，把七个模块聚合在一个插件里，后端是 Python 服务层，前端是 Vue 联邦组件（`__init__.py::get_render_mode()` 返回 `("vue", "dist/assets")`）。

- 源码目录：`plugins.v3/downloadmanagerlocal/`
- 市场元数据：仓库根 `package.v3.json` 的 `DownloadManagerLocal` 条目
- 插件身份：`plugin_name="下载中心"`、`plugin_config_prefix="downloadmanagerlocal_"`、`plugin_order=18`、`auth_level=2`
- 渲染产物：`plugins.v3/downloadmanagerlocal/dist/`（联邦入口 `dist/assets/remoteEntry.js`）

七模块（口径与 `README.md`、`__init__.py::plugin_desc` 一致；IYUU 辅种与速度监控均已移除）：

| # | 模块 | 一句话职责 | 主要实现文件 |
| --- | --- | --- | --- |
| 1 | 转移做种 | 从源下载器复制种子到目标下载器（路径映射、删源、去重），并内嵌做种校验子能力 | `modules/transfer/service.py`、`modules/transfer/pipeline.py`、`modules/transfer/recheck.py` |
| 2 | 命名补刀 | 按 TMDB 识别结果重命名种子名，事件驱动 + cron 扫描双触发，失败归档并可恢复/补刀 | `modules/rename/service.py`、`modules/rename/events.py`、`modules/rename/archive.py` |
| 3 | 站点标签 | 按 tracker 域名映射站点标签与剧名/分类标签，支持历史补全与临时标签回收 | `modules/sitetag/service.py`、`utils/tag_cleanup.py` |
| 4 | H&R 助手 | 按站点规则跟踪 H&R 做种时长/比例，达标移除标签、超期告警，并作为删除路径的保护闸门 | `modules/hr/` |
| 5 | 自动删种 | 按条件（做种时长/标签/来源等 AND 组合）定期暂停、删除任务或删任务加文件 | `modules/autoremove/` |
| 6 | 失败清理 | 整理失败事件删源文件与下载历史；定时巡检清理已成功整理的重复残留 | `modules/failclean/` |
| 7 | 上传限速 | 按站点合计上限 + 下载器总上限统一调控 qBittorrent / Transmission 上传限速 | `modules/uploadlimit/service.py`、`modules/uploadlimit/allocator.py`、`modules/uploadlimit/worker.py` |

入口层 `__init__.py` 只维护 `_PluginBase` 契约、插件身份、配置生命周期、事件注册、扩展点声明和薄委托，业务编排在 `modules/` 与 `controller/`。

## 2. 目录结构

```
plugins.v3/downloadmanagerlocal/
├── __init__.py                     # 插件入口：身份/生命周期/事件注册/薄委托
├── README.md                       # 面向用户的模块与生效条件说明
├── AGENTS.md                       # 本文件（AI 交接 + 结构说明）
├── controller/
│   ├── api.py                      # build_api_routes(plugin)：API route metadata
│   └── handlers.py                 # 38 个 api_* handler 与响应 shape
├── model/
│   ├── api.py                      # Pydantic 请求/业务/响应模型
│   ├── state.py                    # 持久化 key 常量与 dict 读写 helper
│   └── upload_limit.py             # 上传限速 DTO 与 schema
├── adapter/
│   ├── moviepilot.py               # 宿主下载器/站点/下载历史访问
│   ├── telegram_target.py          # 管理员 Telegram 通知目标
│   └── upload_limit.py             # qBittorrent/Transmission 上传设置读写适配
├── core/                           # 插件骨架（非业务模块）
│   ├── lifecycle.py                # 初始化编排与停止编排
│   ├── config.py                   # 运行时字段初始化、扁平键→嵌套键映射
│   └── scheduler.py                # build_plugin_services：定时服务声明
├── modules/                        # 业务模块，一模块一文件夹，主逻辑统一 service.py
│   ├── transfer/
│   │   ├── service.py              # 转移做种主流程
│   │   ├── pipeline.py             # 转移事务：确认目标完整后才允许删源、失败 3 次放弃
│   │   ├── tasks.py                # 多任务引擎：transfer_tasks 解析与校验
│   │   ├── payload_export.py       # 源端种子文件统一导出（qB/TR/rt）
│   │   ├── recheck.py              # 做种校验队列与后台 worker
│   │   └── events.py               # TransferComplete/DownloadAdded 延迟批次
│   ├── rename/
│   │   ├── service.py              # 重命名、补刀、来源过滤、配置构建
│   │   ├── events.py               # DownloadAdded 防抖即时重命名
│   │   └── archive.py              # 补刀失败归档、恢复、删除、统计
│   ├── sitetag/
│   │   └── service.py              # 站点识别、标签写入、临时标签回收
│   ├── uploadlimit/
│   │   ├── service.py              # 上传限速扫描/分配/持久化/恢复
│   │   ├── allocator.py            # 纯逻辑额度分配器
│   │   └── worker.py               # 30 秒常驻协调 worker
│   ├── diagnostics/
│   │   └── service.py              # 只读诊断数据构建
│   ├── cleanup/
│   │   └── service.py              # 同步删除与 PluginAction/WebhookMessage
│   ├── hr/                         # H&R 模块子包（presets.json 内置站点验证预设）
│   ├── autoremove/                 # 自动删种子包
│   ├── failclean/                  # 失败清理子包
│   └── __init__.py
├── utils/
│   ├── config.py                   # PLUGIN_CONFIG_DEFAULTS 与配置清洗
│   ├── torrent_adapter.py          # qB/TR 字段适配
│   ├── name_cleaner.py             # 发布名清洗与补刀 hash 收集
│   ├── tag_cleanup.py              # 临时标签归属判定
│   ├── path.py / tracker.py          # 无状态工具
│   └── ...
├── dist/                           # Vue 联邦构建产物
└── icons/downloadmanagerlocal.png  # 插件图标
```

前端源码不在插件目录内，位于仓库级 `frontend.v3/downloadmanagerlocal/`（`src/components/Config.vue`、`Page.vue`、`api.js`），本工作树对应本地仓库 `D:/work/project/person/MoviePilot-Plugins/frontend.v3/downloadmanagerlocal/`；插件目录只保留 `dist/` 构建产物。

**v3.8.0 结构口径**：`Config.vue` = 纯配置页（mainTabs 7 个：转移做种/H&R/自动删种/失败清理/命名补刀/站点标签/上传限速；做种校验为转移做种子页签；区块体系「基础设置/内容层/高级设置」；零操作按钮/零状态展示/零预览表格；站点限速表为纯表单，随保存提交；大输入控件下沉区块底）。`Page.vue` = **8 侧栏页签**（运行总览/命名历史/H&R 任务/删种记录/失败清理/站点标签/上传限速/运行诊断），`refreshActive()` 按页签分组取数；总览 = 总览带 + 运行链路图 + 需要关注 + 模块卡×8（单份 markup 按 tab 过滤：总览 8 张、模块页签 1 张自动展开、history/diagnostics 不渲染）；记录表按页签归位（历史+归档→命名历史、hr 任务→H&R、autoremove 预览→删种记录、清理统计→失败清理、标签清理工具→站点标签）；运行详情（速度观测/上传调控）与诊断归运行诊断页签；全部手动操作在各页签模块卡内。

V3 测试在 `tests/v3/downloadmanagerlocal/`。

## 3. 模块详解

### 3.1 转移做种

- 职责：把源下载器的种子按路径映射复制到目标下载器，支持删源、去重、转移后做种校验；`TransferComplete` 事件驱动 + 兜底 interval 扫描。
- 失败重试上限（v3.9.6）：同一颗源种子最多尝试 `MAX_TRANSFER_ATTEMPTS = 3` 次。计数跨事务累计、存进来源记录（`attempts`），在**回滚完成后** +1（回滚本体的重试不计入，否则一次失败的多次回滚轮次会把计数吃满）；达上限置终态 `failed` 并附带最后一次失败原因，自动轮次不再选中。**手动触发 `/transfer_run`**（`trigger_source="手动"`）视为用户明确要求重试，`attempts` 清零后重来。判据 `pipeline.transfer_is_abandoned(previous, manual)` 是纯函数，放在 pipeline 而非 service 就是为了能被夹具直接加载并单测（7 组参数化 + 1 组真实累计/上限）。
- 关键文件：`modules/transfer/service.py`（主流程 `transfer`、兜底 `fallback_transfer`、延迟 `delayed_transfer`、后处理）、`modules/transfer/pipeline.py`（事务化：目标确认完整前保留源）、`modules/transfer/recheck.py`（做种校验队列与 worker）、`modules/transfer/events.py`（延迟批次调度）、`adapter/moviepilot.py`。
- 关键配置（v3.9.0 多任务引擎）：`transfer_tasks`（JSON 任务数组：name/enabled/from_downloader/to_downloader/include_category/include_labels/exclude_labels/empty_label_ok/no_paths/from_path/to_path/delete_source/delete_duplicate/keep_category/keep_tag/transfer_tag）、`transfer_rename_enabled`（转移后重命名，默认关，仅 qB 显示名语义，TR 目的端禁用）、`downloader_ext`（rt 下载器扩展配置 JSON：webui_url/source_plugin）、`transfer_enabled`、`delay_minutes`、`transfer_fallback_enabled`、`transfer_fallback_interval_minutes`、`frompath`/`topath`（已并入任务，旧键保留兼容读取）、`add_torrent_tags`、`scan_limit`、`pause_source`、`notify`、`seed_autostart`（`transfer_cron`/`transfer_event_enabled` 已移除读取，见 `core/config.py:83-84`）、`seed_skipverify`、`seed_check_interval`、`seed_max_wait_minutes`。`fromtorrentpath`（源种子文件路径）已废弃：加载时忽略并提示一次；单链路旧键（fromdownloader/todownloader/筛选/高级）保留作为旧配置迁移视图的数据源
- 端点：无专用 REST 路由；结果汇总进 `/overview`。
- 调度：`TorrentTransferFallback`（interval，`transfer_fallback_interval_minutes`）。
- 事件：`TransferComplete`（延迟调度）。
- 生命周期：`_transfer_active`（`utils/config.py::is_transfer_active`）成立时才启用；配置校验失败会关闭 `enabled` 并写回配置。

### 3.2 命名补刀

- 职责：按 TMDB 识别结果与原始发布名模板重命名种子；支持事件防抖即时重命名与 cron 周期扫描；失败进入归档，可恢复、可单条补刀。
- 关键文件：`modules/rename/service.py`（`RENAME_FLAT_CONFIG_KEYS`、`DEFAULT_RENAME_CONFIG`、`build_rename_config`、`rename_candidate`、`retry_failed_renames`、`retry_rename_by_hash`）、`modules/rename/events.py`（`handle_download_added_rename`）、`modules/rename/archive.py`、`utils/name_cleaner.py`。
- 关键配置：`rename_enabled`、`rename_notify`、`rename_cron_enabled`、`rename_on_download_added`、`rename_downloaders`、`rename_cron`、`rename_add_tag_after_rename`、`rename_movie_format`、`rename_tv_format`、`rename_exclude_dirs`、`rename_exclude_tags`、`rename_include_tags`、`rename_hash_white_list`、`rename_event_debounce_seconds`。
- 端点：`GET /rename_status`、`GET /rename_history`、`GET /rename_archive`、`POST /retry_renames`、`POST /retry_rename`、`POST /delete_rename_history`、`POST /restore_rename_archive`、`POST /delete_rename_archive`、`POST /recovery_torrent`。
- 调度：`DownloadCenterRenameScan`（cron `rename_cron`，需 `rename_enabled` 且 `rename_cron_enabled` 且 cron 非空）。
- 事件：`DownloadAdded`（`rename_on_download_added` 默认 true，按 `rename_downloaders` 过滤，`rename_event_debounce_seconds` 防抖）。

### 3.3 站点标签

- 职责：把 tracker 域名解析为站点名写标签，支持二级分类/剧名标签、历史补全、临时标签回收与人工清理。
- 关键文件：`modules/sitetag/service.py`（`DEFAULT_TAG_CONFIG`、`build_tag_config`、`complement_history`、`process_download_added`、`cleanup_temporary_tags_for_event`、`tag_torrent`）、`utils/tag_cleanup.py`、`utils/tracker.py`。
- 关键配置：`tag_enabled`、`tag_siteprefix`（默认 `🏠`）、`tag_tracker_mappings_str`、`tag_custom_sites_str`（站点库未收录站点的 `域名 -> 标签名` 自定义标签表，转移后标签与历史补全全链路兜底）、`tag_interval_cron`、`tag_enable_media_tag`、`tag_enable_tag`、`tag_enable_category`、`tag_enable_del_tags`、`tag_downloaders`、`tag_all_cat`、`tag_all_cat_rename`、`tag_rename_type`、`tag_path_rename`、`tag_catprefix`。
- 端点：`GET /sites`、`GET /tag_status`、`POST /tag_cleanup_scan`、`POST /tag_cleanup_execute`。
- 调度：`DownloadCenterSiteHistory`（cron `tag_interval_cron`，默认 `5 4 * * *`）；注册判据是模块级 `enable`，见 §9 注意事项。
- 事件：`DownloadAdded`（即时补全 + 临时标签回收）。

### 3.4 H&R 助手

- 职责：按站点规则跟踪 H&R 做种时长/比例，达标清除标签，超期告警，支持体积分档与每日汇总通知；并作为所有破坏性删除路径的保护闸门。
- 关键文件：`modules/hr/service.py`（`HrService`）、`modules/hr/scanner.py`、`modules/hr/evaluator.py`、`modules/hr/rules.py`（站点 YAML 规则与体积分档）、`modules/hr/guard.py`（`HrGuard`）、`modules/hr/cleanup.py`、`modules/hr/notify.py`、`modules/hr/models.py`、`modules/hr/constants.py`。
- 端点：`GET /hr/tasks`、`GET /hr/skip_stats`、`GET /hr_presets`（内置站点验证预设，只读）、`POST /hr_check`、`POST /hr_scan`、`POST /hr_clear_task`、`POST /hr_clear_compliant`、`POST /hr_clear_missing`。
- 关键配置：`hr_enabled`、`hr_protection_enabled`、`hr_auto_discover`、`hr_enable_site_config`、`hr_downloader`、`hr_sites`（站点名数组；v3.8.0 起存站点名非站点库 id，旧数字 id 加载时 warning 丢弃）、`hr_notify`（none/on_error/always）、`hr_check_period`（分钟）、`hr_hit_and_run_tag`、`hr_auto_cleanup_days`、`hr_notify_summary_cron`、`hr_exclude_tags`、`hr_exclude_categories`、`hr_duration`、`hr_deadline_days`、`hr_additional_seed_time`、`hr_ratio`、`hr_upload_multiplier`、`hr_upload_gte_download`、`hr_active`、`hr_size_tiers`、`hr_brush_plugin`、`hr_site_config_str`（YAML；条目支持 `enabled` 与 `trackers`）。
- 双层站点规则（v3.6.0）：`modules/hr/presets.json` 为随代码发布的内置站点验证预设（11 站，只读）；`hr_site_config_str` 为自定义层。`rules.build_site_rules` 合并语义：内置为底 → 自定义同名**整条覆写**（不做字段级合并）→ 条目 `enabled: false` 为影子条目（屏蔽该站全部站点规则，含内置，回退全局规则）→ 最后 `apply_global_defaults` 回填全局未设置字段。`HrSiteRule.enabled` 默认 `true`，旧 YAML 无此字段 = 启用，完全向后兼容。前端 H&R 设置页以合并视图展示（来源列 + 行启用 switch）。
- 自定义站点 tracker 兜底（v3.6.0）：`HrSiteRule.trackers`（域名或完整 URL 列表）。`scanner.resolve_site` 顺序 = 用户 `tag_tracker_mappings` → MP 站点库 → 规则条目 `trackers` 兜底（域名精确比对，`_rule_domain_map` 归一化，仅启用条目参与）。trackers 识别出的站点无 MP site_id，白名单判定走 `HrConfig.site_in_scope`（一律按站点名）：站点名 ∈ `hr_sites` **或** 站点名存在自定义规则条目（配了规则 = 纳管意向）。MP 站点库能识别的站点无需填 trackers。
- 调度：`HitAndRunCheck`（interval，`hr_check_period`）、`HitAndRunDiscover`（interval，`hr_check_period × 2`，需 `hr_auto_discover`）、`HitAndRunSummary`（cron `hr_notify_summary_cron`）。
- 事件：`DownloadAdded`（普通/RSS 来源纳管）、`PluginTriggered`（刷流 `brushflow_download_added` 纳管）、`PluginAction`（`hnr_check`/`hnr_scan`/`hnr_clear_compliant`/`hnr_clear_missing` 命令）。

### 3.5 自动删种

- 职责：按条件组（AND 语义）扫描候选并执行暂停 / 删除任务 / 删除任务及文件；执行前查询 H&R 保护闸门。
- 关键文件：`modules/autoremove/service.py`（`AutoRemoveService`、`collect_candidates`、`run_cycle`）、`modules/autoremove/scanner.py`、`modules/autoremove/criteria.py`、`modules/autoremove/rules.py`、`modules/autoremove/models.py`、`modules/autoremove/constants.py`。
- 关键配置：`remover_enabled`、`remover_notify`、`remover_action`（`pause`/`delete`/`deletefile`）、`remover_downloaders`、`remover_cron`（默认 `0 */12 * * *`）、`remover_samedata`、`remover_mponly`、`remover_size`、`remover_ratio`、`remover_time`、`remover_upspeed`、`remover_labels`、`remover_pathkeywords`、`remover_trackerkeywords`、`remover_errorkeywords`、`remover_torrentstates`、`remover_torrentcategorys`。
- 端点：`GET /autoremove_status`、`POST /autoremove_run`、`POST /autoremove_preview`（预览不执行）。
- 调度：`AutoRemoveTorrents`（cron `remover_cron`，需 `remover_enabled` 且 cron 非空；`0`/空表示不注册）。

### 3.6 失败清理

- 职责：`TransferFailed` 事件触发删除源文件与下载历史；定时巡检查出「已有成功整理历史 + 目标文件仍存在 + 残留超过 `failcleanup_retain_hours`」的重复源并清理。
- 关键文件：`modules/failclean/service.py`（`FailCleanService.handle_transfer_failed`、`cleanup_repeat_sources`）、`modules/failclean/events.py`、`modules/failclean/config.py`、`modules/failclean/hostapi.py`、`modules/failclean/notify.py`、`modules/failclean/constants.py`。
- 关键配置：`failcleanup_enabled`、`failcleanup_notify`、`failcleanup_cron`（默认 `0 */2 * * *`）、`failcleanup_clean_repeat`、`failcleanup_retain_hours`（默认 6）。
- 端点：`GET /failclean_status`、`POST /failclean_scan`（手动巡检）。
- 调度：`DownloadCenterRepeatCleanup`（cron `failcleanup_cron`，需 `failcleanup_enabled` 且 `failcleanup_clean_repeat`）。
- 事件：`TransferFailed`（即时删源，无保留期；同一 `(hash, 路径)` 30 秒内重复事件不重复删）。

### 3.7 上传限速

- 职责：统一写下载器全局上传上限；用户填正数的站点按站点合计上限跨下载器共享额度，空值/`0` 站点不写单种限速。
- 关键文件：`modules/uploadlimit/service.py`、`modules/uploadlimit/allocator.py`、`modules/uploadlimit/worker.py`、`adapter/upload_limit.py`、`model/upload_limit.py`、`utils/config.py::normalize_upload_limit_config`。
- 关键配置：`upload_limit_enabled`（默认 false）、`upload_limit_downloaders`、`upload_limit_downloader_limits_kib`、`upload_limit_site_rules`（站点名 → `{limit_kib}`）、`upload_limit_grace_minutes`（默认 30）。
- 端点：`GET /upload_limit_status`、`POST /upload_limit_reallocate`、`POST /upload_limit_site_tags`、`POST /upload_limit_site_rules_update`、`POST /upload_limit_disable_restore`。
- 调度：无独立 MoviePilot service；由常驻 worker 每 30 秒协调一轮，`DownloadAdded` 可提前唤醒。
- 事件：`DownloadAdded`（`wake_upload_limit_worker`）。

### 3.8 支撑层

- `core/lifecycle.py`：`initialize_plugin`（初始化运行时配置、启动 worker、登记一次性任务、构建 `HrService`/`AutoRemoveService`/`FailCleanService`）与 `stop_plugin_service`（发退出信号、代次递增、清空调度、停止各后台服务）。
- `core/scheduler.py`：`build_plugin_services(plugin)` 汇总全部定时服务声明。
- `modules/diagnostics/service.py`：`/diagnostics` 的只读诊断数据。
- `modules/cleanup/service.py`：同步删除（`DownloadFileDeleted`/`DownloadDeleted`/`WebhookMessage`/`PluginAction`）。
- `controller/handlers.py`：全部 handler 与 `schemas.Response[T]` 包装；`controller/api.py` 只做 route metadata；`__init__.py` 从 `controller.handlers` 直接导入 14 个 handler 别名。
- `model/api.py`：`ApiBusinessModel` / `ApiRequestModel` / `Response[T]` 家族。

## 4. 配置键清单

`utils/config.py::PLUGIN_CONFIG_DEFAULTS` 是单次合并构造的扁平默认值，`__init__.py::get_form()` 返回它的 deepcopy；各模块复用同一批 `*_CONFIG_DEFAULTS` 常量，没有第二份实现。

### 4.1 开关体系（v3.5.1 规范化）

- **单一真源**：`utils/config.py::MODULE_SWITCHES`——`{module: (扁平开关键, plugin 属性名)}`，七模块 transfer/rename/tag/hr/autoremove/failclean/upload_limit 全部登记。
- **唯一门控口径**：`module_active(config, module)` = 插件总开关 `enabled` AND 模块开关。总开关关闭时，无论模块开关状态，模块一律视为关闭。
- **属性层**：`core/config.py` 把 7 个 `plugin._*_enabled` 属性统一赋门控值；`plugin._module_switches` 存裸开关快照（展示层区分「插件停用」vs「模块停用」用）。
- **服务配置层**：hr/autoremove/failclean 的 `init_module` 中 `self._config.enabled = module_active(...)`，因此 `core/scheduler.py` 各 `_build_*_services` 的注册条件（读各 service 的 `self._config.enabled` / `_site_tag_config["enable"]` / `_rename_config["enabled"]`）天然走门控值，调度注册无需重复判断总开关。
- **嵌套视图对齐**：`_site_tag_config["enable"]` 与 `_rename_config["enabled"]` 在构造后对齐门控属性；`tag_enabled → enable` 已纳入 `_TAG_FLAT_PREFIX_MAP`。
- **API 层**：`controller/handlers.py::_require_module(plugin, module, label)` 拦截 9 个模块核心执行端点（retry_renames/retry_rename/recovery_torrent/tag_cleanup_execute/hr_check/hr_scan/autoremove_run/failclean_scan/upload_limit_reallocate）。数据管理类端点（清历史、恢复/删除归档、hr_clear_*、upload_limit_disable_restore）不受门控——停用模块后仍允许管理自己的数据。
- **组合函数**：`is_transfer_active`/`is_upload_limit_active` 基于门控属性，只追加配置完整性条件（下载器/路径/额度）；`is_plugin_active` = 七模块门控属性任一为真。
- **新增模块时**：先在 `MODULE_SWITCHES` 登记，再让属性/服务/端点走注册表口径，禁止散落手写 `enabled and xxx_enabled`。

**总键数：117**（dev MP form 端点实测）（v3.7.0 删 6 键：`onlyonce`/`hr_onlyonce`/`remover_onlyonce`/`rename_onlyonce`/`rename_retry`/`rename_recovery`；分组见下，`utils/config.py` 显式键 + 7 处 spread 合并去重后）。

| 分组 | 键数 | 键 |
| --- | --- | --- |
| 总开关 + 转移做种 | 27 | `enabled`、`delay_minutes`、`transfer_fallback_enabled`、`transfer_fallback_interval_minutes`、`seed_check_interval`、`seed_max_wait_minutes`，加 `TRANSFER_DEFAULTS` + `transfer_tasks`/`transfer_rename_enabled`/`downloader_ext`：`transfer_enabled`、`notify`、`nolabels`、`includelabels`、`includecategory`、`frompath`、`topath`、`fromdownloader`、`todownloader`、`deletesource`、`deleteduplicate`、`fromtorrentpath`、`nopaths`、`seed_autostart`、`seed_skipverify`、`transferemptylabel`、`add_torrent_tags`、`remainoldcat`、`remainoldtag`、`scan_limit`、`pause_source` |
| 命名补刀 | 14 | `rename_enabled`、`rename_notify`、`rename_cron_enabled`、`rename_on_download_added`、`rename_downloaders`、`rename_exclude_dirs`、`rename_hash_white_list`、`rename_exclude_tags`、`rename_include_tags`、`rename_cron`、`rename_add_tag_after_rename`、`rename_movie_format`、`rename_tv_format`、`rename_event_debounce_seconds` |
| 站点标签 | 15 | `tag_enabled`、`tag_siteprefix`、`tag_tracker_mappings_str`、`tag_custom_sites_str`、`tag_interval_cron`、`tag_enable_media_tag`、`tag_enable_tag`、`tag_enable_category`、`tag_enable_del_tags`、`tag_downloaders`、`tag_all_cat`、`tag_all_cat_rename`、`tag_rename_type`、`tag_path_rename`、`tag_catprefix` |
| 上传限速 | 5 | `upload_limit_enabled`、`upload_limit_downloaders`、`upload_limit_downloader_limits_kib`、`upload_limit_site_rules`、`upload_limit_grace_minutes` |
| H&R | 23 | `hr_enabled`、`hr_protection_enabled`、`hr_auto_discover`、`hr_enable_site_config`、`hr_downloader`、`hr_sites`、`hr_notify`、`hr_check_period`、`hr_hit_and_run_tag`、`hr_auto_cleanup_days`、`hr_notify_summary_cron`、`hr_exclude_tags`、`hr_exclude_categories`、`hr_duration`、`hr_deadline_days`、`hr_additional_seed_time`、`hr_ratio`、`hr_upload_multiplier`、`hr_upload_gte_download`、`hr_active`、`hr_size_tiers`、`hr_brush_plugin`、`hr_site_config_str` |
| 自动删种 | 17 | `remover_enabled`、`remover_notify`、`remover_action`、`remover_downloaders`、`remover_cron`、`remover_samedata`、`remover_mponly`、`remover_size`、`remover_ratio`、`remover_time`、`remover_upspeed`、`remover_labels`、`remover_pathkeywords`、`remover_trackerkeywords`、`remover_errorkeywords`、`remover_torrentstates`、`remover_torrentcategorys` |
| 失败清理 | 5 | `failcleanup_enabled`、`failcleanup_notify`、`failcleanup_cron`、`failcleanup_clean_repeat`、`failcleanup_retain_hours` |

各模块默认值来源：`utils/config.py::TRANSFER_DEFAULTS`、`modules/rename/service.py::DEFAULT_RENAME_CONFIG`（配 `RENAME_FLAT_CONFIG_KEYS` 映射）、`modules/sitetag/service.py::DEFAULT_TAG_CONFIG`、`modules/hr/constants.py::HR_FORM_DEFAULTS`、`modules/autoremove/constants.py::REMOVER_FORM_DEFAULTS`、`modules/failclean/constants.py::FAILCLEAN_FORM_DEFAULTS`。

配置读取：`controller/handlers.py` 通过 `plugin.get_config()` 读当前实例配置；站点标签扁平键→嵌套键映射在 `core/config.py::_TAG_FLAT_PREFIX_MAP` / `_flat_tag_module_config`（`tag_enabled → enable` 已登记，见 §4.1）。

## 5. API 端点表

`controller/api.py::build_api_routes` 目前声明 38 条路由（15 GET + 23 POST），全部 `auth="bear"`，均为 Vue 前端调用。GET 查询返回声明的裸业务模型，POST 操作返回 `schemas.Response[T]`。

### GET（14）

| path | summary | handler |
| --- | --- | --- |
| `/downloaders` | 获取下载器列表 | `api_downloaders` |
| `/rename_history` | 获取重命名历史 | `api_rename_history` |
| `/overview` | 获取下载中心总览 | `api_overview` |
| `/upload_limit_status` | 获取上传限速状态 | `api_upload_limit_status` |
| `/diagnostics` | 获取诊断信息 | `api_diagnostics` |
| `/rename_archive` | 获取补刀归档记录 | `api_rename_archive` |
| `/sites` | 获取站点列表（用于辅种站点选择） | `api_sites` |
| `/hr/tasks` | 获取 H&R 任务列表与汇总 | `api_hr_tasks` |
| `/hr/skip_stats` | 获取 H&R 保护跳过计数 | `api_hr_skip_stats` |
| `/hr_presets` | 获取内置 H&R 站点验证预设（只读） | `api_hr_presets` |
| `/autoremove_status` | 获取自动删种模块状态 | `api_autoremove_status` |
| `/failclean_status` | 获取整理失败清理模块状态 | `api_failclean_status` |
| `/tag_status` | 获取站点标签模块状态 | `api_tag_status` |
| `/rename_status` | 获取命名补刀模块状态 | `api_rename_status` |

### POST（20）

| path | summary | handler |
| --- | --- | --- |
| `/upload_limit_reallocate` | 立即重新分配上传额度 | `api_upload_limit_reallocate` |
| `/upload_limit_site_tags` | 扫描上传限速站点标签 | `api_upload_limit_site_tags` |
| `/upload_limit_site_rules_update` | 立即保存上传限速站点策略 | `api_upload_limit_site_rules_update` |
| `/upload_limit_disable_restore` | 停用上传限速并恢复原值 | `api_upload_limit_disable_restore` |
| `/retry_renames` | 一键补刀重命名 | `api_retry_renames` |
| `/retry_rename` | 单条补刀重命名 | `api_retry_rename` |
| `/delete_rename_history` | 删除重命名历史记录 | `api_delete_rename_history` |
| `/restore_rename_archive` | 恢复补刀归档记录 | `api_restore_rename_archive` |
| `/delete_rename_archive` | 删除补刀归档记录 | `api_delete_rename_archive` |
| `/recovery_torrent` | 恢复种子原始名称 | `api_recovery_torrent` |
| `/tag_cleanup_scan` | 扫描下载器标签并清理临时标签 | `api_tag_cleanup_scan` |
| `/tag_cleanup_execute` | 按扫描快照清理标签 | `api_tag_cleanup_execute` |
| `/hr_check` | 立即执行一轮 H&R 状态检查 | `api_hr_check` |
| `/hr_scan` | 立即执行一轮 H&R 自动发现与状态检查 | `api_hr_scan` |
| `/hr_clear_task` | 清除单条 H&R 记录 | `api_hr_clear_task` |
| `/hr_clear_compliant` | 批量清除已满足的 H&R 记录 | `api_hr_clear_compliant` |
| `/hr_clear_missing` | 批量清除需做种的 H&R 记录 | `api_hr_clear_missing` |
| `/autoremove_run` | 手动执行一轮自动删种 | `api_autoremove_run` |
| `/autoremove_preview` | 预览自动删种候选（不执行） | `api_autoremove_preview` |
| `/failclean_scan` | 手动执行重复下载残留巡检 | `api_failclean_scan` |

Vue helper 仅在顶层字段恰为 `success/message/data` 且 `success` 为布尔值时解包，裸业务模型原样返回。旧根级 `api.py` 兼容导出层已删除，handler 唯一来源是 `controller/handlers.py`。

## 6. 调度任务表

`core/scheduler.py::build_plugin_services(plugin)` 按运行时配置构造声明：

| id | name | trigger | func | 注册条件 |
| --- | --- | --- | --- | --- |
| `TorrentTransferFallback` | 转移做种兜底服务 | interval，`transfer_fallback_interval_minutes` 分钟 | `plugin._fallback_transfer` | `_transfer_active` 且 `transfer_fallback_enabled` |
| `HitAndRunCheck` | H&R状态检查 | interval，`hr_check_period` 分钟 | `HrService.check_tasks` | `hr_enabled` |
| `HitAndRunDiscover` | H&R自动发现 | interval，`hr_check_period × 2` 分钟 | `HrService.discover_tasks` | `hr_enabled` 且 `hr_auto_discover` |
| `HitAndRunSummary` | H&R通知汇总 | cron `hr_notify_summary_cron`（默认 `0 8 * * *`） | `HrService.send_summary` | `hr_enabled` 且 cron 可解析 |
| `AutoRemoveTorrents` | 自动删种 | cron `remover_cron`（默认 `0 */12 * * *`） | `AutoRemoveService.run_cycle` | `remover_enabled` 且 cron 非空、可解析 |
| `DownloadCenterRepeatCleanup` | 重复下载残留清理 | cron `failcleanup_cron`（默认 `0 */2 * * *`） | `FailCleanService.cleanup_repeat_sources` | `failcleanup_enabled` 且 `failcleanup_clean_repeat` |
| `DownloadCenterSiteHistory` | 站点标签历史补全 | cron `tag_interval_cron`（默认 `5 4 * * *`） | `complement_history` | 模块配置 `enable` 为真且 cron 非空（见 §9） |
| `DownloadCenterRenameScan` | 命名补刀扫描 | cron `rename_cron` | `scan_renames` | `rename_enabled` 且 `rename_cron_enabled` 且 cron 非空 |

无效 cron 只禁用对应服务并记 error 日志，不抛异常。v3.7.0 起无 `onlyonce` 一次性任务：立即运行语义由数据页模块卡按钮走执行端点（`transfer_run`/`tag_complement`/`autoremove_run`/`failclean_scan` 等）。

## 7. 事件订阅表

事件在 `__init__.py` 用 `@eventmanager.register(...)` 声明，业务在 `modules/`：

| 事件 | 入口方法 | 实现 | 作用 |
| --- | --- | --- | --- |
| `TransferComplete` | `on_transfer_complete` | `modules/transfer/events.py::handle_transfer_complete_event` | 按 `delay_minutes` 保存每个 hash 最早到期时间，串行登记 date job |
| `DownloadAdded` | `on_download_added` | `modules/transfer/events.py::handle_download_added_event` | 临时标签回收 → 站点标签即时补全 → 事件重命名 → H&R 纳管 → 唤醒上传限速 worker |
| `TransferFailed` | `on_transfer_failed` | `modules/failclean/events.py::handle_transfer_failed_event` | 按配置删除源文件与下载历史 |
| `DownloadFileDeleted`、`DownloadDeleted` | `on_download_sync_delete` | `modules/cleanup/service.py::handle_sync_delete_by_hash_event` | 按源 hash 同步删除转种/辅种目标任务（经 H&R guard） |
| `WebhookMessage` | `on_webhook_message` | `modules/cleanup/service.py::handle_webhook_message_event` | Emby `library.deleted` 事件按路径反查 hash 后同步删除 |
| `PluginAction` | `on_plugin_action` | `modules/cleanup/service.py::handle_plugin_action_event` | H&R 命令（`hnr_check`/`hnr_scan`/`hnr_clear_compliant`/`hnr_clear_missing`）与网盘同步删除（`networkdisk_del`） |
| `PluginTriggered` | `on_plugin_triggered` | `modules/transfer/events.py::handle_plugin_triggered_event` | 刷流 `brushflow_download_added` 按 BRUSH 来源纳管 H&R |

`get_command()` 返回空列表，无远程命令。

## 8. 持久化数据 key

通过 `_PluginBase.get_data()` / `save_data()` 读写，key 常量集中在 `model/state.py` 与各模块 `constants.py`：

| key | 归属 | 作用 |
| --- | --- | --- |
| `rename_records` | `model/state.py` | 重命名历史（hash → record） |
| `rename_retry_state` | `model/state.py` | 补刀失败状态、归档状态、失败次数与原因 |
| `seed_recheck_queue` | `model/state.py` | 做种校验队列（下载器名 → hash → item） |
| `transfer_stats` | `model/state.py` | 转种成功累计/今日与兜底计数（schema v2） |
| `transfer_skip_stats` | `model/state.py` | 转种跳过计数 |
| `transfer_schedule` | `model/state.py` | 延迟转种队列（schema v1，ISO 到期时间） |
| `upload_limit_state` | `model/state.py` | 上传限速运行态（schema v1） |
| `hr_tasks` | `modules/hr/constants.py` | H&R 任务集合 |
| `hr_notify_events` | `modules/hr/constants.py` | H&R 待汇总通知事件 |
| `remover_state` | `modules/autoremove/constants.py` | 最近一轮删种状态与候选明细 |
| `failclean_status` | `modules/failclean/constants.py` | 最近巡检与累计清理计数 |
| `<source_downloader>-<source_hash>` | `modules/cleanup/service.py` | 单条转种源→目标映射记录 |

重构时这些 key 必须保持后向兼容，不得改名或迁移，除非先写兼容读取 + 回归测试。

## 9. 约束与坑

- **dev reload 用类名 id**：V3 本地调试实例 reload 路径是 `POST /api/v1/plugin/reload/DownloadManagerLocal`（类名，不是小写目录名）。
- **单仓库口径**：本仓库 `D:/work/project/person/MoviePilot-Plugins` 是唯一维护点；z2561221 克隆仅作整合期基底，已弃。前端源码在仓库级 `frontend.v3/downloadmanagerlocal/`，构建产物回到插件目录 `dist/`。
- **前端只保留一份源码**：插件目录内不再有 `frontend/`，源码统一在仓库级 `frontend.v3/downloadmanagerlocal/`（`Config.vue`/`Page.vue`/`api.js`）。
- **设置页「恢复默认」（v3.6.3）**：`Config.vue` 顶部 `PANE_RESET_KEYS` 是页签→键集的第二份分组真源（78 个前缀键自动归组 + transfer 25 键显式列表 + 全局 `enabled` 不归组）；新增配置键时必须在 `defaults` 常量登记且确认前缀能落入对应页签，否则该键永不被重置。重置只改表单，点「保存配置」才落库；H&R 页签重置会清空 `hr_site_config_str` 回全局基准。
- **`package.v3.json` 编辑规范**：向 `history` 插新版本条目时禁止用相邻行替换（会吞掉旧键名导致 JSON 破坏）；优先单行整行替换或全量重写，改完立即 `python -m json.tool package.v3.json` 校验。V3 发布版本两处同步：`__init__.py::plugin_version` 与 `package.v3.json`（version + history 顶部新条目）；插件目录内无 `plugin.json`（MP V3 不读取，已删除）。
- **速度监控已整体移除**：`modules/speed_*`、`speed_monitor_*` 配置键、监控会话与告警链路在本版本代码中 0 残留；历史 changelog 中出现的「速度监控」字样只作追溯。
- **IYUU 辅种已移除**：`iyuu_helper.py`、`modules/iyuu.py`、`iyuu_*` 配置键均已删除（v3.4.0 六合一整合基线时移除）。
- **命名补刀事件开关**：唯一键是 `rename_on_download_added`（默认 true）；旧名 `rename_event_enabled` 已删除，勿再引用。
- **站点标签历史补全注册判据（v3.5.1 已修）**：`_TAG_FLAT_PREFIX_MAP` 历史上缺 `tag_enabled → enable` 映射，导致 `_site_tag_config["enable"]` 恒为默认 False、补全 cron 服务永不注册；现已登记映射并随门控值对齐，开关 `tag_enabled` 即可注册。
- **H&R 保护闸门**：`modules/hr/guard.py::HrGuard().should_skip(path, downloader, hash)` 是转移删源、自动删种、失败清理、同步删除四条破坏性路径的统一入口，未达标任务不会被连带删除；`/hr/skip_stats` 读各路径跳过计数。
- **做种校验后台线程**：改动 `modules/transfer/recheck.py` 必须保持退出事件与锁语义，否则出现重复 worker 或无法停止。
- **上传限速语义**：`upload_limit_grace_minutes` 内不写站点/单种额度但仍受下载器总上传上限；`allocated_kib` 是分配额度，不是实际吞吐或 Peer 能力证明；停用恢复走 compare-and-set。
- **快速抢占运行态**：`MIGRATION_OBSERVE_ONLY_KEY = "migration_observe_only"` 为真时自动删种只列候选、不执行下载器写操作。
- **相对导入**：插件包内模块用相对导入，不依赖源码预装到 `app.plugins.downloadmanagerlocal`；模块间引用写 `..hr.guard` 形式（`modules/transfer/pipeline.py:8`、`modules/uploadlimit/service.py:14` 的 `...model`/`...utils` 同理按层级上推），不写绝对自引用。
- **API 契约**：route 的 path/method/auth/summary 改动会破坏 Vue 前端调用；`auth` 必须保持 `bear`。

## 10. 验证与调试

- 离线回归：`python -m pytest tests/v3/downloadmanagerlocal/ -q`（V3 测试在 `tests/v3/downloadmanagerlocal/`）。
- 语法自检：`python -c "import ast; ast.parse(open('<file>').read())"`。
- 前端构建：在 `frontend.v3/downloadmanagerlocal/` 内 `vite build`，产物输出到 `plugins.v3/downloadmanagerlocal/dist/`（须含 `dist/assets/remoteEntry.js`，不打包 vuetify 共享）。
- 本地 MP V3 调试：后端 `http://127.0.0.1:17430`、前端 `17431`；启动/鉴权/部署/reload 见本地仓库 `D:/work/project/person/MoviePilot-Plugins/docs/mp-local-debug.md`。
- 运行态验收：reload 后核对 history、installed、overview 与静态资产；文件同步、哈希、reload、API 与页面验收分别记录，不能互相替代。
- 写入类测试（删种、重命名、标签、限速、下载器控制）只用 fake / mock，不连接真实下载器。
