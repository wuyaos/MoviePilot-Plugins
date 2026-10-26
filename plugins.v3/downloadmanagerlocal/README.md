# DownloadManagerLocal V3

下载中心是 MoviePilot V3 原生插件，把转移做种（含做种校验）、命名补刀（种子重命名）、站点标签、H&R 助手、自动删种、失败清理和上传限速七个模块聚合到一个插件里，并通过 Vue 联邦页面提供配置、运行总览与只读诊断。

`v3.6.0`：H&R 站点规则升级为双层模型——内置 11 站验证预设（随代码发布、只读）+ 自定义 YAML 覆写层，同名整条覆写，条目支持 `enabled` 影子开关（关闭即回退全局规则）与 `trackers` 兜底识别（MP 站点库未收录的自定义站点按 tracker 域名匹配），旧配置零迁移；设置页改为合并视图（来源标注、行启用开关、继承值提示）。

`v3.5.1`：模块开关规范化——总开关 AND 模块开关统一门控口径，覆盖 7 模块属性、3 个服务初始化、9 个执行端点与 tag 历史补全调度注册；诊断页区分「插件停用」与「模块停用」。

`v3.5.0`：移除速度监控模块；命名补刀的事件触发开关收敛为 `rename_on_download_added`（默认开启），并补齐包含/排除标签过滤；删种与 H&R 页补齐手动执行、候选预览、残留巡检、立即核查和清除入口。

`v3.4.0`：六合一整合基线——合并 H&R 助手（原 H&R 助手 Pro）、自动删种、失败清理三个模块，移除 IYUU 辅种。

## 能力构成

- 转移做种：从源下载器复制种子到目标下载器，支持路径映射、删除源任务、删除重复任务；做种校验（跳过校验/自动开始做种）已并入本模块。
- 命名补刀：按 TMDB 识别结果重命名种子名，事件驱动 + cron 扫描双触发，失败自动归档并支持恢复/单条补刀。
- 站点标签：给下载任务补站点标签与剧名标签，支持 TMDB 二级分类映射与历史补全。
- H&R 助手：按站点规则跟踪 H&R 做种时长/比例，达标移除标签，超期告警，支持体积分档与每日汇总通知；站点规则为双层模型（内置 11 站验证预设 + 自定义覆写 + 条目级启用开关）。
- 失败清理：整理失败（TransferFailed 事件）删除源文件与下载历史；定时巡检清理已成功整理的本地残留媒体文件。
- 上传限速：统一写入下载器全局上传上限；填正数的站点按站点合计上限跨下载器共享额度，停用时自动恢复原值。

## 生效条件（核心开关）

| 开关 | 说明 |
|---|---|
| `enabled` | 插件总开关 |
| `transfer_enabled` / `transfer_cron` / `transfer_event_enabled` | 转移做种：开关 / 兜底扫描周期 / 事件驱动 |
| `rename_enabled` / `rename_cron` / `rename_on_download_added` | 命名补刀：开关 / 扫描周期 / 下载入列事件触发 |
| `tag_enabled` / `tag_interval_cron` | 站点标签：开关 / 历史补全周期 |
| `hr_enabled` / `hr_check_period` / `hr_notify_summary_cron` | H&R：开关 / 检查间隔（分钟）/ 汇总通知周期 |
| `remover_enabled` / `remover_cron` | 自动删种：开关 / 执行周期（0 表示不注册定时服务） |
| `failcleanup_enabled` / `failcleanup_clean_repeat` / `failcleanup_cron` | 失败清理：总开关 / 重复残留巡检 / 巡检周期 |
| `upload_limit_enabled` | 上传限速 |

## 配置要点

- H&R 站点规则（v3.6.0 双层模型）：内置 11 站验证预设随代码发布、只读、自动生效；`hr_site_config_str`（YAML，按 site_name 或站点 id 生效）为自定义层，同名站点整条覆写内置；条目加 `enabled: false` 可屏蔽该站（含内置预设），回退全局规则；未设置的字段按全局规则（`hr_duration`/`hr_deadline_days`/`hr_ratio` 等）回填。设置页提供合并视图：来源标注、行级启用开关、未设字段「继承」提示。自定义站点可填 `trackers`（域名/URL 列表）：MP 站点库识别不到的站按 tracker 域名兜底识别，配了规则条目即视为纳入 H&R 白名单（无需加入 `hr_sites`）。
- 生效口径（v3.5.1 门控）：模块实际生效 = 插件总开关 `enabled` AND 模块开关；总开关关闭时所有模块一律停用，执行类 API 返回 400。
- 自动删种：`remover_conditions_*` 条件组（AND 语义），`remover_action`（pause/delete/deletefile），`remover_torrentstates` 限定任务状态。
- 自动删种：条件项 AND 组合（做种时长/体积/比率、标签、tracker、路径关键词、错误关键词、任务状态等），`remover_action`（pause/delete/deletefile），`remover_mponly` 仅处理 MoviePilot 添加的任务。
- 删除保护：转移删源、自动删种、失败清理路径统一经过 H&R guard（`HrGuard().should_skip`），未达标任务不会被连带删除；同步删除（源删除事件连带删除转种目标）当前不受 guard 保护。

## 测试与构建

- 离线回归：`python -m pytest tests/v3/downloadmanagerlocal/ -q`
- 前端构建：`frontend.v3/downloadmanagerlocal/` 内 `vite build`，产物输出到 `plugins.v3/downloadmanagerlocal/dist/`（vite outDir 相对路径，禁止打包 vuetify 共享）。
