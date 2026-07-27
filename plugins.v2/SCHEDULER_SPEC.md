# MoviePilot V2 插件定时任务编写规范

> 适用于本仓库 `plugins.v2/` 下依赖 MoviePilot 公共调度器的插件。
>
> 核心原则：**插件只声明任务和执行逻辑，MoviePilot 统一负责任务的注册、移除、重载和生命周期管理。**

## 1. 调度方式选择

### 1.1 公共调度器（默认、推荐）

普通长期任务必须通过插件入口 `get_service()` 返回服务描述，由 MoviePilot 的 `Scheduler` 统一注册。

适用场景：

- Cron 定时任务；
- 固定间隔任务；
- 需要显示在 MoviePilot 调度列表中的任务；
- 需要随插件启用、禁用、保存配置和重载而同步变化的任务。

插件不得在 `get_service()` 中自行创建 `BackgroundScheduler`。

### 1.2 插件内部调度器

仅用于插件内部的短生命周期一次性任务，例如 `onlyonce` 的 `date` 任务。必须在 `stop_service()` 中完整清理：

```python
def stop_service(self):
    scheduler = self._scheduler
    self._scheduler = None
    if not scheduler:
        return
    try:
        scheduler.remove_all_jobs()
        if scheduler.running:
            scheduler.shutdown(wait=False)
    except Exception as err:
        logger.warning(f"停止插件内部调度器失败：{err}")
```

禁止同一个业务同时注册一份公共任务和一份内部长期任务，否则会导致重复执行、任务列表与实际运行状态不一致。

## 2. 配置字段规范

### 2.1 任务开关

配置必须有明确的 `enabled` 默认值，每次 `init_plugin()` 都必须重新赋值，禁止依赖类变量或旧实例状态：

```python
config = config or {}
self._enabled = bool(config.get("enabled", False))
```

禁止：

```python
if "enabled" in config:
    self._enabled = bool(config.get("enabled"))
```

原因：插件可能经历首次加载、全量重载、文件热更新、配置迁移和重启，运行态字段必须由当前持久化配置确定。

### 2.2 调度模式和字段

Cron 与 Interval 是两种不同语义，不得使用一个字段伪装另一种模式。

推荐配置：

```python
{
    "enabled": True,
    "schedule_mode": "interval",
    "interval_minutes": 10,
    "cron": "",
}
```

如果插件只支持一种模式，应只保留对应字段：

- 固定时刻：`cron`，例如 `5 */4 * * *`；
- 固定间隔：`interval_minutes`，例如 `10`。

请求“每隔 N 分钟”时必须使用 Interval；`*/N * * * *` 是 Cron 表达式，表示每小时的固定分钟点，不等价于从注册时刻起每隔 N 分钟。

### 2.3 配置规范化

`init_plugin()` 负责读取和规范化配置，不负责执行长期业务：

```python
self._interval_minutes = max(
    1,
    self._safe_int(config.get("interval_minutes"), 10),
)
self._cron = str(config.get("cron") or "").strip()
```

允许：

- 类型转换；
- 默认值填充；
- 范围限制；
- 旧配置迁移；
- 一次性开关消费；
- 首次生成随机时间并持久化。

禁止每次初始化都重新生成随机时间。随机调度时间必须首次生成后写入配置，后续复用同一值。

## 3. `get_service()` 契约

### 3.1 必须是无副作用的声明函数

`get_service()` 可能在启动、保存配置、插件重载和调度刷新时被多次调用，必须可重复调用且结果稳定。

允许：

- 读取已初始化的运行态字段；
- 校验 Cron 或 Interval 参数；
- 构造触发器；
- 返回服务描述。

禁止：

- HTTP 请求、Cookie 读取或站点访问；
- 发送通知；
- 写配置或写业务数据；
- 生成未持久化的随机值；
- 启动线程或执行任务；
- 创建插件内部 `BackgroundScheduler`；
- 调用正式业务函数。

### 3.2 标准结构

```python
SERVICE_ID = "ExamplePlugin"
SERVICE_NAME = "示例插件定时任务"

def get_service(self) -> List[Dict[str, Any]]:
    if not self._enabled:
        logger.info(f"{SERVICE_NAME} 未注册：插件未启用")
        return []

    try:
        trigger = self._build_trigger()
    except Exception as err:
        logger.error(f"{SERVICE_NAME} 配置无效：{err}")
        return []

    if trigger is None:
        return []

    return [{
        "id": SERVICE_ID,
        "name": SERVICE_NAME,
        "trigger": trigger,
        "func": self.scheduled_run,
        "kwargs": {},
    }]
```

### 3.3 服务 ID

服务 ID 必须稳定、明确且在插件内唯一：

```python
"id": "AzKeepAlive"
```

禁止使用通用 ID：

```python
"id": "cron"
"id": "run"
"id": "service"
```

MoviePilot 最终会组合插件 ID 和服务 ID 生成 job 标识。一个插件有多个服务时，必须使用不同 ID，例如：

```python
"AutoSignIn.Signin"
"AutoSignIn.Retry"
```

### 3.4 执行入口

定时服务应绑定公开、无参数、语义明确的包装方法：

```python
def scheduled_run(self):
    return self.run_task(trigger="schedule", force=False)
```

注册：

```python
"func": self.scheduled_run
```

不要把私有方法、复杂参数或配置页专用方法直接作为调度入口。API、Bot 命令和定时任务可以共用底层 `run_task()`，但入口语义应分别明确。

## 4. Cron 编写规范

### 4.1 固定时刻任务

```python
from apscheduler.triggers.cron import CronTrigger
from app.core.config import settings

trigger = CronTrigger.from_crontab(
    self._cron,
    timezone=settings.TZ,
)
```

配置示例：

```text
5 */4 * * *
```

含义为每天每 4 小时的第 5 分钟执行。

### 4.2 Cron 校验

至少校验：

- 非空；
- 5 个字段；
- `CronTrigger.from_crontab()` 能成功解析。

非法配置必须记录清晰日志并返回空服务，不得让插件初始化崩溃：

```python
try:
    trigger = CronTrigger.from_crontab(self._cron, timezone=settings.TZ)
except Exception as err:
    logger.warning(f"Cron 配置无效，跳过定时注册：cron={self._cron!r}，error={err}")
    return []
```

## 5. Interval 编写规范

### 5.1 间隔任务

“每隔 N 分钟/小时”必须使用 `IntervalTrigger`：

```python
from apscheduler.triggers.interval import IntervalTrigger
from app.core.config import settings

trigger = IntervalTrigger(
    minutes=self._interval_minutes,
    timezone=settings.TZ,
)
```

服务示例：

```python
def get_service(self):
    if not self._enabled:
        return []
    return [{
        "id": "TangRedPacketClaim",
        "name": "不可躺自动领红包",
        "trigger": IntervalTrigger(
            minutes=self._interval_minutes,
            timezone=settings.TZ,
        ),
        "func": self.scheduled_run,
        "kwargs": {},
    }]
```

### 5.2 间隔范围

必须限制最小值，避免配置为 0 或负数：

```python
self._interval_minutes = max(
    1,
    self._safe_int(config.get("interval_minutes"), 10),
)
```

站点有接口限流时，建议使用更高的业务下限，并在配置说明中写明限制。

调度周期与单轮请求间隔必须分开：

```text
interval_minutes：两轮任务开始之间的间隔
request_interval：同一轮 HTTP 请求之间的间隔
claim_interval：同一轮红包领取请求之间的间隔
```

## 6. 任务生命周期规范

### 6.1 公共任务不由插件自己停止和启动

公共调度任务由 MoviePilot 管理。插件的 `stop_service()` 不应自行删除公共 Scheduler 的 job，也不应在其中重新注册公共任务。

插件只需要清理自己创建的资源：

- 内部 `BackgroundScheduler`；
- `threading.Timer`；
- 文件监控线程；
- HTTP 客户端；
- 停止事件和资源锁。

### 6.2 重载安全

插件重载后，任务必须绑定新实例，不能继续引用旧实例。插件代码不得假设 `get_service()` 只调用一次。

`init_plugin()` 必须：

1. 停止本插件自有的内部资源；
2. 从当前配置重新初始化全部运行态字段；
3. 不启动长期公共任务；
4. 不依赖旧实例字段。

### 6.3 一次性任务

`onlyonce` 等一次性动作必须：

1. 读取开关；
2. 立即将开关持久化为 `False`；
3. 再创建内部 `date` 任务；
4. `stop_service()` 可安全取消该任务。

禁止把一次性开关保留为 `True` 到任务执行结束，否则重启或重载可能重复执行。

## 7. 执行函数规范

### 7.1 所有入口共用运行锁

定时、API、命令和配置页立即执行必须共用同一把锁：

```python
_run_lock = threading.Lock()

def run_task(self, *, trigger="schedule", force=False):
    if not self._run_lock.acquire(blocking=False):
        logger.warning(f"{self.plugin_name} 已有任务运行，跳过 trigger={trigger}")
        return {"status": "running", "message": "已有任务正在执行"}
    try:
        return self._run_task_locked(trigger=trigger, force=force)
    except Exception as err:
        logger.exception(f"{self.plugin_name} 执行异常：{err}")
        return {"status": "failed", "message": str(err)}
    finally:
        self._run_lock.release()
```

### 7.2 运行失败不得注销任务

网络失败、Cookie 失效、站点维护、下载器不可用和业务无目标都属于一次执行结果，不能因此修改：

```python
self._enabled = False
```

也不得删除公共调度服务。应记录失败或跳过，并等待下一周期重试。只有用户明确关闭插件时，才允许关闭 `enabled`。

### 7.3 不要把任务注册放进业务函数

禁止：

```python
def run_task(self):
    Scheduler().update_plugin_job("ExamplePlugin")
```

业务执行失败或重复触发时不应改变调度结构。任务注册由框架的启动、配置更新和重载流程负责。

### 7.4 业务执行要有边界

定时入口应快速完成以下职责：

1. 检查运行锁；
2. 检查插件开关；
3. 读取当前配置和必要数据；
4. 执行一轮业务；
5. 保存结果和日志；
6. 释放锁。

禁止在定时入口中创建永不结束的轮询循环。需要轮询时，应设置超时、停止事件和最大轮询次数。

## 8. 异常、跳过和通知规范

任务结果至少区分：

- `completed`：执行完成；
- `skipped`：本轮无目标、未到业务间隔、已达上限等正常跳过；
- `failed`：本轮执行失败；
- `auth_failed`：认证失败，但插件仍保持启用；
- `running`：已有相同任务执行中。

异常必须：

- 在插件日志中保留插件名、任务入口和错误原因；
- 不吞掉关键异常；
- 不因为异常改变调度配置；
- 不将完整 HTML、Cookie、Token 或密码写入日志。

通知应按配置开关发送。无目标的正常轮次不应制造错误通知。

## 9. 配置保存和迁移规范

### 9.1 保存配置后必须重新注册

框架配置更新流程应保证：

```text
保存配置 → 初始化当前插件实例 → 删除旧 job → 重新计算 get_service() → 注册新 job
```

插件不得依赖用户再次打开页面或手动运行来恢复任务。

### 9.2 插件重命名必须迁移配置

插件 ID、配置 key 和类名变更时，必须显式迁移旧配置：

```python
new_config = self.get_config("TangRedPacketClaim")
if not new_config:
    old_config = self.get_config("TangRedPacket")
    if old_config:
        new_config = migrate_config(old_config)
        self.update_config(new_config, "TangRedPacketClaim")
```

迁移应：

- 只执行一次；
- 保留用户的 `enabled` 和调度配置；
- 记录迁移日志；
- 明确是否删除旧配置；
- 配套测试旧配置、空配置和新配置三种情况。

## 10. 测试规范

每个提供公共定时任务的插件至少覆盖：

### 10.1 配置状态

```text
enabled=false → get_service() == []
enabled=true → get_service() 返回服务
enabled 缺失 → 使用明确默认值
非法 Cron/Interval → 不崩溃且不注册非法服务
```

### 10.2 重启和重载

模拟持久化配置创建新插件实例并调用 `init_plugin()`，确认：

- 启用插件能生成服务；
- 服务函数绑定当前实例；
- 重建实例后旧 job 被移除；
- 新 job 数量正确；
- 不需要再次保存配置才能注册。

### 10.3 配置切换

测试：

```text
enabled=true → false：旧 job 被移除
enabled=false → true：新 job 被注册
Cron/Interval 修改：旧 trigger 被替换
```

### 10.4 执行异常

模拟网络超时、Cookie 失效、站点 500、无目标和下载器不可用，确认：

- 执行结果正确分类；
- 运行锁在异常后释放；
- `enabled` 保持原值；
- 下一周期仍可执行；
- 不产生重复 job。

### 10.5 触发器语义

Interval 测试必须确认 `interval` 等于配置值；Cron 测试必须确认时区和下次触发时间正确。不能只断言 `get_service()` 返回非空列表。

## 11. 日志和验收标准

注册日志至少应包含插件、服务、触发器和结果：

```text
插件初始化完成：plugin=AzKeepAlive enabled=True
插件服务计算完成：plugin=AzKeepAlive service_count=1
插件服务注册完成：job=AzKeepAlive_AzKeepAlive trigger=cron
任务开始：plugin=AzKeepAlive trigger=schedule
任务结束：plugin=AzKeepAlive status=completed
```

验收必须确认：

1. 冷启动后启用插件出现在 `moviepilot scheduler list`；
2. 不保存配置、不手动重载也能注册；
3. 重启前后任务数量一致；
4. 重载后 job 回调绑定新插件实例；
5. 禁用后任务消失，重新启用后恢复；
6. 运行失败不会注销任务；
7. 同一插件同一服务最多一个 job；
8. 仓库中通过 AST、单元测试和必要的 MoviePilot 本地调度检查。

## 12. 最小模板

```python
from typing import Any, Dict, List

from apscheduler.triggers.interval import IntervalTrigger
from app.core.config import settings
from app.log import logger


class ExamplePlugin(_PluginBase):
    SERVICE_ID = "ExamplePlugin"
    SERVICE_NAME = "示例插件定时任务"

    _enabled = False
    _interval_minutes = 10
    _run_lock = threading.Lock()

    def init_plugin(self, config: dict = None):
        config = config or {}
        self._enabled = bool(config.get("enabled", False))
        self._interval_minutes = max(
            1,
            self._safe_int(config.get("interval_minutes"), 10),
        )

    def get_state(self) -> bool:
        return self._enabled

    def get_service(self) -> List[Dict[str, Any]]:
        if not self._enabled:
            return []
        return [{
            "id": self.SERVICE_ID,
            "name": self.SERVICE_NAME,
            "trigger": IntervalTrigger(
                minutes=self._interval_minutes,
                timezone=settings.TZ,
            ),
            "func": self.scheduled_run,
            "kwargs": {},
        }]

    def scheduled_run(self):
        if not self._run_lock.acquire(blocking=False):
            logger.info("示例插件已有任务执行，跳过本轮")
            return
        try:
            return self.run_task(trigger="schedule")
        except Exception as err:
            logger.exception(f"示例插件定时任务失败：{err}")
        finally:
            self._run_lock.release()

    def stop_service(self):
        # 公共任务由 MoviePilot Scheduler 清理。
        # 这里只清理插件自行创建的资源。
        pass
```

> 模板中的 `run_task()`、`_safe_int()` 和业务逻辑需要由具体插件实现。不要复制未使用的抽象层；简单插件保持简单。
