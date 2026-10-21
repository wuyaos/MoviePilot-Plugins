"""Single submission, fresh readback even on exceptions; caller owns site lock."""
from datetime import datetime
from .models import SignResult, SignStatus
from .verification import normalize_evidence


def run_page(adapter, bound_uid="", readonly=False, bind=None, business_date=None):
    day = business_date or datetime.now().astimezone().date().isoformat()
    try:
        page = adapter.fetch_page()
        uid = adapter.verifier.identity(page)
        if not uid or (bound_uid and uid != bound_uid):
            return SignResult(SignStatus.UNCONFIRMED, "页面身份缺失或冲突")
        if bind and not bound_uid:
            bind(uid)
        evidence = adapter.verifier.parse(page, uid, day)
        result = normalize_evidence(evidence, uid, day, before_submit=True)
        if readonly or result.confirmed:
            return result
        # A token alone is not permission to submit on an unknown page.
        if not adapter.verifier.token(page) or not evidence or not evidence.button_text or result.status != SignStatus.FAILED:
            return SignResult(SignStatus.UNCONFIRMED, "未确认本人当日未签到，不提交", evidence=evidence)
    except Exception:
        return SignResult(SignStatus.UNCONFIRMED, "签到前读取不可达或解析异常")
    try:
        adapter.submit(page)
    except Exception:
        pass
    finally:
        try:
            after = adapter.fetch_page()
            evidence = adapter.verifier.parse(after, uid, day)
            result = normalize_evidence(evidence, uid, day)
            if result.confirmed and hasattr(adapter.verifier, "reward"):
                result.reward = adapter.verifier.reward(after, uid, day)
        except Exception:
            result = SignResult(SignStatus.UNCONFIRMED, "新页面不可达或解析异常，需只读复核")
    return result
