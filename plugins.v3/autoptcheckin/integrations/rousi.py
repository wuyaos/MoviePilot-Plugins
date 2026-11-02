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


def _session_result(page):
    code = getattr(page, 'status_code', None)
    data = _body(page)
    if code == 200 and isinstance(data.get('user'), dict) and data.get('csrf_token'):
        return LoginResult(LoginStatus.LOGIN_OK, 'PeerGo 会话有效')
    if code == 401:
        return LoginResult(LoginStatus.AUTH_FAILED, 'PeerGo 会话认证失败（HTTP 401）')
    detail = f'HTTP {code}' if code is not None else '无响应'
    return LoginResult(LoginStatus.UNCONFIRMED, f'PeerGo 会话未确认（{detail}；未重复登录）')


def login(http, info, *, session=None):
    """Only an explicit unauthenticated response permits account/password refresh."""
    page = session if session is not None else http.get(BASE + '/api/v1/session')
    checked = _session_result(page)
    if checked.status != LoginStatus.AUTH_FAILED:
        return checked
    username, password = info.get('rousi_username', ''), info.get('rousi_password', '')
    if not username or not password:
        return LoginResult(LoginStatus.AUTH_FAILED, 'Cookie 已失效，且未配置完整账号密码')
    page = http.post(BASE + '/api/v1/session', json={
        'identifier': username, 'password': password, 'remember_me': True},
        headers={'Origin': BASE, 'Referer': BASE + '/login'})
    checked = _session_result(page)
    if checked.status == LoginStatus.LOGIN_OK:
        checked.message = 'PeerGo 登录成功'
    return checked

def signin(http, info):
    session = http.get(BASE + "/api/v1/session")
    auth = _body(session)
    checked = _session_result(session)
    if checked.status == LoginStatus.AUTH_FAILED:
        refreshed = login(http, info, session=session)
        if refreshed.status != LoginStatus.LOGIN_OK:
            return SignResult(SignStatus(refreshed.status.value), refreshed.message)
        session = http.get(BASE + "/api/v1/session")
        checked = _session_result(session)
        auth = _body(session)
    if checked.status != LoginStatus.LOGIN_OK:
        return SignResult(SignStatus(checked.status.value), checked.message)
    csrf = auth["csrf_token"]
    page = http.get(BASE + "/api/v1/me/attendance")
    body = _body(page)
    if page.status_code == 401:
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
    if status == 401 or getattr(verified, "status_code", None) == 401:
        # 已尝试提交，不能返回会触发换源的 AUTH_FAILED 再领一次。
        return SignResult(SignStatus.UNCONFIRMED, "PeerGo 提交后会话失效，签到结果待确认", metadata=metadata)
    message = ('PeerGo 提交后回读仍未签到'
               if getattr(verified, 'status_code', None) == 200 and fresh.get('claimed_today') is False
               else 'PeerGo 签到回读未确认')
    return SignResult(SignStatus.UNCONFIRMED, message, metadata=metadata)


class RousiProtocol(CredentialLoginProtocol):
    credentials = ROUSI_CREDENTIALS
    def signin(self, context):
        return signin(context.http, getattr(context, "info", {}))
