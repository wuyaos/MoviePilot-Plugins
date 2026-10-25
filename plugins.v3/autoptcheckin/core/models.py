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
    MAINTENANCE = "maintenance"
    NETWORK_ERROR = "network_error"
    PROTOCOL_PENDING = "protocol_pending"

class LoginStatus(StrEnum):
    LOGIN_OK = "login_ok"
    AUTH_FAILED = "auth_failed"
    UNCONFIRMED = "unconfirmed"

@dataclass(frozen=True)
class LoginPage:
    text: str
    url: str = ""
    status_code: int = 200

@dataclass(frozen=True)
class Evidence:
    button_text: str = ""
    uid: str | None = None
    date: str = ""
    status: str = ""
    source: str = "page"
    raw_summary: str = ""

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
    def skipped(cls, message: str = "该站点正在执行另一个动作，请稍后重试") -> "SignResult": return cls(SignStatus.SKIPPED, message)

@dataclass
class LoginResult(SignResult):
    status: LoginStatus
    @property
    def confirmed(self) -> bool:
        return self.status == LoginStatus.LOGIN_OK

def extract_reward_sentence(text: str) -> str | None:
    import re
    for pattern in (r"(?:奖励|获得|签到奖励)[：:\s]*([^。\n]{1,80})", r"(?:bonus|reward)[：:\s]*([^\.\n]{1,80})"):
        match = re.search(pattern, text or "", re.I)
        if match: return match.group(1).strip()
    return None

def extract_bonus(text: str) -> RewardSummary:
    import re
    values = re.findall(r"(?:余额|balance)[^\d-]*([\d.]+)", text or "", re.I)
    return RewardSummary(reported=extract_reward_sentence(text), current_balance=values[-1] if values else None)
