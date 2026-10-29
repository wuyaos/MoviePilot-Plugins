# 历史资料：禁止作为当前执行指令

> 本文已由 `docs/downloadmanagerlocal-final-implementation-spec.md` 取代。仅供追溯，旧待裁决、默认值、回退命令不得照抄执行。
> 原路径：`.ralph/dml-page-designs.md`。原文保存在下方，不代表现行约定。

---

# 数据页逐页设计（v1 草案，待讨论）

> 体例：每页一节 —— 标题徽标 / 统计徽标行 / 明细表格列 / 现状缺口 / 待裁决。
> 方向依据：细节一律**表格**，统计用**徽标一行**（用户 m19977）；「运行诊断」与「运行总览」两页最后设计（用户 m19987）。
> 数据源均以现有接口为准（`controller/api.py` 路由清单），不新增写入点，除非「待裁决」明确授权。
> 状态：**讨论中，未实施**。转移做种页见 `.ralph/dml-page-transfer-plan.md`。

---

## 0. 跨页问题（先看这条，影响所有页）

**统计口径不统一：一部分计数落盘、一部分只存在内存，插件重载即清零。**

| 模块 | 计数来源 | 重载后 | 证据 |
| --- | --- | --- | --- |
| 转移做种 | `transfer_stats`（持久化） | 保留 | `model/state.py::record_transfer_success` |
| 种子重命名 | `plugin._rename_status`（**进程内**） | **清零** | `modules/rename/service.py:810-826`（`_new_rename_status` docstring 写明「进程内状态结构」，`_rename_module_state` 只挂 `plugin._rename_status`） |
| 站点标签 | `plugin._site_tag_status`（**进程内**） | **清零** | `modules/sitetag/service.py:571-579`（`_module_state` 挂实例属性） |
| H&R 管理 | 由持久化任务派生 | 保留 | `modules/hr/service.py:528-547`（`_summary_view` 遍历 `self._tasks`） |
| 自动删种 | `remover_state`（持久化） | 保留 | `modules/autoremove/service.py` + 步骤9 新增 `clear_history()` 同步内存/磁盘 |
| 失败清理 | `failclean_status`（持久化） | 保留 | 步骤10 新增状态锁 + `total` 累计 |
| 上传限速 | `UPLOAD_LIMIT_STATE_KEY`（持久化） | 保留 | `modules/uploadlimit/service.py:109-136` |

**建议**：徽标要统一，就先统一「计数是否落盘」。否则「种子重命名」「站点标签」两卡的徽标会在每次重载后归零，与相邻卡片表现不一致。
最小做法：rename 的 `renamed/failed/skipped` 与 tag 的 `completed/skipped/matched` 改为落盘键（`plugin.save_data`，沿用现有 state 形状，不新增 UI 字段）。

**跳过统计两套口径**（转移做种页报告 §4 已记）：持久化 `transfer_skip_stats` 唯一写入点是 `hr_protected`，其余三格恒 0；H&R / 自动删种 / 失败清理三卡的四类跳过来自 `HrGuard` 内存计数（`modules/hr/guard.py:129-148`），重载清零。

---

## 1. 种子重命名页

### 标题徽标
`启用/关闭` · `观察中` · `定时批次：进行中/空闲`

### 统计徽标行（推荐 5 个，左→右）
| 徽标 | 字段 | 备注 |
| --- | --- | --- |
| 本次成功 | `get_module_status().renamed` | 见「口径问题」：当前是自启动累计 |
| 本次失败 | `.failed` | |
| 本次跳过 | `.skipped` | |
| 历史记录 | `_rename_history_stats().total`（含 success/failed/dirty） | 记录条数 |
| 失败归档 | `archive_stats.archived / threshold` | 「34 / 阈值 3」形式 |

「最近运行」`last_run` 建议放标题右侧 `text-caption`，不占徽标位。

### 明细表格

**表 1：重命名记录**（数据源 `GET /rename_history?page=&page_size=`，落盘键 `RENAME_RECORDS_KEY`）
| 列 | 字段 |
| --- | --- |
| 时间 | `time` |
| 原名 | `original_name` |
| 新名 | `after_name`（旧记录可能为空） |
| 结果 | `success` → 成功 / 失败 |
| 原因 | `reason`（失败时） |
| hash | `hash` 前 8 位 |
| 操作 | 补刀 / 恢复原名 / 删除记录（页签已有，卡片是否重复见待裁决 2） |

**表 2：失败归档**（数据源 `GET /rename_archive`，落盘键 `RETRY_STATE_KEY`）
| 列 | 字段 | 证据 |
| --- | --- | --- |
| 名称 | `name` | `modules/rename/archive.py:149-158` |
| 分类 | `category_label`（中文，来自 `FAILURE_CATEGORY_LABELS`） | `archive.py:43-46` |
| 失败次数 | `fail_count` | 同 `archive.py:147` |
| 最近失败 | `last_failed_at` | `archive.py:156` |
| 归档时间 | `archived_at` | `archive.py:160` |
| 归档原因 | `archive_reason` | `archive.py:161` |
| 操作 | 恢复 / 删除归档（`/restore_rename_archive`、`/delete_rename_archive`） | |

### 现状缺口
- 记录翻页在专项页签（15/页）；卡片若出表格需按 `detail_limit`（20/50/100/200）截断并显示「仅显示前 N 条，共 M 条」。
- 「脏名称」计数（`_rename_history_stats().dirty`，`modules/diagnostics/service.py:55-60`）已算但**从未展示**，可作为第 6 个徽标或并入提示。
- 归档阈值来自配置（`DEFAULT_ARCHIVE_THRESHOLD` / `rename_archive_threshold`），当前以「N / 阈值 3」硬拼在一行里。

### 待裁决
1. 「本次成功/失败/跳过」是**自启动累计**（重载清零）——落盘持久化（推荐，与转移做种一致）还是保持现状？
2. 卡片表格是否带「操作」列（补刀/恢复/删除），还是卡片只读、操作留在专项页签（推荐只读，避免两处重复且误触）？
3. 「脏名称 N」是否升为徽标（会发现被污染的原名记录）？
4. 归档徽标是否显示阈值（「34 / 阈值 3」）还是只显示归档数？

---

## 2. H&R 管理页

### 标题徽标
`启用/关闭` · `观察中` · `保护闸门：开启/关闭/无法确认`
（「无法确认」来自 `modules/hr/guard.py` 的 `unconfirmed`，生命周期层 `expect`/`mark_unconfirmed`；诊断页已有同类状态，见 `Page.vue` 自动删种「保护闸门：无法确认（已保守跳过）」）

### 统计徽标行（推荐 6 个 + 1 个合并）
| 徽标 | 字段（`get_service_infos().summary`） |
| --- | --- |
| 任务总数 | `total` |
| 待做种 | `needs_seeding` |
| 做种中 | `in_progress` |
| 已达标 | `compliant` |
| 超期 | `overdue` |
| 已删除 | `deleted` |
| 跳过 | `skip_stats` 四类**合并 1 个**（hover/详情展开四类明细） |

`pending` 字段也存在（`_STATUS_SUMMARY_FIELDS` 映射），但语义上是「待检查」的过渡态，建议不占徽标。

### 明细表格：H&R 任务（数据源 `GET /hr/tasks`，字段来自 `modules/hr/service.py:512-526`）
| 列 | 字段 |
| --- | --- |
| 名称 | `name` |
| 站点 | `site` |
| 状态 | `status_text`（中文） |
| 进度 | `progress`（0–1 → 百分比） |
| 剩余 | `remain_seconds`（→ 天/小时） |
| 截止 | `deadline`（时间戳，0 = 未设考核期） |
| 类型 | `type` |
| 下载器 | `downloader_id` |
| hash | `torrent_hash` 前 8 位 |
| 操作 | 清理（`/hr_clear_task`）、达标清理（`/hr_clear_compliant`）、缺失清理（`/hr_clear_missing`） |

### 现状缺口 / 注意
- H&R 的「清理」**不是清日志**，而是丢弃任务纳管记录（`CLEARABLE_STATUSES = (NEEDS_SEEDING, COMPLIANT, OVERDUE)`，`modules/hr/service.py:41`）——语义与其它模块的「清理记录」不同，按钮文案必须区分，否则用户会以为只是清历史。
- 四类跳过统计来自内存 guard（见 §0），重载清零；若按转移做种页的决定「不做跳过统计」，本页也应一致处理（待裁决 3）。
- 保护闸门状态是全局单一开关 + 快照，不是每任务字段。

### 待裁决
1. 任务表是否显示 `progress`（进度）与 `remain_seconds`（剩余）两列都留，还是只留更直观的一列？
2. 「跳过」徽标：合并 1 个（推荐）还是四类全列？
3. H&R 跳过统计（内存、重载清零）与其他模块统一处理方式：删除 / 持久化后显示 / 只在本页显示（需全模块一致）？
4. H&R 任务表的「操作」列是否保留三个清理入口（有误删风险，需二次确认文案写明后果）？

---

## 3. 自动删种页

数据源：`GET /autoremove_status` → `service.get_module_status()`（`modules/autoremove/service.py:152-168`）+ 落盘 `remover_state`（`_record_status`，`service.py:392-411`）。

### 标题徽标
`启用/关闭` · `观察中` · `保护闸门：开启/关闭/无法确认`（`guard_enabled` / `guard_unconfirmed`）

### 统计徽标行（推荐 7 数字 + 3 非数字进副标题）
| 徽标 | 字段 |
| --- | --- |
| 候选 | `candidates` |
| 暂停 | `paused` |
| 删除种子 | `deleted` |
| 删除文件 | `deleted_files` |
| 跳过（H&R 保护） | `skipped_protected` |
| 跳过（已消失） | `skipped_missing` |
| 失败 | `failed` |

非数字三项放标题右侧副标题：动作 `action`（暂停 / 删除种子 / 删除种子及文件）、触发来源 `last_trigger`、最近运行 `last_run_at`（转相对时间）。
`config_error` 非空时单独出 `VAlert`（error 色），不占徽标位。

注意：**徽标的 `candidates` 是本轮命中总数，而表格只有前 50 条**（`REMOVER_CANDIDATE_VIEW_LIMIT = 50`，`modules/autoremove/constants.py:21-22`，`service.py:260-262` 截断）→ 截断提示必须写明，否则会被误读为「只有 50 个」。

### 明细表格

**表 1：候选明细**（本轮或「预览」即时结果，字段见 `RemoveCandidate.to_view()`，`modules/autoremove/models.py:92-113`）
| 列 | 字段 | 现有页签是否显示 |
| --- | --- | --- |
| 下载器 | `downloader_id` | ✅ |
| 名称 | `name` | ✅ |
| 站点 | `site` | ✅ |
| 体积 | `size_text` | ✅ |
| 分享率 | `ratio` | ✅ |
| 做种时长 | `seeding_hours`（小时） | ✅ |
| 命中原因 | `reason` | ✅ |
| 平均上传 | `average_upload_bps` | ❌ 未显示 |
| 分类 | `category` | ❌ |
| 标签 | `tags`（数组） | ❌ |
| 状态 | `state` | ❌ |
| 同数据 | `same_data`（标记） | ❌ |
| hash | `torrent_hash` 前 8 位 | ❌ |

现有页签表 7 列在 `Page.vue:1730-1740`（桌面）+ 移动卡片 `Page.vue:1744+`。

**表 2：按下载器明细**（`remover_state.details`，**当前 UI 完全未展示**）
| 列 | 字段（`_downloader_detail`，`service.py:444-456`） |
| --- | --- |
| 下载器 | `downloader` |
| 候选 | `candidates` |
| 暂停 | `paused` |
| 删除种子 | `deleted` |
| 删除文件 | `deleted_files` |
| 跳过保护 | `skipped_protected` |
| 跳过缺失 | `skipped_missing` |
| 失败 | `failed` |
| 错误 | `error` |

### 现状缺口
- 按下载器明细 `details` **已落盘但前端从未展示**（`_autoremove_detail` 也只把它当 items 用候选列表）。
- 候选表缺 4 类已有字段（平均上传 / 分类 / 标签 / 同数据）。
- 观察期提示已存在（`Page.vue:1707-1709` 的 `VAlert`）。

### 待裁决
1. 候选表是否补 `average_upload_bps` / `category` / `tags` / `same_data` 四列（更全，但列数到 11，桌面表需要横向滚动）？
2. 是否新增「按下载器」表（数据现成；单下载器时只是冗余一行，多下载器时才有价值）？
3. 「动作」用文字值做徽标，还是放标题副标题（推荐副标题，徽标行保持纯数字）？
4. `config_error` 单独 `VAlert`（推荐）还是并入徽标行？
5. 候选 50 条上限：提升（改后端常量）还是保留 + 截断提示写明？

---

## 4. 失败清理页

数据源：`GET /failclean_status` → `service.get_module_status()`（`modules/failclean/service.py:170-189`）。

### 标题徽标
`启用/关闭` · `观察中`

### 统计徽标行（推荐 5 个 + 1 合并）
| 徽标 | 字段 |
| --- | --- |
| 本轮扫描 | `scan.scanned` |
| 本轮清理 | `scan.cleaned` |
| 本轮失败 | `scan.failed` |
| 累计清理 | `total.cleaned` |
| 累计失败 | `total.failed` |
| 跳过 | `scan.skipped` + `event.skipped` + `total.skipped` + `skip_stats` 四类（合并 1 个，展开看明细） |

`event`（事件删除 / 失败 / 跳过）建议并入副标题或合并徽标，避免徽标行过长。
`retain_hours`（保留期）、`last_scan_trigger`（巡检触发）、`last_scan_time`（最近巡检）放副标题。

### 明细表格：**没有逐条记录可用**
- `_recent_deletes` 只是 30 秒去重表（`(hash, 路径) → 时间戳`，`service.py:90`、`_is_recent_delete`/`_mark_recent_delete` `service.py:389-400`），初始化即清空，不能当记录。
- `_scan_once` 的 `cleaned_paths` / `failed_paths` 是**局部变量**（`service.py:220-221`），不落盘。
- 现状：`Page.vue` 里**根本没有 `activeTab === 'failclean'` 的模板块**（7 个 `v-if="activeTab === ..."` 中没有 failclean），`MODULE_RECORD_VIEWS.failclean.anchor` 为空串并注明「失败清理没有逐条记录，只切页签看最近一次执行结果」（`Page.vue:787`）→ **失败清理页签目前是空白页**。

若要按「细节=表格」的方向做本页，只有两条路：
- **A 不加写入点**：卡片只出徽标 + 一句空态说明（「本模块只保留计数，不保留逐条记录」）。零风险，但本页没有表格。
- **B 新增逐条记录**：在 `handle_transfer_failed`（事件即时删除）与 `_scan_once`（巡检清理）两处登记内存环形缓冲（如最近 50 条：时间 / 文件名 / 路径 / 结果 / 原因），随 status 一起暴露。需要动写操作路径，**未授权前不做**（且注意 `clear_history()` 已定义「清最近结果保留累计」的语义，环形缓冲要同步清理）。

### 待裁决
1. 走 A（无表格，只计数）还是 B（新增环形缓冲记录）？B 需要授权动两个写入点。
2. 若走 A：本页保留空态说明，还是干脆隐藏该页签（TABS 里去掉 `failclean`）？
3. 徽标取 6 个（上述）是否过多？`event` 三段计数放徽标还是副标题？
4. 保留期 / 巡检触发 / 最近巡检是否统一放副标题（推荐）？

---

## 3. 后续页顺序（讨论排期）
1. **转移做种**（已出方案：`.ralph/dml-page-transfer-plan.md`，待 5 项裁决）
2. **种子重命名**（本文 §1）、**H&R 管理**（本文 §2）← 本轮
3. 自动删种 → 失败清理 → 站点标签 → 上传限速
4. 最后：**运行诊断** + **运行总览**两页整体设计（用户 m19987）
