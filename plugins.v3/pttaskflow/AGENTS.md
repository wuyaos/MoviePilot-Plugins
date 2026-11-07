# PtTaskFlow（V3）

声明式 PT 站点任务框架的 V3 专用版（自 V2 v0.4.9 迁移）。站点通过组合 `Task` 实例接入；前端只消费 `Control`，引擎只消费 `Unit` 与 `TaskResult`。

## 与 V2 的差异（边界）

- **无签到任务**：`TaskType.CHECKIN`、`Checkin` 任务类、`actions/checkin.py`、hxpt FluxTorrent 签到模块均已删除；新站点不得再声明 Checkin。剩余任务类型：`Chat/Claim/Exchange/Medal/Lottery/ActionTask`（长驻）。
- **UI 沿用宿主 Vuetify 渲染**：`get_render_mode()` 返回 `("vuetify", None)`；`get_form()` 返回 `build_form(self)`（`ui/form.py` VForm dict）、`get_page()` 返回 `build_page(self)`（`ui/page.py`）。不使用 Vue 模块联邦前端（曾试建 `frontend.v3/pttaskflow/` 后按用户要求回退，已删除）。
- **imports 全部走 `app.sdk.*`**：`app.sdk.events` / `app.sdk.plugin` / `app.sdk.config`；`SiteOper` 来自 `app.db.oper`；日志用 `logging.getLogger("PtTaskFlow")`，不 mock 宿主 logger。
- **CookieCloud 自实现**：`core/cookie_cache.py::cookiecloud_cookies()`（settings + CryptoJsUtils 自解密），cookie 值过滤 `"\r\n;"` 与含 `=` 的 name，剔除 `_CF_ONLY_COOKIES` 集合；loader 返回 `{domain: "k=v; k2=v2"}`。
- 调度注册用 `app.sdk.scheduler.update_plugin_job/remove_plugin_job`；忙碌状态判定 `engine._lock.locked()`（无 running 属性）。

## 目录职责

- `__init__.py`：插件生命周期、站点读取、UI 接线（get_form/get_page）、API（`GET/PUT /config`、`POST /run`、`POST /manual-run`，全部 `{success, message, data}` envelope）；不得放站点业务。
- `ui/form.py`：配置页 VForm dict（全局设置 + 站点任务卡片），由 `Control` 数据驱动；去签到排序。
- `ui/page.py`：数据页 VForm dict（运行统计概览 + 站点任务状态卡片 + 趋势），历史合并无签到。
- `core/models.py`：`Control`、`Unit`、`TaskResult` 纯数据模型。
- `core/task.py`：`Task` 抽象与 `Chat/Claim/Exchange/Medal/Lottery/ActionTask` 任务类型（无 Checkin）。
- `core/site.py`：站点身份、HTTP 原语、喊话确认；不读配置、不写历史。
- `core/shoutbox.py`：声明式喊话快照与反馈关联，无发送副作用。
- `core/engine.py`：Task→Unit→TaskResult 编排、当天终态跳过、历史落库。
- `core/task_log.py`：统一任务生命周期日志。
- `core/config.py`：`PluginConfig` 解析、`filter_stale_site_ids`、`migrate_legacy_config`。
- `core/cookie_cache.py`：CookieCache 失效识别 + `cookiecloud_cookies()`。
- `core/history.py`：`HistoryStore`（`latest(limit)` 等）。
- `core/scheduler.py`：`TaskScheduler`（主定时 + 织梦 24h 独立 date 任务）。
- `core/notify.py`：按站点分组发送汇总通知。
- `actions/`：抽奖、勋章等站点请求/响应策略；不感知配置、历史和调度。
- `sites/`：24 站每站一个文件，仅声明身份、任务组合、Profile；特殊协议只覆写最小原语。

## 新增站点规范

1. 在 `sites/<domain_or_name>.py` 定义唯一的 `Site` 子类。
2. 必填 `site_name`、`domain`；仅域名/名称无法唯一匹配时声明 `match_keywords`。
3. 通过 `tasks = [Chat(...), Claim(...)]` 组合任务（**不声明 Checkin**），不使用反射装饰器。
4. 喊话站必须声明 `ShoutboxProfile`；站点差异通过 Profile 表达，只有发送 API 确实特殊时才覆写 `send_message`。
5. 将站点类显式添加到 `sites/__init__.py`；不得依赖包扫描顺序隐式路由。
6. 不修改 `core/engine.py`、前端组件来适配具体站点。若现有抽象无法表达，先判断能力应属于 `Task`、`Action`、`Profile` 还是 `Site` 原语。

## 任务类规范

每个 `Task` 必须实现或继承以下契约：

- `name`：稳定持久化标识，发布后禁止改名；配置 key 为 `task_{site_id}_{name}`。
- `task_type`：仅用于展示/排序，不作为业务分支依据。
- `controls(site)`：声明控件（`SWITCH/SELECT_ONE/SELECT_MANY`），key 必须是顶层扁平字符串。
- `is_enabled(site, config)`：只解释本任务配置。
- `expand(site, config)`：生成独立 Unit；多消息/多勋章必须一项一个 execution_key。
- `run(site, unit)`：必须返回 `TaskResult`，不得返回裸字符串、tuple 或 dict。

禁止引擎从中文文案猜测 success/terminal/retryable；状态由 Action/TaskResult 显式表达。

## 日志规范

任务生命周期只通过 `TaskLogger` 输出（插件、运行场景、站点、执行单元、阶段/结果）；Site/Action 只记录 HTTP 或解析异常。禁止输出 Cookie、Token、完整请求头/响应体；诊断响应最多截取 200 字符并脱敏。

## 验证

```bash
PYTHONIOENCODING=utf-8 C:/app/scoop/apps/micromamba/2.9.0-0/base/envs/mp3/python.exe -m pytest tests/v3/pttaskflow -q
micromamba run -n base python scripts/validate_plugin.py --repo . --target v3 --plugin pttaskflow --class-name PtTaskFlow --pretty --pyflakes
micromamba run -n base python -c "import ast,pathlib;[ast.parse(p.read_bytes()) for p in pathlib.Path('plugins.v3/pttaskflow').rglob('*.py')];print('AST OK')"
micromamba run -n base python -m json.tool package.v3.json >/dev/null
```
