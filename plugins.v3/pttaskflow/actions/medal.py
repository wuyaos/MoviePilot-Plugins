"""勋章购买策略接口。

具体站点实现 ``inspect``/``purchase``，并显式映射终态与重试语义；
Task/Engine 不从中文返回文案猜测“未过期、余额不足、购买成功”。
"""
from abc import ABC, abstractmethod
from enum import Enum

from ..core.models import TaskResult


class MedalState(str, Enum):
    PURCHASED = "purchased"
    ACTIVE = "active"
    INSUFFICIENT_FUNDS = "insufficient_funds"
    UNAVAILABLE = "unavailable"
    REJECTED = "rejected"
    TECHNICAL_FAILURE = "technical_failure"


class MedalAction(ABC):
    default_medal_id = ""

    @abstractmethod
    def purchase(self, site, medal_id: str) -> TaskResult:
        """检查并购买指定勋章，返回显式 TaskResult。"""
        raise NotImplementedError
