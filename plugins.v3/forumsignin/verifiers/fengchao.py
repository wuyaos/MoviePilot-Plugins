"""Explicit API evidence exception approved for the forum skeleton."""
from ..core.models import Evidence, RewardSummary, SignResult, SignStatus


def verify(payload, submitted=False):
    checkin = payload.get("checkIn", payload)
    already = checkin.get("alreadyCheckedIn")
    checked = checkin.get("checkedInToday")
    if submitted and isinstance(already, bool):
        status = SignStatus.ALREADY if already else SignStatus.SUCCESS
    elif checked is True:
        status = SignStatus.ALREADY
    elif checked is False:
        status = SignStatus.FAILED
    else:
        return SignResult(SignStatus.UNCONFIRMED, "蜂巢 API 未返回明确签到状态")
    streak = checkin.get("currentStreak")
    note = f"连续签到{streak}天" if isinstance(streak, int) and streak > 0 else ""
    account = payload.get("account") or {}
    evidence = Evidence(uid=str(payload.get("userId") or account.get("uid") or ""),
                        date=str(checkin.get("lastCheckinTime") or "")[:10],
                        status=status.value, source="api", note=note)
    reward = RewardSummary(reported=str(checkin["reward"]) if "reward" in checkin else None,
                           current_balance=str(payload["points"]) if "points" in payload else None,
                           unit="积分")
    return SignResult(status, note or "蜂巢 API 签到状态已确认", evidence=evidence, reward=reward)
