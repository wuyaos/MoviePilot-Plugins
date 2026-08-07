# input: 签到/登录处理器返回的 (ok, message)
# output: 语言无关的结构化签到状态枚举
# pos: helper 层，供编排层按状态分类，避免依赖简繁文案子串匹配
from enum import Enum
from typing import Optional


class SigninStatus(str, Enum):
    """签到/登录结果状态，语言无关。

    message 仅用于通知展示，结果分类以此枚举为准，避免简繁文案差异导致漏判。
    """
    SUCCESS = "success"                 # 签到成功
    ALREADY = "already"                 # 今日已签到
    SIM_SIGNIN = "sim_signin"           # 仿真签到成功
    LOGIN = "login"                     # 模拟/仿真登录成功
    NEEDS_ADAPTER = "needs_adapter"     # 通用处理器无法签到，需专属适配器
    FAILED = "failed"


# 视为成功的状态集合，供编排层判断是否进入重试。
SUCCESS_STATUSES = frozenset({
    SigninStatus.SUCCESS, SigninStatus.ALREADY,
    SigninStatus.SIM_SIGNIN, SigninStatus.LOGIN,
})

# 成功语义文案（含繁体），按特异性优先匹配；存在子串关系的条目必须排在前面。
# 例如 "仿真签到成功" 必须早于 "签到成功"，否则会被后者先行命中。
_STATUS_PATTERNS = (
    (SigninStatus.SIM_SIGNIN, ("仿真签到成功", "仿真簽到成功")),
    (SigninStatus.LOGIN, (
        "模拟登录成功", "模擬登錄成功",
        "仿真登录成功", "仿真登錄成功",
        "登录成功", "登錄成功",
    )),
    (SigninStatus.ALREADY, ("今日已签到", "今日已簽到", "已签到", "已簽到")),
    (SigninStatus.SUCCESS, ("签到成功", "簽到成功")),
)

# 通用处理器检测到的"需专属适配器"提示文案。
_ADAPTER_HINTS = ("需要 POST 签到适配器", "需要验证码签到适配器")


def infer_signin_status(ok: bool, message: Optional[str]) -> SigninStatus:
    """根据签到/登录返回的布尔结果与文案推断结构化状态。

    适配器仍返回 ``(bool, str)``，本函数集中完成简繁文案到状态的映射，
    使编排层不再散落子串判断。文案仅用于区分成功子类；成功与否以 ``ok`` 为准。
    """
    text = message or ""
    for status, patterns in _STATUS_PATTERNS:
        if any(p in text for p in patterns):
            return status
    if any(hint in text for hint in _ADAPTER_HINTS):
        return SigninStatus.NEEDS_ADAPTER
    return SigninStatus.SUCCESS if ok else SigninStatus.FAILED
