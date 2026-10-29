# 历史资料：禁止作为当前执行指令

> 本文已由 `docs/downloadmanagerlocal-final-implementation-spec.md` 取代。仅供追溯，旧待裁决、默认值、回退命令不得照抄执行。
> 原路径：`.ralph/dml-ui-improvement-report.md`。原文保存在下方，不代表现行约定。

---

# DML 数据页展示体系改进报告（P7-2c）

## 结论与执行边界

**建议采用：A 轻量记录入口、B 查询参数、C 保留两层展示并统一展示组件、D 旧记录显式回退。**

本轮不建议新增七模块执行日志存储。应先补齐现有数据的真实读取链路、条数限制、名称展示和清理语义，再完成本地 MP 页面验收。

**当前不能将 P7-2c 标为完成。** 除四项需求尚未实施外，本次发现以下直接影响实施的事实：

1. 总览页面首次打开不会加载 `diagnostics`，因此新增的 `module_details` 未必显示。
2. `transfer_stats` 清理的是统计，不是转移记录。不能把该接口包装成“清理转移执行记录”。
3. 转移记录的实际写入点在 `modules/transfer/pipeline.py`，不在 `modules/cleanup/service.py`。
4. H&R 列表优先显示站点名，不一定显示种子名。
5. 自动删种、失败清理的现有清理接口只修改持久化数据，没有同步服务内存状态；直接增加按钮会暴露“清完仍显示、以后又写回”的问题。
6. 失败清理状态包含累计计数。按照方案“不额外增加统计重置”的边界，新按钮不能借“清理记录”清空累计计数。

本报告是只读分析和实施建议，**未修改仓库、未运行测试、未执行本地 reload 或部署**。其中测试通过数量引用历史任务记录，不冒充本次实测。

执行模型必须先取得用户对 A—D 推荐组合的确认，再实施下文步骤。提交、推送、QNAP 部署均不包含在实施授权中。

---

## 一、基线与文档差异

### 1.1 以实际文件为准

本次读取时：

- `plugins.v3/downloadmanagerlocal/__init__.py:49` 为 `plugin_version = "3.9.12"`。
- `frontend.v3/downloadmanagerlocal/src/components/Page.vue` 实际为 **2590 行**，不是背景中的约 4400 行。
- 下列指定文件不存在：
  - `plugins.v3/downloadmanagerlocal/modules/diagnostics/handlers.py`
  - `plugins.v3/downloadmanagerlocal/modules/rename/handlers.py`
  - `plugins.v3/downloadmanagerlocal/modules/transfer/handlers.py`
- 当前相关 handler 集中在 `plugins.v3/downloadmanagerlocal/controller/handlers.py`。**不得为了匹配任务描述而创建上述三个文件。**

工作区存在大量阶段七之前的在途改动及新增测试、构建产物。实施时只撤销自己新增的修改，禁止 `git reset --hard`、`git clean` 或整文件恢复到 HEAD。

### 1.2 权威方案的章节编号与任务描述不同

实际 `docs/downloadmanagerlocal-optimization-plan.md`：

| 内容 | 实际章节和证据 |
|---|---|
| 不额外增加统计重置 | §1，`:37` |
| 无历史数据不新造历史系统 | §7.2，`:231` |
| 清理接口与锁要求 | §7.3，`:233-240` |
| 测试要求、禁止机械断言整段文案 | §9，`:273-298` |
| 发布、本地验证、QNAP 部署 | §10，`:301-329` |
| 停止条件 | §11，`:333` 起 |

文件没有任务描述所称的“§4.7 阶段七”；实际 §6 是通知要求，不是测试要求。本报告按实际章节内容执行，不按错误编号推导要求。

### 1.3 测试数量

`.ralph/dml-seven-optimizations.md` 的迭代13记录后端 **262 passed**，迭代14新增 `test_module_details.py` 的六项测试后记录 **268 passed**；前端仍为 **6 pass**。

因此：

- 262 是较早基线，不应作为当前精确数量。
- 实施前重新跑一次全量，记录实际收集数和通过数。
- 不得删掉迭代14测试来“回到 262”。
- 本报告没有独立重跑上述命令。

---

## 二、四项需求现状核对

### 2.1 各模块表现风格统一

**核对结论：主线报告对“三套展示方式并存”的判断成立，但不能据此认定真实页面已展示完整。**

证据：

- 总览模块卡：`frontend.v3/downloadmanagerlocal/src/components/Page.vue:1292-1398`。
- 原有摘要行 `card.details`：`frontend.v3/downloadmanagerlocal/src/components/Page.vue:1372-1376`。
- 新增运行明细 rows/items：`frontend.v3/downloadmanagerlocal/src/components/Page.vue:1380-1394`。
- 上传限速独立分支：`frontend.v3/downloadmanagerlocal/src/components/Page.vue:1327-1366`。
- 专项记录区：
  - 命名历史：`frontend.v3/downloadmanagerlocal/src/components/Page.vue:1402`
  - 重命名归档：`frontend.v3/downloadmanagerlocal/src/components/Page.vue:1481`
  - 自动删种候选：`frontend.v3/downloadmanagerlocal/src/components/Page.vue:1558`
  - H&R：`frontend.v3/downloadmanagerlocal/src/components/Page.vue:1622`
  - 转移：`frontend.v3/downloadmanagerlocal/src/components/Page.vue:1683`
  - 站点标签工具：`frontend.v3/downloadmanagerlocal/src/components/Page.vue:1823`

结构差异：

- 普通模块：标签值网格＋两行明细卡。
- 专项记录：桌面表格＋移动卡片。
- 上传限速：下载器状态卡＋站点状态网格。
- 空态分别使用 `.dm-state`、`.dm-monitor-empty` 等不同规则，见 `frontend.v3/downloadmanagerlocal/src/components/Page.vue:2256,2275`。

**新增反证：数据读取没有接通。**

- `moduleDetails` 只读取 `diagnostics.value?.module_details`：`frontend.v3/downloadmanagerlocal/src/components/Page.vue:705-713`。
- 首次挂载调用 `refreshActive()`：`frontend.v3/downloadmanagerlocal/src/components/Page.vue:1187-1190`。
- 总览刷新只调用 `loadOverview`、`loadModuleStatuses`：`frontend.v3/downloadmanagerlocal/src/components/Page.vue:755-765`。
- 当前只有诊断页分支调用 `loadDiagnostics`：`frontend.v3/downloadmanagerlocal/src/components/Page.vue:780-801`。

因此，直接进入总览时，`diagnostics` 初始为 `null`，运行明细没有数据；先进入诊断页再返回总览，才可能显示之前读取的快照。**必须新增首次总览加载与刷新链路测试。**

另外，上传限速位于 `v-if` 独立分支，通用运行明细位于其 `v-else`，所以即使后端返回了 `module_details.upload_limit`，当前模板也不渲染这一通用明细。

### 2.2 执行记录查看／清理按钮

**核对结论：各模块拥有的数据性质不同，不能统一称作“执行日志”。主线报告对转移清理能力的描述有实质错误。**

| 模块 | 当前真实数据 | 推荐入口名称 | 当前可复用的清理能力 |
|---|---|---|---|
| 转移 | 来源→目标映射、事务状态、在途队列 | 查看转移记录 | **不能用 `transfer_stats` 清记录** |
| 重命名 | 成功／失败历史及失败归档 | 查看执行记录 | `rename_history`、`rename_archive` |
| H&R | 当前纳管任务与保护状态 | 查看任务 | 既有已满足／已消失／单条清理 |
| 自动删种 | 最近一轮候选与结果 | 查看本轮结果 | `autoremove_state`，须修内存同步 |
| 失败清理 | scan/event/total 三组计数 | 查看运行明细 | 须明确“最近结果”与累计计数边界 |
| 站点标签 | 本轮聚合统计、标签清理扫描快照 | 查看运行明细 | 无独立持久化历史清理 |
| 上传限速 | 下载器／站点运行状态与错误 | 查看运行状态 | 无独立执行历史清理 |

证据：

- 清理白名单：`plugins.v3/downloadmanagerlocal/controller/handlers.py:460-507`。
- `transfer_stats` 仅遍历 `TRANSFER_STATS_KEY`、`TRANSFER_SKIP_STATS_KEY` 并写空字典：`plugins.v3/downloadmanagerlocal/controller/handlers.py:480-487`。
- 转移记录由 `_iter_transfer_records` 枚举来源映射，再投影到 records：`plugins.v3/downloadmanagerlocal/controller/handlers.py:818-844,906-930`。
- 来源映射供同步删除关联目标：`plugins.v3/downloadmanagerlocal/modules/transfer/pipeline.py:41-58`；同步删除实际读取它：`plugins.v3/downloadmanagerlocal/modules/cleanup/service.py` 的 `_cleanup_transfer_target`。
- H&R 已有按钮：`frontend.v3/downloadmanagerlocal/src/components/Page.vue:1630-1631,1659,1677`。
- 标签扫描调用的是 `POST tag_cleanup_scan`，不是纯查看历史：`frontend.v3/downloadmanagerlocal/src/components/Page.vue:1130-1145`。**查看记录按钮不得偷偷触发它。**

#### 清理缓存问题

- 当前自动删种清理只执行 `save_data(...,{})`：`plugins.v3/downloadmanagerlocal/controller/handlers.py:489-493`。
- API 状态读取服务的 `self._status`：`plugins.v3/downloadmanagerlocal/modules/autoremove/service.py:151-155`。
- 后续运行又将 `self._status` 保存：`plugins.v3/downloadmanagerlocal/modules/autoremove/service.py:389-390`。
- 失败清理同样只写空持久化：`plugins.v3/downloadmanagerlocal/controller/handlers.py:495-499`。
- 失败清理 API 返回内存状态：`plugins.v3/downloadmanagerlocal/modules/failclean/service.py:168-179`，后续保存内存状态：`plugins.v3/downloadmanagerlocal/modules/failclean/service.py:423-425`。

现有清理测试使用 `FakePlugin` 内存字典，没有覆盖真实服务缓存，见 `tests/v3/downloadmanagerlocal/test_cleanup_module_data.py:63-73,206-235`。

**实施结论：先修清理状态同步，再增加对应按钮。不得通过 reload 插件来伪装清理成功。**

### 2.3 明细最大条数可调

**核对结论：主线报告基本正确，但“改一个常量即可”不成立。**

证据：

- `MODULE_DETAIL_ITEM_LIMIT = 20`：`plugins.v3/downloadmanagerlocal/modules/diagnostics/service.py:156`。
- `_detail` 固定截断 items，不返回 total/limit/truncated：`plugins.v3/downloadmanagerlocal/modules/diagnostics/service.py:193-200`。
- 重命名更早已截成最近五条：`plugins.v3/downloadmanagerlocal/modules/diagnostics/service.py:58-62`。
- 重命名明细消费的是上述截断列表：`plugins.v3/downloadmanagerlocal/modules/diagnostics/service.py:278-285`。
- 历史页分页固定 15：`frontend.v3/downloadmanagerlocal/src/components/Page.vue:51,625,638`。
- 转移记录每页 15：`frontend.v3/downloadmanagerlocal/src/components/Page.vue:582-586`。

必须区分：

1. `detail_limit`：总览／通用运行明细中的 items 样本上限。
2. `page_size`：命名历史、归档、转移记录的分页大小。
3. 观察预览的内存样本上限：`plugins.v3/downloadmanagerlocal/utils/config.py:275,289-306`。

本轮只调整第1项，不把另外两项一起改动。

### 2.4 列表显示种子名，而非只有 hash

**核对结论：转移记录确有缺口，但不止主线报告所说的一处；H&R 的“已显示名字”也需要修正。**

#### 转移记录

- 在途事务只显示短 hash：`frontend.v3/downloadmanagerlocal/src/components/Page.vue:1757`。
- 最近记录桌面表格只显示短 hash：`frontend.v3/downloadmanagerlocal/src/components/Page.vue:1792`。
- 最近记录移动卡片只显示短 hash：`frontend.v3/downloadmanagerlocal/src/components/Page.vue:1812`。
- 主线报告引用的移动端 `:3248` 不适用于当前2590行文件。

根因：

- `begin_transfer` 构造 item 时不保存种子名：`plugins.v3/downloadmanagerlocal/modules/transfer/pipeline.py:90-115`。
- `save_source_record` 将 item 保存为来源映射：`plugins.v3/downloadmanagerlocal/modules/transfer/pipeline.py:50-59`。
- handler 投影 pending、records 时也没有名称字段：`plugins.v3/downloadmanagerlocal/controller/handlers.py:885-919`。

**主线报告把写入点归到 cleanup/service.py 不正确；该文件主要读取映射执行同步删除。**

#### H&R

当前标题实际是：

`task.site || task.name || task.torrent_hash`

见 `frontend.v3/downloadmanagerlocal/src/components/Page.vue:1652,1667`。

站点存在时，种子名只在 `title` 提示中，不直接显示。应改为种子名作为主标题，站点作为次级信息，桌面与移动同时修改。

#### 其他列表

- 命名历史已有原名／改名：`frontend.v3/downloadmanagerlocal/src/components/Page.vue:1432-1433,1449`。
- 自动删种已有名称：`frontend.v3/downloadmanagerlocal/src/components/Page.vue:1594,1607`。
- 通用候选优先取 name：`plugins.v3/downloadmanagerlocal/modules/diagnostics/service.py:222`。
- 标签、上传限速的部分 items 是**站点聚合**，不是种子列表。不得把站点名伪装成缺失种子名。

---

## 三、四个裁决点

### A．执行记录：推荐轻量方案

**推荐：复用现有数据入口与安全清理接口，不新增七模块日志存储。**

理由：

- 符合方案 §7.2“不为凑按钮新造历史系统”。
- 当前模块的数据并非同一种历史事件；统一入口比强行统一存储更小、更可靠。
- 避免在上传限速等高频路径增加持久化写入。
- 阶段七已有较多待验收改动，不应再改变七条业务写入链路。

必须采用以下按钮映射：

| 模块键 | 查看动作 | 清理动作 |
|---|---|---|
| transfer | 跳转 transfer，并定位最近记录 | 不新增；不清来源映射 |
| rename | 跳转 history，定位命名历史／归档 | 两个独立按钮，分别调用原白名单对象 |
| hr | 跳转 hr | 定位既有安全清理按钮，不新增“清空全部” |
| autoremove | 跳转 autoremove | 修好缓存同步后清理最近运行结果 |
| failclean | 跳转 failclean | 清理最近结果，**保留累计计数** |
| tag | 跳转 sitetag，展开运行明细 | 不显示历史清理按钮 |
| upload_limit | 跳转 upload，展开运行状态 | 不显示历史清理按钮 |
| seed | 保留现有说明 | 不造第八套记录 |

**被否方案：完整环形缓冲＋七模块登记＋新 API＋统一抽屉。**

代价与拒绝理由：

- “七模块”不等于“七个写入点”：事件、定时、手动、恢复／回滚、逐条操作可能有多个出口。
- 需区分候选、观察预览、成功、失败、跳过；错误登记会污染真实执行历史。
- 需设计锁、批量提交、清理竞争、字段长度、保存失败与重载恢复。
- 会引入新的持久化数据契约、路由契约及测试桩维护。

**轻量方案的明确代价：**不能提供标签、失败清理、上传限速的逐种子长期审计日志，也不能清除转移来源映射。若用户明确要求这些能力，停止本方案，另立完整日志方案；不得把轻量方案标成“七模块完整执行日志”。

### B．明细上限：推荐查询参数

推荐接口：

`GET /diagnostics?detail_limit=20`

约束：

- 白名单：`20 / 50 / 100 / 200`
- 默认：20
- 非整数由 FastAPI 返回422；整数但不在白名单返回400。
- 前端用页面内 `ref(20)` 保存选择，切页签保留，关闭数据页后重置。
- 不写插件配置，不增加 Config.vue 控件，不新增 localStorage。
- 响应每模块新增：
  - `total`：截断前可用条数
  - `limit`：本次请求上限
  - `truncated`：是否截断

**被否方案：插件配置项落盘。**

代价：

- 需修改默认值、配置初始化、前端保存与重置键集。
- Config.vue 的 `initialConfig` watcher 会清空并回填 form，见 `frontend.v3/downloadmanagerlocal/src/components/Config.vue:1198-1199`；新增保存链路可能影响未保存草稿。
- 展示偏好不应引起插件重载或业务配置回流。

查询参数方案的代价是关闭页面后不记住选择。本轮接受此代价。

### C．风格统一：推荐保留两层，不合并页面导航

推荐边界：

- 总览：状态、计数、有限样本、查看入口。
- 专项页：完整分页记录、逐条操作、专用状态。
- 不删除专项表格，不将所有数据搬进新抽屉。
- 本轮不做结构性去重，避免违反“不重新设计导航与布局”。
- 抽一个纯展示组件 `ModuleDetailPanel.vue`：
  - 标题、说明、错误、rows/items、空态、截断提示。
  - `actions` slot 放按钮。
  - 默认 slot 放已有表格或上传限速专用网格。
  - 不取数、不调用 API、不保存配置、不实现业务清理。
- 上传限速保留专用网格，统一外围标题、间距、错误和空态；不要重复渲染同一组站点／错误数据。

**被否方案：合并总览运行明细与专项记录区。**

代价：

- 总览样本与专项完整记录用途不同，合并会改变用户操作路径。
- H&R 与重命名记录带逐条操作，不能简单替换成 title/meta 卡片。
- 在无真实浏览器证据时大范围删除区域，回归风险高。

推荐方案仍保留部分内容重复；本轮接受这一代价，只统一视觉与语义。

### D．转移旧数据：推荐显式回退，不迁移

推荐：

- 新事务保存 `source_name`。
- 列表主标题显示 `source_name`；次级显示短 hash。
- 缺少名称的旧记录显示“名称未记录”＋短 hash。
- 名称含义固定为**转移发起时的源种子名**。
- 本轮不新增 `to_download_name` 或 `after_name`，避免未经验证地宣称它是目标当前名称。

**被否方案：实时回查／批量迁移旧名称。**

原因及代价：

- 源或目标种子可能已经删除。
- 名称可能已经变化，无法证明是历史名称。
- 读取页面会增加下载器 IO。
- 批量回填会修改大量来源映射，增加安全关联数据的写风险。

回退方案的代价是旧记录无法凭空恢复名字；页面必须如实说明。

---

## 四、实施步骤

### 通用执行规则

下列命令均在 Windows 原生 Niubash 中运行；Python 统一使用：

`micromamba run -n base python -X utf8`

**本报告不授权执行这些命令。** 它们供用户确认方案后的执行模型使用。

每步开始前：

1. 重新读取目标函数，行号仅作定位。
2. 保存该步文件的当前副本到仓库外。
3. 只修改本步列出的文件及测试。
4. 本步失败即停止后续步骤。
5. 回退只恢复本步开始前副本；新增文件仅删除本步新建且未被其他任务修改的文件。禁止恢复到 HEAD。

### 步骤0：核对环境、留存基线

**文件与锚点：**不改产品源码；核对版本、工作区、当前测试。

```bash
cd /d/work/project/person/MoviePilot-Plugins
git status --short
git diff --stat
micromamba run -n base python -X utf8 -c "import sys; print(sys.executable); import pytest; print(pytest.__version__)"
micromamba run -n base python -X utf8 -m json.tool package.v3.json > /dev/null
micromamba run -n base python -X utf8 -m pytest tests/v3/downloadmanagerlocal -q --tb=short
(cd frontend.v3/downloadmanagerlocal && node --test tests/config-setup.test.mjs && npm run build)
```

**期望：**解释器不是 hermes 环境；全部退出码0；记录实际后端数量，参考268；前端现有6项通过。

**失败回退：**不开始改代码。环境解析到错误 Python 时停止修环境，不在报告命令中偷偷换裸 `python`，也不安装依赖掩盖问题。

### 步骤1：新转移事务保存名称

**文件与锚点：**

- `plugins.v3/downloadmanagerlocal/modules/transfer/pipeline.py:15-18` 的适配器导入。
- `plugins.v3/downloadmanagerlocal/modules/transfer/pipeline.py::begin_transfer`，`:101-115` 的 item。
- `tests/v3/downloadmanagerlocal/test_transfer_pipeline.py`。

**改法：**

- 复用 `utils.torrent_adapter.get_torrent_name`。
- item 新增 `source_name`，从传入 torrent 读取。
- 不增加额外 `save_data`，让现有 `save_transaction`、`save_source_record` 自然携带字段。
- 测试 dict／对象种子名称；完成、回滚、重载后字段不丢失；无名称时保存空串，业务不失败。

```bash
micromamba run -n base python -X utf8 -m pytest tests/v3/downloadmanagerlocal/test_transfer_pipeline.py tests/v3/downloadmanagerlocal/test_torrent_field_shapes.py -q --tb=short
```

**期望：**全部通过；原有删源保护、失败次数、回滚测试不变绿。

**失败回退：**恢复本步 pipeline 与测试副本，不修改转移策略来适配名称字段。

### 步骤2：API 带出名称

**文件与锚点：**

- `plugins.v3/downloadmanagerlocal/controller/handlers.py::api_transfer_status`，`:885-919`。
- `tests/v3/downloadmanagerlocal/test_manual_run_endpoints.py`。

**改法：**

- pending、records 两处均新增 `source_name`，缺失返回空串。
- 不修改来源映射 key、hash、状态、排序、分页。
- 用当前 endpoints fixture 补测试：新记录、旧记录、在途记录、混合分页；同时覆盖 `_iter_transfer_records` 接受的 dict 和 ORM 行列表。
- 禁止在 GET 中查询下载器补名。

```bash
micromamba run -n base python -X utf8 -m pytest tests/v3/downloadmanagerlocal/test_manual_run_endpoints.py tests/v3/downloadmanagerlocal/test_transfer_pipeline.py -q --tb=short
```

**期望：**旧记录仍可读取；名称字段穿透 status；路由数量不变。

**失败回退：**只恢复本步 handler 投影与测试修改。

### 步骤3：前端名称优先，覆盖桌面与移动

**文件与锚点：**

- `frontend.v3/downloadmanagerlocal/src/components/Page.vue::transferShortHash` 附近。
- 同文件 `:1757,1792,1812,1652,1667`。
- 新增 `frontend.v3/downloadmanagerlocal/tests/page-setup.test.mjs`。

**改法：**

- 增加一个名称展示函数，使用 `source_name`，空白名称视作缺失。
- 在途事务、最近记录桌面、最近记录移动：名称为主，短 hash 为辅；完整 hash 可保留在 tooltip。
- H&R：主标题改为 `task.name` 优先；缺失时名称未记录＋短 hash；站点另作次级信息。
- 不修改站点聚合列表的含义。
- 测试中文、长名称、空白名称、缺失名称及含 `<>&` 的名称；必须保持 Vue 文本转义，不使用 `v-html`。

前端测试沿用 `config-setup.test.mjs` 的完整 setup 执行方式，替换 API 与生命周期边界，不为测试安装 DOM 依赖。

```bash
(cd frontend.v3/downloadmanagerlocal && node --test tests/page-setup.test.mjs tests/config-setup.test.mjs && npm run build)
```

**期望：**名称选择行为测试通过、构建通过；两种布局都使用新名称逻辑。

**失败回退：**恢复本步 Page.vue；移除本步新增测试。构建产物最终统一重建，不从 HEAD 恢复旧资源。

### 步骤4：后端明细增加可调上限与截断元信息

**文件与锚点：**

- `plugins.v3/downloadmanagerlocal/modules/diagnostics/service.py::_detail`
- `_module_details`、七个明细 builder、`build_diagnostics`
- `_rename_history_stats`
- `tests/v3/downloadmanagerlocal/test_module_details.py`

**改法：**

- 所有相关函数增加可选 `detail_limit`，默认20，保持现有无参调用兼容。
- `_detail` 先过滤有效条目，再计算总数、截断。
- 返回保留原四字段，并新增 `total/limit/truncated`。
- 重命名不能继续先截五条；按请求上限提供最近失败样本，并用实际失败总数作为 total。
- 若给 `_rename_history_stats` 增加默认参数，不要引用尚未定义的后置常量；将常量移到函数前或采用明确的默认20。
- 不把完整失败列表泄漏到响应。
- 不改观察预览的20条内存上限，不改历史分页。
- 保留单模块异常隔离，错误块同样包含新增元信息。

现有测试 `test_module_details_covers_seven_modules` 在 `tests/v3/downloadmanagerlocal/test_module_details.py:145` 精确断言字段集合，必须有意加入新字段；不得简单删掉整个断言。

```bash
micromamba run -n base python -X utf8 -m pytest tests/v3/downloadmanagerlocal/test_module_details.py tests/v3/downloadmanagerlocal/test_module_isolation.py -q --tb=short
```

**期望：**20／50／100／200样本截断正确；total不是截断后数量；重命名不再被五条提前限制；异常模块不拖垮其他模块。

**失败回退：**恢复本步诊断服务和测试，不放宽模块隔离断言。

### 步骤5：查询参数贯穿真实路由

**文件与锚点：**

- `plugins.v3/downloadmanagerlocal/__init__.py::api_diagnostics`，`:275-276`
- 同文件 `_diagnostics`，`:432-433`
- `plugins.v3/downloadmanagerlocal/controller/handlers.py::api_diagnostics`，`:173-178`
- `tests/v3/downloadmanagerlocal/test_manual_run_endpoints.py`

**改法：**

- 入口暴露 `detail_limit: int = 20`。
- handler 在通用查询异常捕获之前验证整数白名单，白名单外明确400，避免被转换成500。
- 参数依次传给 `_diagnostics`、`build_diagnostics`。
- 保留 `controller/api.py:125-132` 的原鉴权、GET、响应模型，不新建路由。
- `DiagnosticsResult` 基类允许 extra，见 `plugins.v3/downloadmanagerlocal/model/api.py:12-15`；本轮无需重建全部 DTO。
- 测试必须通过 route endpoint 验证参数穿透；仅测 builder 不够。

```bash
micromamba run -n base python -X utf8 -m pytest tests/v3/downloadmanagerlocal/test_manual_run_endpoints.py tests/v3/downloadmanagerlocal/test_module_details.py tests/v3/downloadmanagerlocal/test_api_body_annotations.py tests/v3/downloadmanagerlocal/test_relative_imports.py -q --tb=short
```

**期望：**默认20；允许值正确穿透；非法整数400；现有39条路由契约不变。非整数422需在真实 FastAPI 路径补验。

**失败回退：**恢复本步两个产品文件及测试，不增加备用新端点绕过旧链路。

### 步骤6：接通首次总览加载与条数选择

**文件与锚点：**

- `frontend.v3/downloadmanagerlocal/src/components/Page.vue::loadDiagnostics`
- `loadOverviewTab`、`refreshActive`、`moduleDetail`
- 总览标题区 `:1285-1291`
- `frontend.v3/downloadmanagerlocal/tests/page-setup.test.mjs`

**改法：**

- 增加 `detailLimit = ref(20)`，选项固定20／50／100／200。
- `loadDiagnostics` 请求附带当前 `detail_limit`。
- 总览刷新包含诊断读取；有通用明细的模块页签刷新也读取诊断。
- history、transfer、diagnostics 同样需要获取清理数量或明细时，纳入其现有刷新分组。
- 每轮刷新最多一次 diagnostics 请求，不从多个子 loader 重复调用。
- 选择变化只刷新诊断数据，不刷新全部业务状态，不保存配置、不 reload。
- 复用 `beginPageRequest`／`isCurrentPageRequest`；增加诊断请求独立序号或等价的最新请求判定，防止20条旧响应覆盖200条新响应。
- `moduleDetail` 带出 total/limit/truncated，缺失新字段时兼容旧响应。
- 自动刷新时保留已有快照；不得为条数选择增加新的轮询定时器。

```bash
(cd frontend.v3/downloadmanagerlocal && node --test tests/page-setup.test.mjs tests/config-setup.test.mjs && npm run build)
```

**期望：**首次总览即请求诊断；切页签、改变条数、请求乱序、卸载后返回均有测试；没有配置 POST/PUT。

**失败回退：**恢复本步 Page.vue 与测试；不得用“先打开诊断页”作为产品使用前置条件。

### 步骤7：抽取纯展示组件

**文件与锚点：**

- 新增 `frontend.v3/downloadmanagerlocal/src/components/ModuleDetailPanel.vue`
- 新增 `frontend.v3/downloadmanagerlocal/tests/module-detail-panel.test.mjs`

**改法：**

- props：title、subtitle、rows、items、total、limit、truncated、error、emptyText。
- 两个 slot：actions、default。
- 默认 slot用于专用内容；没有专用内容时渲染 rows/items。
- 错误和已有数据允许同时出现；不得因 error 丢掉已有 rows。
- 有 rows、无 items 时不显示误导性的“暂无记录”。
- 截断提示按数字生成，不硬编码20。
- 组件内部不 import API、不使用业务模块配置。
- 将通用明细所需 CSS 移入组件自己的 scoped 样式，不依赖父组件 scoped 样式跨组件命中。

已有 lockfile包含 Vue compiler/server-renderer，可使用既有 Vue 工具做渲染行为测试；不得修改 package.json/lockfile安装测试框架。

```bash
(cd frontend.v3/downloadmanagerlocal && node --test tests/module-detail-panel.test.mjs && npm run build)
```

**期望：**空态、错误、长文本、截断数量和 slot 渲染通过；不比较完整 HTML 快照。

**失败回退：**删除本步新建的组件与测试，不动 Page.vue。

### 步骤8：逐组接入统一外观

**文件与锚点：**

- `frontend.v3/downloadmanagerlocal/src/components/Page.vue:1327-1394`
- 专项记录区的标题／空态外围
- 前述两个前端测试文件

**改法顺序：**

1. 普通模块运行明细替换为共享组件。
2. 上传限速使用同一外围组件，原网格放 default slot；同一站点与错误不重复展示。
3. 专项页仅替换标题、操作区和空态外围；桌面表格、移动卡片和逐条操作保留。
4. 保留现有 `data-record-block` 标识。
5. 不合并页签、不删除专项记录、不把清理标签改成清理日志。

每组改完先执行下列测试，三组完成后再构建：

```bash
(cd frontend.v3/downloadmanagerlocal && node --test tests/page-setup.test.mjs tests/module-detail-panel.test.mjs tests/config-setup.test.mjs)
(cd frontend.v3/downloadmanagerlocal && npm run build)
```

**期望：**原操作函数仍被调用；记录与分页未丢失；标题／间距／空态统一。

**失败回退：**仅撤销当前组替换；不重写整个 Page.vue。

### 步骤9：修自动删种清理的内存同步

**文件与锚点：**

- `plugins.v3/downloadmanagerlocal/modules/autoremove/service.py`
  - `__init__` 的 `_lock/_run_lock`：`:64-66`
  - `get_module_status`：`:151-155`
- 新增 `tests/v3/downloadmanagerlocal/test_cleanup_runtime_status.py`

**改法：**

- 新增窄方法 `clear_history()`，返回真实清理数量。
- 非阻塞取得现有 `_run_lock`；正在运行时返回明确的忙状态供 handler 转409，不等待整个下载器流程。
- 再持有 `_lock`，清持久化最近结果，并将 `_status` 恢复为已有空状态。
- 先保证持久化成功，再提交内存状态变化；保存失败不能返回成功。
- 不改配置、观察开关、H&R 状态、候选筛选条件。
- 释放锁使用 finally。

```bash
micromamba run -n base python -X utf8 -m pytest tests/v3/downloadmanagerlocal/test_cleanup_runtime_status.py tests/v3/downloadmanagerlocal/test_observe_isolation_autoremove.py -q --tb=short
```

**期望：**清理后 API 状态为空；忙时不清；保存失败不假成功；不调用下载器。

**失败回退：**恢复本步服务文件与测试；暂不新增自动删种清理按钮。

### 步骤10：失败清理只清最近结果，保留累计

**文件与锚点：**

- `plugins.v3/downloadmanagerlocal/modules/failclean/service.py`
  - `__init__`：`:81-91`
  - `get_module_status`：`:168-179`
  - `_record_result`、`_record_scan_result`、`_save_status`：`:385-425`
- `tests/v3/downloadmanagerlocal/test_cleanup_runtime_status.py`

**改法：**

- 增加专用于状态读改写的 `RLock`。
- 状态快照读取、结果更新、保存及清理使用同一状态锁。
- 不在状态锁中执行网络／文件删除；`_record_scan_result` 调用 `_record_result` 时使用可重入锁。
- 提供 `clear_history()`：
  - 清最近扫描时间、触发来源、scan/event 最近结果。
  - 保留 `total` 累计值。
  - 保留 H&R 跳过统计、`_recent_deletes` 去重状态、配置。
- 提供窄的纯函数，判断是否存在可清理的最近结果，并生成清理后状态；服务与无服务回退共用。
- 只有累计值、没有最近结果时返回 removed=0。
- 写入失败不修改内存结果、不返回成功。

```bash
micromamba run -n base python -X utf8 -m pytest tests/v3/downloadmanagerlocal/test_cleanup_runtime_status.py tests/v3/downloadmanagerlocal/test_failclean_scan.py tests/v3/downloadmanagerlocal/test_observe_boundaries.py -q --tb=short
```

**期望：**最近结果归零、累计保留；并发更新不丢失；不触发文件或下载器写操作。

**失败回退：**恢复本步服务与测试；不启用新的失败清理按钮。不得退回“清空整个状态对象”的实现。

### 步骤11：清理 handler 与数量口径对齐

**文件与锚点：**

- `plugins.v3/downloadmanagerlocal/controller/handlers.py::_cleanup_actions`
- `plugins.v3/downloadmanagerlocal/modules/diagnostics/service.py::_cleanup_stats`
- `tests/v3/downloadmanagerlocal/test_cleanup_module_data.py`
- `tests/v3/downloadmanagerlocal/test_cleanup_runtime_status.py`

**改法：**

- 自动删种／失败清理存在服务时调用 `clear_history()`。
- 服务不存在时仅清持久化允许部分；失败清理仍使用步骤10纯函数保留累计。
- `_cleanup_stats.failclean_state` 按“是否有最近结果”计0或1，不按整个状态对象是否非空判断。
- rename_history 清理使用现有 `serialized_rename_state`；不要只给清理新增一把与写入端无关的锁。
- 白名单仍为现有五项，不加入 transfer来源映射、队列、限速恢复状态。
- 保持 `transfer_stats` 原含义，不在本轮新增其清理按钮。
- 更新原测试对 failclean `{}` 的预期，明确验证新的“最近结果清理、累计保留”契约；不是删断言凑通过。

```bash
micromamba run -n base python -X utf8 -m pytest tests/v3/downloadmanagerlocal/test_cleanup_module_data.py tests/v3/downloadmanagerlocal/test_cleanup_runtime_status.py tests/v3/downloadmanagerlocal/test_module_details.py -q --tb=short
```

**期望：**数量与 removed 一致；服务在／不在两种情况一致；未知对象400；忙状态409；安全状态保持原值。

**失败回退：**恢复本步 handler、诊断计数和测试，保留前两步服务能力但暂不接按钮。

### 步骤12：增加查看与清理入口

**文件与锚点：**

- `frontend.v3/downloadmanagerlocal/src/components/Page.vue::moduleCards`
- `selectTab`、`openCleanupDialog`、`confirmCleanupData`
- `CLEANUP_TARGETS`
- `frontend.v3/downloadmanagerlocal/tests/page-setup.test.mjs`

**改法：**

- 严格采用裁决A的映射表。
- 查看按钮只执行页签切换、必要GET、展开与滚动，不触发扫描／预览／补全／重新分配。
- `selectTab` 完成后 `await nextTick()`，再定位对应 `data-record-block` 或模块卡；不能只改 activeTab 后立即滚动。
- 清理按钮复用同一个确认框和 `cleanup_module_data`。
- 重命名历史／归档是两个不同按钮，不合成“全部清理”。
- 清理确认显示对象、数量、影响及“不修改下载器数据”。
- 失败清理文案明确保留累计统计。
- 自动删种清理成功后同时清除前端 `autoremovePreview`，避免本地预览覆盖已清状态。
- 重命名批量清理成功后，将对应分页重置为1，再刷新，避免停留在被清空的末页。
- 清理失败保持失败反馈，不显示成功；只刷新诊断和对应模块。
- H&R按钮复用既有安全清理，不新增清空所有任务。

```bash
(cd frontend.v3/downloadmanagerlocal && node --test tests/page-setup.test.mjs tests/module-detail-panel.test.mjs tests/config-setup.test.mjs && npm run build)
```

**期望：**查看操作无业务POST；清理只提交目标白名单对象；取消确认不请求；0条禁用；失败／409反馈明确；无记录模块无假按钮。

**失败回退：**恢复本步按钮映射、确认框与测试，不回退已验证的名称和条数功能。

### 步骤13：全量离线门禁

**文件与锚点：**所有本轮产品文件、测试、构建产物；不新增依赖。

```bash
cd /d/work/project/person/MoviePilot-Plugins
micromamba run -n base python -X utf8 -c "import ast; from pathlib import Path; files=list(Path('plugins.v3/downloadmanagerlocal').rglob('*.py')); [ast.parse(p.read_text(encoding='utf-8-sig'), filename=str(p)) for p in files]; print('AST OK',len(files))"
micromamba run -n base python -X utf8 -m json.tool package.v3.json > /dev/null
micromamba run -n base python -X utf8 -m pytest tests/v3/downloadmanagerlocal -q --tb=short
(cd frontend.v3/downloadmanagerlocal && node --test tests/config-setup.test.mjs tests/page-setup.test.mjs tests/module-detail-panel.test.mjs && npm run build)
git diff --check
git status --short
git diff --stat
```

**期望：**全部退出码0；原有测试仍收集并通过，新增测试使数量增加；依赖文件无本轮变动；diff仅为本插件与直接测试依赖。

**失败回退：**定位首个失败步骤，只撤销该步。测试持续失败且未定位时停止，不进入本地部署。

版本提升在功能与本地验证完成后单独处理，三处同步；不得提前猜测新版本号，也不得因本报告自动提交。

---

## 五、本地 MP 验收

### 5.1 前置门槛

仅在用户已授权本地同步／reload、步骤13全部通过后执行。

必须确认：

- 后端 `http://127.0.0.1:17430` 可用。
- 前端 `http://127.0.0.1:17431` 可用。
- API key来自 `D:/tmp/.mp_local_key`，不打印。
- `onlyonce` 等一次性执行开关关闭。
- 业务作用域只包含测试下载器和测试种子。
- 没有其他回归脚本正在修改本地插件配置。
- 本地生效目录是真目录，不是指向仓库的 junction。

不要直接沿用历史 PID；不要重启整个实例来掩盖插件问题。`.ralph` 记录的启动方式与 `docs/mp-local-debug.md` 部分历史命令存在环境差异，实例不可用时停止，先核实环境。

### 5.2 同步完整插件目录

构建产物直接输出到插件 `dist`。必须同步同一工作树的**完整插件目录**，不能只同步 Page chunk。

下面命令会修改本地调试实例，必须在授权后运行；目标路径固定，不得替换为生产路径。

```bash
cd /d/work/project/person/MoviePilot-Plugins
export DML_UI_BACKUP="D:/tmp/dml-ui-local-$(date +%Y%m%d-%H%M%S)"
micromamba run -n base python -X utf8 -c "import os,shutil; from pathlib import Path; s=Path('D:/work/project/person/MoviePilot-Plugins/plugins.v3/downloadmanagerlocal'); d=Path('D:/test/MoviePilot-v3/app/plugins/downloadmanagerlocal'); b=Path(os.environ['DML_UI_BACKUP']); assert s.is_dir() and d.is_dir(); assert d.resolve()==d.absolute(); assert not b.exists(); shutil.copytree(d,b,ignore=shutil.ignore_patterns('__pycache__','*.pyc')); shutil.rmtree(d); shutil.copytree(s,d,ignore=shutil.ignore_patterns('__pycache__','*.pyc')); print('SYNC OK')"
```

**期望：**`SYNC OK`；备份目录保留。

随后比较同步后的文件集合及内容哈希：

```bash
micromamba run -n base python -X utf8 -c "import hashlib; from pathlib import Path; s=Path('D:/work/project/person/MoviePilot-Plugins/plugins.v3/downloadmanagerlocal'); d=Path('D:/test/MoviePilot-v3/app/plugins/downloadmanagerlocal'); manifest=lambda r:{p.relative_to(r).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in r.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}; assert manifest(s)==manifest(d),'manifest mismatch'; print('MANIFEST SAME')"
```

**期望：**`MANIFEST SAME`。

**失败回退：**立即停止，不 reload。由备份恢复本地调试插件完整目录，保留失败证据；不改仓库源码。

### 5.3 reload 与 API 验证

先检查配置，不打印完整配置或凭据：

```bash
micromamba run -n base python -X utf8 -c "import json,urllib.request; k=open('D:/tmp/.mp_local_key').read().strip(); u='http://127.0.0.1:17430/api/v1/plugin/DownloadManagerLocal'; d=json.load(urllib.request.urlopen(urllib.request.Request(u,headers={'X-API-KEY':k}),timeout=90)); c=d.get('data',d); assert isinstance(c,dict); assert not c.get('onlyonce'),'onlyonce must be false'; print('ONLYONCE OFF')"
```

检查测试下载器作用域必须通过现有测试环境配置核对，不输出凭据。若作用域无法确认，停止。

重载：

```bash
curl --fail-with-body -sS -X POST "http://127.0.0.1:17430/api/v1/plugin/reload/DownloadManagerLocal" -H "X-API-KEY: $(cat /d/tmp/.mp_local_key)"
```

读取可调明细：

```bash
micromamba run -n base python -X utf8 -c "import json,urllib.request; k=open('D:/tmp/.mp_local_key').read().strip(); u='http://127.0.0.1:17430/api/v1/plugin/DownloadManagerLocal/diagnostics?detail_limit=50'; d=json.load(urllib.request.urlopen(urllib.request.Request(u,headers={'X-API-KEY':k}),timeout=90)); d=d.get('data') or d; m=d['module_details']; assert set(m)=={'transfer','rename','tag','hr','autoremove','failclean','upload_limit'}; assert all(x['limit']==50 and len(x['items'])<=50 and x['total']>=len(x['items']) for x in m.values()); print('DETAIL LIMIT OK')"
```

**期望：**

- reload业务回执成功，不仅HTTP200。
- 七模块字段齐全。
- 50条上限生效。
- 非整数参数422、白名单外整数400。
- 转移新记录带名称，旧记录仍可查询。
- 日志无新增导入／响应验证异常。

**失败回退：**恢复本地完整备份后reload一次；保存错误类型与脱敏日志。不要改鉴权或关闭模块来绕过失败。

### 5.4 必须进行的真实页面验收

浏览器打开 `http://127.0.0.1:17431`，登录后从插件中心打开下载中心数据页。

按以下顺序逐项记录结果：

1. **首次总览**：新打开数据页，不先进入诊断页，展开七模块运行明细。
2. **条数选择**：20→50→200；核对实际展示数量及 total、截断提示；快速切换后没有旧响应覆盖。
3. **查看按钮**：全部跳到正确页签并定位；不得因“查看”启动扫描、删种或限速。
4. **命名记录**：分页、归档、单条操作入口仍在；批量清理后的页码与空态正确。
5. **转移名称**：新记录显示源种子名；旧记录显示名称未记录＋短hash；完整hash仍可查。
6. **H&R名称**：有站点时仍直接显示种子名，站点是次级信息。
7. **清理结果**：自动删种结果清理后立即消失，刷新不复活；失败清理最近结果清空、累计计数不变。
8. **无历史模块**：标签／限速不出现假“清理日志”按钮。
9. **响应式**：1440px、760px附近和390px宽度；桌面表格与移动卡片分别核对名称、按钮、空态。
10. **主题与布局**：明暗主题、长中文名称、错误状态、下载器图标、配置页边框、底部按钮与滚动。

当前转移在途区只有桌面表格，见 `frontend.v3/downloadmanagerlocal/src/components/Page.vue:1743-1771`，而移动断点隐藏 `.dm-desktop-table`，见 `frontend.v3/downloadmanagerlocal/src/components/Page.vue:2539`。若390px验收证实在途事务消失，应在该区补同字段移动卡片；不得顺带重构整个转移页。

浏览器不可用时，将页面验收标为**阻塞／未验证**，不能以 API 返回或构建成功替代。

### 5.5 测试下载器回归

现有回归脚本在仓库外，需先确认文件存在和只作用于测试下载器。它包含真实测试写操作，需复用明确的本地测试授权：

```bash
cd /d/work/tmp/dml-test
micromamba run -n base python -X utf8 regress_all.py --slow
```

期望现有快慢场景全部通过，并保留证据目录。脚本若不可用或解释器仍指向失效路径，停止报告，不自行改生产下载器或安装另一套环境。

---

## 六、测试清单与断言要求

### 后端必须新增／扩展

| 测试文件 | 核心覆盖 |
|---|---|
| `tests/v3/downloadmanagerlocal/test_transfer_pipeline.py` | 名称读取、持久化、回滚／完成／重载保留；原安全行为不变 |
| `tests/v3/downloadmanagerlocal/test_manual_run_endpoints.py` | pending/records新旧名称；分页；route参数穿透；非法参数 |
| `tests/v3/downloadmanagerlocal/test_module_details.py` | 默认与四档上限；total/truncated；超过五条重命名失败；七模块异常隔离 |
| 新增 `tests/v3/downloadmanagerlocal/test_cleanup_runtime_status.py` | 服务缓存同步；累计保留；忙状态；保存失败；并发更新；不调用外部写接口 |
| `tests/v3/downloadmanagerlocal/test_cleanup_module_data.py` | 白名单不扩张；活动映射／队列／限速恢复保留；无服务回退；清理数量一致 |

原有全量命令必须保持通过，包括 H&R snapshots、观察模式、模块隔离、相对导入、接口参数注解、转移任务引擎等。

### 前端必须新增／保留

- 保留现有 `frontend.v3/downloadmanagerlocal/tests/config-setup.test.mjs` 六项。
- 新增 `frontend.v3/downloadmanagerlocal/tests/page-setup.test.mjs`：
  - 首次总览加载诊断。
  - 条数参数、切页保留、请求乱序与卸载防回流。
  - 查看按钮不会触发业务POST。
  - 清理目标、取消、0条、失败、409、对应模块刷新。
  - 新旧名称和H&R名称优先级。
- 新增 `frontend.v3/downloadmanagerlocal/tests/module-detail-panel.test.mjs`：
  - rows/items、错误、空态、截断数量和slot行为。

**禁止：**

- 断言整段中文说明或完整HTML字符串。
- 只搜索源码中“出现某按钮文字”就宣称点击行为已通过。
- 删除失败测试、减少收集数量，或把所有未知字段断言改成永真。
- 引入 jsdom、测试框架、日志库或其他新依赖。

---

## 七、风险与禁止项

### 7.1 持久化体积与写频

插件使用 `get_data/save_data` 读写可持久化结构，不能当作零成本内存容器。

- `get_data` 是读取，新增日志真正增加写频的是 `save_data`。
- 宿主具体采用文件JSON还是数据库JSON字段，本仓库不能独立证明；不能据此编造磁盘布局。
- 转移名称应并入现有事务写入，不额外写一次。
- 不新增七模块高频逐条日志，不在GET中保存数据。
- `detail_limit` 限制响应样本，不是持久化保留上限，也不能减少宿主一次读取全部历史的成本。

### 7.2 清理并发与安全状态

- 清理必须与对应写入端使用同一锁。
- 不能新造一把只保护清理、不保护业务保存的锁。
- 不清来源→目标映射、活动队列、H&R保护状态、限速恢复依据。
- 失败清理累计统计保留；不新增“统计重置”入口。
- 清理成功后检查即时状态和下一次真实更新，不只检查持久化字典变空。

### 7.3 前端双渲染

桌面表格和移动卡片是两套 markup。只改桌面会漏掉移动端。转移最近记录、H&R、命名历史、自动删种都要分别检查。

### 7.4 文案与国际化边界

- 使用统一中文名称和动作口径。
- “查看记录”“清理记录”“移除标签”“删除种子”“删除种子及文件”不得混用。
- H&R任务不是完成日志，候选不是执行成功。
- 不机械替换API路径、配置键、历史版本说明。
- 不新增国际化框架。

### 7.5 配置刷新回流

本方案不改 `core/config.py`、`utils/config.py` 的配置默认值，也不改 Config.vue 保存链路。条数选择不能触发配置保存、模块重载或重置草稿。

### 7.6 发布边界

- 本地离线门禁与真实页面全绿后，才允许申请QNAP部署。
- QNAP需用户另行授权。
- 完整部署同版本后端＋资源＋dist，不散拷单个chunk。
- 按权威方案§10.3备份、核对完整文件清单与哈希、reload、检查版本与真实页面。
- 不操作其他容器，不用真实生产种子测试写操作。
- 提交／推送需授权，只暂存显式路径，不使用 `git add -A`、`git add .`。

---

## 八、不确定项与停止条件

以下无法由当前仓库静态读取确认：

1. 用户是否接受轻量方案不提供七模块逐种子长期日志。
2. 本地17430／17431当前是否在线、浏览器是否恢复可用。
3. 当前API key有效性、下载器作用域和一次性执行开关。
4. 当前Python环境是否仍存在历史记录中的解析偏差。
5. 仓库外 `regress_all.py` 和部署脚本是否仍存在、是否与当前环境一致。
6. 当前宿主持久化的具体后端、JSON序列化／事务成本。
7. 当前测试真实通过数量；268与6是历史记录，不是本次实测。
8. 生产旧转移记录的实际字段分布与可恢复名称比例。
9. QNAP当前安装版本、完整目录状态与可用备份。

出现以下情况停止，不自行兜底：

- A—D未获确认。
- 需要清理有效转移映射或安全状态。
- 需要改变生产配置才能验收。
- 测试持续失败且原因未定位。
- 浏览器验收不可执行。
- 本地运行版本与同步文件不一致。
- 需要扩大为完整日志系统、改其他插件／容器或新增依赖。

---

## Review

- **Correct：**主线报告对展示结构差异、明细硬编码上限、缺少截断提示，以及转移名称未落盘的总体判断成立。
- **Fixed：**本报告已纠正文件位置、行号、测试基线及清理语义；未修改代码。
- **Finding：P1**，首次总览不读取诊断数据，`module_details`展示依赖先访问诊断页。位置：`frontend.v3/downloadmanagerlocal/src/components/Page.vue:705-713,755-801`。最小修复：接通总览及对应模块刷新链路，补首次加载与请求乱序测试。
- **Finding：P1**，自动删种／失败清理只清持久化、不清内存状态。位置：`plugins.v3/downloadmanagerlocal/controller/handlers.py:489-499`；状态读取分别在 `plugins.v3/downloadmanagerlocal/modules/autoremove/service.py:151-155`、`plugins.v3/downloadmanagerlocal/modules/failclean/service.py:168-179`。最小修复：服务级清理方法、共享状态锁、真实服务测试；失败清理保留累计。
- **Finding：P1**，不能将 `transfer_stats` 接口作为转移记录清理。位置：`plugins.v3/downloadmanagerlocal/controller/handlers.py:480-487,906-930`。最小修复：不增加该误导按钮，保留来源映射。
- **Finding：P2**，H&R与转移列表的实际名称展示不符合需求。位置：`frontend.v3/downloadmanagerlocal/src/components/Page.vue:1652,1667,1757,1792,1812`。按上述名称链路修正，兼容旧数据。
- **Merge verdict：BLOCK**——此结论针对P7-2c验收／发布就绪性，不代表已审完所有在途diff。完成推荐方案、全量回归及本地真实页面验收后再复核；QNAP部署继续后置并单独授权。
