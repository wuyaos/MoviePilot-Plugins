"""只信任回读的本人当日行；旧二元组不决定最终状态。"""
from .models import Evidence, SignResult, SignStatus


SUCCESS_STATES = {"已签到", "签到成功", "success", "already"}
FAILURE_STATES = {"未签到", "not_signed"}


def normalize_evidence(evidence: Evidence | None, uid: str, business_date: str,
                       before_submit: bool = False) -> SignResult:
    if (evidence is None or not uid or not business_date or not evidence.button_text
            or evidence.uid != uid or evidence.date != business_date
            or evidence.source not in ("page", "api")):
        return SignResult(SignStatus.UNCONFIRMED, "页面缺少按钮或本人当日记录，或账号不匹配", evidence=evidence)
    if evidence.status in SUCCESS_STATES:
        return SignResult(SignStatus.ALREADY if before_submit else SignStatus.SUCCESS,
                          "本人当日签到记录已确认", evidence=evidence)
    if evidence.status in FAILURE_STATES:
        return SignResult(SignStatus.FAILED, "新页面本人当日记录确认尚未签到", evidence=evidence)
    return SignResult(SignStatus.UNCONFIRMED, "记录状态无法识别", evidence=evidence)
