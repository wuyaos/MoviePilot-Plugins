"""抽奖动作策略接口。"""
from abc import ABC, abstractmethod

from ..core.models import TaskResult


class LotteryAction(ABC):
    @abstractmethod
    def execute(self, site) -> TaskResult:
        """执行抽奖并返回结构化结果。"""
        raise NotImplementedError
