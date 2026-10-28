"""只信任回读的本人当日行；旧二元组不决定最终状态。"""
from typing import Callable
from .models import Evidence, RewardSummary, SignResult, SignStatus, LoginResult, LoginStatus, LoginPage

SUCCESS_STATES = {"已签到", "签到成功", "success", "already"}
FAILURE_STATES = {"未签到", "not_signed", "failed"}

def normalize_evidence(evidence: Evidence | None, uid: str, business_date: str,
                       before_submit: bool = False) -> SignResult:
    if evidence is None:
        return SignResult(SignStatus.UNCONFIRMED, "签到页未读取到可确认的签到证据", evidence=evidence)
    if not evidence.date or not business_date or evidence.date != business_date:
        return SignResult(SignStatus.UNCONFIRMED, "本人记录行日期非今日，需只读复核", evidence=evidence)
    if evidence.source != "page":
        return SignResult(SignStatus.UNCONFIRMED, "证据来源非页面回读，不予确认", evidence=evidence)
    if evidence.status in SUCCESS_STATES:
        return SignResult(SignStatus.ALREADY if before_submit else SignStatus.SUCCESS,
                          "本人当日签到记录已确认", evidence=evidence)
    if evidence.status in FAILURE_STATES:
        return SignResult(SignStatus.FAILED, "新页面本人当日记录确认尚未签到", evidence=evidence)
    return SignResult(SignStatus.UNCONFIRMED, "记录状态无法识别", evidence=evidence)

def verify_after_submit(fetch_page: Callable[[], str], verifier, uid: str, business_date: str) -> SignResult:
    # 提交超时或异常，调用方都必须进入本方法（无条件回读）。
    try:
        page = fetch_page()
        evidence = verifier.parse(page, uid, business_date) if page else None
        return normalize_evidence(evidence, uid, business_date)
    except Exception:
        return SignResult(SignStatus.UNCONFIRMED, "新页面不可达或解析异常，需只读复核")

def extract_reward_evidence(submission: str = "", recent_activity: str = "", *,
                            balance_before: str | None = None,
                            balance_after: str | None = None) -> RewardSummary:
    from .models import extract_reward_sentence
    # 只有明确的奖励句子才是本次奖励；最近动向只作辅助，不冒充接口报告。
    return RewardSummary(reported=extract_reward_sentence(submission),
                         balance_before=balance_before, balance_after=balance_after,
                         current_balance=balance_after,
                         recent_activity=extract_reward_sentence(recent_activity))


def verify_login(fetch_page, verifier, uid="") -> LoginResult:
    """页面可达即登录态；身份仅作展示证据，不参与状态判定。"""
    from urllib.parse import urlsplit
    try:
        page = fetch_page()
    except Exception:
        return LoginResult(LoginStatus.UNCONFIRMED, "登录回读页面不可达")
    if isinstance(page, LoginPage):
        path = urlsplit(page.url).path.lower().rstrip("/")
        if path.rsplit("/", 1)[-1] in {"login.php", "login", "signin", "signin.php"} or page.status_code in {401, 403}:
            return LoginResult(LoginStatus.AUTH_FAILED, "页面转向登录或认证失败")
        if page.status_code != 200:
            return LoginResult(LoginStatus.UNCONFIRMED, "登录回读页面不可达")
        page = page.text
    if not page:
        return LoginResult(LoginStatus.UNCONFIRMED, "登录回读页面不可达")
    try:
        evidence = verifier.parse_login(page)
    except Exception:
        evidence = Evidence()
    return LoginResult(LoginStatus.LOGIN_OK, "已登录", evidence=evidence)
