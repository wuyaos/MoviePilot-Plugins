"""PtTaskFlow 核心数据模型。

这些是纯数据对象，串联三条边界：
- ``Control``：任务向 UI 声明配置控件，UI 只消费它，不感知任务类型。
- ``Unit``：任务展开出的一次实际执行，引擎只消费它，不感知站点 DOM。
- ``TaskResult``：一次执行的结构化结果，历史/通知只消费它，不猜中文文案。

任何一层都不反向依赖具体站点或任务子类。
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class ControlKind(str, Enum):
    """配置控件类型。UI 按此渲染 VSwitch / VSelect。"""

    SWITCH = "switch"
    SELECT_ONE = "select_one"
    SELECT_MANY = "select_many"


@dataclass(frozen=True)
class Control:
    """任务声明的一个配置控件。

    :param kind: 控件类型。
    :param key: 顶层扁平配置 key，同时作为前端表单 model 绑定名。
    :param label: 显示名。
    :param hint: 提示文本。
    :param options: SELECT_* 的下拉选项，[{id, label}]。
    :param placeholder: 下拉未选择时的占位提示。
    """

    kind: ControlKind
    key: str
    label: str
    hint: str = ""
    options: List[Dict[str, Any]] = field(default_factory=list)
    placeholder: str = ""


@dataclass
class Unit:
    """任务展开出的一次实际执行单元。

    :param task: 产生本单元的任务实例（回调 ``task.run`` 用）。
    :param site: 执行所在站点实例。
    :param execution_key: 跳过/重试隔离键；同任务多单元必须各不相同。
    :param label: 展示名（通知/历史/日志）。
    :param argument: 执行参数（喊话消息、勋章 id、申领 exam_id 等）。
    """

    task: Any
    site: Any
    execution_key: str
    label: str
    argument: Any = None


@dataclass
class TaskResult:
    """一次执行单元的结构化结果。

    :param success: 是否成功。
    :param message: 结果文本。
    :param terminal: 是否当天终态（成功或确定幂等），True 则不再重试/补跑。
    :param retryable: 是否可技术重试。
    :param rewards: 结构化奖励 [{type, description, amount, unit, is_negative}]。
    """

    success: bool
    message: str = ""
    terminal: bool = False
    retryable: bool = False
    rewards: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def ok(cls, message: str = "执行成功", rewards: Optional[List[Dict]] = None) -> "TaskResult":
        return cls(success=True, message=message, terminal=True, retryable=False, rewards=rewards or [])

    @classmethod
    def idempotent(cls, message: str) -> "TaskResult":
        """确定幂等状态（今日已签到/已领取）：终态成功，不重试。"""
        return cls(success=True, message=message, terminal=True, retryable=False)

    @classmethod
    def business(cls, message: str) -> "TaskResult":
        """业务性未完成（资格不足、窗口未到）：非终态、不技术重试。"""
        return cls(success=False, message=message, terminal=False, retryable=False)

    @classmethod
    def fail(cls, message: str = "执行失败") -> "TaskResult":
        """技术失败（HTTP/解析/Cookie）：可重试。"""
        return cls(success=False, message=message, terminal=False, retryable=True)


# 供任务声明惰性求值 label 的回调签名（site -> str）。
LabelFn = Callable[[Any], str]
