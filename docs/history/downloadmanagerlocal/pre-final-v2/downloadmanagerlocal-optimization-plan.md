# 历史资料：禁止作为当前执行指令

> 本文已由 `docs/downloadmanagerlocal-final-implementation-spec.md` 取代。仅供追溯，旧待裁决、默认值、回退命令不得照抄执行。
> 原路径：`docs/downloadmanagerlocal-optimization-plan.md`。原文保存在下方，不代表现行约定。

---

# DownloadManagerLocal 七项优化执行方案（可交接版）

本文是交给执行模型（含低推理能力模型）的实施方案。按编号顺序执行；每一步都写明文件、命令、判定条件与停止条件。禁止自行扩大范围或改变设计。

---

## 0. 交付前置状态

- 本文编制时**尚未授权开始修改代码**。用户明确回复“开始按此方案执行”后，才进入开发阶段。
- 当前基线版本：`3.9.12`（在 `plugins.v3/downloadmanagerlocal/__init__.py` 的 `plugin_version` 与 `package.v3.json` 的 `version` 中确认）。执行时必须重新核对实际值。
- 编制时工作区已有未提交改动，禁止重置、覆盖或回滚：
  - 已修改：`frontend.v3/downloadmanagerlocal/src/components/Config.vue`、`package.v3.json`、`plugins.v3/downloadmanagerlocal/__init__.py`、`plugins.v3/downloadmanagerlocal/modules/hr/service.py`、`plugins.v3/downloadmanagerlocal/dist/assets/remoteEntry.js`
  - 新增：`frontend.v3/downloadmanagerlocal/tests/`（含 `config-setup.test.mjs`、`config-browser.html`）、`plugins.v3/downloadmanagerlocal/dist/assets/__federation_expose_Config-BUXSx-eE.js`、`plugins.v3/downloadmanagerlocal/dist/assets/__federation_expose_Config-BudxCGgM.css`、`tests/v3/downloadmanagerlocal/test_hr_check_snapshots.py`
  - 删除：`plugins.v3/downloadmanagerlocal/dist/assets/__federation_expose_Config-CLN3Fucu.js`、`...-CPcpSvl6.css`
- 环境：Windows 原生 Niubash shell；Python 一律用 `micromamba run -n base python`，不要用 `python3` / 裸 `python`。
- 仓库根：`D:/work/project/person/MoviePilot-Plugins`

### 绝对禁止
1. 不重写整体架构，不引入通用事件总线、模块加载框架、策略引擎、消息队列、国际化框架。
2. 不重新设计页面导航与整体布局。
3. 不引入 IYUU、速度监控等已移除功能。
4. 不修改其他插件、下载器配置、站点配置或其他容器。
5. 不用真实种子测试删除、改名、打标、限速等写操作。
6. 不用清空配置解决兼容问题。
7. 不为了掩盖初始化错误而自动关闭用户模块开关。
8. 不把预览结果当作真实执行成功。
9. 不分别部署前端和后端；最终只部署同一版本的完整插件包。

---

## 1. 已确认需求（无需再问）

| 项 | 要求 |
| --- | --- |
| 模块隔离 | 模块独立启停；保留明确的前后置条件与联动；关闭的模块不干扰其他模块 |
| 通知 | 统一格式；各模块保留独立通知开关 |
| 数据清理 | 各模块适合清理的历史与归档；不额外增加统计重置 |
| 观察模式 | **每模块独立开关**，不加全插件强制观察总开关 |
| 下载器标识 | 品牌图标＋实例名称，设置页与数据页统一 |
| 设置页边框 | 去掉插件内层套框，保留宿主弹窗外壳 |
| 文案 | 简短、统一、易懂；必要说明放对应控件下方 |
| 统一名称 | **种子重命名**、**H&R 管理**、**观察模式**、**定时补查** |
| 工程约束 | 最小修改，优先复用现有函数 |

---

## 2. 必须先问用户的三个决策（未确认前不得进入开发）

三个问题一次问完，记录答案后再继续。

**决策 A｜观察开关的升级默认值**
现状：`migration_observe_only`（`plugins.v3/downloadmanagerlocal/modules/autoremove/constants.py` 的 `MIGRATION_OBSERVE_ONLY_KEY`）只控制自动删种。
建议口径：老配置升级时，自动删种继承原值；其他模块保持升级前实际行为（默认允许执行），不在升级瞬间改变写入权限；全新安装时有写操作的模块默认开启观察；一旦保存过新开关则优先用新值。
**禁止**把原自动删种的观察值直接套用到所有模块。

**决策 B｜观察模式与已有上传限速恢复**
已修改过上传限速后开启观察模式，二选一：
1) 禁止一切限速写入，已有额度保持（建议）；
2) 允许一次明确确认的“恢复原限速”，之后进入观察。
不允许把恢复写操作当作只读清理执行。

**决策 C｜清理重命名归档后是否允许重新补试**
归档状态参与自动重试筛选，删除记录会改变后续行为，二选一：
1) 只清显示记录，保留“不自动重试”标记；
2) 连归档状态一起删除，允许重新识别、重试。
选 2 时确认框必须写明后果。

---

## 3. 阶段一：核对基线（只读，不改代码）

### 3.1 读规则
先读 `AGENTS.md`、`plugins.v3/downloadmanagerlocal/AGENTS.md`，遵守其中的编辑规范、相对导入要求与发布三处同步要求。

### 3.2 基线命令（仓库根）
```bash
git status --short
git diff --stat
micromamba run -n base python -m json.tool package.v3.json > /dev/null
micromamba run -n base python -m pytest tests/v3/downloadmanagerlocal -q --tb=short
cd frontend.v3/downloadmanagerlocal && node --test tests/config-setup.test.mjs && npm run build
```
参考基线：后端 `201 passed`、前端 `5 passed`。这只是历史参考，新增测试后数目可增加。
**基线下不通过时：先记录失败并区分“已有问题 / 本轮引入”，不要大范围顺手修复。**

### 3.3 建立写操作清单（手工即可，不要写自动扫描框架）
按以下字段列表：
```text
模块 | 入口 | 实际写函数 | 是否已有观察判断 | 关联后续动作
```
至少覆盖：定时任务、下载/整理事件、页面手动操作、后台校验与重试、停止/重载时的恢复操作、模块间联动。

---

## 4. 阶段二：模块隔离

### 4.1 涉及文件
- `plugins.v3/downloadmanagerlocal/utils/config.py`
- `plugins.v3/downloadmanagerlocal/core/config.py`
- `plugins.v3/downloadmanagerlocal/core/lifecycle.py`
- `plugins.v3/downloadmanagerlocal/core/scheduler.py`
- `plugins.v3/downloadmanagerlocal/modules/*/events.py`
- `plugins.v3/downloadmanagerlocal/controller/handlers.py`

### 4.2 已知风险点（直接修）
1. `core/config.py` 的 `initialize_runtime_config(plugin, config=None)` 在模块门控判定前就无条件执行 `plugin._rename_config = build_rename_config(config)` 与 `plugin._site_tag_config = build_tag_config(_flat_tag_module_config(config))`，关闭模块或坏配置仍会被解析。
2. `core/lifecycle.py` 的 `_disable_invalid_transfer_config(plugin, config)` 会把插件**总开关**关掉并落盘（`plugin._enabled = False` + `plugin.update_config`）。
3. `core/lifecycle.py` 的 `_init_service_isolated(plugin, label, module, service_cls, config)` 中 `service = service_cls(plugin)` 在 `try` 之外，构造异常会中断整个初始化。
4. 同函数 except 分支会 `config[disable_key] = False` 并 `plugin.update_config(config=config)` 落盘关闭模块开关。
5. 需检查上传限速启动/恢复（`start_upload_limit_worker`、`restore_upload_limits`）与做种校验 worker（`ensure_seed_recheck_worker`）是否遵循同一隔离边界。

### 4.3 修改要求
**A. 模块关闭时**：不执行该模块业务初始化与业务写操作；不因该模块遗留坏配置阻断其他模块；允许读取该模块历史数据；资源收尾若涉及下载器写入，按观察模式口径处理。
**B. 模块启用但配置错误时**：只把该模块标记为运行异常；不改插件总开关；不改用户持久化开关；页面显示模块名与简短原因；不启动该模块无法安全运行的任务。
**C. 异常隔离**：对象构造与初始化都纳入该模块异常边界；定时任务声明、事件分支、停止操作分别隔离；不要在普通函数外重复套 `try/except`。
**D. 联动**：关联模块关闭 → 跳过该联动；关联模块观察 → 只生成该模块自己的预览；前置动作失败或仅预览 → 不执行依赖其真实成功的后续动作；H&R 启用但保护状态无法确认 → 仅阻止相应危险删除，不拖停其他动作。

### 4.4 验收
- 仅开启任意单模块均可运行。
- 关闭模块带坏配置，其他模块正常。
- 转移配置错误不会关闭整个插件。
- 模块初始化异常不会自动改写用户开关。
- 页面能区分“关闭”与“故障”。

---

## 5. 阶段三：每模块观察模式

### 5.1 配置键
沿用现有模块前缀，不新增嵌套配置体系：

| 模块 | 新键 |
| --- | --- |
| 转移做种 | `transfer_observe_only` |
| 种子重命名 | `rename_observe_only` |
| 站点标签与分类 | `tag_observe_only` |
| H&R 管理 | `hr_observe_only` |
| 自动删种 | `remover_observe_only` |
| 失败清理 | `failcleanup_observe_only` |
| 上传限速 | `upload_limit_observe_only` |

旧键 `migration_observe_only` 保留兼容读取，仅作自动删种新键缺失时的回退；升级默认值按决策 A。

### 5.2 实现约束
- 复用 `utils/config.py` 的 `MODULE_SWITCHES` 模块标识（transfer/rename/tag/hr/autoremove/failclean/upload_limit）。
- 允许增加一个小型公共判断函数集中解析模块观察状态；不要把所有下载器调用改写成通用命令对象或代理框架。
- 每个实际写边界必须由后端控制；前端禁用按钮不能代替后端判断。
- 一轮运行使用明确的模式快照；保存开关后新一轮使用新模式；停止/重载要阻止旧后台任务继续写入。
- 新增配置键登记进 `Config.vue` 的 `defaults`，并确认能落入对应页签的重置键集（`PANE_RESET_KEYS`），否则重置按钮覆盖不到。

### 5.3 必须拦截的动作
| 模块 | 观察模式下不得执行 |
| --- | --- |
| 转移 | 添加目标种子、暂停/启动、删除源种子 |
| 种子重命名 | 修改名称、恢复原名 |
| 标签分类 | 增删标签、修改分类 |
| H&R | 自动打标等下载器写操作 |
| 自动删种 | 暂停、移除种子、删除文件 |
| 失败清理 | 删除种子与磁盘文件 |
| 上传限速 | 设置或恢复下载器/单种上传额度 |

只读查询、候选筛选、状态计算允许执行。

### 5.4 预览结果与状态隔离
预览显示：候选对象、拟执行动作、命中条件或跳过原因、尚无法验证的后续条件。
例如转移预览没有真正添加目标种子，不能宣称“目标校验完成”“可安全删源”。

预览**不得**：增加真实成功次数、消耗真实失败重试次数、标记已转移/已改名/已删除、加入真实执行队列、覆盖上传限速恢复依据。
关闭观察模式后重新扫描，不直接执行旧候选清单。

### 5.5 提示规则
- 开关名称固定为 `观察模式`。
- 开启时说明：`只预览候选，不执行写操作。`；涉及文件删除的模块可补 `不会删除种子或文件。`
- 关闭时不显示任何观察期横幅、警告或通知附注；普通失败提示与危险操作确认保持。

---

## 6. 阶段四：统一通知

### 6.1 现状通知位置
`plugins.v3/downloadmanagerlocal/modules/transfer/service.py`、`modules/rename/service.py`、`modules/hr/notify.py`、`modules/autoremove/service.py`、`modules/failclean/notify.py`、`modules/uploadlimit/service.py`（站点标签按现有调用链核对，不新增逐条通知）。

### 6.2 实现
新增一个小型公共函数，例如 `plugins.v3/downloadmanagerlocal/utils/notify.py`，负责：统一标题与文本、统一数量字段含义、按各模块现有通知开关发送、捕获通知异常不中断业务。
不要开发消息队列、模板语言或通知调度系统。

### 6.3 格式
```text
下载中心 · 种子重命名

下载器：QB1
结果：成功 8，跳过 3，失败 1
原因：……
```
观察模式：
```text
下载中心 · 自动删种

预览：12 个候选，未执行
下载器：QB1
```

### 6.4 规则
- 自动任务每轮汇总；无候选、无变化的正常轮次默认不推送。
- 关闭模块不发送其业务通知。
- 手动操作始终有页面反馈，不受外部通知开关影响。
- 通知失败不导致业务重试。
- 页面、日志、通知对“候选/成功/失败/跳过”的含义一致。

---

## 7. 阶段五：数据页清理

### 7.1 涉及文件
- `plugins.v3/downloadmanagerlocal/modules/rename/archive.py`（已有 `list_rename_archive`、`delete_rename_archive`、`restore_rename_archive`、`rename_archive_stats`、`clear_rename_retry_state`、`is_rename_archived` 等，优先复用）
- `plugins.v3/downloadmanagerlocal/model/state.py`、`model/api.py`
- `plugins.v3/downloadmanagerlocal/controller/api.py`、`controller/handlers.py`
  （现有清理类端点参考：`/hr_clear_task`、`/hr_clear_compliant`、`/hr_clear_missing`）
- `frontend.v3/downloadmanagerlocal/src/components/Page.vue`、`components/api.js`

### 7.2 本轮范围
| 模块 | 可以清理 | 不可以清理 |
| --- | --- | --- |
| 种子重命名 | 归档与允许删除的历史记录 | 未确认语义的重试/恢复依据 |
| 转移 | 已结束且不再被活动流程引用的历史 | 活动队列、校验队列、有效源→目标映射 |
| H&R | 已结束、确认可移除的历史 | 未达标或仍需保护的任务 |
| 自动删种 | 历史执行结果 | 下载器中的种子 |
| 失败清理 | 历史结果 | 实际文件与种子 |
| 标签、限速 | 确实已有的历史展示记录 | 当前策略、标签、分类、限速恢复状态 |

没有独立历史数据的模块，不要为凑按钮新造历史系统。

### 7.3 API 与交互
- 写入类清理用 `POST`，沿用现有响应格式与鉴权。
- 后端校验可清理范围，不信任前端传来的 ID。
- 确认前显示对象、范围、数量。
- 确认框写明“不修改下载器数据”或实际影响。
- 返回真实清理数量；只刷新对应模块。
- 沿用已有锁，避免清理与后台保存互相覆盖。
- 不做“清空全部插件数据”入口。

---

## 8. 阶段六：图标、边框、文案

### 8.1 下载器图标
新建共享组件，例如 `frontend.v3/downloadmanagerlocal/src/components/DownloaderBadge.vue`：
- qBittorrent / Transmission / rTorrent 使用本地品牌图标，旁边保留实例名（如 `QB1`）。
- 未知类型用通用图标。
- 设置页 `Config.vue` 与数据页 `Page.vue` 复用同一组件。
- 深浅色主题均可读；不联网加载图标，不引入额外图标框架。
- 现状：`Config.vue` 使用 `mdi-alpha-q-box` 等字母图标（约 329 行附近的 `downloaderIconMap`、`downloaderLabelMap`），需要替换。

### 8.2 设置页边框
`frontend.v3/downloadmanagerlocal/src/components/Config.vue`：
- `.dm-config` 当前为 `width: min(1120px, calc(100vw - 48px)); padding: 8px;`
- `.dm-card` 当前为 `border-radius: 14px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));`
- 处理：去掉与宿主弹窗重复的外边框、外间距、双层圆角；保留内部导航与表格分隔线；保持当前主导航、子页签与表单布局；确认无横向溢出、重复滚动或底部按钮被遮挡。

### 8.3 全部可见文案
检查 `Config.vue`、`Page.vue`、API 反馈与通知中的用户可见文本：
1. 统一使用已确认名称：种子重命名 / H&R 管理 / 观察模式 / 定时补查。
2. 控件名简短；条件、单位、注意事项放下方说明（如 `<div class="dm-hint">`）。
3. 不把内部变量名或配置键当面向用户的说明。
4. 不同页面同一动作口径一致。
5. 正常过滤不写成失败。
6. 必须区分：`清理记录` / `移除标签` / `删除种子` / `删除种子及文件`。
7. 不机械替换代码标识符、API 路径、配置键、历史版本记录。
8. 不为文案引入国际化框架。

---

## 9. 测试要求

只围绕行为断言，不要机械断言整段文案或完整 HTML。

### 9.1 模块隔离
单模块开启；关闭模块带坏配置；启用模块初始化失败；定时任务声明失败；一个事件分支失败其他继续；初始化与运行错误不修改持久化开关。

### 9.2 观察模式（每个有写操作的模块）
1. 开启观察，写函数调用次数为 `0`。
2. 关闭观察，满足条件时调用正确写函数。
3. 定时、事件、手动入口均不能绕过。
4. 预览不增加成功记录、重试次数或真实待执行队列。
5. 模块之间观察状态互不影响。
6. 转移预览不触发真实重命名、打标或删源。
7. 旧配置兼容与新键优先正确。
8. 上传限速恢复符合决策 B。

### 9.3 数据清理
只删除指定历史；活动任务与安全状态保留；非法范围被拒绝；不调用下载器或文件删除接口；清理与后台更新不互相覆盖；重命名后续重试符合决策 C。

### 9.4 既有回归必须保持
- H&R `snapshots` 修复（`tests/v3/downloadmanagerlocal/test_hr_check_snapshots.py`）。
- 带 H&R 分档 YAML 的配置页初始化（`frontend.v3/downloadmanagerlocal/tests/config-setup.test.mjs`）。
- 转移任务打开、保存不丢失。
- 路径映射两端均空允许执行；只填一端拒绝保存。

---

## 10. 发布与完整部署门槛

### 10.1 开发完成后（仓库根）
```bash
micromamba run -n base python -m json.tool package.v3.json > /dev/null
micromamba run -n base python -m pytest tests/v3/downloadmanagerlocal -q --tb=short
cd frontend.v3/downloadmanagerlocal && node --test tests/config-setup.test.mjs && npm run build
```
另需：所有 `.py` 通过 `micromamba run -n base python -c "import ast; ast.parse(open('<file>').read())"`；本地真实页面核对七项行为；核对 git diff 只含本轮目标与直接依赖。

### 10.2 版本三处同步
- `plugins.v3/downloadmanagerlocal/__init__.py` 的 `plugin_version`
- `package.v3.json` 的 `version`
- `package.v3.json` 的 `history` 顶部新条目（编辑规范见仓库 `AGENTS.md` 与插件 `AGENTS.md`：禁止用相邻行替换法插入，优先单行整行替换或全量重写，改完立即校验 JSON）

版本号以执行时仓库状态决定，不要提前硬编码。提交/推送需用户对该轮授权。

### 10.3 QNAP 部署（需用户单独授权；只碰 MP 容器）
- SSH 主机：`qnap`；Docker：`/share/CACHEDEV9_DATA/.qpkg/container-station/bin/docker`；容器：`MP`
- 容器内插件目录：`/app/app/plugins/downloadmanagerlocal`
- 容器内 API：`http://127.0.0.1:3000`，密钥文件 `/tmp/.mpq_key`（不得打印密钥内容）
- 可用完整部署脚本：`D:/tmp/dml_full_deploy.py`（模式 `pack` / `plan` / `apply` / `verify`，本地打包生成 `D:/tmp/dml-3.9.12.tgz` 与 `D:/tmp/dml-3.9.12-manifest.json`）。若 `D:/work/tmp/dml-test/deploy_mirror.py` 存在，可参照其全类型校验口径（本方案未核实该脚本是否仍在）。
- 上传链路：先 `octssh_transfer` 上传到 `qnap:/tmp/`，再 `docker cp` 进 `MP:/tmp/`，最后 `docker exec MP python /tmp/<script> <mode>`
- 部署报告与备份：`/config/dml-hotfix-backups/`（最近一次为 `full-3.9.12-20261029T014201Z`，报告 `full-3.9.12-report.json`）
- reload 端点：`POST /api/v1/plugin/reload/DownloadManagerLocal`（用类名，不是小写目录名）

步骤：①检查一次性执行标志（`onlyonce`），防止 reload 触发业务；②对容器内**完整插件目录**做带时间戳备份；③保全完整配置且不打印凭据；④准备完整包（后端＋资源＋前端 `dist`）；⑤列出新增/覆盖/过时文件清单并确认只涉及本插件；⑥完整部署并清理本插件过时资源；⑦校验文件集合与每个文件哈希；⑧reload 一次；⑨检查运行版本、配置与新增日志；⑩在 QNAP 真实页面确认任务列表、图标、边框、观察提示、清理入口。

不得用 HTTP 200、文件已上传或本地测试通过代替线上页面验收。没有测试下载器或单独授权时，真实写动作标为未验证。

---

## 11. 执行模型停止条件

出现以下情况立即停止并报告，不自行兜底：
- 第 2 节三个决策未确认；
- 需要删除安全状态或有效转移映射；
- 无法判断某“恢复”操作是否属于下载器写入；
- 需要改现役配置才能继续测试；
- 需要修改其他插件或容器；
- 发现本轮之外的问题需要较大重构；
- 测试持续失败且原因未定位；
- 部署文件清单出现非预期删除；
- 本地版本、运行版本与安装状态不一致且原因不明。

停止时按此格式报告：
```text
已完成：
当前阻塞：
相关文件：
失败证据：
需要用户决定：
未执行的操作：
```

---

## 12. 最终交付内容

1. 七项需求逐项完成情况；
2. 采用的三个决策；
3. 版本与提交；
4. 实际测试结果；
5. 可重新运行的验证命令；
6. 完整部署文件清单校验结果；
7. 备份、日志、截图位置；
8. 未验证项与遗留问题。

**执行原则：先确认缺失决策，再按阶段最小实现；开发可分步骤，交付必须是一个完整、可验证的版本。**
