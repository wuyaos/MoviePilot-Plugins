"""V3 签到结果与回读证据模型。"""
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

class SignStatus(StrEnum):
    SUCCESS = "success"
    ALREADY = "already"
    FAILED = "failed"
    UNCONFIRMED = "unconfirmed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    AUTH_FAILED = "auth_failed"
    NETWORK_ERROR = "network_error"

@dataclass(frozen=True)
class Evidence:
    button_text: str = ""
    uid: str = ""
    date: str = ""
    status: str = ""
    source: str = "page"
    raw_summary: str = ""
    note: str = ""

@dataclass(frozen=True)
class RewardSummary:
    reported: str | None = None
    balance_before: str | None = None
    balance_after: str | None = None
    current_balance: str | None = None
    recent_activity: str | None = None
    unit: str | None = None

@dataclass
class SignResult:
    status: SignStatus
    message: str = ""
    evidence: Evidence | None = None
    reward: RewardSummary | None = None
    site_id: str = ""
    account: str = ""
    run_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    @property
    def confirmed(self) -> bool: return self.status in (SignStatus.SUCCESS, SignStatus.ALREADY)
    @classmethod
    def skipped(cls, message: str = "任务忙，未排队") -> "SignResult": return cls(SignStatus.SKIPPED, message)
