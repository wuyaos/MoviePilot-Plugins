# Agent Note: DML 标签清理独立区块与一键清理

Status: implemented

## Problem

DML 分类标签模块原先只有「标签补全后附带扫描」：`tag_enable_del_tags` 开启时，`complement_history()`（下载中心站点标签历史补全定时任务）末尾调用 `scan_tag_candidates()` 只读扫描，**没有任何定时删除入口**；数据页的手动清理需要经过「选下载器 → 扫描 → 勾选弹窗 → 确认」多步弹窗。用户要求：无弹窗一键清理，以及带开关/定时的独立标签清理区块。

## Decision

新配置键（平铺存储，映射进 `DEFAULT_TAG_CONFIG.cleanup_*`）：`tag_cleanup_enabled`（默认 **false**，不自动迁移旧 `tag_enable_del_tags`——旧行为只读、新行为会真删）、`tag_cleanup_downloaders`（空=不执行，不隐式扩大范围）、`tag_cleanup_cron`（默认 `15 4 * * *`，独立于补全计划 `tag_interval_cron`）。

新调度 `DownloadCenterTagCleanup`（`core/scheduler.py`）：分类标签模块关闭不注册；开关开启且下载器非空才注册。手动与定时共用 `modules/sitetag/service.py::run_tag_cleanup()`：扫描（`scan_tag_candidates` 只读预筛）→ 筛零关联（`removable and count==0`）→ `execute_tag_cleanup` 执行前复查复用（防扫描后新增关联误删）→ 合并扫描期读取失败（有删除也有失败=部分成功 `code=2`；无候选有失败=`code=2` 不执行）。观察模式（`tag_observe_only`）沿用既有门控，零删除。旧「允许删除标签」开关与补全末尾附带扫描已移除。

数据页把原清理入口换成 `doTagCleanupRun()`：直接 POST `/tag_cleanup_run`，无弹窗无预览；按钮走 `moduleActions`（key `tag-cleanup-run`），运行中 `moduleRunning` 防重入。

## Alternatives considered

- 复用补全计划附带清理：一个开关两种语义，误开启即每日删标签，且无法单独设清理时间，故拆独立调度。
- 旧开关自动迁移：旧值只代表「愿意扫描」，等价「愿意删除」会静默引入破坏性行为。
- 独立观察开关：与模块级 `tag_observe_only` 双状态易漂移，故复用模块级。

## Consequences

`DEFAULT_TAG_CONFIG` +3 键 → 依赖键数契约的测试更新（gating 119→122/117→120、路由 42→43、`model.api` 桩补 `TagCleanupRunRequest/RunResult`、sitetag.service 桩补 `run_tag_cleanup`、多个 `DEFAULT_TAG_CONFIG` 桩补 3 键）。移除附带扫描时曾误删 `complement_history` 的 `return result`，被 `test_sitetag_execution_history` 捕获后修复——测试桩的 `sys.modules` 污染顺序曾掩盖该错误，单文件跑绿不代表全量绿，验收以全量 1005 passed 为准。

后端 1005 passed（新增 `test_tag_cleanup_run.py` 3 项：错误合并、无候选不执行、配置回退）；前端 node --test 160 passed（`page-setup` 改断言直调 `doTagCleanupRun` 无弹窗、`visual-roles` error 语义键换 `tag_cleanup_enabled`、`page-module-headers` tag actions 增 `tag-cleanup-run`、density fixture 重生成且保留 CRLF、form-section Config 业务脚本冻结 SHA 更新为 9ab3312a）。部署前自动清理默认关闭，真实定时删除需用户在 UI 显式开启；本轮未在 QNAP 启用。
