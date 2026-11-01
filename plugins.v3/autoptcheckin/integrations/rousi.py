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
        data = json.loads(getattr(response, 'text', ''))
        return data if isinstance(data, dict) else {}
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
    settings = ((body.get('policy') or {}).get('settings') or {})
    if not settings:
        return SignResult(SignStatus.PROTOCOL_PENDING, 'PeerGo 未读到签到活动配置，未提交')
    if not settings.get('enabled', False):
        return SignResult(SignStatus.PROTOCOL_PENDING, 'PeerGo 签到活动当前未开放')
    if settings.get('fixed_enabled'):
        mode = 'fixed'
    elif settings.get('random_enabled'):
        mode = 'random'
    else:
        return SignResult(SignStatus.PROTOCOL_PENDING, 'PeerGo 当前没有可用的签到奖励模式')

    # 提交只尝试一次；即使超时，也先回读，不能因回包缺字段就重放奖励请求。
    result = None
    submit_error = None
    try:
        result = http.post(BASE + '/api/v1/me/attendance', json={'mode': mode}, headers={
            'Origin': BASE, 'Referer': BASE + '/account/economy',
            'X-CSRF-Token': csrf, 'Idempotency-Key': str(uuid4())})
    except Exception as exc:
        submit_error = type(exc).__name__
    verified = None
    try:
        verified = http.get(BASE + '/api/v1/me/attendance')
        fresh = _body(verified)
    except Exception:
        fresh = {}
    status = getattr(result, 'status_code', None)
    metadata = {'attendance': {'mode': mode, 'submit_http': status,
                               'read_http': getattr(verified, 'status_code', None)}}
    if submit_error:
        metadata['attendance']['submit_error'] = submit_error
    if getattr(verified, 'status_code', None) == 200 and fresh.get('claimed_today') is True:
        record = fresh.get('today_record') or {}
        reward = record.get('total_reward')
        message = 'PeerGo 签到成功（已回读确认）'
        if isinstance(reward, (int, float)) and not isinstance(reward, bool):
            message += f'；获得 {reward} 魔力值'
        return SignResult(SignStatus.SUCCESS, message, metadata=metadata)
    if status in (401, 403) or getattr(verified, 'status_code', None) in (401, 403):
        return SignResult(SignStatus.AUTH_FAILED, 'PeerGo 会话认证失败', metadata=metadata)
    message = ('PeerGo 提交后回读仍未签到'
               if getattr(verified, 'status_code', None) == 200 and fresh.get('claimed_today') is False
               else 'PeerGo 签到回读未确认')
    return SignResult(SignStatus.UNCONFIRMED, message, metadata=metadata)


class RousiProtocol(CredentialLoginProtocol):
    credentials = ROUSI_CREDENTIALS
    def signin(self, context):
        return signin(context.http, getattr(context, "info", {}))
