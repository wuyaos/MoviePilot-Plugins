# 历史资料：禁止作为当前执行指令

> 本文已由 `docs/downloadmanagerlocal-final-implementation-spec.md` 取代。仅供追溯，旧待裁决、默认值、回退命令不得照抄执行。
> 原路径：`.ralph/dml-seven-optimizations.md`。原文保存在下方，不代表现行约定。

---

# DML 七项优化：模块隔离 / 观察模式 / 统一通知 / 数据清理 / 图标边框文案

方案正文（权威）：`docs/downloadmanagerlocal-optimization-plan.md`
仓库：`D:/work/project/person/MoviePilot-Plugins`　插件：`plugins.v3/downloadmanagerlocal`
起始版本：3.9.12（执行时核对 `__init__.py` 的 `plugin_version` 与 `package.v3.json`）

## 用户已确认决策

- **A｜观察开关升级默认值**：自动删种继承原 `migration_observe_only`，其他模块保持升级前行为（默认可执行），仅全新安装默认开启观察，保存过新开关后以新值为准。
- **B｜观察模式与已有上传限速**：观察期内禁止一切限速写入，已有额度保持原样，不执行恢复。
- **C｜重命名归档清理**：连归档状态一起删除，被清理的种子可重新识别与补试；确认框必须写明该后果。
- **D｜部署**：本轮不部署 QNAP；**用户追加约束（m17354）**：所有修改完成后必须先在本地 MP（17430/17431）实测通过，再按方案 10.3 完整包流程部署 QNAP（部署另行确认）。

## Goals

- 模块独立启停与故障隔离：关闭模块不干扰其他模块；单模块可独立运行。
- 每个有写操作的模块具备独立“观察模式”（只预览不写入）。
- 通知格式统一，各模块保留独立通知开关。
- 数据页可清理各模块历史/归档（不碰下载器数据与安全状态）。
- 下载器品牌图标＋实例名统一；设置页去掉内层套框；用户可见文案统一。
- 全量回归通过，产物可作为完整包部署（部署另行授权）。

## Checklist

### 阶段一 基线核对
- [x] P1-1 读 `AGENTS.md`、`plugins.v3/downloadmanagerlocal/AGENTS.md` 并遵守其编辑/发布规范
- [x] P1-2 跑基线命令（json 校验 / pytest / 前端 node --test / npm run build）并记录结果 → 全绿，见 Verification
- [x] P1-3 产出写操作清单：模块｜入口｜写函数｜是否已有观察判断｜关联后续动作 → 见「写操作清单」

### 阶段二 模块隔离
- [x] P2-1 `core/config.py::initialize_runtime_config` 先判模块门控再解析（关闭模块不解析、坏配置不阻断）→ `_module_config_guarded` + `_downgrade_faulted_module_gates`，测试见 test_gating.py
- [x] P2-2 `core/lifecycle.py` 不再自动关插件总开关、不再落盘改写用户模块开关，改为 `plugin._module_faults` 标记运行异常（`_mark_transfer_config_invalid`、`_init_service_isolated`）
- [x] P2-3 隔离三处：service 构造已入异常边界、停止操作 `_stop_isolated`/`_stop_background_services` 逐个隔离、定时任务声明按 `module_faults` 跳过；事件分支沿用 `modules/transfer/events.py::_event_step`
- [x] P2-4 联动规则：关联模块关闭→跳过（`modules/transfer/service.py` 补刀/同步目录、`modules/autoremove`、`modules/failclean` 均按 `module_active` 门控）；关联模块观察→只预览；前置未真实成功→不执行后续（P3 观察模式落地后统一复核，见 Notes）
- [x] P2-5 隔离测试与验收：后端 220 passed（新增 `test_hr_guard_intent.py` 3 项 + `test_module_isolation.py` 5 项）；页面区分「关闭/故障」→ `modules/diagnostics/service.py::_module_fault_checks` 出 `error` 状态 + `Page.vue` 故障徽标/汇总项/自动删种保护闸门文案（`guard_unconfirmed`）

### 阶段三 观察模式
- [x] P3-1 新增 `transfer_/rename_/tag_/hr_/remover_/failcleanup_/upload_limit_observe_only` 键 + 公共解析函数 + 旧键回退（决策 A）→ `utils/config.py` 新增 `OBSERVE_ONLY_KEYS`/`LEGACY_OBSERVE_ONLY_KEYS`/`OBSERVE_ONLY_DEFAULTS`、`module_observe_only()`/`build_module_observe_flags()`/`module_observe_flags()`/`observe_only()`；`core/config.py` 初始化时落 `plugin._module_observe_only` 快照；自动删种改读新口径（旧键 `migration_observe_only` 继承）；前端 `defaults` 登记 7 键（老配置 false）+ 全新安装补丁（空 initialConfig → true）+ transfer 页签显式重置键集
- [x] P3-2（本条是迭代5 的中间记录，已被下方条目取代：transfer / rename / tag 写边界在迭代6 完成并有 `test_observe_boundaries_transfer.py`（6）+ `test_observe_boundaries_rename_tag.py`（5）覆盖）
- [x] P3-2 七个模块写边界后端拦截（转移增删/暂停、改名、标签分类、H&R 打标、删种删文件、失败清理删文件、限速设置）→ upload_limit（P3-4）、failclean（`_delete_source_file` 守卫返回 skipped）、hr（`register_task`/`_remove_tag` 双守卫）、autoremove（run 层观察分支）、cleanup（`execute_cleanup` 强制仅预览）、rename（`retry_failed_renames`/`retry_rename_by_hash`/`rename_candidate`/`_handlers` 四处守卫 + service 懒导入 `utils.config` 破循环）、tag（`_apply_metadata`/`execute_tag_cleanup` 守卫）；边界测试 `test_observe_boundaries_transfer.py`（6）+ `test_observe_boundaries_rename_tag.py`（5）
- [x] P3-4 上传限速观察期禁止一切写入且不执行恢复（决策 B）→ `modules/uploadlimit/service.py`：`run_upload_limit_cycle()` 观察期直接返回 `service_status=observe_only`（不调用任何写函数、不恢复），`restore_upload_limits()` 观察期返回 `code=1` 回执不动下载器
- [x] P3-5 前端各页签观察开关、提示文案、`defaults` 与 `PANE_RESET_KEYS` 覆盖 → 完成：七页签各插「观察模式（只预览不写入）」VSwitch（md=4，warning 色，dm-hint 逐模块文案）；remover 旧「仅观察不执行」开关迁移为 `remover_observe_only`；watch 回填旧键继承（已保存新键不覆盖）；PANE_RESET_KEYS.remover 去掉 concat 旧键

### 阶段四 统一通知
- [x] P4-1 新增 `utils/notify.py`：`MODULE_TITLES`/`module_title()`（「下载中心 · 模块名（后缀）」）/`result_text()`（成功/跳过/失败 + 观察期「预览：N 个候选，未执行」）/`notify_module_result()`（默认 Manual 类型、异常吞掉告警返回 False 不中断业务）；开关与消息类型留在各模块调用点
- [x] P4-2 六模块接入（保留原开关与消息类型）：transfer 汇总（suffix 任务已停止/执行完成）、rename `notify_rename_result`、autoremove `_notify` + 观察分支补预览通知（`_config.notify` 门控）、failclean `_send` 标题加统一前缀、hr `SUMMARY_TITLE=module_title("hr")`、uploadlimit 限速写入异常通知；站点标签按方案不新增逐条通知

### 阶段五 数据页清理
- [x] P5-1 重命名归档清理 API（决策 C：连归档状态删除）→ `archive.py::clear_rename_archive`（只删 archived=True，重试期计数保留）+ POST `/cleanup_module_data`（`CleanupModuleRequest/CleanupModuleResult`，白名单外 HTTP 400）；测试 test_cleanup_module_data.py 5 项
- [x] P5-2 其他模块可清理范围核对与实现 → 白名单五对象：rename_archive/rename_history/transfer_stats（stats+skip_stats 两键）/autoremove_state（remover_state）/failclean_state（failclean_status）；hr 已有 clear_task/clear_compliant/clear_missing 不新增；tag/upload_limit 无独立历史不造按钮；transfer_schedule、upload_limit_state 不在名单（测试断言不被触碰）
- [x] P5-3 前端清理入口 + 确认框写明对象/数量/后果 + 只刷新对应模块 → 诊断页「数据清理」块（CLEANUP_TARGETS 五项，数量来自 diagnostics.cleanup_data，0 条禁用按钮）；确认框列 label/数量/后果 + 决策 C 文案（归档清理后可重新识别与补刀）+「不修改下载器任务与文件、H&R 安全状态、活动队列与限速恢复状态」；confirmCleanupData 后按模块刷新（rename→loadHistory+loadArchive、transfer→loadOverview、autoremove/failclean→各自 status、全部 reload diagnostics）

### 阶段六 图标 / 边框 / 文案
- [x] P6-1 共享 `DownloaderBadge.vue`（品牌图标＋实例名），Config/Page 复用 → 品牌色圆标 Q/T/R（qBittorrent #2f7ac0 / Transmission #b52025 / rTorrent #5f7a8a）+实例名，未知类型 mdi-download-outline；纯本地样式不联网不加框架；Config.vue 转移任务列表替换（删 DOWNLOADER_TYPE_ICONS/LABELS/downloaderTypeIcon/downloaderTypeLabel，保留 downloaderTypeOf/downloaderTitle 传 props）；Page.vue 诊断卡源/目标下载器替换（type 来自 diagnostics.downloaders.*.type）
- [x] P6-2 设置页去掉与宿主弹窗重复的外边框/外间距/双层圆角，保持内部布局 → `.dm-config` width 改 100%、去掉 padding 8px；`.dm-card` 去 border-radius:14px 与 1px 边框（双层圆角/边框消除）；media query 同步删除残留行；内部导航分隔线/子页签/表单布局不动
- [x] P6-3 可见文案统一 → Config：导航「命名补刀」→「种子重命名」（desc 同步）、「H&R管理」→「H&R 管理」、「定时重命名/周期」→「定时补查/周期」、自动删种动作「删除任务/及文件」→「删除种子/及文件」（下拉+hint+desc）；Page：流程步骤「兜底补刀」→「定时补查」、卡片 title「命名补刀」→「种子重命名」、指标「定时改名」→「定时补查」、状态行动作三词同步；手动补刀按钮与后端 msg 口径保持一致不改；转移任务配置删除按钮「删除任务」语义正确保留；方案 §9 禁止机械文案断言，未新增文案测试

### 阶段七 验证与交付
- [x] P7-1 新增行为测试（隔离/观察/清理）并与既有回归一起全绿 → 后端 257 passed（含 test_module_panes.py 6 项 transfer 页签联动矩阵，迭代12）；隔离/观察/清理各自测试见阶段二/三/五 Verification
- [x] P7-2 本地真实页面验收七项行为（本地 MP 17430/17431 + 测试下载容器）→ 迭代13 已验 API 层（诊断/隔离/清理/观察回执）+ 修两个线上 bug；迭代13 慢用例补齐（TEXTRA 175s / BATCH120 377s / OBSERVE 18 断言 全 OK）；**迭代21 已用真实浏览器验收**：数据页 8 模块卡 / 7 个「查看记录」/ 4 个「清理」按钮 / 条数选择器=20 / 截断提示真实渲染、诊断页下载器徽标与品牌色、设置弹窗导航文案（H&R 管理、种子重命名）与 `.dm-config` padding=0、清理确认框文案与数量——详见 Verification「迭代21」条目；**仍缺**：肉眼级视觉确认（截屏对比）与「查看记录」按钮的实际点击跳转
- [x] P7-2b 数据页每模块明细（用户 m18492）→ 后端 `_module_details` 七模块（transfer/rename/tag/hr/autoremove/failclean/upload_limit 各含 rows/items/error）+ payload `module_details`；前端 Page.vue 模块卡「运行明细」块（rows 网格 + items 卡片 + error 文本）与 `.dm-module-detail-items` 样式；`test_module_details.py` 6 项；本地 MP 同步 reload 后实测 `module_details` 七键齐全（failclean 12 行含三段计数与跳过统计、rename 9 行、autoremove 5 条候选、transfer 12 行）
- [x] P7-2c 数据页展示体系四项（用户 m18958）：①各模块表现风格统一 ②执行记录查看/清理按钮 ③明细最大条数可调 ④列表显示种子名而非只有 hash —— 现状核对见下方「数据页展示体系核对报告」；用户 m18979 定「GPT-6.1-Sol 出报告 → 主线执行」，已按报告推荐裁决（A 轻量/B 查询参数/C 两层保留＋抽组件/D 旧记录显式回退）实施，报告步骤 1-13 全部落地，全量门禁绿（后端 295 + 前端 39 + build）；**浏览器可视化确认仍阻塞**（见 P7-2，非代码问题）
- 报告流程（用户 m18979）：由 GPT-6.1-Sol（`reviewer` 只读代理，run `d4a85efe-97dc-4460-bc5a-bb61cd89d2a8`）分析并产出「适配低能力模型执行」的报告 → `.ralph/dml-ui-improvement-report.md`；主线按报告步骤执行（四项裁决点需先定稿）
- 执行进度（按报告步骤，迭代15 起）：
  - 环境：本机 `micromamba run -n base python` 实际解析到 hermes venv（无 pytest），统一改用绝对解释器 `C:/app/scoop/apps/micromamba/2.9.0-0/base/python.exe -X utf8`（Python 3.15.0 / pytest 9.1.1）；后端基线 268 passed；插件 3.9.12；`Page.vue` 2590 行
  - 报告裁决：A 轻量按钮映射（复用 cleanup/remove/transfer_stats 端点）｜B 查询参数 `?detail_limit=`（20·50·100·200，默认 20，不落盘）｜C 保留两层展示 + 抽 `ModuleDetailPanel.vue` 统一风格｜D 旧记录显式回退「名称未记录 + 短 hash」，不做回填迁移
  - [x] 步骤1 转移事务保存名称：`modules/transfer/pipeline.py` 事务 item 新增 `source_name`（复用 `utils.torrent_adapter.get_torrent_name`）；测试 +4
  - [x] 步骤2 API 带出名称：`controller/handlers.py::api_transfer_status` pending/records 投影新增 `source_name`（缺失空串）；测试 +2（dict 与 ORM 行形态）
  - 门禁：43 passed（transfer_pipeline + torrent_field_shapes）、53 passed（manual_run_endpoints + transfer_pipeline）
  - [x] 步骤3 前端名称优先（桌面+移动）：`Page.vue` 新增 `transferName`/`transferTitle`（`source_name` 空白视为未记录），在途列表、最近记录桌面表与移动卡三处改为「名称（短 hash 副标签）」，`title` 保留完整 hash；旧记录显示「名称未记录」+ 短 hash
  - [x] 步骤4 明细上限后端贯穿：诊断服务新增 `MODULE_DETAIL_LIMIT_CHOICES=(20,50,100,200)`/`MODULE_DETAIL_ITEM_LIMIT=20`/`resolve_detail_limit()`；`_detail()` 过滤后按上限截断并新增 `total/limit/truncated`（`truncated = 显示条数 < 总数`）；`_rename_history_stats(recent_limit)` 不再固定截 5 条、`_rename_detail` 用真实失败数当 total；`_module_details`/`build_diagnostics(detail_limit)` 逐层透传；测试 +7
  - [x] 步骤5 查询参数贯穿真实路由：`controller/handlers.py::api_diagnostics(plugin, detail_limit: int = 20)` 先校验白名单（白名单外用 HTTP 400 明确拒绝，不让脏值走到 500 路径），再传 `plugin._diagnostics(detail_limit)`；`__init__.py::api_diagnostics`/`_diagnostics` 同步带参（默认 20）；`api_overview` 仍按默认 20 取样本；测试 +2（走 `build_api_routes()` 的真实 endpoint：缺省 20 / 200 穿透 / 21 拒绝且不进构建；handler 默认值与服务白名单同源）
  - [x] 步骤6 首次总览加载与条数选择：`detailLimit` ref（默认 20）+ 每轮刷新带 `?detail_limit=`；watch 只重拉诊断（不落盘、不重载业务数据、响应乱序丢弃、页面销毁后不写）；`moduleDetail()` 带出 `total/limit/truncated` 并兼容旧响应；模板 `.dm-detail-limit-select` 选择器 + 截断提示「仅显示前 N 条，共 M 条…」；`loadOverviewTab()` 接通首次总览加载诊断；测试 `page-setup.test.mjs` +8
  - [x] 步骤7 抽纯展示组件：新增 `frontend.v3/downloadmanagerlocal/src/components/ModuleDetailPanel.vue`（props `title/subtitle/rows/items/total/limit/truncated/error/emptyText`；slots `actions`/默认；error 与 rows 并存；有 rows 无 items 不显示误导空态；截断提示全部由传入数字生成；不 import 插件 API 与业务配置；通用明细 CSS 放在组件自身 `scoped` 样式内，不依赖父组件命中）+ `tests/module-detail-panel.test.mjs` **8 pass**（用项目既有 `@vue/compiler-sfc` + `vue/server-renderer` 编译真实模板做 SSR 渲染断言，编译产物写 `node_modules/.dml-module-detail-panel/`，不比较整段 HTML）
  - [x] 步骤8 逐组接入统一外观（**3/3 组完成**）：第1组（总览卡普通模块运行明细，`Page.vue:1450-1459`）与第2组（上传限速专项，`Page.vue:1396-1434`，专属网格走 `#appendix` 槽、刻意不传 `items` 避免同一数据重复出现）均改用共享组件 `ModuleDetailPanel.vue`；第3组：7 个记录块标题外围统一为 `dm-record-block-head > div > dm-record-block-title`（补齐缺包裹的 `module-data-cleanup`，`Page.vue:2083-2091`），tag 扫描块补「尚未扫描」空态（`Page.vue:1906`，`v-if="!cleanupScan && !cleanupMessage"`，不与扫描结果/提示重复），组内空态由自有 `.dm-cleanup-empty` 改用共享 `.dm-monitor-empty`（删除该样式规则、`.dm-monitor-empty` 补 `gap: 8px`）；随第1组替换删除只服务旧块的三条 item 样式；保留 `data-record-block`、桌面表格、移动卡片与逐条操作；新增 `tests/page-consistency.test.mjs` 5 项结构回归（块清单/标题外围/空态兜底/共享组件仅总览卡透传 items/appendix 专属网格）
  - [x] 步骤9 自动删种清理内存同步：`modules/autoremove/history.py`（新，空模板+`empty_status/history_removed_count/cleared_status`，零插件依赖，供服务与 handler 回退共用）；`service.py` 删本地 `_empty_status` 改从 history 取，新增 `clear_history()`（非阻塞取 `_run_lock`：忙→`{"busy": True}` 不清理；再持 `_lock`：先 `save_data` 成功才改内存；无最近结果→`removed=0` 不写盘）
  - [x] 步骤10 失败清理最近结果/累计分离：`modules/failclean/history.py`（新，`EMPTY_STATUS`＋`as_float/as_counter/history_removed_count/cleared_status(raw)`，清最近结果保留 `total`）；`service.py` 新增状态锁 `RLock`（`_record_result`/`_record_scan_result`/`_load_status`/`_save_status`/`get_module_status` 全走同一把锁，可重入不死锁）、`clear_history()`（保护 `_recent_deletes` 与 H&R 跳过统计，保存失败不改内存）；`STATUS_TEMPLATE` 改从 history 取空模板
  - [x] 步骤11 handler 与数量口径对齐：`controller/handlers.py::_cleanup_actions` 两个清理由「直接写空值」改为「服务在用→`clear_history()`（`busy`→HTTP 409，含明确文案）／服务不在→纯函数判定 `history_removed_count` + `cleared_status`（自动删种归零、失败清理保留累计）」；`modules/diagnostics/service.py::_cleanup_stats` 的 `autoremove_state`/`failclean_state` 改按「有没有最近结果」计 0/1（不再按状态对象是否非空误报）；白名单仍为五项，未加 transfer 来源映射/队列/限速恢复状态
  - [x] 步骤9-11 测试：新增 `tests/v3/downloadmanagerlocal/test_cleanup_runtime_status.py` **11 项**（内存与持久化同步、无历史返回0、忙返回 busy 且不动盘、保存失败保内存、失败清理保 total 与去重状态、只有累计算0、状态锁可重入、计数纯函数口径、handler 忙→409、handler 以服务返回为准）；按新契约更新 `test_cleanup_module_data.py::test_cleanup_actions_whitelist_semantics`（不再是「写成 `{}`」断言）→ 全量 **295 passed in 5.69s**
  - [x] 前端清理链兼容已确认（无需改）：`Page.vue::confirmCleanupData`（777-806）失败走 catch 置 `actionOk=false` + 错误文案，`postJsonApi` 非成功码同样判失败，不假成功；成功后才刷新诊断与对应模块
  - [x] 步骤12 查看与清理入口（`Page.vue`）：新增 `MODULE_RECORD_VIEWS`（7 个有记录模块 → 页签 + `data-record-block`/`data-runtime-section` 锚点，seed 无）与 `MODULE_CLEANUP_KEYS`（只含白名单四对象：rename_history/rename_archive 两个独立按钮、autoremove_state、failclean_state）；`openModuleRecords()` = `selectTab` + `await nextTick()` + 锚点滚动（无真实 DOM 时跳过定位），全过程只发 GET，不触发扫描/预览/补全/重新分配；模块卡新增「查看记录」「清理记录」按钮（`item.count === 0` 禁用，数量取诊断 `cleanup_data`）；清理成功后 rename 分页回第一页、autoremove 清掉 `autoremovePreview`；失败清理确认文案改「只清最近一次执行结果，累计清理统计保留」；transfer/hr/tag/upload_limit/seed 不给清理按钮（hr 复用既有安全清理）
  - [x] 步骤12 测试：`tests/page-setup.test.mjs` 11 → **18 项**（映射覆盖与锚点真实性、清理按钮严格映射白名单且无「全部清理」、0 条禁用与计数口径、七模块查看记录零写请求 + 锚点定位、无 DOM 不抛错、清理后分页/预览同步且只发一条 `cleanup_module_data`、确认框口径）
  - [x] 步骤13 全量门禁：`package.v3.json` JSON OK；后端 `pytest tests/v3/downloadmanagerlocal -q` → **295 passed in 5.77s**；前端 `node --test tests/*.test.mjs` → **39 pass / 0 fail**（config 6 + page 18 + panel 10 + consistency 5）；`npm run build` ✓ built in 1.30s（`__federation_expose_Page-OdumzmAu.js` 221.00 kB、`Page-C7v1bjO4.css` 22.70 kB、`Config-D0KxFYW8.js` 229.08 kB、`Config-B82oEuzP.css` 17.07 kB、`DownloaderBadge-CLJTHaaB.js` 4.61 kB、`remoteEntry.js` 3.78 kB`）
- [x] P7-3 AST 校验、`package.v3.json` 校验、git diff 范围核对、版本三处同步、提交（需用户授权）→ 迭代9 已提交 09f882b5（阶段二~五后端，14 文件 +1205/-556，显式路径暂存核对通过）；**迭代21 完成版本三处同步至 3.9.13**（`__init__.py` / `package.v3.json` version+history / description 修正）；提交推送仍待用户授权（改动集：阶段二~七全部前后端 + 方案与报告文件）
- [ ] P7-4（阻塞·需授权）按方案 10.3 完整包部署到 QNAP 并线上验收
- [x] P7-5 记录最终可重跑命令与产物路径 → Final Verification 命令持续维护；迭代9 补记提交 09f882b5

## 写操作清单（P1-3 产出）

扫描口径：`rg` 全量扫 `plugins.v3/downloadmanagerlocal`（排除 `dist/`）+ 逐模块核对；行号为本轮基线（3.9.12 工作树）。

| 模块 | 入口 | 实际写函数（文件:行） | 现有观察判断 | 关联后续动作 |
| --- | --- | --- | --- | --- |
| 转移做种 | `TransferComplete` 延迟批次；`TorrentTransferFallback` interval；手动 `/transfer_run` 等 | `modules/transfer/service.py:108,134,155` `downloader.add_torrent`；`modules/transfer/pipeline.py:76,160` `delete_torrents(delete_file=False)`（源/目标回滚）、`:171,230,265` `start_torrents`、`:221` `recheck_torrents`；`utils/torrent_adapter.py:132` `delete_torrents(delete_file=True)`（删源带文件）；转移后改名 `service.py:215,614` 交给 rename 模块 | 无 | 删源须先确认目标完整；失败 3 次进终态；删源经 H&R guard |
| 种子重命名 | `DownloadAdded` 事件（防抖）；`DownloadCenterRenameScan` cron；`/retry_renames`、`/retry_rename`、`/recovery_torrent`、`/delete_rename_history`、`/restore_rename_archive`、`/delete_rename_archive` | `modules/rename/service.py:400,446` `dl.rename_torrent`、`:36` `trc.rename_torrent_path`（TR）、`:854` `dl.set_torrents_tag([RENAME_TAG])`；`controller/handlers.py:499` `dl.rename_torrent(original_name)`（恢复原名） | 无 | 失败写 `rename_retry_state` 归档；归档恢复/删除改变重试行为 |
| 站点标签 | `DownloadAdded` 事件（即时补全＋临时标签回收）；`DownloadCenterSiteHistory` cron；`/tag_cleanup_scan`、`/tag_cleanup_execute` | `modules/sitetag/service.py:45,252` `remove_torrents_tag`、`:47,243` `delete_torrents_tag`、`:455,659` `set_torrents_tag` | 无 | 临时标签回收；分类/剧名标签；站点标签被上传限速读取 |
| H&R 管理 | `HitAndRunCheck`/`Discover`/`Summary` 调度；`DownloadAdded`、`PluginTriggered`、`PluginAction` 事件；`/hr_check`、`/hr_scan`、`/hr_clear_*` | `modules/hr/scanner.py:223` `set_torrents_tag`、`:240` `remove_torrents_tag` | 无 | 是四条破坏性删除路径的保护闸门（`modules/hr/guard.py::HrGuard.should_skip`） |
| 自动删种 | `AutoRemoveTorrents` cron；`/autoremove_run`（`/autoremove_preview` 只读） | 单一漏斗 `modules/autoremove/service.py::_apply_action`（331–343）：pause→`stop_torrents`、delete→`delete_torrents(delete_file=False)`、deletefile→`delete_torrent_with_files`（→`utils/torrent_adapter.py:132`） | **有**：`migration_observe_only`→`self._observe_only`（`constants.py:15,30`、`service.py:87,132`） | 删前查 H&R guard（pause 跳过 guard）；结果写 `remover_state` |
| 失败清理 | `TransferFailed` 事件；`DownloadCenterRepeatCleanup` cron；`/failclean_scan` | `modules/failclean/hostapi.py:60` `delete_media_file`→`StorageChain().delete_media_file`、`:70` `delete_download_history_file`→`DownloadHistoryOper().delete_file_by_fullpath`、`:75` `send_download_file_deleted` | 无 | 同 (hash,路径) 30 秒去重；`failcleanup_retain_hours` 保留期 |
| 上传限速 | 30 秒常驻 worker（`modules/uploadlimit/worker.py`）；`DownloadAdded` 唤醒；`/upload_limit_reallocate`、`/upload_limit_site_rules_update`、`/upload_limit_disable_restore` | `adapter/upload_limit.py:73` `write_global_upload_limit`、`:122` `restore_global_upload_settings`、`:272` `write_torrent_upload_limit`、`:322` `restore_torrent_upload_settings` | 无 | 停用恢复走 compare-and-set；grace 期不写单种额度 |
| 同步删除（支撑层） | `DownloadFileDeleted`/`DownloadDeleted`、`WebhookMessage`、`PluginAction` | `modules/cleanup/service.py:180` `delete_torrents(delete_file=True)` | 无 | 经 H&R guard |

阶段二/三直接可用的结论：

1. 观察门控只需落在少数漏斗函数上：autoremove `_apply_action`、uploadlimit 4 个 write/restore、rename 3 处改名 + 1 处打标、sitetag 4 处标签写、hr 2 处标签写、transfer 的 add/delete/start/recheck、failclean hostapi 3 处、cleanup 1 处。
2. 现有观察实现仅 autoremove，且默认 True（`constants.py:30` 表单默认、`service.py:87` 缺省回退 True）——决策 A 要求的“其他模块保持升级前行为”即这些新键默认 False。

## Verification
- 基线实测（阶段一，3.9.12 工作树）：`python -m json.tool package.v3.json` OK；`pytest tests/v3/downloadmanagerlocal -q --tb=short` → **201 passed in 4.76s**；`node --test tests/config-setup.test.mjs` → **5 pass / 0 fail**；`npm run build` → OK（1.52s，产出 `__federation_expose_Config-BUXSx-eE.js` 223.76 kB、`__federation_expose_Page-DzhQdK7y.js` 194.99 kB、`remoteEntry.js`）
- 基线命令：仓库根 `micromamba run -n base python -m pytest tests/v3/downloadmanagerlocal -q --tb=short`；`frontend.v3/downloadmanagerlocal` 下 `node --test tests/config-setup.test.mjs`、`npm run build`
- 参考基线：后端 201 passed，前端 5 passed（历史参考，新增用例后允许增加）
- 迭代1（阶段二 P2-1/P2-2，本轮）：`micromamba run -n base python -m pytest tests/v3/downloadmanagerlocal -q --tb=short` → **210 passed**（基线 201 + 新增 9）；AST 校验 7 个改动文件全 OK；新增用例：test_gating.py 5 项（fault 帮助函数、门控解析关闭不解析、坏配置只标记、总开关关闭不解析）、test_module_isolation.py 4 项（故障标记不落盘、构造异常隔离、转移配置错误不关总开关、上传限速边界）
- 迭代1 生产代码改动：`utils/config.py`（+record_module_fault/clear_module_fault/module_faults）、`core/config.py`（+_module_config_guarded/_downgrade_faulted_module_gates）、`core/lifecycle.py`（+_mark_transfer_config_invalid/_init_upload_limit_isolated、_init_service_isolated 重写）、`modules/transfer/service.py`（+2 处 rename 模块关闭门控）、`modules/diagnostics/service.py`（+_module_fault_checks、payload 增 module_faults）
- 迭代2（阶段二 P2-3 完成）：`micromamba run -n base python -m pytest tests/v3/downloadmanagerlocal -q --tb=short` → **212 passed**（迭代1 210 + 新增 2）；完整 final command 全绿：`package.v3.json` JSON OK、前端 `node --test` **5 pass**、`npm run build` ✓ built in 1.49s
- 迭代2 生产代码改动：`core/lifecycle.py`（+_stop_isolated/_stop_background_services，`stop_plugin_service` finally 改为逐个隔离停止）；`core/scheduler.py`（build_plugin_services 改 `(module, builder)` 对，模块在 `module_faults` 中直接跳过声明）；新增用例 test_stop_plugin_service_isolates_failing_stop、test_scheduler_skips_faulted_module_declaration
- 迭代3（阶段二 P2-4/P2-5 完成）：后端 `micromamba run -n base python -m pytest tests/v3/downloadmanagerlocal -q --tb=short` → **220 passed in 4.58s**（迭代2 212 + 新增 3 守护闸门 + 5 隔离/诊断）；前端 `node --test tests/config-setup.test.mjs` → **5 pass / 0 fail**；`npm run build` → ✓ built in 1.51s（`__federation_expose_Page-Fxa_Tq7z.js` 195.85 kB、`__federation_expose_Config-BUXSx-eE.js` 223.76 kB、`remoteEntry.js`）
- 迭代3 生产代码改动：`core/lifecycle.py`（+`_hr_protection_expected`/`_sync_hr_guard_intent`）；`modules/hr/service.py`（`mark_unconfirmed()` 三处中断路径 + 已有 `_refresh_guard`）；`modules/hr/guard.py`（`expect`/`mark_unconfirmed`/`unconfirmed`，迭代3前已加但本轮补测试）；`frontend.v3/downloadmanagerlocal/src/components/Page.vue`（诊断卡「故障」状态与图标、`moduleFaultLabels`/`moduleFaultItems` 汇总项、自动删种「保护闸门：无法确认（已保守跳过）」、`.dm-diagnostic-card--error` 样式）
- 迭代4（阶段三 P3-1/P3-4，本轮）：后端 `micromamba run -n base python -m pytest tests/v3/downloadmanagerlocal -q --tb=short` → **227 passed in 4.61s**（迭代3 220 + test_gating 观察口径 3 项 + test_observe_mode 4 项）；完整 final command 全绿：`package.v3.json` JSON OK、前端 `node --test` **5 pass / 0 fail**、`npm run build` ✓ built in 1.39s（`__federation_expose_Config-C_2t-JXj.js` 224.55 kB、`__federation_expose_Page-D9zaBXab.js` 195.90 kB、`remoteEntry.js`）；AST 校验 7 个改动文件全 OK
- 迭代4 生产代码改动：`utils/config.py`（+`OBSERVE_ONLY_KEYS`/`LEGACY_OBSERVE_ONLY_KEYS`/`OBSERVE_ONLY_DEFAULTS`、`PLUGIN_CONFIG_DEFAULTS` 增 7 键=117、`module_observe_only`/`build_module_observe_flags`/`module_observe_flags`/`observe_only`）；`core/config.py`（+`plugin._module_observe_only` 快照）；`modules/autoremove/service.py`（观察值改读 `module_observe_only(source,"autoremove")`，移除 `as_bool`/`MIGRATION_OBSERVE_ONLY_KEY` 直接引用）；`modules/uploadlimit/service.py`（+两处观察守卫）；`frontend.v3/downloadmanagerlocal/src/components/Config.vue`（defaults 增 7 观察键=false、`OBSERVE_ONLY_KEYS` 常量、`initialConfig` 为空时打开观察、transfer 重置键集加 `transfer_observe_only`）；`Page.vue`（上传限速状态映射 +「观察模式」）
- 迭代4 测试基建改动（桩同步，非产品代码）：`test_gating.py`（键数 110→117 断言、+3 用例）、新增 `test_observe_mode.py`（4 用例）、`test_transfer_active_gate.py`（autoremove constants 桩补 `MIGRATION_OBSERVE_ONLY_KEY`，否则 `utils/config.py` 导入失败）
- 迭代4 待办提示：`PANE_RESET_KEYS.transfer` 是显式数组（新增 transfer 观察键必须手工加入）；后端 `PLUGIN_CONFIG_DEFAULTS` 的观察键默认 True 仅对空配置生效（老配置不带新键 → False）
- 迭代5（阶段三 P3-2 前半，本轮）：后端 `micromamba run -n base python -m pytest tests/v3/downloadmanagerlocal -q --tb=short` → **231 passed in 4.63s**（迭代4 227 + 新增 test_observe_boundaries 4 项）；完整 final command 全绿：`package.v3.json` JSON OK、前端 `node --test` **5 pass / 0 fail**、`npm run build` ✓ built in 1.48s；AST 校验 5 个改动文件全 OK
- 迭代5 生产代码改动：`utils/config.py`（+`OBSERVE_PREVIEW_SAMPLE_LIMIT=20`/`OBSERVE_MODULE_LABELS`/`record_observe_preview`/`observe_skip`/`observe_previews`）；`modules/failclean/service.py`（`_delete_source_file` 顶部观察守卫，返回 `deleted=0/skipped=True`）；`modules/hr/service.py`（`register_task` 打标、`_remove_tag` 移除标签两处 `observe_skip` 守卫）；`modules/diagnostics/service.py`（payload 增 `module_observe_only`/`observe_previews`，并修回被误替换的 `"checks"` 键）
- 迭代5 测试基建改动：新增 `test_observe_boundaries.py`（4 项：观察期 failclean 不删文件/不删历史且返回 skipped、观察期 hr 不打标/不移除标签但纳管照常、两者未观察时原写路径照做，并校验 `observe_previews` 计数与样本）；`test_failclean_scan.py` 的 `utils.config` 桩补 `observe_skip`
- 迭代5 待办提示：日志前缀契约 `test_log_prefix_contract.py` 的 I3 只接受 `MODULES` 内模块段，共享守卫日志用裸前缀 `【PT下载中心】观察模式[模块]`；观察预览上限 20 条/模块，对外出口只有诊断 payload 的 `observe_previews`
- 迭代6（阶段三 P3-2 后半，本轮）：后端 `"C:/app/scoop/apps/micromamba/2.9.0-0/base/python.exe" -X utf8 -m pytest tests/v3/downloadmanagerlocal -q --tb=short` → **236 passed in 4.92s**（迭代5 231 + test_observe_boundaries_rename_tag 5 项）；P3-2 全部写边界完成；完整 final command（新解释器绝对路径）全绿：JSON OK、236 passed、前端 `node --test` **5 pass / 0 fail**、`npm run build` ✓ built in 1.35s（产物哈希不变）
- 迭代6 生产代码改动：`modules/rename/service.py`（守卫 4 处：`retry_failed_renames`/`retry_rename_by_hash`/`rename_candidate`/`_handlers` 前置 `observe_skip`；顶层 `from ...utils.config import ...` 改函数内懒导入破循环；`retry_failed_renames` 内 `from ...utils.tag_cleanup import normalize_tags` 同步懒导入）；`modules/sitetag/service.py`（`_apply_metadata`/`execute_tag_cleanup` 守卫，`_apply_metadata` 顶部懒导入 `observe_skip`）
- 迭代6 测试基建改动：新增 `test_observe_boundaries_rename_tag.py`（5 项：观察期 rename_candidate 不写下载器且登记样本、未观察时照常 rename_torrent、观察期 _apply_metadata changed=False+observe_only、未观察时照常写入、观察期 execute_tag_cleanup 返回预览回执）；`test_module_isolation.py`/`test_contract_backends.py` 的 `utils.config` 桩补 `observe_skip`/`module_observe_flags` 等、`model.state` 桩补 `RENAME_RETRY_STATE_KEY`
- 禁止：真实种子写操作测试、清空配置、用 HTTP 200/文件已上传代替线上页面验收

- 迭代9（阶段五 P5-1/P5-2，本轮）：后端 **251 passed in 5.0s**（迭代8 246 + test_cleanup_module_data 5 项）；完整 final command 全绿：JSON OK、251 passed、前端 `node --test` **6 pass / 0 fail**、`npm run build` ✓ built in 1.29s；AST 校验 5 个改动文件全 OK
- 迭代9 生产代码改动：`modules/rename/archive.py`（+`clear_rename_archive`，决策C 只删 archived=True 连归档状态、重试期计数保留）；`model/api.py`（+`CleanupModuleRequest{module}`/`CleanupModuleResult{module,removed}`）；`controller/handlers.py`（+`api_cleanup_module_data`：`_cleanup_actions` 白名单 rename_archive/rename_history/transfer_stats/autoremove_state/failclean_state，白名单外 HTTP 400）；`core/lifecycle.py`（stop 时释放 5 个数据清理锁）；`modules/diagnostics/service.py`（迭代10 补：`cleanup_data` 数量统计供确认框显示；迭代9 原记录的「cleanup_locked 锁标记」实际未实现，前端不禁用改为 0 条禁用）
- 迭代9 测试：新增 `test_cleanup_module_data.py` 5 项（归档清理只删 archived、空态/全归档、白名单语义与不触碰 transfer_schedule/upload_limit_state、未知模块 400）
- 迭代9 提交：**09f882b5**「feat(dml): 模块隔离与观察模式+统一通知+数据清理后端（阶段二~五）」14 文件 +1205/-556；显式路径 git add（暂存仅本轮 14 文件，`.ralph/` 在 gitignore 除外）；未推送（等待阶段七统一推送）
- 迭代9 反思要点：①效率——前两轮插入等待浪费时间，改为直接并行开跑；②链路风险——P5 后端端点未经 HTTP 层验证，合并进 P7-2 一起本地页面验收；③范围——阶段五只做「历史/统计/归档」，不碰下载器数据/安全状态/队列，符合方案 §7；④循环状态——9/40 迭代、7 阶段完成 5 个，P5-3/P6 合并一轮 + P7 一轮即可收口

- 迭代10（阶段五 P5-3 + 阶段六 P6-1，本轮）：完整 final command 全绿：JSON OK、后端 **251 passed**、前端 `node --test` **6 pass / 0 fail**、`npm run build` ✓ built in 1.31s（新增 `DownloaderBadge-CLJTHaaB.js` 4.61 kB 独立 chunk；`__federation_expose_Page-BRkvuETa.js` 204.07 kB、`__federation_expose_Config-DSh4LybG.js` 229.07 kB）
- 迭代10 生产代码改动：后端 `modules/diagnostics/service.py`（+`_cleanup_stats(plugin, archive_stats)`，constants 懒导入，payload +`cleanup_data` 五对象数量）；`controller/handlers.py`（`clear_transfer_stats` 改条数口径 len(data)，与诊断数量一致）。前端新增 `src/components/DownloaderBadge.vue`；`Config.vue`（import badge、转移任务路由替换、删 4 个图标函数/常量）；`Page.vue`（import badge、诊断卡下载器替换、+`CLEANUP_TARGETS`/`cleanupCounts`/`openCleanupDialog`/`confirmCleanupData`、诊断页数据清理块、清理确认框、dm-cleanup-* 样式）
- 迭代10 口径说明：transfer_stats 数量 = len(transfer_stats)+len(transfer_skip_stats) 条；autoremove_state/failclean_state 记录型对象按 1 条计（与后端清理返回一致）
- 迭代11（阶段六 P6-2/P6-3，本轮）：完整 final command 全绿：JSON OK、后端 **251 passed in 5.04s**、前端 `node --test` **6 pass / 0 fail**、`npm run build` ✓ built in 1.30s（`__federation_expose_Config-D0KxFYW8.js` 229.08 kB、`__federation_expose_Page-BPlBr1Tn.js` 204.07 kB）；改动仅 Config.vue/Page.vue 两文件（样式+文案），零后端改动；剩余：P7-2 本地 MP 验收（m17354）→ QNAP 部署另行授权
- 迭代12（P7-1 矩阵测试，本轮）：完整 final command 全绿：JSON OK、后端 **257 passed in 5.21s**（251 + `test_module_panes.py` 6 项）、前端 `node --test` **6 pass / 0 fail**、`npm run build` ✓ built in 1.31s
- 迭代12 新增 `tests/v3/downloadmanagerlocal/test_module_panes.py` 6 项（transfer 页签联动矩阵，全部行为断言非 tautology）：rename 关→转移后补刀不发生且 tag 联动不受影响、rename 开→补刀执行、双开→互不阻断、transfer_rename_enabled=False 优先拦截、一键补刀 rename 关→明确回执跳过、rename 开→走过门控到下一层回执。与 test_transfer_tasks_engine 已有的 post_transfer_process rename on/off（234/255/276 行）部分重叠但断言维度不同（tag 联动 + 一键补刀门控为新增覆盖）
- 迭代12 关键教训（测试基建）：①`_module` 替身里 `__path__` **不能 pop 后漏赋**——engine 版靠 `attrs` update 自带 `__path__`，pop 后必须显式 `result.__path__ = path`，否则桩变成非包，相对导入报 "is not a package"（首轮 6 errors 根因，DBG 打印 `path: None` 定位）；②transfer/service 导入链需要 `modules/hr.guard` 桩，单文件跑靠 namespace-package 侥幸通过、全量被前序文件残留的空 hr 包破坏（单过全挂），必须显式装桩不依赖文件序；③fixture 疑难用「临时 DBG 打印 sys.modules 桩的 `__path__`/`__spec__`」+ 顺序实验（单文件/全量/交错）定位，比逐行 diff 更快
- 迭代12 口径修正：此前任务文件记录的「test_module_linkage.py 5 项」**不存在**（迭代11 计划记录失实，磁盘上从未有该文件）；矩阵语义实际落在 test_module_panes.py（本轮新增）+ test_transfer_tasks_engine.py 既有联动测试
- 迭代13（P7-2 本地 MP 实机验收 + 两个线上 bug 修复，本轮）：后端 **262 passed in 5.39s**（257 + test_relative_imports 3 + test_api_body_annotations 2）；前端 6 pass、build ✓ 1.32s
- 迭代13 本地实例启动口径（修正 mp.ps1 失效项）：`micromamba 2.10` 的 `run -n mp3` 报 `prefix does not exist`（mp3 实际在 `C:/app/scoop/apps/micromamba/2.9.0-0/base/envs/mp3`），直接绝对路径 `C:/app/scoop/apps/micromamba/2.9.0-0/base/envs/mp3/python.exe app/main.py` + `set -a && source config/app.env` 可起；前端 `node public/service.js`。（mp.ps1 在 2.10 环境下 Start-Process 起的进程随即退出）
- 迭代13 修复 bug①：`modules/diagnostics/service.py::_cleanup_stats` 两处懒导入写成 `from ..modules.autoremove.constants` / `from ..modules.failclean.constants`（`..` 已指向 `modules`，多一层 → `No module named 'app.plugins.downloadmanagerlocal.modules.modules'`），诊断接口线上 500；同一函数 `from ..model.state` 也少一层（应为 `...model.state`）。四处改对后诊断 200
- 迭代13 修复 bug②：`__init__.py` 六个端点 `payload=None` 无类型注解 → FastAPI 当 query 参数，JSON body 永远为空；实测 `/cleanup_module_data` 无论传什么都 400「module Field required, input_value={}」。改 `cleanup_module_data` 为 `payload: CleanupModuleRequest`（顶层补 import），其余五个（`autoremove_run`/`autoremove_preview`/`failclean_scan`/`transfer_run`/`tag_complement`，均不读字段）改 `payload: dict | None = None`。修后实测：白名单外 `transfer_schedule` → 400「未知的数据清理对象」，白名单内 `failclean_state` → 200「已清理 1 条」
- 迭代13 新增防复发静态测试：`test_relative_imports.py`（3 项：全插件相对导入磁盘可解析、能检出 `..modules.x` 少/多层错误、`..` 同级与 `...` 顶层正例）；`test_api_body_annotations.py`（2 项：`__init__.py` 所有 `payload*` 参数必须有注解、能检出无注解反例）
- 迭代13 本地验收实测结果：①观察模式 rename=true 时 `retry_renames` 立即返回「补刀已开始」（后台执行，预览计数需等后台线程，`observe_previews` 首查为空）；②关 `tag_enabled` 后 reload：`module_faults={}`、`form` 仍 200、诊断 checks 里「站点标签=off」其余 ok，模块隔离成立；③`cleanup_data` 真实数量 rename_archive 31 / rename_history 34 / transfer_stats 6 / autoremove_state 1 / failclean_state 1
- 迭代13 用户新增约束（m18505）：本地 MP + **测试下载容器** 做场景预判测试通过后才允许 QNAP 部署实测；用户新增需求（m18492）：数据页每个模块面要展示明细（失败清理目前只有数字）→ todo #82
- 迭代13 待办提示：本地 `test-qb`/`test-qb-2` 两个下载器均「未连接」，观察期写边界与转移链路只能等测试容器起后才能真跑；本机 bash 无 `docker` 命令（需确认测试容器入口）
- 迭代13 测试环境打通（用户 m18574「测试用下载器以及测试种子」+ m18583「先进行本地 mp 测试」）：测试下载器是 **WSL 容器**（`C:/Program Files/WSL/wslc.exe`，WSL 3.0.3.0），六个容器 `dml-test-qb`(29080→8080) / `dml-test-qb2`(29082) / `dml-test-tr`(29091→9091) / `dml-test-tr2`(29092) / `dml-test-rt`(29580→80) / `dml-test-rt2`(29582) 已存在但 Exited；`wslc start <name>` 逐个启动（**一次只接受一个容器名**），`wslc list` 确认 Up，六个端口 TCP+HTTP 200 全通
- 迭代13 种子夹具：`D:/work/tmp/dml-test/seed_clients.py --n 12` 灌种（rt/rt-2/tr-2 已存在 12 个，qb/qb-2/tr 新加 12 个），`--status` 汇总 6/6 实例就绪；测试种子为自造 info_hash（announce `udp://tracker.dml-test.local:6969/announce`），数据文件在 `D:/work/tmp/dml-test/downloads`（容器内 /downloads），因此入库即显示完成、无需真实做种
- 迭代13 关键坑（已修正）：下载器容器起晚于 MP 启动时，MP 的 downloader 实例不会自愈（诊断 `available=false`「不可用」，日志「下载器 test-qb 未连接，跳过本次检查」）；但**不需要重启 MP**——harness 调用 `plugin/reload` 后实例即重建（16:31 实测 `downloaders.from/to = 连接正常`）。**另一个坑**：`bg_task stop` 只杀 wrapper，detached 的 python 子进程会存活（PID 20176 自 15:55:50 一直在 17430 监听，`bg-60` 与用户 `mp.ps1 start`（`bg-56`）都因此绑不上端口而退出）；重启 MP 必须按 PID/端口杀，或先 `netstat -ano | grep 17430` 确认无监听；实测 `downloaders.from/to = 连接正常`、`observe` 七键全 false（决策 A：老配置保持升级前行为）、`faults={}`、`cleanup_data` rename_archive 31 / rename_history 34 / transfer_stats 6 / autoremove_state 1 / failclean_state 0
- 迭代13 本地 MP 启动口径（可复用）：`cd /d/test/MoviePilot-v3 && set -a && source config/app.env && exec "C:/app/scoop/apps/micromamba/2.9.0-0/base/envs/mp3/python.exe" app/main.py`（后端 17430，**当前活实例 PID 20176，自 15:55:50 起持续监听；bg-60 因端口占用已退出**）；前端 `node public/service.js`（17431，`bg-59`）；MP 数据目录 `D:/test/MoviePilot-v3/config`，本地插件作用域已限定测试下载器（`remover_downloaders=["test-qb"]`、`rename_downloaders=["test-qb-2"]`、transfer 任务 `test-qb→test-qb-2` 且 `include_labels=TEXTRA`），不会碰真实种子
- 迭代13 场景回归驱动：`D:/work/tmp/dml-test/regress_all.py`（快用例集 FIXTURE/PYTEST/MUT/RM/TAG/REN/HR/FC/ULPAGE，慢用例 TEXTRA/BATCH120 加 `--slow`）。**必须先改 `PY` 为绝对解释器**：`PY = ["C:/app/scoop/apps/micromamba/2.9.0-0/base/python.exe", "-X", "utf8"]` —— 原 `micromamba run -n base python` 在 PATH 有 hermes venv 时解析到 `C:\Users\wff19\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe`（错环境）。后台任务 `bg-61` 正在跑
- 迭代13 回归阶段结果（快用例集，进行中）：FIXTURE 退出码 0（6s）；PYTEST **262 passed**（7s，与仓库全量一致）；MUT 6/6 语义变异全被抓住（10s）；RM 断言 **19/19 PASS**（29s）；TAG 断言 **10/10 PASS**（38s，含自定义站点标签、幂等、下载器过滤、现场恢复无损键）；REN **18/18 PASS**（199s）、HR **21/21 PASS**（24s）、FC **17/17 PASS**（3s）、ULPAGE **70/70 PASS + 1 SKIP**（16s）→ **[回归] 全部通过**，场景断言合计 155 条 + 262 单测 + 6 变异全中；慢用例另起后台任务跑 `--slow --only TEXTRA BATCH120`（TEXTRA 删源端到端 ≤1800s、BATCH120 120 种子批量 ≤3600s）。日志 `C:\Users\wff19\AppData\Local\Temp\kendex-pi-bg\lanes\01a172fc-99ea-7422-8431-1bcf1d39810f\bg-61-1793262472614.log`，证据目录 `D:/work/tmp/dml-test/modules-evidence/`
- 迭代13 结论（当前）：本地 MP + 测试下载器 + 测试种子的**快用例集回归全部通过**（155 条场景断言 + 262 单测 + 6 变异全中），覆盖 RM/TAG/REN/HR/FC/ULPAGE 六类写路径与数据页；慢用例 `bg-62`：**TEXTRA 删源端到端 20/20 PASS**（175s，转移 delete_source 链路真跑通），BATCH120（120 种子批量）16:37 起进行中（≤3600s），跑完后再下最终结论；**八模块全绿之前不得进 QNAP**（用户 m18505 约束）；观察模式七键与隔离行为已由 API 层验证，真写路径「观察期不写入」由新建 `observe_case.py` 覆盖（待 BATCH120 结束后执行）
- 迭代13 收口（慢用例 + 观察真写）：`bg-62` 慢用例两条全 OK —— `TEXTRA 删源端到端 delete_source=True` **20/20 PASS**（175s）、`BATCH120 120 种子批量一轮收齐` **PASS**（377s，远快于预估 30 分钟）；`bg-63`（链式等 BATCH120 结束后自动跑）`OBSERVE 观察模式七模块零写入` **18 断言 OK**（10s），日志末尾「[回归] 全部通过」。**至此快+慢共 11 步回归全绿**：FIXTURE/PYTEST/MUT/RM/TAG/REN/HR/FC/ULPAGE/TEXTRA/BATCH120/OBSERVE
- 迭代14（#82 数据页模块明细，本轮）：后端 `modules/diagnostics/service.py` 新增 `_module_details(plugin, history, archive)` 与七个模块明细函数（transfer/rename/tag/hr/autoremove/failclean/upload_limit），`build_diagnostics` payload 增 `module_details`；`MODULE_DETAIL_ITEM_LIMIT = 20` 截断候选/失败列表；每个模块明细形如 `{title, rows, items, error}`，单模块读取异常只记 `error` 不影响其他模块（模块隔离）。前端 `Page.vue` 模块卡「运行明细」块（`moduleDetails`/`moduleDetail`/`moduleDetailVisible` + rows 网格 + items 卡片 + error 文本 + `.dm-module-detail-items` 样式）
- 迭代14 验证：完整 final command 全绿 —— `package.v3.json` JSON OK、后端 **268 passed in 5.64s**（262 + `test_module_details.py` 6 项）、前端 `node --test` **6 pass / 0 fail**、`npm run build` ✓ built in 1.40s（`__federation_expose_Page-BgNlHcg1.js` 208.23 kB、`__federation_expose_Config-D0KxFYW8.js` 229.08 kB、`DownloaderBadge-CLJTHaaB.js` 4.61 kB）
- 迭代14 本地 MP 实测：`plugins.v3/downloadmanagerlocal` 全量同步到 `/d/test/MoviePilot-v3/app/plugins/downloadmanagerlocal`（md5 核对 SAME、清 `__pycache__`）→ `POST /api/v1/plugin/reload/DownloadManagerLocal?apikey=<key>` 返回 200 → `GET .../diagnostics` 实测 `module_details` **七键齐全**：failclean 12 行（含「本轮扫描 / 清理 / 失败 / 跳过」「事件删除 / 失败 / 跳过」「累计清理 / 失败 / 跳过」「保留期（小时）」「巡检触发」+ 四类跳过统计）、rename 9 行（含「失败归档 34 / 阈值 3」「历史记录 37」）、autoremove 5 条候选、transfer 12 行。本地 MP key 文件 `D:/tmp/.mp_local_key`（query 参数 `apikey=`）
- 迭代14 阻塞项：浏览器可视化验收未能执行 —— `agent-browser-cli tabs` 返回空、`open` 报「没有可用的浏览器标签页」、`restart` 挂起（被 guardrail kill），判定为浏览器/扩展未就绪而非插件问题；本地 MP 已服务新构建（`app/plugins/downloadmanagerlocal/dist/assets/remoteEntry.js` 指向 `__federation_expose_Page-BgNlHcg1.js`），浏览器就绪后可直接验「运行明细」块与 P6 的图标/边框/文案
- 迭代15（报告步骤1-5 完成，本轮）：完整 final command 全绿 —— `package.v3.json` JSON OK、后端 **284 passed in 5.60s**（迭代14 的 268 + 步骤1 名称写入 4 + 步骤2 API 投影 2 + 步骤4 明细上限 7 + 步骤5 路由穿透 2 + 步骤1-2 期间新增的 shape/回归用例）、前端 `node --test` **6 pass / 0 fail**、`npm run build` ✓ built in 1.28s（`__federation_expose_Page-DajjSWk4.js` 210.45 kB、`__federation_expose_Config-D0KxFYW8.js` 229.08 kB、`DownloaderBadge-CLJTHaaB.js` 4.61 kB）
- 迭代15 报告步骤门禁：步骤4 门禁 `test_module_details.py` **13 passed**；步骤5 门禁（报告原文命令）`test_manual_run_endpoints.py + test_module_details.py + test_api_body_annotations.py + test_relative_imports.py` → **37 passed in 0.83s**
- 迭代15 口径裁决（自查发现并修正）：`_detail()["truncated"]` 语义定为「**显示条数 < 声称总数**」（`count > len(shown)`），而非「总数超过上限」——否则调用方给出真实 total（如重命名失败 34 条）但样本已截断时会出现「显示不全却报未截断」。写入 `test_detail_ignores_invalid_items_and_keeps_caller_total` 固化
- 迭代15 测试基建改动：`test_manual_run_endpoints.py` 的 `utils.config` 桩补 `module_faults`/`module_observe_flags`/`observe_previews`（handler 内懒导入真实诊断服务取白名单常量所致）
- 迭代15 未做：非整数查询参数（`?detail_limit=abc`）走真实 FastAPI 解析应返回 422 —— 未验证（本仓库单测用 `fastapi` 替身，无真实 ASGI 应用），列为待验项，不得写成已验证
- 迭代16（报告步骤6 完成；步骤7-8 未实施）：完整 final command 全绿 —— `package.v3.json` JSON OK、后端 **284 passed in 5.52s**、前端 **`node --test tests/config-setup.test.mjs tests/page-setup.test.mjs` → 6 + 11 pass / 0 fail**、`npm run build` ✓ built in 1.25s（`__federation_expose_Page-v7Rpvwqa.js` 212.88 kB、`__federation_expose_Config-D0KxFYW8.js` 229.08 kB、`__federation_expose_Page-DksSZdRP.css` 21.69 kB、`DownloaderBadge-CLJTHaaB.js` 4.61 kB`）
- 迭代16 生产代码改动（仅步骤6）：`Page.vue`（`DETAIL_LIMIT_CHOICES`/`detailLimit`（:17-18）、`diagnostics?detail_limit=`（:691）、`watch(detailLimit)` 只重拉诊断（:705）、`moduleDetail()` 兼容旧响应并带 `total/limit/truncated`（:760-762）、模板条数选择器（:1346-1352）与截断提示（:1457）、`.dm-detail-limit-select` 样式（:2230））；**未新增 `ModuleDetailPanel.vue`，steps 7-8 未做**
- 迭代16 测试基建改动：`page-setup.test.mjs` 新增记录型 harness（`mountRecording(handlers)` 记录 get/post 调用并可注入 promise）+ 8 项行为测试：总览单次诊断且带 `detail_limit=20`、切模块/诊断页签各一次且诊断页不重复、条数改写只发一条 `diagnostics?detail_limit=200` 且零 POST（不落盘）、乱序响应丢弃旧结果、销毁后不写状态、`moduleDetail` 兼容旧响应、白名单与后端一致 + 模板绑定断言
- 迭代16 未做（如实记录，不得写成已完成）：**步骤7-8 抽组件未实施**（`ModuleDetailPanel.vue` 不存在）、`?detail_limit=abc` 的 FastAPI 422 未验、浏览器可视化验收仍受浏览器不可用阻塞
- 迭代17（反思检查点 + 报告步骤7 + 步骤8 第1组）：完整 final command 全绿 —— `package.v3.json` JSON OK、后端 **284 passed in 5.42s**（本轮零后端改动）、前端 **`node --test tests/config-setup.test.mjs tests/page-setup.test.mjs tests/module-detail-panel.test.mjs` → 6 + 11 + 8 = 25 pass / 0 fail**、`npm run build` ✓ built in 1.28s（`__federation_expose_Page-Bw93DmOM.js` 214.23 kB、`__federation_expose_Page-jeYheICM.css` 22.65 kB、`__federation_expose_Config-D0KxFYW8.js` 229.08 kB、`DownloaderBadge-BUiqiauh.css` 0.60 kB`）
- 迭代17 生产代码改动：新增 `frontend.v3/downloadmanagerlocal/src/components/ModuleDetailPanel.vue`（纯展示，无 API 依赖）；`Page.vue`（:5 `import ModuleDetailPanel from './ModuleDetailPanel.vue'`、:1445-1454 总览卡运行明细改用该组件、删除随替换失效的三条 item 样式）
- 迭代17 测试基建改动：新增 `frontend.v3/downloadmanagerlocal/tests/module-detail-panel.test.mjs` 8 项（编译真实 SFC + SSR 渲染断言：空态、有 rows 无 items 不出空态、error 与 rows 并存、截断数字来自 props 不硬编码 20、default slot 取代 rows/items、actions slot、长文本原样渲染 + 换行类、组件不依赖 API/业务模块）
- 迭代17 未做（不得写成已完成）：步骤8 第 2/3 组（上传限速套同外围 + default slot、专项页标题/操作区/空态外围收敛）、`?detail_limit=abc` 的 FastAPI 422、浏览器可视化验收（仍受浏览器不可用阻塞）
- 迭代18（报告步骤8 第2/3组，本轮）：完整 final command 全绿 —— `package.v3.json` JSON OK、后端 **284 passed in 5.55s**（本轮零后端改动）、前端 **`node --test tests/config-setup.test.mjs tests/page-setup.test.mjs tests/module-detail-panel.test.mjs tests/page-consistency.test.mjs` → 6 + 11 + 10 + 5 = 32 pass / 0 fail**、`npm run build` ✓ built in 1.31s（`__federation_expose_Page-CLeu9i7D.js` 215.72 kB、`__federation_expose_Page-BxAt9swu.css` 22.47 kB、`__federation_expose_Config-D0KxFYW8.js` 229.08 kB、`DownloaderBadge-CLJTHaaB.js` 4.61 kB、`remoteEntry.js` 3.78 kB`）
- 迭代18 生产代码改动（仅 `Page.vue`）：第2组 上传限速专项明细套共享组件（`Page.vue:1396-1434`，`#appendix` 槽承载 `dm-upload-status-grid`/`dm-upload-site-status-*` 两套专属网格，行内注释说明不传 `items` 的理由）；第3组 7 记录块标题外围统一（`module-data-cleanup` 补 `dm-record-block-head` 包裹，`Page.vue:2083-2091`）、tag 扫描块补未扫描空态（`Page.vue:1906`）、组内空态改用共享 `.dm-monitor-empty`（`Page.vue:1936`）并删除 `.dm-cleanup-empty` 样式、`.dm-monitor-empty` 补 `gap: 8px`
- 迭代18 结构性核对（只读脚本 `D:/work/tmp/dml-test/check_record_blocks.mjs`，可重跑，读 Page.vue 按 `data-record-block` 切块统计）：修复后 7/7 记录块 head+title+空态/数据面 全 OK（`not-uniform=0`）；修复前 6/7 OK，`module-data-cleanup` MISS（有 title 无 head 包裹）——以此为准做的最小修复
- 迭代18 新增测试：`frontend.v3/downloadmanagerlocal/tests/page-consistency.test.mjs` 5 项（记录块清单稳定、标题外围一致、空态/数据面兜底、共享明细组件仅总览卡透传 items 且必带 total/limit/truncated、上传限速必须走 `#appendix` 且不传 items）；`module-detail-panel.test.mjs` 本轮由 8 增至 10 项
- 迭代18 未做（不得写成已完成）：`?detail_limit=abc` 的 FastAPI 422、浏览器可视化验收（图标/边框/文案与明细渲染仍无可视确认）、步骤9-13
- 迭代19（报告步骤9-11，本轮）：后端全量 **295 passed in 5.69s**（284 → +11）；改动 `modules/autoremove/history.py`（新）、`modules/autoremove/service.py`、`modules/failclean/history.py`（新）、`modules/failclean/service.py`、`controller/handlers.py`、`modules/diagnostics/service.py`、`tests/v3/downloadmanagerlocal/test_cleanup_runtime_status.py`（新）、`tests/v3/downloadmanagerlocal/test_cleanup_module_data.py`（按新契约更新断言，非删断言）；前端源码与 `dist/` 本轮零改动
- 迭代19 交付语义：①清理记录不再「清完仍显示」（服务内存与持久化同步，失败不假成功）②失败清理「清最近结果、保留累计计数」③清理与运行竞争返回 HTTP 409 ④数据页清理条数按「有无最近结果」计 0/1，不再按状态对象是否非空误报
- 迭代19 全量门禁（本轮末补跑，前后端一起绿）：`package.v3.json` JSON OK；后端 `pytest tests/v3/downloadmanagerlocal -q` → **295 passed in 5.69s**；前端 `node --test tests/*.test.mjs` → **32 pass / 0 fail**；`npm run build` ✓ built in 1.32s（`__federation_expose_Page-CLeu9i7D.js` 215.72 kB、`Page-BxAt9swu.css` 22.47 kB、`Config-D0KxFYW8.js` 229.08 kB、`Config-B82oEuzP.css` 17.07 kB —— 与迭代18 产物同名同尺寸，证明本轮前端零改动）
- 迭代19 未做（不得写成已完成）：步骤12 查看/清理入口（需求②按钮映射）、`?detail_limit=abc` 的 FastAPI 422、浏览器可视化验收（图标/边框/文案与明细渲染仍无可视确认）
- 迭代20（报告步骤12-13，本轮）：完整 final command 全绿 —— `package.v3.json` JSON OK、后端 **295 passed in 5.77s**（本轮零后端改动）、前端 **`node --test tests/*.test.mjs` → 39 pass / 0 fail**（config 6 + page-setup 18 + module-detail-panel 10 + page-consistency 5）、`npm run build` ✓ built in 1.30s（`__federation_expose_Page-OdumzmAu.js` 221.00 kB、`__federation_expose_Page-C7v1bjO4.css` 22.70 kB、`Config-D0KxFYW8.js` 229.08 kB、`Config-B82oEuzP.css` 17.07 kB、`DownloaderBadge-CLJTHaaB.js` 4.61 kB、`remoteEntry.js` 3.78 kB`）
- 迭代20 生产代码改动（仅 `frontend.v3/downloadmanagerlocal/src/components/Page.vue`，+2740 字符）：`MODULE_RECORD_VIEWS`/`MODULE_CLEANUP_KEYS`/`moduleRecordView()`/`moduleCleanupButtons()`/`scrollToModuleAnchor()`/`openModuleRecords()`（插在 `openCleanupDialog` 之后）；`confirmCleanupData` 的 rename 分支加分页回第一页、autoremove 分支清 `autoremovePreview`；`CLEANUP_TARGETS.failclean_state.consequence` 改「只清最近一次执行结果，累计清理统计保留；实际文件与种子保持不变。」；模块卡按钮区在「详情」前插入「查看记录」与「清理记录」（0 条禁用）
- 迭代20 测试基建改动：`tests/page-setup.test.mjs` 的 setup 返回列表新增 `tabs/page/archivePage/cleanupCounts/cleanupTargetKey/cleanupConfirmDialog/cleanupRunning/CLEANUP_TARGETS/confirmCleanupData/openCleanupDialog/autoremovePreview/MODULE_RECORD_VIEWS/MODULE_CLEANUP_KEYS/moduleRecordView/moduleCleanupButtons/openModuleRecords`；追加 7 项步骤12 用例
- 迭代20 自查纠错（先反证再勾选）：首轮两项失败均为**测试自身写错**而非产品缺陷 —— ①负向断言 `!/全部清理/.test(source)` 命中我自己写的注释（改为只断言按钮标签不含「全部」）；②锚点断言把选择器 `[data-record-block="x"]` 当字面量在模板里找（模板只有属性），改为剥离方括号后校验属性存在
- 迭代20 未做（当时结论；迭代21 已补齐三项）：浏览器可视化验收（当时 `agent-browser-cli` 无可用标签页）、`?detail_limit=abc` 的真实 FastAPI 422 未验、提交推送与 QNAP 部署待授权
- 迭代21（浏览器可视化验收 + 版本 3.9.13，本轮）：**首次通过真实浏览器完成数据页/设置页/清理确认框验收**（`agent-browser-cli` 恢复可用，本地 MP 17430/17431，tab `1686439424`；加载 `remoteEntry.js?v=3.9.13` + `__federation_expose_Page-OdumzmAu.js`）
  - 数据页（插件卡菜单 →「查看数据」）：`moduleCards=8`；`查看记录` 精确出现在 7 个有记录模块（transfer/hr/autoremove/failclean/rename/tag/upload_limit，seed 无）；`清理记录` 4 个（autoremove、failclean、rename 的「清理历史」「清理归档」两个独立按钮），均有数量故未禁用；条数选择器实测 `value=20`（标签「20 明细条数」）；展开详情后 79 行明细 + 27 个 items 卡片；**截断提示真实渲染**：`仅显示前 20 条，共 37 条（上限 20 条）；可在「总览」页调整明细条数。`
  - 运行诊断页：下载器徽标 2 个（`test-qb`、`test-qb-2`），品牌色实测 `rgb(47, 122, 192)`＝qBittorrent #2F7AC0；「数据清理」块存在且白名单 5 个按钮均可用
  - 设置弹窗：导航标签实测 `转移做种 / H&R 管理 / 自动删种 / 失败清理 / 种子重命名 / 站点标签 / 上传限速`（无「命名补刀」，P6-3 生效）；`.dm-config` 计算样式 `width=958.857px、max-width=100%、padding=0px`（P6-2 生效）；内层 `.dm-config .dm-card` 仍带 `radius=20px / border-width=0.571429px`（来自宿主主题/Vuetify 层，非本插件规则；双层外框是否彻底消除**仍需肉眼确认**，本轮只取得计算样式证据）
  - 清理确认框（现场截获）：标题「确认清理失败清理记录」+「将删除 1 条」+「最近一次执行结果」+「只清最近一次执行结果，累计清理统计保留；实际文件与种子保持不变。」+「不修改下载器…」——步骤12/迭代19 的文案与数量口径在真实页面成立
  - 版本三处同步完成：`__init__.py::plugin_version = "3.9.13"`、`package.v3.json` `version=3.9.13` + history 顶部新条目、`description` 修正「命名补刀」→「种子重命名」；JSON 校验 OK；本地 MP 同步 + reload 后 `diagnostics.plugin.version == 3.9.13`
  - 复验脚本：`D:/tmp/dml_live_recheck.py`（11 项接口断言，本轮全 OK，含 `?detail_limit=abc` → **422** 真实 FastAPI 校验、`?detail_limit=21` → 400）；浏览器脚本 `D:/tmp/ab_probe4.js`（数据页）/`ab_probe5a.js`（截断提示）/`ab_probe6c.js`（诊断徽标+清理块）/`ab_probe9.js`（设置弹窗样式与文案）
  - 仍未做：肉眼级视觉确认（截图对比）、「查看记录」按钮的真实点击跳转（单测覆盖，未在浏览器点击）、提交推送（P7-3 待授权）、QNAP 部署（P7-4 待授权）
- 迭代22（描述文案真正落地 + 「查看记录」浏览器验收 + 视觉审查委派，本轮）：
  - **修正迭代21 的误记**：上一轮只改了 `package.v3.json` 的 description，但插件卡显示的是 `__init__.py::plugin_desc` —— 浏览器复验时卡片仍显示「命名补刀」，根因即此
  - `plugins.v3/downloadmanagerlocal/__init__.py`：`plugin_desc` 改为「转移做种、种子重命名、站点标签、H&R 保护、自动删种、失败清理与上传限速，一站式下载管理。」；模块 docstring（第 3 行）同步
  - 版本三处同步 **3.9.14**（`__init__.py::plugin_version`、`package.v3.json` version + history 顶部新条目）；`json.tool` OK、`ast.parse` OK
  - 本地 MP 同步 + `reload` 200 → `diagnostics.plugin.version == 3.9.14`（复验脚本轮询第 2 次即通过）；浏览器 `location.reload()` 后卡片描述实测「下载中心 v3.9.14 转移做种、种子重命名、站点标签、H&R 保护、自动删种、失败清理与上传限速，一站式下载管理。」，`descFixed=true`
  - **「查看记录」真实点击跳转验收（P7-2 剩余缺口之一，已闭合）**：种子重命名卡「查看记录」点击 → 激活页签由 `运行总览` 变 `命名历史`；`[data-record-block="rename-history"]` 存在、`anchorTop=162`、`inViewport=true`、滚动容器 `.dm-main` `scrollTop=24`
  - 设置弹窗计算样式：`.dm-config` `width=958.857px / padding=0px / border-width=0px / border-radius=0px / 透明背景`，内含内层 `.dm-card`；导航 7 项文案 = 转移做种 / H&R 管理 / 自动删种 / 失败清理 / 种子重命名 / 站点标签 / 上传限速
  - 运行诊断页：下载器徽标 4 个（源/目标各 2）全部 `rgb(47,122,192)`，文本形如 `Qtest-qb`、`Q test-qb-2`；「数据清理」块存在
  - 截图产物（供视觉审查/用户复核）：`D:/tmp/dml_overview.png`（总览 + 3 卡展开运行明细）、`D:/tmp/dml_diag.png`（运行诊断，2.39 MB）、`D:/tmp/dml_config.png`（设置弹窗 `.dm-config`，22 KB）
  - **视觉审查改由多模态模型执行**：主线模型不支持读图（`read` PNG 返回 `[Current model does not support images]`），已委派 `reviewer`（只读）+ `pa-responses/GPT-6.1-Sol`（多模态）看图审查三张截图 → `.ralph/dml-visual-review.md`；提示词要求先「逐字自证看到的文本」防幻觉、看不到就明说「无法看到图像」、不确定项单列
  - 浏览器脚本：`D:/tmp/ab_verify2.js`（卡片描述 + 打开数据页 + 点击「查看记录」）、`ab_diag2.js`（运行诊断徽标/清理块）、`ab_settings.js`（配置弹窗样式与导航）、`ab_reload.js`（`location.reload` 包装，避免 CLI 等待被 reload 打断）
  - 文档清理：阶段三那条**中间记录** `- [ ] P3-2 …剩余 transfer/rename/tag 待做` 已改为 `- [x]` 并注明「已被下方完成条目取代（迭代6 完成 + 两项边界测试）」，避免与完成条目矛盾（唯一剩余未勾选项就是 P7-4 待授权）
  - 未做/阻塞：视觉审查报告返回中（异步）；提交推送（P7-3）与 QNAP 部署（P7-4）待授权；本轮未跑场景回归（无后端逻辑改动，仅描述文案 + 版本号）
  - 迭代22 全量门禁（升版 3.9.14 后重跑）：`json.tool` OK、后端 **295 passed in 5.71s**、前端 **39 pass / 0 fail**、`npm run build` ✓ built in 1.38s（`__federation_expose_Page-OdumzmAu.js` 221.00 kB、`Config-D0KxFYW8.js` 229.08 kB）
  - **工作树状态（交付前必须知悉）**：`git status --short` = `M frontend.v3/downloadmanagerlocal/src/components/Page.vue`、`M package.v3.json`、`M plugins.v3/downloadmanagerlocal/__init__.py`、`M plugins.v3/downloadmanagerlocal/modules/hr/service.py`、`?? frontend.v3/downloadmanagerlocal/src/components/ModuleDetailPanel.vue`、`?? frontend.v3/downloadmanagerlocal/src/components/DownloaderBadge.vue`、`?? frontend.v3/downloadmanagerlocal/tests/`、`?? tests/v3/downloadmanagerlocal/test_hr_check_snapshots.py`、`?? .ralph/dml-ui-improvement-report.md`、`?? .ralph/dml-visual-review.md`、`M/D plugins.v3/downloadmanagerlocal/dist/*`（构建产物，含删除旧 chunk）→ 即 **P7-2c 全部四项改动 + H&R 修复 + 3.9.14 升版全部未提交**；阶段二~五只有后端部分在 `09f882b5` 里，前端当时未提交，**回退到该提交 ≠ 回到 3.9.13**（如实记录，原风险描述偏差）
  - 视觉审查阻塞：`reviewer` 换成 `pa-responses/GPT-6.1-Sol` 后仍返回「Current model does not support images」（与主线同一供应商图片通道），证据 `.ralph/dml-visual-review.md`（1.1 KB，15 行）；三张截图 `D:/tmp/dml_overview.png`（3824×1875）/`dml_diag.png`（3824×1875）/`dml_config.png` 已留存可直接复核；**替代路线的可选项**：`ab probe` 提供 DOM 几何/颜色/文本已测，肉眼级确认需用户看图或换图片通道可用（原生多模态）的模型
- 迭代23（场景回归重跑 + 视觉确认通道探测，本轮；无代码改动、无版本变更）：
  - 目标：补齐 P7-2 剩余缺口的两项前置条件——①在 3.9.14（含 H&R 修复 + P7-2c 四项）上重跑全量场景回归，确认改动未破坏真写链路；②寻找 pi 已知可读图的模型通道，替代此前失败的视觉审查
  - ① 测试下载器就绪核对：`"C:/Program Files/WSL/wslc.exe" list` 实测 6/6 `Up 3 hours` —— `dml-test-qb`(29080→8080)、`dml-test-qb2`(29082)、`dml-test-tr`(29091→9091)、`dml-test-tr2`(29092)、`dml-test-rt`(29580→80)、`dml-test-rt2`(29582→80)
  - ① 场景回归启动：后台任务 `bg-66`（pid 26308）跑 `cd /d/work/tmp/dml-test && "C:/app/scoop/apps/micromamba/2.9.0-0/base/python.exe" -X utf8 regress_all.py --slow`（本地 MP 17430 + 自造测试种子；快用例集 + TEXTRA/BATCH120/OBSERVE），日志 `C:\Users\wff19\AppData\Local\Temp\kendex-pi-bg\lanes\01a172fc-99ea-7422-8431-1bcf1d39810f\bg-66-1793272685283.log`，结果待回填
  - ② 图片通道现状：主线 `read` 与委派的 `pa-responses/GPT-6.1-Sol` 均返回「Current model does not support images」（同一供应商 Responses 图片通道不可用）；本机模型清单核查（`~/.pi/agent/models.json` 的 `providers`）发现候选 `DeepSeek-V4-Flash-Vision-Exp`（`pa-completions`，`models.json:254` 有定义；pi 内置 provider 数据中同名模型注册为 `input: ["text","image"]`）
  - ② 探测方式：委派 `reviewer`（只读）+ `pa-completions/DeepSeek-V4-Flash-Vision-Exp` 读 `D:/tmp/dml_config.png`，要求「逐字抄出确实看到的界面文字；拿不到图像就明说无法看到，禁止推测」——run `267ea0ec-c135-441c-b97b-e621f628840f`；能读图则以该模型补做视觉审查，不能读图则保留「视觉确认阻塞」并交由用户看图（不伪造视觉结论）
  - 本轮边界：未改任何代码、未升版本、未提交、未部署；P7-3 提交推送与 P7-4 QNAP 部署仍待用户授权
- 数据页展示新方向（用户 m19977/m19987，**先讨论后实施，未定稿**）：①细节一律用**表格**显示；②统计结果用**徽标（chips）一行**显示；③「运行诊断」与「运行总览」两页**最后设计**（等各模块展示定稿后再动）
- 草案数据来源：`plugins.v3/downloadmanagerlocal/modules/diagnostics/service.py::_module_details` 的七个构造器（`_transfer_detail`/`_rename_detail`/`_sitetag_detail`/`_hr_detail`/`_autoremove_detail`/`_failclean_detail`/`_uploadlimit_detail`）

| 模块 | 标题徽标 | 统计徽标行（一行） | 明细表格列 | 逐条数据现状 |
| --- | --- | --- | --- | --- |
| 转移做种 | 启用/关闭·观察中 | 调度中、今日成功、累计成功、今日兜底、兜底成功、跳过 N | 时间、种子名、源、目标、结果/原因 | 计数现成；转移记录含 `source_name`，可直出 |
| 种子重命名 | 启用/关闭·观察中 | 定时批次（进行中/空闲）、本次成功、本次失败、本次跳过、历史 N、失败归档 N/阈值 | 时间、原名、新名、结果、原因 | 计数 + 最近失败 items 现成 |
| 站点标签 | 启用/关闭·观察中 | 补全 N、跳过 N、命中站点 N | 站点、任务数 | **仅聚合**（逐条需新增记录点） |
| H&R 管理 | 启用/关闭·观察中 | 任务总数、待做种、做种中、已达标、超期、已删除、保护闸门开/关 | 名称、站点、状态、剩余/进度、更新 | 任务列表 items 现成 |
| 自动删种 | 启用/关闭·观察中 | 动作、触发来源、候选、暂停、删除种子、删除文件、跳过 N、失败 | 名称、分类/标签、大小、做种时长、动作、跳过原因 | 候选 items 现成 |
| 失败清理 | 启用/关闭·观察中 | 本轮 扫描/清理/失败/跳过、累计 清理/失败/跳过 | 时间、名称、路径、结果、原因 | **仅计数，无逐条记录** |
| 上传限速 | 启用/关闭·观察中 | 服务状态、模式、管理 N、宽限 N、上传中 N、探测中 N、受保护 N、当前速率、已分配额度 | 站点、任务数、额度 KiB、状态 | 站点聚合 + errors 现成 |

- 统一约定（提案）：卡片 = 标题行（名称 + 状态徽标）→ 统计徽标行 → 明细表格；表格沿用 `detail_limit`（20/50/100/200）并在卡片内显示「仅显示前 N 条，共 M 条」；空态统一「暂无…」一行；跳过 4 类默认合并 1 个徽标
- 待裁决 5 项：①列名全模块统一还是外框统一+列自定义 ②徽标一行上限（建议 4–7，超出合并）③启用/观察模式放标题徽标还是统计行 ④是否授权为失败清理/站点标签/转移做种新增逐条记录写入点 ⑤条数用选择器+截断提示还是卡片内分页
- 更正（自查）：迭代22 记录的「截图产物供视觉审查/用户复核」**不成立**——`D:/tmp/dml_overview.png` 与 `D:/tmp/dml_config.png` 实为 MP 加载/失败占位页（`dml_overview.png` 底部提示逐字「页面加载似乎遇到了阻碍，请尝试 清除缓存」，0 卡片 0 表格），完整报告 `.ralph/dml-visual-review2.md`；P7-2 的「肉眼级视觉确认」仍属未完成
- 转移做种页方案报告（用户 m20045 定稿项 + m20066/m20069 催促「报告/方案」）已落盘 `.ralph/dml-page-transfer-plan.md`：定稿＝徽标只留**在途/今日成功/累计成功**、H&R 保护不做本页统计、三张表（任务配置/在途事务/最近记录，最近记录带清理按钮）；含失败数据取证（`pipeline.py:181` 终态 failed、`pipeline.py:148-151` rollback+error、`attempts`，但 `api_transfer_status` records 未返回 error/attempts/created_at）、在途与历史同源两视图（队列 `_queue_key(目标,目标hash)` vs 来源索引 `源-源hash`）、清理新增 `transfer_records` 与同步删除依赖风险、9 步实施步骤 + 验收命令 + **5 项待裁决**
- 顺带修掉的夹具缺陷（bg-66 唯一失败）：FC 失败清理 3 条断言失败根因＝中断的 OBSERVE 用例残留 `failcleanup_observe_only=True`，失败清理按观察模式设计只记不删（日志原文「观察模式[失败清理]：跳过删除源文件…FC-02-success-and-target.mkv」）；已在 `D:/work/tmp/dml-test/ensure_fixtures.py` 新增 `OBSERVE_KEYS` + `reset_observe()`（先 get 全量→改单键→整份 put，避免剥键），复位后 `fc_case2.py` **17/17 PASS**（bg-66 的 FC 为假失败，非产品 bug）
- 迭代13 新增观察模式真写验证用例 `D:/work/tmp/dml-test/observe_case.py`（导入 tag_case 的 MP/qB 助手 + dml_e2e 的客户端表）：七模块全部切 `observe=true` → 依次触发 `transfer_run`/`retry_renames`/`rename_scan`/`tag_complement`/`autoremove_run`/`failclean_scan`/`hr_check`/`hr_scan` → 断言两侧 qB 快照（hash 集合 + name/tags/category/upload_limit/dl_limit，**排除 state** 避免做种抖动误报）与插件侧计数（rename_history/rename_archive/cleanup_data/upload_limit managed）零变化，末尾还原观察键并断言还原一致。uploadlimit 无手动入口（worker 事件驱动），用 `upload_limit_status.cycle` 是否前进证明周期真跑过，未前进则如实记 SKIP 而非假 PASS。已挂入 `regress_all.py` STEPS 的 `OBSERVE`（900s，快用例集第 10 步）；**必须等 `bg-62`（BATCH120 会改配置）跑完再跑**，否则配置并发冲突。负向对照由同批 RM/TAG/REN 用例提供（观察关闭时确有写入）
- 逐页设计第二轮（Ralph 迭代 23，零代码改动）：新增 `.ralph/dml-page-designs.md` —— §0 **跨页口径问题**（统计计数持久化不统一：`rename` 的 `plugin._rename_status`、`sitetag` 的 `plugin._site_tag_status` 是**进程内**、重载清零，其余五个模块（transfer `transfer_stats` / autoremove `remover_state` / failclean `failclean_status` / upload_limit `UPLOAD_LIMIT_STATE_KEY` / hr 由持久化任务派生）保留；跳过统计两套口径）＋ §1 种子重命名页（标题徽标＝启用·观察·定时批次；5 个统计徽标＝本次成功/失败/跳过·历史记录·失败归档「N/阈值」；表1 重命名记录 7 列 + 表2 失败归档 7 列；4 项待裁决）＋ §2 H&R 管理页（标题徽标＝启用·观察·保护闸门三态；6+1 徽标＝总数/待做种/做种中/已达标/超期/已删除+跳过合并；任务表 10 列；4 项待裁决）＋ §3 后续页排期（自动删种→失败清理→站点标签→上传限速→最后运行诊断+运行总览）
- 逐页设计取证：`modules/rename/service.py:810-826`（`_new_rename_status` docstring「进程内状态结构」、`_rename_module_state` 只挂 `plugin._rename_status`）、`modules/rename/archive.py:43-46/147-161`（归档字段 `name/category_label/fail_count/last_failed_at/archived_at/archive_reason`）、`modules/sitetag/service.py:571-579`、`modules/hr/service.py:41`（`CLEARABLE_STATUSES`）`:512-526`（任务字段 `downloader_id/torrent_hash/name/site/status/status_text/progress/remain_seconds/deadline/type/deleted`）`:528-547`（summary 字段）、`modules/uploadlimit/service.py:109-136`、路由清单 `controller/api.py`（`/hr/tasks`、`/hr/skip_stats`、`/hr_clear_task|hr_clear_compliant|hr_clear_missing`、`/rename_history`、`/rename_archive`、`/restore_rename_archive`、`/delete_rename_archive`、`/cleanup_module_data`）

## Final Verification

- Exact monitor-rerunnable command（仓库根）：
  `"C:/app/scoop/apps/micromamba/2.9.0-0/base/python.exe" -X utf8 -m json.tool package.v3.json > /dev/null && "C:/app/scoop/apps/micromamba/2.9.0-0/base/python.exe" -X utf8 -m pytest tests/v3/downloadmanagerlocal -q --tb=short && (cd frontend.v3/downloadmanagerlocal && node --test tests/*.test.mjs && npm run build)`
- Working directory: `D:/work/project/person/MoviePilot-Plugins`
- Required preserved artifacts: `tests/v3/downloadmanagerlocal/`、`frontend.v3/downloadmanagerlocal/tests/*.test.mjs`（config-setup / page-setup / module-detail-panel / page-consistency）、`frontend.v3/downloadmanagerlocal/src/components/ModuleDetailPanel.vue`、`plugins.v3/downloadmanagerlocal/dist/`（构建产物）
- Local MP live recheck（可重跑，需本地 MP 后端 17430 在跑、key 在 `D:/tmp/.mp_local_key`）：
  `cd /d/work/project/person/MoviePilot-Plugins && cp -rf plugins.v3/downloadmanagerlocal/. /d/test/MoviePilot-v3/app/plugins/downloadmanagerlocal/ && find /d/test/MoviePilot-v3/app/plugins/downloadmanagerlocal -type d -name __pycache__ -prune -exec rm -rf {} + ; cd /d/work/tmp/dml-test && "C:/app/scoop/apps/micromamba/2.9.0-0/base/python.exe" -X utf8 -c "import json,urllib.request; K=open('D:/tmp/.mp_local_key').read().strip(); B='http://127.0.0.1:17430'; P='/api/v1/plugin/'; print(urllib.request.urlopen(urllib.request.Request(B+P+'reload/DownloadManagerLocal?apikey='+K, method='POST'), timeout=120).status); d=json.load(urllib.request.urlopen(B+P+'DownloadManagerLocal/diagnostics?apikey='+K, timeout=90)); d=d.get('data') or d; print(sorted((d.get('module_details') or {}).keys()))"`
  （期望：reload 200、七键 `['autoremove','failclean','hr','rename','tag','transfer','upload_limit']`）
- 场景回归（可重跑，需 6 个 WSL 测试下载器 `wslc start dml-test-qb|qb2|tr|tr2|rt|rt2` + 本地 MP）：
  `cd /d/work/tmp/dml-test && "C:/app/scoop/apps/micromamba/2.9.0-0/base/python.exe" -X utf8 regress_all.py --slow`（快用例集约 6 分钟；`--only OBSERVE` 单跑观察模式真写验证；证据落 `D:/work/tmp/dml-test/modules-evidence/`）
- 迭代7（阶段三 P3-3+P3-5，本轮）：后端 **240 passed in 4.99s**（迭代6 236 + retry_failed_renames 观察拦截 2 项 + autoremove run 层统一口径 2 项）；完整 final command 全绿：JSON OK、240 passed、前端 `node --test` **6 pass / 0 fail**（新增观察开关行为 1 项）、`npm run build` ✓ built in 1.34s（`__federation_expose_Config-EoHlb7hW.js` 229.96 kB）
- 迭代7 生产代码改动：`modules/rename/service.py`（retry_failed_renames/retry_rename_by_hash 首行补 observe_skip 前置、顶层相对导入改函数内懒导入破循环）；`modules/autoremove/service.py`（run 层观察改统一口径）；`frontend Config.vue`（七页签观察开关、remover 开关迁移、watch 旧键回填、PANE_RESET_KEYS 清理）；`Page.vue`/`diagnostics`（迭代5-6 已就位）
- 迭代8（阶段四 P4-1/P4-2，本轮）：后端 **246 passed in 5.00s**（迭代7 240 + test_notify_module 6 项）；完整 final command 全绿：JSON OK、246 passed、前端 `node --test` **6 pass / 0 fail**、`npm run build` ✓ built in 1.29s；AST 校验 7 个改动文件全 OK
- 迭代8 生产代码改动：新增 `plugins.v3/downloadmanagerlocal/utils/notify.py`（module_title/result_text/notify_module_result + MODULE_TITLES 七模块映射）；`modules/transfer/service.py`（汇总通知统一标题与口径）；`modules/rename/service.py`（notify_rename_result 改统一出口，异常路径收口）；`modules/autoremove/service.py`（_notify 统一标题、REMOVER_NOTIFY_TITLE 顶部 import 移除、观察分支补「预览：N 个候选，未执行」通知）；`modules/failclean/notify.py`（_send 标题加「下载中心 · 失败清理（…）」前缀）；`modules/hr/notify.py`（SUMMARY_TITLE 改 module_title("hr")）；`modules/uploadlimit/service.py`（异常通知统一标题/口径，MessageType 保持函数内导入——顶部导入会破坏 test_observe_mode 的桩架构）
- 迭代8 教训：uploadlimit 顶部新增 app.schemas.types 导入会让 test_observe_mode 的 app 桩失效（'app' is not a package），该文件保持函数内延迟导入惯例；autoremove 测试桩 SimpleNamespace 需补 notify=False（观察分支读取 _config.notify）
- 迭代9（阶段五 P5-1/P5-2 + 反思，本轮）：后端 **251 passed in 5.07s**（迭代8 246 + test_cleanup_module_data 5 项）；AST 校验 5 个改动后端文件全 OK；前端未动
- 迭代9 生产代码改动：`modules/rename/archive.py`（+`clear_rename_archive`）、`model/api.py`（+`CleanupModuleRequest`/`CleanupModuleResult`）、`controller/handlers.py`（+`_cleanup_actions` 白名单/`api_cleanup_module_data`，顶层 import 加 `TRANSFER_STATS_KEY`）、`controller/api.py`（+`/cleanup_module_data` POST 端点与 `CleanupModuleResult` import）、`__init__.py`（+`api_cleanup_module_data` 薄包装）；测试基建：test_manual_run_endpoints/test_upload_limit_site_tags_rules 的 model.state 桩补 `TRANSFER_STATS_KEY`、MODEL_NAMES 补 Cleanup* 两名、路由数断言 38→39
- Result: 阶段三、四、五（P5-1/P5-2 后端）完成；解释器 `C:/app/scoop/apps/micromamba/2.9.0-0/base/python.exe`（-X utf8，micromamba 2.10 base 无 python）；剩余 P5-3 前端清理入口、阶段六图标边框文案、七本地 MP 验收→QNAP 部署（另行授权）

## Reflection（迭代9 检查点）

1. **已完成**：阶段一~四全绿 + 阶段五后端（隔离/观察/通知/清理 API），251 passed，从基线 201 增至 251（+50 用例）；零生产事故，无停止条件触发。
2. **有效做法**：观察门控收敛到漏斗函数（autoremove `_apply_action`、rename 4 处、tag 2 处等）而非全文件扫描；统一出口（`utils/notify.py`、`observe_skip`）让接入点少而稳；每轮 2 项+全量回归的节奏可持续。
3. **摩擦与教训**：utils.config ↔ 模块包循环导入需懒导入破环（rename/uploadlimit 两次踩到）；测试桩必须随生产代码顶层 import 同步（本轮 3 处：TRANSFER_STATS_KEY、Cleanup* 模型名、路由数 38→39），今后新增顶层 import/端点时先 grep tests 桩。
4. **方法调整**：无需调整；批量 python 精确替换（带 count 断言 + AST 校验）在本仓库比逐锚点 hashline 编辑更高效可靠，继续沿用。
5. **下一步优先级**：P5-3 前端（api.js + Page.vue 清理入口与确认框，决策 C 文案必须写明「可重新识别与补试」）→ P6 图标/边框/文案 → P7 本地 MP 验收（m17354）→ QNAP 部署另行授权。
## 数据页展示体系核对报告（迭代14，用户 m18958；只读核对，未改代码）

核对基线：3.9.12 工作树 + 迭代14 的 `module_details`。证据行号为本轮实读。

### 现状：数据页三层展示

| 层 | 位置 | 结构 | 证据 |
| --- | --- | --- | --- |
| 运行总览卡 | `Page.vue:1292-1398` | `dm-module-card`：头像+标题+摘要值+描述+操作按钮+「详情」展开；详情内 `card.details`（摘要行）+「运行明细」（rows 网格 + items 卡片） | `Page.vue:1372-1393`、`.dm-module-detail-*` 样式 `Page.vue:2213-2221` |
| 专项页签 | 8 个页签（转移做种/命名历史/H&R 任务/删种记录/失败清理/站点标签/上传限速/运行诊断），`Page.vue:17-27` | `dm-record-block` 记录区：桌面 `VTable`（多列）+ 移动卡片两套渲染 + 空态 | `Page.vue:1402/1481/1558/1622/1683/1823/2015` |
| 上传限速专属 | `Page.vue:1327-1366` | 不套用 rows/items：`dm-upload-status-card`、`dm-upload-site-status-row` 两套自有网格 | `Page.vue:1332-1363` |

结论：同一模块的同类数据在**总览卡「运行明细」**与**专项页签记录区**重复出现（autoremove 候选、H&R 任务、rename 失败记录都是两处），且 items 语义不统一：

- `rename` items = 最近 5 条失败（`service.py:278-285`，`_rename_history_stats` 里 `[:5]` 见 `service.py:58-62`）
- `tag` items = 命中站点聚合「站点 → N 个任务」（`service.py:304`）——不是种子
- `hr` items = 任务列表（`service.py:329`，`_candidate_item`）
- `autoremove` items = 本轮候选（`service.py:353`）
- `upload_limit` items = 站点聚合 + 错误文本混排（`service.py:416-417`）
- `transfer`/`failclean` **无 items**（只有 rows，`service.py:255/388`）

### ① 风格统一

差异点（可核对）：

1. 总览卡详情 = rows(label/value 两列) + items(标题/meta 两行卡片)；专项页签 = 表格多列 + 移动卡片；上传限速 = 第三套网格。三套视觉语言并存。
2. 空态不统一：`暂无命名记录`（`Page.vue:1415`）、`暂无归档记录`（1490）、`暂无候选记录`（1575）、`暂无转移记录`（1776）用 `dm-state`；上传限速用 `dm-monitor-empty`（1350/1364）。
3. 计数口径不一致：总览 rename「失败归档 34 / 阈值 3」来自 `archive_stats`（`service.py:273-276`），专项页签同名信息是分页列表（`handlers.py:395` `page_size: int = 15`）。

建议：抽共享组件 `ModuleDetailPanel.vue`（props: title/rows/items/empty/error/截断提示/记录入口），总览卡与专项页签统一调用；上传限速的专属网格保留（语义确实不同）但空态/标题改用它；表格保留（逐条操作需要）。

### ② 执行记录 / 清理日志按钮

逐条记录的有无（核对结果）：

| 模块 | 逐条记录来源 | 可查入口 | 可清理 |
| --- | --- | --- | --- |
| 转移做种 | `<source_downloader>-<source_hash>` data key（`handlers.py:906-919` 投影 records，分页） | 转移页签「最近记录」 | ✅ 数据清理 `transfer_stats` |
| 种子重命名 | `RENAME_RECORDS_KEY`（`handlers.py:399/431/474/542`）+ 归档 | 命名历史页签（分页 15） | ✅ `rename_history` / `rename_archive` |
| H&R | `service.get_service_infos().tasks` | H&R 任务页签 | ✅ H&R 三个 clear 接口 |
| 自动删种 | `remover_state.candidate_list`（本轮候选） | 删种记录页签 | ✅ `autoremove_state` |
| 站点标签 | 仅本轮扫描结果（`Page.vue:1823-1884`） | 站点标签页签 | ❌ 无 |
| 失败清理 | **无逐条记录**，只有 `scan/event/total` 三段计数（`service.py:362-386`） | 无 | ✅ `failclean_state`（只有 1 个状态对象） |
| 上传限速 | `status.state`（受管/宽限/站点）+ `errors` | 无独立记录区 | ❌ 无 |

缺口：用户要的「执行记录 / 清理日志」对 **failclean、tag、upload_limit 根本没有数据**；transfer 有记录但入口藏在页签深处；清理入口只有诊断页「数据清理」5 个对象（`Page.vue:2015-2027`、`handlers.py::_cleanup_actions`）。

两档方案：

- **A 轻量（复用现有数据）**：总览卡详情加「查看执行记录」按钮 → 跳到对应专项页签并展开；「清理记录」按钮复用现有 `cleanup_module_data`（没有记录对象的模块不显示按钮）。改动集中在 Page.vue + 少量文案。
- **B 完整（新增执行日志）**：新增 `utils/activity.py` 环形缓冲（如每模块最近 200 条：时间/动作/对象名/hash/结果/原因），在 7 个模块的写操作出口统一登记；新增 `GET /module_records?module=&limit=&page=` + `POST` 清理；前端统一「执行记录」抽屉（表格 + 条数选择 + 清空按钮）。风险：`plugin.get_data` 是 JSON 落盘，需控大小与写频（去重/合并同批），且要覆盖 7 个写入点。

### ③ 最大条数上限

- 后端 `MODULE_DETAIL_ITEM_LIMIT = 20`（`service.py:156`）硬编码，只在 `_detail()` 截断 items（`service.py:198`），**payload 不带总数、前端不提示被截断**。
- 表格类列表另有分页：rename 历史 15/页（`handlers.py:395`），transfer 记录同样分页（`handlers.py:930`）。

建议：`/diagnostics` 增 `detail_limit` 查询参数（白名单 20/50/100/200，默认 20，防大 payload）；前端总览加「明细条数」选择器（记住选择，不落盘）；截断时显示「仅显示前 N 条，共 M 条」——需要后端在 `_detail()` 里回传 `total`。表格分页保持不变。

### ④ 种子名（不只是 hash）

已显示名字的列表：rename 历史（`original_name`/`after_name`，`Page.vue:1432-1433`）、归档（`r.name`，1508/1526）、H&R 任务（`task.name`，1652/1667）、删种候选（`item.name`，1594/1607）、诊断失败记录（`item.name`，2007）；后端 `_candidate_item` 也是 name 优先（`service.py:222`）。

**只有 hash 的一处**：转移页签「最近记录」显示 `transferShortHash(record.source_hash)`（`Page.vue:1792`、移动端 3248）。根因是记录写入端不存名字——`handlers.py:906-919` 只投影 `source_hash`/`to_download_id`/`transfer_state`/标记位，记录对象由 `modules/cleanup/service.py` 的 `<source_downloader>-<source_hash>` 键维护（`cleanup/service.py:41-67/148-167`），源种名与转移目标名都没落盘。

建议：①在转移记录写入点补 `source_name` / `to_download_name`（按需再补 rename 后的 `after_name`）；②前端两处置换为「名称 + 短 hash」；③旧记录（无名字）回退显示短 hash 并标「名称未记录」。不建议只靠读取时实时查下载器补名（种子被删就查不到）。

### 建议实施顺序与裁决点

优先级：P1 种子名（收益直接，需动写入点）→ P2 条数上限（改动最小）→ P3 风格统一（纯前端，建议单独一轮）→ P4 执行记录（取决于 A/B）。

需要裁决（4 点）：
1. 执行记录走 A 轻量还是 B 完整（B 需新增存储 + 7 个写入点 + API）？
2. 条数上限做成查询参数（临时可选）还是插件配置项（落盘、随配置发放）？
3. 风格统一是否允许合并总览卡「运行明细」与专项页签记录区（去重），还是两处都保留、只统一样式？
4. 转移记录旧数据（无名字）接受「短 hash + 名称未记录」回退，还是需要回填/迁移历史名字？

## Reflection（迭代17 检查点）

1. **已完成**：阶段一~六 全部收口；阶段七的报告四项数据页需求已落地三项（④ 名称优先＝步骤1-3、③ 条数上限＝步骤4-6、① 风格统一＝步骤7-8 进行中），报告步骤 1-6 完成、7-8 正在做；后端 **284 passed**（基线 201 → 284，+83 用例）、前端 **6 + 11 pass**、`npm run build` 每轮通过；本地 MP + 6 个 WSL 测试下载器 + 自造种子跑完 **11 步场景回归全绿**（155 条场景断言 + 6 条语义变异全被抓住）；期间修掉两个线上 bug（诊断 500 的相对导入多/少一层、6 个端点 `payload` 缺注解导致 JSON body 永远为空）并补了防复发静态测试。
2. **有效做法**：把「改哪个文件哪一行、怎么验证、失败怎么回退」交给只读强模型（GPT-6.1-Sol）产出报告，主线照单执行——省掉主线反复试探；每轮 1-2 项 + final command 全绿 + 任务文件即时落证据；场景回归脚本 `regress_all.py` 作为真实验收（不拿 HTTP 200 冒充）；测试桩与生产代码顶层导入同步（新增顶层 import/端点先 grep tests 桩）。
3. **摩擦与阻塞**：①浏览器可视化验收整轮不可用（`agent-browser-cli` 无标签页/restart 挂起），P6 的图标/边框/文案与数据页明细渲染**至今没有真人视觉确认**；②迭代15-16 任务文件一度把「预期」写成「已完成」（步骤7-8 误记），迭代16 自查 `grep`/`ls` 才发现并纠正——**「先反证再勾选」是硬要求**；③`Page.vue` 2657 行且样式是 `scoped`，抽组件时样式不能靠父组件命中，必须把通用明细 CSS 搬进子组件；④`?detail_limit=abc` 的真实 FastAPI 422 仍未验（单测用 fastapi 替身）。
4. **方法调整**：①勾选前先跑反证命令（`grep -n <新符号> <文件>`、`ls src/components/`）再写完成；②抽组件前先确认 `<style scoped>` 与类名使用点，避免样式静默丢失（本轮 `.dm-module-detail-items/item*` 只服务被替换的块，可移走；`.dm-module-detail-title/grid/row` 仍被 `card.details` 使用，必须留在 Page.vue）；③浏览器验收登记为「阻塞未验」而不是静默跳过，交付报告里必须如实列出。
5. **下一步优先级**：步骤7（新增 `ModuleDetailPanel.vue` + `tests/module-detail-panel.test.mjs` 渲染行为测试）→ 步骤8（总览卡运行明细 → 共享组件、上传限速用同外围 + default slot、专项页只换标题/操作区/空态外围，保留 `data-record-block` 与桌面表格/移动卡片）→ 步骤9-11（自动删种/失败清理清理接口的内存同步、失败清理计数口径、干净竞争 409）→ 步骤12（查看/清理入口）→ 步骤13（全量门禁）→ P7-2 浏览器验收（阻塞）→ 提交推送（待授权）→ QNAP 完整包部署（待授权）。
## Notes
- 当前范围更新：用户要求先原样式 HTML 存档，后续业务实施沿用原样式；配置页字号/控件密度、布局、提示及危险颜色必须逐页询问确认，不自动实施、不自动转下一页。原始存档 `.ralph/style-baseline-original/index.html`（15 配置区域＋当前数据页视图；脱敏只读 computed-style 快照，非全部页面/非响应式证明），manifest 记录尺寸与 SHA-256。浏览器已验证可打开、区域切换、无外部脚本/远端表单、业务按钮不响应。配置页现有实测字段/开关字体16px；分组标题14px、普通提示12px。接下来先讨论转移做种·基础设置。等待用户逐页裁决期间不推进业务代码或部署。
- 更正上述存档验收：用户实测 `.ralph/style-baseline-original/index.html` 布局混乱，原导出无效，“可打开/可切换”不足以证明视觉还原，撤销基线可用结论。todo #90 修复存档，配置页逐页讨论暂缓，不改插件源码。
- 用户最新决定：HTML 基线“先不做”，暂停 todo #90，不继续修复/导出。旧快照保留无效标记，不作为后续样式依据；回到配置页逐页讨论，确认前不修改插件代码。
- 配置页逐块讨论确认：转移基础设置保留Tab/主题，简单开关按内容宽度1～3列，左标签右开关；短数值框120～160px、字段1～3列，普通字段1～2列、长字段整行，标签14px/提示12px、单行框36～40px。用户同意“恢复默认”也开启观察模式；打开/升级已有配置不覆盖用户值。均为已确认规格，尚未实施。下一块讨论转移任务列表。
- 转移模块完整配置预览已获用户确认：做种校验并入转移基础设置；删源/删除重复新增全局默认（均关闭），新任务三态继承/明确开/明确关，旧任务已有布尔值保留为明确覆盖；界面显示来源与生效值。下载器连接扩展不在任务弹窗重复配置，实际已有入口待实施核对。任务弹窗保留路线/路径/筛选/目标属性/风险覆盖；应用仅改表单，保存后生效；删除任务配置不删除种子/文件，也不冒充取消在途事务。仍为规格，未改业务代码；下一模块逐块讨论 H&R 管理。
- H&R 配置完整精简预览获确认：仅基础设置/站点规则两Tab；管理与删除保护合并总开关，旧管理开保护关组合须显式兼容提示不得静默改行为；基础页运行纳管、任务发现检查、通知，排除/标签/刷流/记录保留置更多设置折叠。全局考核移站点规则页，保留预设、自定义、继承、体积分档与原始YAML；hr_active准确语义仍需核实。统一已有选项可搜索多选、自由项chip回车添加/多项粘贴（不按空格拆分）、路径每行一项；前端转换保留后端原格式与匹配逻辑。下一块为自动删种基础设置，所有确认尚未实现。
- 自动删种配置最终确认（覆盖中间单页草案）：两个Tab“基础设置 / 错误种子清理”。基础含运行范围、动作调度、普通规则；更多条件与连带处理折叠。错误清理独立Tab含分支启用、关键词、请求解除H&R授权，下载器/动作/调度继承基础不重复。普通与连带处理遵守H&R，唯一授权限错误删除且非暂停。新错误分支默认关，不扩大旧错误关键词AND规则。说明精简至必要短句，错误示例不得写默认。H&R最终精简预览已确认；全局考核在站点规则。均未实现，下一模块失败清理。
- 失败清理配置预览获确认：单页运行开关/观察/通知，重复残留巡检开关＋计划＋保留时长；关闭重复巡检只影响对应巡检不影响失败事件，保留时长只管重复残留。默认模块关、全新观察开、通知开、重复清理开、0 */2 * * *、6小时；只查询H&R保护不申请解除。风险与说明使用必要短句。尚未实现，下一模块种子重命名。
- 种子重命名配置获确认：保留“基础设置 / 模板与过滤”两Tab。基础含运行范围（启用/观察/通知/下载器）、入列事件与防抖、定时补查与计划；关联输入随开关禁用，开启定时须有效计划。模板整行原文不拆分，变量帮助折叠；标签统一chip输入，目录/hash逐行置更多过滤，保持原有匹配语义与保存格式；界面调整不重置已有模板/过滤。用户仅确认本方案，未授权实现或自动合为一页。
- 分类与标签配置获确认：保留“基础设置 / 映射规则”两Tab；基础含运行范围、站点/剧名标签与下载分类开关、站点标签前缀、历史补全计划，标签删除权限折叠。站点标签前缀全新配置默认值明确为“🏠”（用户确认），已有显式配置不覆盖。映射页集中分类方式/前缀/分类或路径映射及站点映射，切换方式不清空非活动规则；保留匹配顺序与原保存格式。站点映射减少重复展示、保留站点库域名/自定义标签，未保存的移除行不是实际标签删除、不用红色危险语义。只记录方案，未实现。
- 上传限速配置获确认：保留“基础设置 / 限速规则”两Tab。基础含启用/观察、目标下载器（现支持qB/TR、至少选一）、新种宽限30分钟；观察不调限速也不恢复已有额度。规则为紧凑下载器总上限表（正整数必填）与跨所选实例共享的站点合计上限表（空/0不设站点额度但受全局约束），数值右对齐/单位表头，示例额度不作默认。未选统一空态，缺额度字段内提示，说明折叠；移除配置行普通颜色、保存才生效。扫描站点/清空策略留数据页，不新增通知调度，不改分配算法；已有自定义标签前缀保留。均未实现。
- 用户新增配置页导航/窗口行为要求：配置页固定操作区左下角加“查看数据”按钮，返回插件数据页；不是配置保存动作。用户“数据页的保持按钮”暂按“保存按钮”理解：保存不得触发配置窗口关闭，成功后保留当前配置Tab、滚动位置与窗口，仅给成功提示；失败保留输入并显示错误。实施前核对数据页/配置页与宿主保存事件，防止保存事件冒泡或复用close回调误关配置窗口，不得将按钮名称歧义当已核实事实。需求仅归档未实现。

- 每轮更新本文件的 Checklist 与 Verification；完成项必须有命令/产物证据。
- 不修改其他插件、下载器、站点配置或其他容器；不做方案外重构。
- 遇到方案第 11 节停止条件时立即停止并按格式报告，不自行兜底。
- P2-4 的「关联模块观察→只预览」「前置仅预览/失败→不执行后续」两条依赖观察模式（P3）的预览口径，检查点并入 P3-2/P3-3：届时若发现未满足则继续修，不因 P2-4 已勾选而跳过。
- 用户约束（m17354）：本地 MP 实测通过前不部署 QNAP；QNAP 部署另行确认。
