# H&R助手Pro

PT 站 H&R 种子自动标签管理插件，支持多条件 OR 判定、按种子大小分级、自动发现下载器种子和批量清理。

## Input / Output / Pos
- Input: 下载器选择、站点规则、做种时间/分享率/上传倍数阈值和扫描间隔。
- Input: `DownloadAdded` 事件、手动全量扫描、远程命令和批量清理 API。
- Input: `rule.yaml` 内置规则以及配置页覆盖规则。
- Output: H&R 任务记录、种子标签变更、做种状态通知和详情页任务列表。
- Output: 清除已满足记录、清除缺失种子记录和单条任务操作结果。
- Pos: MoviePilot 下载器种子 H&R 管理层。
- Pos: 入口只组装配置、事件和服务，判定逻辑由 `checker.py`/`helper.py` 负责。

## Files
- `__init__.py`: 插件入口、配置解析、下载器发现、事件监听、定时服务、API/命令和页面装配。
- `checker.py`: H&R 扫描、状态判定、任务更新和批量清理流程。
- `config.py`: 插件配置模型、默认值和规则解析。
- `entities.py`: H&R 状态、任务类型和种子任务实体定义。
- `helper.py`: 下载器种子查询、标签操作和站点辅助方法。
- `rule.yaml`: 内置站点 H&R 分级规则示例/默认配置。

## Key Constraints
- `plugin_version` 必须与 `package.v2.json` 中 `PtHitAndRun.version` 同步。
- `__init__.py` 保持编排职责，新增 H&R 判定或下载器细节优先放入 `checker.py`/`helper.py`。
- 仅操作配置中选中的下载器；下载器不可用时记录 warning 并跳过，不能阻断其他下载器。
- `DownloadAdded` 事件处理必须校验 downloader、hash 和 context，避免空事件导致异常。
- 任务状态和标签操作要兼容种子已删除、已满足、需做种、过期等状态。
- 多条件 OR 判定和按大小分级规则必须保持可解释，通知中说明当前状态和剩余要求。
- 批量清理 API 只清理目标状态，不应误删仍需做种的任务。
- 配置模型变更需同步表单、默认配置、历史记录兼容和 `package.v2.json` history。
- 下载器操作失败要落到单任务错误，不要中断整轮扫描。
