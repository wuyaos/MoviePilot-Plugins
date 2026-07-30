"""任务领域模型：Task 抽象基类 + 四种一等任务类型。

任务是一等公民：站点用 ``tasks = [Checkin(), Chat(...), ...]`` 组合实例。
每个任务类自己负责四件事——配置控件、启用判断、单元展开、执行。
引擎/UI 只与 Task 的这四个接口交互，不感知站点内部实现。

配置 key 契约：``task_{site_id}_{task.name}``。``name`` 写死在子类，
是配置和历史的稳定标识，改名等于丢用户配置，务必保持稳定。
"""
from typing import List

from .models import Control, ControlKind, TaskResult, Unit
from .task_keys import site_task_key


class TaskType:
    """任务类型常量。用于 UI 排序、图标和引擎分派。"""

    GENERIC = "generic"
    CHECKIN = "checkin"
    CHAT = "chat"
    CLAIM = "claim"
    EXCHANGE = "exchange"
    MEDAL = "medal"
    LOTTERY = "lottery"


class Task:
    """任务抽象基类。子类声明 ``name`` 和 ``task_type``，实现 run。"""

    name: str = ""
    task_type: str = TaskType.GENERIC

    def key(self, site) -> str:
        """本任务在指定站点的顶层配置 key。"""
        return site_task_key(site, self.name)

    def label(self, site) -> str:
        """展示名，默认站名 + 类型；子类可覆写。"""
        return f"{site.site_name}{self.name}"

    def controls(self, site) -> List[Control]:
        """向 UI 声明配置控件。默认单个开关。"""
        return [Control(ControlKind.SWITCH, self.key(site), self.label(site))]

    def is_enabled(self, site, config: dict) -> bool:
        """从配置读取本任务是否启用。默认按开关。"""
        return bool(config.get(self.key(site), False))

    def expand(self, site, config: dict) -> List[Unit]:
        """展开为执行单元。默认单个单元。"""
        return [Unit(self, site, self.execution_key(site), self.label(site))]

    def execution_key(self, site, suffix: str = "") -> str:
        """跳过/重试隔离键。多单元任务用 suffix 区分。"""
        base = f"{site.domain}:{self.name}"
        return f"{base}:{suffix}" if suffix else base

    def run(self, site, unit: Unit) -> TaskResult:
        """执行单元。子类必须实现。"""
        raise NotImplementedError


class Checkin(Task):
    """签到任务。请求/解析下沉到可替换的 CheckinAction 策略。"""

    name = "daily_checkin"
    task_type = TaskType.CHECKIN

    def __init__(self, action=None, label="签到"):
        from ..actions.checkin import NexusPHPCheckin
        self.action = action or NexusPHPCheckin()
        self._label = label

    def label(self, site) -> str:
        return self._label

    def run(self, site, unit) -> TaskResult:
        return self.action.execute(site)


class Chat(Task):
    """喊话任务。

    - ``messages`` 多条 → 展开为多个执行单元（各自独立 key）。
    - ``options`` 非空 → 渲染下拉单选，只喊选中的一条。
    - ``negatives`` 声明反馈负面标记关键词。
    发送确认与反馈关联由 site.send_and_confirm（基于 ShoutboxProfile）统一处理。
    """

    name = "daily_shotbox"
    task_type = TaskType.CHAT

    def __init__(self, messages=(), options=None, negatives=(), label="喊话"):
        self.messages = list(messages)
        self.options = list(options) if options else None
        self.negatives = tuple(negatives)
        self._label = label

    def label(self, site) -> str:
        return self._label

    def controls(self, site) -> List[Control]:
        if self.options:
            return [Control(ControlKind.SELECT_ONE, self.key(site), self.label(site),
                            options=self.options, placeholder="不喊话")]
        return [Control(ControlKind.SWITCH, self.key(site), self.label(site))]

    def is_enabled(self, site, config: dict) -> bool:
        if self.options:
            return bool(config.get(self.key(site)))
        return bool(config.get(self.key(site), False))

    def expand(self, site, config: dict) -> List[Unit]:
        if self.options:
            selected = str(config.get(self.key(site)) or "")
            if not selected:
                return []
            option = next((o for o in self.options if str(o.get("id")) == selected), None)
            message = (option or {}).get("message") or (option or {}).get("label") or selected
            return [Unit(self, site, self.execution_key(site, selected), f"“{message}”", message)]
        return [Unit(self, site, self.execution_key(site, msg), f"“{msg}”", msg)
                for msg in self.messages]

    def run(self, site, unit) -> TaskResult:
        return site.send_and_confirm(unit.argument, self.negatives)


class Claim(Task):
    """任务申领。下拉单选一个 exam_id。"""

    name = "claim"
    task_type = TaskType.CLAIM

    def __init__(self, options=(), label="任务申领"):
        self.options = list(options)
        self._label = label

    def label(self, site) -> str:
        return self._label

    def controls(self, site) -> List[Control]:
        return [Control(ControlKind.SELECT_ONE, self.key(site), self.label(site),
                        options=self.options, placeholder="不申领")]

    def is_enabled(self, site, config: dict) -> bool:
        return bool(config.get(self.key(site)))

    def expand(self, site, config: dict) -> List[Unit]:
        selected = str(config.get(self.key(site)) or "")
        if not selected:
            return []
        option = next((o for o in self.options if str(o.get("id")) == selected), None)
        label = (option or {}).get("label") or selected
        return [Unit(self, site, self.execution_key(site, selected), label, selected)]

    def run(self, site, unit) -> TaskResult:
        return site.claim_task(unit.argument)


class Medal(Task):
    """勋章续购。

    - 固定单枚：开关控件，action 提供默认 medal_id。
    - 多选：SELECT_MANY，每枚勋章展开为独立单元，一枚失败不阻断另一枚。
    购买状态机（未过期/魔力不足/购买成功/接口失败）由 MedalAction 负责。
    """

    name = "buy_medal"
    task_type = TaskType.MEDAL

    def __init__(self, action, options=None, label="勋章续购"):
        self.action = action
        self.options = list(options) if options else None
        self._label = label

    def label(self, site) -> str:
        return self._label

    def controls(self, site) -> List[Control]:
        if self.options:
            return [Control(ControlKind.SELECT_MANY, self.key(site), self.label(site),
                            options=self.options, placeholder="不购买")]
        return [Control(ControlKind.SWITCH, self.key(site), self.label(site))]

    def is_enabled(self, site, config: dict) -> bool:
        value = config.get(self.key(site))
        if self.options:
            return bool(value)
        return bool(value if value is not None else False)

    def expand(self, site, config: dict) -> List[Unit]:
        if self.options:
            selected = config.get(self.key(site)) or []
            if isinstance(selected, str):
                selected = [selected] if selected else []
            units = []
            for medal_id in selected:
                option = next((o for o in self.options if str(o.get("id")) == str(medal_id)), None)
                label = (option or {}).get("label") or str(medal_id)
                units.append(Unit(self, site, self.execution_key(site, str(medal_id)), label, str(medal_id)))
            return units
        default_id = getattr(self.action, "default_medal_id", "")
        return [Unit(self, site, self.execution_key(site, default_id), self.label(site), default_id)]

    def run(self, site, unit) -> TaskResult:
        return self.action.purchase(site, unit.argument)


class ActionTask(Task):
    """由 Action 驱动的单单元任务。

    用于兑换、站点专属检查等不值得新增通用 Task 子类的业务。``name`` 必须
    由站点显式传入且发布后保持稳定；Action 仍需返回结构化 ``TaskResult``。
    """

    def __init__(self, name: str, action, label: str, task_type=TaskType.GENERIC):
        if not name:
            raise ValueError("ActionTask.name 不能为空")
        self.name = str(name)
        self.action = action
        self._label = label
        self.task_type = task_type

    def label(self, site) -> str:
        return self._label

    def run(self, site, unit) -> TaskResult:
        return self.action.execute(site)


class Exchange(ActionTask):
    """兑换任务。默认稳定名称为 ``daily_exchange``。"""

    def __init__(self, action, label="兑换", name="daily_exchange"):
        super().__init__(name=name, action=action, label=label, task_type=TaskType.EXCHANGE)


class Lottery(ActionTask):
    """抽奖任务。请求/结果解析下沉到 LotteryAction。"""

    def __init__(self, action, label="抽奖", name="daily_lottery"):
        super().__init__(name=name, action=action, label=label, task_type=TaskType.LOTTERY)
