# PtTaskFlow

声明式 PT 站点任务框架。站点通过组合 `Task` 实例接入；UI 只消费 `Control`，引擎只消费 `Unit` 与 `TaskResult`。

## 目录职责

- `__init__.py`：MoviePilot 插件生命周期、站点读取、公开 API；不得放站点业务。
- `core/models.py`：`Control`、`Unit`、`TaskResult` 纯数据模型。
- `core/task.py`：`Task` 抽象与 `Checkin/Chat/Claim/Exchange/Medal/Lottery/ActionTask` 任务类型。
- `core/site.py`：站点身份、HTTP 原语、喊话确认；不读配置、不写历史。
- `core/shoutbox.py`：声明式喊话快照与反馈关联，无发送副作用。
- `core/engine.py`：Task→Unit→TaskResult 编排、当天终态跳过、历史落库。
- `core/task_log.py`：统一任务生命周期日志。
- `actions/`：签到、抽奖、勋章等站点请求/响应策略；不感知配置、历史和调度。
- `sites/`：每站一个文件，仅声明身份、任务组合、Profile；特殊协议只覆写最小原语。
- `ui/`：消费 Control/历史数据，不判断具体站点。
- `core/notify.py`：按站点分组发送汇总通知。

插件入口必须提供 `get_form`、`get_page`、`get_api`、`get_service`、`get_command` 和 `stop_service`；配置保存不得持久化 `onlyonce`。

## 新增站点规范

1. 在 `sites/<domain_or_name>.py` 定义唯一的 `Site` 子类。
2. 必填 `site_name`、`domain`；仅域名/名称无法唯一匹配时声明 `match_keywords`。
3. 通过 `tasks = [Checkin(), Chat(...), Claim(...)]` 组合任务，不定义 `Tasks` 转发类，不使用反射装饰器。
4. 喊话站必须声明 `ShoutboxProfile`；站点差异通过 Profile 表达，只有发送 API 确实特殊时才覆写 `send_message`。外部奖励使用 `Direction.EXTERNAL` 与 `external_feedback_xpath`。
5. 将站点类显式添加到 `sites/__init__.py` 的 `SITE_CLASSES`；不得依赖包扫描顺序隐式路由。
6. 不修改 `core/engine.py`、`ui/form.py` 来适配具体站点。若现有抽象无法表达，先判断能力应属于 `Task`、`Action`、`Profile` 还是 `Site` 原语。

### 标准模板

```python
from ..core.shoutbox import ShoutboxProfile
from ..core.site import Site
from ..core.task import Chat, Checkin

class ExamplePT(Site):
    site_name = "ExamplePT"
    domain = "example.org"
    tasks = [
        Checkin(),
        Chat(messages=["求魔力"]),
    ]
    shoutbox = ShoutboxProfile(
        message_terms=lambda message: [message],
        confirmation_wait_seconds=2,
    )
```

## 任务类规范

每个 `Task` 必须实现或继承以下契约：

- `name`：稳定持久化标识，发布后禁止改名；配置 key 为 `task_{site_id}_{name}`。
- `task_type`：仅用于展示/排序，不作为业务分支依据。
- `controls(site)`：声明 UI 控件，key 必须是顶层扁平字符串。
- `is_enabled(site, config)`：只解释本任务配置。
- `expand(site, config)`：生成独立 Unit；多消息/多勋章必须一项一个 execution_key。
- `run(site, unit)`：必须返回 `TaskResult`，不得返回裸字符串、tuple 或 dict。

禁止引擎从中文文案猜测 success/terminal/retryable；状态由 Action/TaskResult 显式表达。

## Action 规范

- Action 只负责请求路径、参数、响应解析和业务状态映射。
- 不读取插件配置、不写历史、不发通知、不管理重试。
- 技术失败返回 `TaskResult.fail`；确定幂等返回 `TaskResult.idempotent`；资格不足等业务状态返回 `TaskResult.business`。
- 购买类状态必须区分已拥有/未过期、余额不足、不可购买、购买成功和技术失败。

## 日志规范

任务生命周期只通过 `TaskLogger` 输出：

```text
[PtTaskFlow] [主定时] [RailgunPT] [签到] 开始
[PtTaskFlow] [主定时] [RailgunPT] [签到] 成功 -> 今日已签到
[PtTaskFlow] [主定时] 完成 -> 执行 2 / 成功 2 / 失败 0 / 跳过 0
```

- 固定维度：插件、运行场景、站点、执行单元、阶段/结果。
- Site/Action 只记录 HTTP 或解析异常，不重复记录任务开始/成功/失败。
- 禁止日志输出 Cookie、Token、完整请求头、完整响应体；诊断响应最多截取 200 字符并脱敏。
- 单元失败必须记录 `Exception` 类型和站点/单元上下文；批次末必须输出汇总。

## 奖励分类

标准输出类型：`上传量`、`下载量`、`魔力值`、`VIP`、`raw_feedback`。
站点自定义货币（电力、工分、火花、啤酒瓶、幸运星、象草等）统一归为 `魔力值`；原始名称保留在 description。
损失不是 reward type，使用 `is_negative=True` 独立表达。

## 验证

提交前至少运行：

```bash
python3 -c "import ast,pathlib;[ast.parse(p.read_text()) for p in pathlib.Path('plugins.v2/pttaskflow').rglob('*.py')];print('AST OK')"
pyflakes $(find plugins.v2/pttaskflow -name '*.py')
python3 -m unittest discover -s plugins.v2/pttaskflow/tests -p 'test_*.py'
python3 -m json.tool package.v2.json >/dev/null
git diff --check
```
