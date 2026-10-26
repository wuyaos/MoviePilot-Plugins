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


# ---- 统一结果值（执行/记录边界唯一出口）----
# 统一 status：signed/login_ok/failed/pending/skipped/cancelled；reason 精确值见下。
# 适配器内部保留 SignStatus/LoginStatus 原始值；仅历史、状态表与 API 载荷在边界归一。
UNIFIED_REASON_ALREADY = "already_signed"
UNIFIED_REASON_UNKNOWN = "result_unknown"


def unify_result(status, reason: str | None = None) -> tuple[str, str]:
    """原始执行值 → (统一 status, reason)。

    - success → signed（无 reason，代表本次成功）；already → signed+already_signed；signed 保持幂等。
    - auth_failed → failed+auth_failed；unconfirmed → pending+result_unknown；
      network_error/maintenance/protocol_pending → pending+同名 reason。
    - skipped/cancelled 透传（门控 reason 保留）；未知值封闭为 pending，原值由调用方保留。
    - 原细分 reason 不丢弃：调用方在 metadata 中保留。
    """
    status = getattr(status, "value", None) or status or ""
    reason = reason or ""
    if status == "success":
        return "signed", ""
    if status == "already":
        return "signed", UNIFIED_REASON_ALREADY
    if status == "signed":
        # 新归一产物（本次成功无 reason）保持幂等；legacy 旧值的 already 解释
        # 只发生在旧读边界（状态表 version==1 兼容 / 旧 history 无 reason 字段）。
        return "signed", (UNIFIED_REASON_ALREADY if reason == UNIFIED_REASON_ALREADY else reason)
    if status == "failed":
        return "failed", reason
    if status == "auth_failed":
        return "failed", "auth_failed"
    if status == "login_ok":
        return "login_ok", reason
    if status == "unconfirmed":
        return "pending", UNIFIED_REASON_UNKNOWN
    if status in ("network_error", "maintenance", "protocol_pending"):
        return "pending", status
    if status == "skipped" or status == "cancelled":
        return status, reason
    # 未知值封闭到统一六值：pending 兜底，原始值由调用方保留在 metadata.raw_status。
    return "pending", reason or UNIFIED_REASON_UNKNOWN


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
