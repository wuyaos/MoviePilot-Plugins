# FarmAuto

MoviePilot V2「农场自动化 Pro」多站点插件。

## 插件标识

- 目录：`plugins.v2/farmauto/`
- 入口类（MP 插件 ID）：`FarmAuto`
- 配置前缀：`farmauto_`

## 模块职责

- `__init__.py`：MoviePilot V2 生命周期入口，装配配置、调度、事件、API、统计和页面
- `core/models.py`：作物、仓库、动作和运行报告 dataclass
- `core/http_client.py`：统一 Session、限速、重试/退避、认证异常和代理回退
- `core/strategy.py`：无网络与全局状态的统一自动运营计划
- `core/executor.py`：单站页面快照、仓库读取与动作顺序执行
- `core/reporting.py`：通知文本与 MoviePilot VNode 面板数据构造
- `sites/base.py`：站点 URL、解析默认实现及能力协议
- `sites/`：站点适配与注册表
- `tests/test_smoke.py`：PlayLet 离线 HTML 解析冒烟测试
- `tests/test_core.py`：有效期、盈利阈值与计划顺序离线测试
- `tests/test_executor.py`：执行成功、dry-run 与单步异常隔离测试
- `tests/test_<site>.py`：各站离线 HTML fixture 解析测试

## 站点清单

| 站点 | ID | 能力 |
|---|---|---|
| PlayLet | `playlet` | 一键收获、临期出售、仓库分页 |
| NovaHD | `novahd` | 一键收获、临期出售、仓库分页 |
| 好学 | `haoxue` | 一键收获、临期出售、仓库分页 |
| 包子 | `baozi` | 一键收获 |
| 拾刻 | `skit` | 一键收获、临期出售、仓库分页 |
| 思齐 | `siqi` | OCR 原生一键收获/逐格降级/一键种空地/偷菜/点赞/扩地 |

## 阶段状态

### 已完成

- 核心模型、HTTP 客户端、纯策略、单站编排和报告构造
- `FarmSiteConfig` 能力协议与 6 个站点解析迁移/新增
- 完整插件入口、站点管理 Cookie 读取、调度、事件/API、配置和页面接线
- dry-run、单步异常隔离、编排层统计持久化与离线测试
- 价格趋势滚动记录、单站策略覆盖
- `package.v2.json` 元数据登记（v2.3）

### 待真实回归

- 在真实站点回归认证、解析、操作 URL 与动态出售 key
- 思齐 executor 层开关与 POST 编排（第二期，当前仅能力层，默认不执行）

## 设计要点

- 站点以 `capabilities` 显式声明可选能力，编排器不按站点 ID 分支。
- 所有网络请求经统一客户端；Cookie 仅作为请求参数，不写入日志、通知或 API。
- 单站执行只产出报告，不修改持久统计；Phase 2 在多站编排层统一更新一次。
- `dry_run` 仅记录计划，不发送动作请求。
- 站点间协作如后续需要，必须使用 `EventType.PluginAction`，不得硬依赖其他插件模块。

## 校验

```bash
find plugins.v2/farmauto -name '*.py' -print0 | xargs -0 -n1 python3 -c 'import ast,sys; ast.parse(open(sys.argv[1]).read())'
python3 -m pytest plugins.v2/farmauto/tests/ -q
```
