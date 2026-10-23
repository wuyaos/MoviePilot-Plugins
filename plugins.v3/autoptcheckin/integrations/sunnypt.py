"""SunnyPT JWT attendance integration."""
import json

from ..core.credentials import CredentialSpec
from ..core.models import LoginResult, LoginStatus, SignResult, SignStatus
from .login import CredentialLoginProtocol

API = "https://api.sunnypt.top"
REFERER = "https://sunnypt.top/user/attendance"
SUNNYPT_CREDENTIALS = CredentialSpec(kind="password", refresh="password", identity_field="uid")


def _body(response):
    try:
        return json.loads(response.text)
    except (TypeError, ValueError):
        return {}


def _token(http, info):
    token = info.get("sunnypt_token", "")
    if token:
        return token
    username, password = info.get("sunnypt_username", ""), info.get("sunnypt_password", "")
    if not username or not password:
        return ""
    response = http.post(API + "/login", json={"username": username, "password": password}, headers={"Referer": REFERER})
    body = _body(response)
    return (body.get("data") or {}).get("token", "") if response.status_code == 200 and body.get("code") == 0 else ""


def login(http, info):
    token = _token(http, info)
    if not token:
        return LoginResult(LoginStatus.AUTH_FAILED, "SunnyPT 缺少有效 JWT 或账号密码")
    response = http.get(API + "/api/v1/attendance/status", headers={"Authorization": f"Bearer {token}", "Referer": REFERER})
    body = _body(response)
    return LoginResult(LoginStatus.LOGIN_OK if response.status_code == 200 and body.get("code") == 0 else LoginStatus.AUTH_FAILED,
                       "SunnyPT 登录验证成功" if response.status_code == 200 and body.get("code") == 0 else "SunnyPT JWT 验证失败")


def signin(http, info):
    token = _token(http, info)
    if not token:
        return SignResult(SignStatus.AUTH_FAILED, "SunnyPT 缺少有效 JWT 或账号密码")
    for attempt in range(2):
        response = http.post(API + "/api/v1/attendance/check-in", json={}, headers={"Authorization": f"Bearer {token}", "Referer": REFERER})
        body = _body(response)
        code = body.get("code")
        if response.status_code == 200 and code == 0:
            return SignResult(SignStatus.SUCCESS, body.get("msg") or "SunnyPT 签到成功")
        if code == 400001:
            return SignResult(SignStatus.ALREADY, "今日已签到")
        if code == 400000:
            if attempt == 0:
                token = _token(http, {**info, "sunnypt_token": ""})
                if token:
                    continue
            return SignResult(SignStatus.AUTH_FAILED, "SunnyPT 登录状态失效")
        return SignResult(SignStatus.UNCONFIRMED, "SunnyPT 签到结果未确认")
    return SignResult(SignStatus.AUTH_FAILED, "SunnyPT 登录状态失效")


class SunnyPtProtocol(CredentialLoginProtocol):
    credentials = SUNNYPT_CREDENTIALS
    def signin(self, context):
        return signin(context.http, getattr(context, "info", {}))
