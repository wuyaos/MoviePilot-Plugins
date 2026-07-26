"""统一任务结果对象。

替代原 ptautotask/groupchatzone 中靠字符串判断成败、靠 label 匹配反馈的脆弱方式。
任务方法可返回 TaskResult 或 str（向后兼容）。
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class TaskResult:
    """任务执行结果。"""

    success: bool
    message: str = ""
    # 喊话反馈（groupchatzone 核心能力）：{site, message, rewards:[{type,description,...}]}
    feedback: Optional[Dict] = None
    # 直接产出的奖励（非喊话类，如领勋章/抽奖的中奖信息）
    rewards: List[Dict] = field(default_factory=list)
    # 本次真实购买成功的勋章 ID；未过期、余额不足等检查结果不写入。
    purchased_medal_ids: List[str] = field(default_factory=list)

    @classmethod
    def ok(cls, message: str = "执行成功", feedback: Dict = None, rewards: List[Dict] = None,
           purchased_medal_ids: List[str] = None) -> "TaskResult":
        return cls(success=True, message=message, feedback=feedback, rewards=rewards or [],
                   purchased_medal_ids=purchased_medal_ids or [])

    @classmethod
    def fail(cls, message: str = "执行失败") -> "TaskResult":
        return cls(success=False, message=message)

    def to_status_text(self) -> str:
        """转换为状态文本（用于历史记录展示）。"""
        return self.message or ("执行成功" if self.success else "执行失败")
