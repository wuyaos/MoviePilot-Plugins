# 历史资料：禁止作为当前执行指令

> 本文已由 `docs/downloadmanagerlocal-final-implementation-spec.md` 取代。仅供追溯，旧待裁决、默认值、回退命令不得照抄执行。
> 原路径：`.ralph/dml-page-transfer-plan.md`。原文保存在下方，不代表现行约定。

---

# 转移做种页 展示改造方案（v1 草案，待确认）

> 目标：数据页「转移做种」卡片改为「一行徽标统计 + 表格显示细节」，与其它模块统一。
> 本文是实现规格，供按步执行；每步含改动文件、命令、期望输出、回退动作。
> 状态：**尚未实施**。文末「待裁决」项确认后才动代码。

---

## 0. 已定稿（用户 m20045）

| 项 | 决定 |
| --- | --- |
| 统计徽标 | 只保留 **在途 / 今日成功 / 累计成功** 三个 |
| H&R 保护 | 不在本页做统计徽标；改为从 H&R 管理源头排除，或由 H&R 管理通知各模块 |
| 明细表格 | **任务配置 / 在途事务 / 最近记录** 三张 |
| 最近记录 | 加一个**清理记录按钮** |
| 待补充 | 「失败有没有」——见 §2（有） |

---

## 1. 术语与数据来源（权威口径）

| 徽标 | 含义 | 口径 | 代码位置 |
| --- | --- | --- | --- |
| 在途 N | 已加到目标下载器、**收尾流程未走完**的转移事务（含 `rollback` 回滚中） | 瞬时 | 队列 `seed_recheck_queue`，读取 `modules/transfer/recheck.py:58 load_seed_recheck_queue` |
| 今日成功 | **今天完成收尾的转移种子数** | 当日，`today_stamp()` 日切 | `transfer_stats.today_success`，写入 `model/state.py:100 record_transfer_success`，调用点 `modules/transfer/pipeline.py:300` |
| 累计成功 | **有史以来完成收尾的转移种子数** | 累计 | `transfer_stats.success_total` |

补充口径（写进 UI 提示文案，避免误读）：

- 删源被 H&R 保护拦住时**仍记成功**（`modules/transfer/pipeline.py:296-300` 先记 `hr_protected`，再 `phase=completed` + `record_transfer_success`）。
- 兜底（`fallback`）是「第一轮没转成、留待后续再试」的路径（`modules/transfer/pipeline.py:117`），**兜底成功 ⊂ 累计成功**（`model/state.py:88-91` 的 `min(success_total, fallback_success)` 约束）。本页不显示兜底徽标。
- 收尾流程＝等目标端校验完成 → 确认在做种/完整 → 转移后处理 →（可选）删源；由 `seed_recheck_loop` 每轮推进，`advance_transfer` 返回成功才出队（`modules/transfer/recheck.py:195-196`）。

事务 `phase`（存为 `transfer_state`）：`source_pausing` → `adding` → `target_added`/`verifying` → `completed`；失败 `rollback`；连续失败达上限置终态 `failed`（`modules/transfer/pipeline.py:181`，上限常量 `MAX_TRANSFER_ATTEMPTS`，判定 `transfer_is_abandoned`，`modules/transfer/pipeline.py:31-44`）。

在途与历史不是两张独立数据源，是**同一批事务的两个存储视图**（`save_transaction`，`modules/transfer/pipeline.py:47` 每次推进同时写两处）：

| 视图 | 存储键 | 内容 |
| --- | --- | --- |
| 队列（在途） | `_queue_key(目标下载器, 目标hash)` | 未完成事务；完成后 `queue.pop` |
| 来源索引（历史） | `f"{源下载器}-{源hash}"`（`save_source_record`，`pipeline.py:56`） | 每条事务的最后快照，**含未完成的** |

`controller/handlers.py:844 _iter_transfer_records` 读来源索引。**所以「最近记录」必须按状态过滤**，否则在途项会混进来。

---

## 2. 失败数据：有（现状 + 缺口）

**有失败记录**，但当前接口没把它们暴露给前端：

| 失败信息 | 存在与否 | 位置 |
| --- | --- | --- |
| 终态 `failed`（连续失败达上限，自动轮次永久跳过） | 有 | `modules/transfer/pipeline.py:181` `item["phase"] = "failed"`；跳过判定 `pipeline.py:31-44`；运行期日志 `modules/transfer/service.py:414-418` |
| 回滚中 `rollback` + 错误原因 `error` | 有 | `pipeline.py:148-151`（异常分支写 `phase="rollback"`、`item["error"]=str(exc)`） |
| 失败次数 `attempts` | 有 | `pipeline.py:104-119` 写入；手动触发重置为 0（`modules/transfer/service.py:481`） |
| 接口是否返回 | **没有** | `controller/handlers.py:930-947` 的 records 行只给 `task/source_downloader/source_hash/source_name/downloader/hash/phase/delete_source/hr_protected/fallback/updated_at`，**缺 `error`、`attempts`、`created_at`** |

→ 实施时后端补这 3 个字段即可（源索引 dict 里本来就有，`save_source_record` 用 `{**item}` 全量落盘），无需新增写入点。

---

## 3. 三张表的列定义

数据源：`GET /api/v1/plugin/DownloadManagerLocal/transfer_status`（`controller/handlers.py:869 api_transfer_status`），一次返回 `tasks` / `pending` / `records`（分页 `page`/`page_size`）+ `summary`。

### 表 1：任务配置（来自 `tasks`）
| 列 | 字段 |
| --- | --- |
| 启用 | `enabled` |
| 任务 | `name` |
| 源 → 目标 | `from_downloader` → `to_downloader` |
| 范围 | `include_category` / `include_labels`（空显示「全部」） |
| 排除 | `exclude_labels` |
| 路径 | `from_path` / `to_path`（`no_paths` 时显示「不需要路径」） |
| 删源 | `delete_source` |
| 去重 | `delete_duplicate` |
| 保留 | `keep_category` / `keep_tag` |
| 转移标签 | `transfer_tag` |
| 空标签放行 | `empty_label_ok` |

### 表 2：在途事务（来自 `pending`）
| 列 | 字段 |
| --- | --- |
| 任务 | `task` |
| 种子名 | `source_name`（旧数据为空 → 显示短 hash + 「名称未记录」） |
| 源 → 目标 | `source_downloader`(`source_hash` 前 8) → `downloader`(`hash` 前 8) |
| 阶段 | `phase` → 中文：`source_pausing`=暂停源、`adding`=添加目标、`target_added`=已添加、`verifying`=校验中、`rollback`=回滚中 |
| 已等待 | `waited_minutes`（分钟） |
| 标记 | `fallback`=兜底、`skipverify`=跳过校验、`autostart`=自动开始、`delete_source`=将删源 |

### 表 3：最近记录（来自 `records`，**按状态过滤 + 分页**）
| 列 | 字段 |
| --- | --- |
| 更新时间 | `updated_at`（补 `created_at` 后可加「创建时间」） |
| 种子名 | `source_name`（缺失回退同表 2） |
| 源 → 目标 | 同上 |
| 阶段 | `phase`（额外取值 `completed`=已完成、`failed`=已放弃、`stopped_after_add`=已添加后中止） |
| 结果 | 成功 / 失败 / 回滚（由 `phase` 映射） |
| 失败原因 | `error`（**需后端补**，`failed`/`rollback` 才有值） |
| 重试次数 | `attempts`（**需后端补**） |
| 标记 | `fallback` / `hr_protected` / `delete_source` |

表格行为（三张表统一，用新组件 `ModuleTable.vue` 承载）：
- 上限沿用 `detail_limit`（20/50/100/200，来自总览页设置），超出显示「仅显示前 N 条，共 M 条」
- 「最近记录」额外提供 `page/page_size`（接口已有，15/页）与**清理记录**按钮
- 空态统一：任务配置「暂无转移任务」、在途「暂无在途转移」、最近记录「暂无转移记录」
- 桌面表格 + 移动卡片两种渲染都要改（`Page.vue` 现有双渲染）

---

## 4. H&R 保护：现状机制 + 两种方法取舍

**现状（已经是「源头判定 + 各模块执行前查询」）**：

- `modules/hr/guard.py` 里的 `HrGuard` 是**进程内单例**，H&R 管理扫描后调用 `update(enabled=..., protected=[(downloader_id, hash)])` 写入受保护集合；`is_protected()` 查询。
- 各模块删东西前调用 `should_skip(path, downloader_id, hash)`：命中则 `record_skip(path)` 计数并返回 True（跳过）。
- 四条路径常量（`guard.py:24-33`）：`transfer_source`(转移删源，`modules/transfer/pipeline.py:65`)、`auto_remove`(自动删种)、`transfer_failure`(整理失败清理，`modules/failclean/service.py:343`)、`sync_delete`(同步删除，`modules/cleanup/service.py:167`)。
- **H&R 管理是唯一状态源**，其它模块不自己判 H&R —— 所以「模块直接对接 H&R」在语义上已经成立，缺的只是**候选层排除**。

**方法一：从 H&R 管理源头就排除（推荐）**
在各模块**生成候选集**时就用同一个 guard 过滤（如转移选定待转种子时排除受保护项、自动删种候选生成时排除），使「候选里根本没有它」，而不是执行到删除那一步才被拦。
- 收益：统计干净（不再出现「候选有 N 个、执行只动 N-1 个」的错位）、日志噪音少。
- 代价：要在候选生成处加 guard 过滤（7 处左右）；**执行前校验仍必须保留**——从「生成候选」到「执行」之间，种子的 H&R 状态可能变化（守卫刷新、重新扫描），删掉就是真删保护中的种子。

**方法二：模块对接 H&R 管理通知**
H&R 状态变化时发事件，各模块更新本地集合，而不是每轮查全局快照。
- 收益：模块不依赖 guard 单例，可单测、易解耦。
- 代价：要定义事件与订阅、处理重启后的状态重建（启动仍要拉一次全量）、丢失事件的补偿；当前是单进程单实例，收益不抵复杂度。

**顺带查出的现存缺陷（本次一并修）**
- 转移卡那 4 行「跳过（转移源种子/自动删种/整理失败/同步删除）」读的是**持久化** `transfer_skip_stats`（`modules/diagnostics/service.py:96`），但该键**唯一写入点只写 `hr_protected`**（`modules/transfer/pipeline.py:66-68`）→ 这 4 行**恒为 0**，无意义。
- H&R / 自动删种 / 失败清理三卡的同类 4 类来自 **HrGuard 内存计数**（`modules/hr/service.py:540`、`modules/autoremove/service.py:157-170`、`modules/failclean/service.py:188`）→ **插件重载即清零**。
- 结论：H&R 跳过统计目前口径不统一（一半持久化恒 0、一半内存易失）。本页按用户决定**不再显示**；是否统一持久化、放哪个页面，见待裁决 4。

---

## 5. 「清理记录」按钮

**现状**：清理白名单在 `controller/handlers.py:521-527 _cleanup_actions`，已有 5 个目标：`rename_archive`、`rename_history`、`transfer_stats`(清 `transfer_stats` + `transfer_skip_stats`)、`autoremove_state`、`failclean_state`。**没有「转移记录」目标**，且 `transfer_stats` 未接入前端按钮。

**要做的**：新增清理目标 `transfer_records`，清掉**已完成/已放弃**的事务记录（来源索引键 `f"{源下载器}-{源hash}"`），保留在途。

**必须知道的风险（依赖）**：同步删除功能靠这些记录找「转种目标」——`modules/cleanup/service.py:148-186 _cleanup_transfer_target` 用记录的 `to_download`/`to_download_id` 去删目标种子。清空记录后，该源种子的「同步删除目标」能力失效（下次用同 hash 事件也找不到映射）。三种处理：

1. 只清 `completed` 且**超过 N 天**的记录（推荐，N 默认 30）
2. 全部清 `completed` + `failed`（简单，但同步删除关联丢失）
3. 清记录同时导出备份（复杂，暂不推荐）

---

## 6. 实施步骤（按序，逐步可验证）

> 前置：仓库 `D:/work/project/person/MoviePilot-Plugins`；Python 用 `micromamba run -n base python`（或 `"C:/app/scoop/apps/micromamba/2.9.0-0/base/python.exe" -X utf8`）。

**步骤 1 — 后端补失败字段**（`controller/handlers.py`，`api_transfer_status` 的 records 组装处）
改动：records 行补 `"error": str(value.get("error") or "")`、`"attempts": int(value.get("attempts") or 0)`、`"created_at": float(value.get("created_at") or 0)`。
验证：`curl` `/transfer_status` → records[0] 含这三个键（无记录时用测试夹具造一条）。
回退：`git checkout -- plugins.v3/downloadmanagerlocal/controller/handlers.py`。

**步骤 2 — 后端新增清理目标**（`controller/handlers.py::_cleanup_actions`）
改动：加 `clear_transfer_records()`（按待裁决 2 的范围），注册 `"transfer_records": clear_transfer_records`。
验证：`POST /cleanup_module_data {"module":"transfer_records"}` → `{code:0, removed:N}`；再查 `/transfer_status` records 变少、在途不变。
回退：同步骤 1。

**步骤 3 — 诊断瘦身**（`modules/diagnostics/service.py::_transfer_detail`，:278-287）
改动：rows 只留三徽标所需（在途/今日成功/累计成功）+ 原有的启用/观察（进标题徽标），删掉 `_skip_stat_rows(...)` 那 4 行与布尔行。
验证：`/diagnostics` 的 `module_details.transfer.rows` 只含预期的键。
回退：`git checkout -- plugins.v3/downloadmanagerlocal/modules/diagnostics/service.py`。

**步骤 4 — 前端新组件**（`frontend.v3/downloadmanagerlocal/src/components/ModuleTable.vue`）
props：`columns`、`rows`、`emptyText`、`limit`、`total`、`loading`；桌面 `v-table` + 移动卡片双渲染；截断提示文案与现有一致。
验证：`cd frontend.v3/downloadmanagerlocal && node --test tests/*.test.mjs`。

**步骤 5 — 前端卡片接线**（`frontend.v3/downloadmanagerlocal/src/components/Page.vue`）
改动：转移卡改为「标题徽标（启用/观察/调度）+ 徽标行（在途/今日成功/累计成功）+ 三张 ModuleTable（数据来自 `/transfer_status`，展开时拉取）」，移除原 12 行文字明细。
验证：本地 MP 实测（步骤 8）。

**步骤 6 — 测试**
- 后端：`tests/v3/downloadmanagerlocal/` 增改断言（records 三新字段、`transfer_records` 清理目标只清完成记录）
- 前端：`frontend.v3/downloadmanagerlocal/tests/` 新增 `transfer-card.test.mjs`（三徽标 + 三表 + 空态 + 截断提示）
验证：见 §7。

**步骤 7 — 版本与元数据**：`plugins.v3/downloadmanagerlocal/__init__.py` 的 `plugin_version`、`package.v3.json` 的 `version` 与 `history` 顶部条目三处同步。

**步骤 8 — 本地 MP 实测**（**必须**，QNAP 部署前）
命令：同步插件目录 → `/reload/DownloadManagerLocal` → 浏览器打开数据页 `http://127.0.0.1:17431/docs#/plugins` 的插件设置/数据页
验收：三徽标显示真实数字；三张表有数据；「清理记录」点击后条数下降且弹确认；在途表不被清空；移动宽度下卡片渲染正常。

**步骤 9 — 提交与 QNAP**：需用户授权（提交；QNAP 用完整包部署，不拆前后端）。

---

## 7. 验收命令

```bash
cd /d/work/project/person/MoviePilot-Plugins
"C:/app/scoop/apps/micromamba/2.9.0-0/base/python.exe" -X utf8 -m json.tool package.v3.json > /dev/null \
  && "C:/app/scoop/apps/micromamba/2.9.0-0/base/python.exe" -X utf8 -m pytest tests/v3/downloadmanagerlocal -q --tb=short \
  && (cd frontend.v3/downloadmanagerlocal && node --test tests/*.test.mjs && npm run build)
```
场景回归（本地 MP 17430 + 六个测试下载器）：
```bash
cd /d/work/tmp/dml-test && "C:/app/scoop/apps/micromamba/2.9.0-0/base/python.exe" -X utf8 regress_all.py --only FIXTURE FC ULPAGE TEXTRA
```

---

## 8. 待裁决（确认后才实施）

1. **三张表的数据来源**：卡片展开时按需拉 `/transfer_status`（推荐，零新增后端遍历）还是塞进 `/diagnostics`（每次总览都遍历全量插件数据）？
2. **「清理记录」范围**：只清 `completed` 且超 N 天（推荐 N=30，保留同步删除关联）／清 `completed`+`failed` 全部／其它？
3. **失败是否进徽标**：按你「只有三个徽标」的决定，失败只在「最近记录」表格里用状态列体现（确认？）
4. **H&R 保护**：选方法一「候选层源头排除 + 保留执行前兜底」（推荐）还是方法二「通知机制」？H&R 跳过统计（4 类 + `hr_protected`）是**删除**、还是统一持久化后放 H&R 管理页？
5. **任务配置表**：只读展示（推荐）还是要在卡片里直接改任务（会与配置页重复）？

---

## 附：本条线的既有验证凭证

- 场景回归（bg-66，3.9.14 上）：12 步中 11 步 OK，FC 失败经查为**夹具状态泄漏**——中断的 OBSERVE 用例残留 `failcleanup_observe_only=True`，失败清理按观察模式设计只记不删；已在 `D:/work/tmp/dml-test/ensure_fixtures.py` 加观察模式门控（复位 7 个 `*_observe_only`），复位后 `fc_case2.py` **17/17 PASS**。
