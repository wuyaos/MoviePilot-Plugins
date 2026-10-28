"""PeerGo attendance and session integration."""
import json
from uuid import uuid4

from ..core.credentials import CredentialSpec
from ..core.models import LoginResult, LoginStatus, SignResult, SignStatus
from .login import CredentialLoginProtocol

BASE = "https://rousi.pro"
ROUSI_CREDENTIALS = CredentialSpec(kind="password", refresh="password")


def _body(response):
    try:
        return json.loads(response.text)
    except (TypeError, ValueError):
        return {}


def login(http, info):
    """Validate configured Cookie, then refresh it with account credentials if needed."""
    page = http.get(BASE + "/api/v1/session")
    data = _body(page)
    if page.status_code == 200 and isinstance(data.get("user"), dict) and data.get("csrf_token"):
        return LoginResult(LoginStatus.LOGIN_OK, "PeerGo 会话有效")
    username, password = info.get("rousi_username", ""), info.get("rousi_password", "")
    if not username or not password:
        return LoginResult(LoginStatus.AUTH_FAILED, "Cookie 已失效，且未配置完整账号密码")
    page = http.post(BASE + "/api/v1/session", json={"identifier": username, "password": password, "remember_me": True}, headers={"Origin": BASE, "Referer": BASE + "/login"})
    data = _body(page)
    if page.status_code == 200 and isinstance(data.get("user"), dict) and data.get("csrf_token"):
        return LoginResult(LoginStatus.LOGIN_OK, "PeerGo 登录成功")
    return LoginResult(LoginStatus.AUTH_FAILED, "PeerGo 账号认证失败")


def signin(http, info):
    session = http.get(BASE + "/api/v1/session")
    auth = _body(session)
    if session.status_code in (401, 403) or not isinstance(auth.get("user"), dict) or not auth.get("csrf_token"):
        refreshed = login(http, info)
        if refreshed.status != LoginStatus.LOGIN_OK:
            return SignResult(SignStatus.AUTH_FAILED, refreshed.message)
        session = http.get(BASE + "/api/v1/session")
        auth = _body(session)
        if session.status_code != 200 or not isinstance(auth.get("user"), dict) or not auth.get("csrf_token"):
            return SignResult(SignStatus.AUTH_FAILED, "PeerGo 会话未登录")
    csrf = auth["csrf_token"]
    page = http.get(BASE + "/api/v1/me/attendance")
    body = _body(page)
    if page.status_code in (401, 403):
        return SignResult(SignStatus.AUTH_FAILED, "PeerGo 会话未登录")
    if page.status_code != 200:
        return SignResult(SignStatus.UNCONFIRMED, "PeerGo 签到状态未确认")
    if body.get("claimed_today") is True:
        return SignResult(SignStatus.ALREADY, "今日已签到")
    result = http.post(BASE + "/api/v1/me/attendance", json={"mode": "fixed"}, headers={"Origin": BASE, "Referer": BASE + "/account/economy", "X-CSRF-Token": csrf, "Idempotency-Key": str(uuid4())})
    data = _body(result)
    if result.status_code in (401, 403):
        return SignResult(SignStatus.AUTH_FAILED, "PeerGo 会话认证失败")
    if result.status_code == 200 and (data.get("claimed_today") is True or data.get("success") is True):
        return SignResult(SignStatus.SUCCESS, "PeerGo 签到成功")
    if result.status_code == 409 or data.get("code") in ("already_claimed", "already_attended"):
        return SignResult(SignStatus.ALREADY, "今日已签到")
    return SignResult(SignStatus.UNCONFIRMED, "PeerGo 签到结果未确认")


class RousiProtocol(CredentialLoginProtocol):
    credentials = ROUSI_CREDENTIALS
    def signin(self, context):
        return signin(context.http, getattr(context, "info", {}))
