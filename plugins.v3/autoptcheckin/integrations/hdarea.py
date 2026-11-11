"""HDArea 官方 REST API 签到（user scope）；配置 hdarea_apikey 时启用。

api_docs.php#sec-rest 契约：X-API-Key 头鉴权（不进 URL 日志），统一包裹
`{success, code, http_code, message, data}`；POST `api/v1/user/signin`
（user scope，站方数据库原子防重），GET `api/v1/user/profile`（read scope）。
未配置 Key 时执行边界回退 generic form（Cookie 表单）通道，登录轨不受影响。
分类只接受显式包裹字段：success=false 且服务端 message 命中已签文案表才判
already，不猜业务 code；429 → protocol_pending 待重试；401/403 → auth_failed。
"""
import json

from ..core.models import SignResult, SignStatus

SIGN_PATH = "api/v1/user/signin"
PROFILE_PATH = "api/v1/user/profile"
# 已签原文声明表：success=false 且 message 命中才判 already；其余 false 保持未确认。
ALREADY_MARKERS = ("已签", "已經簽", "已经签", "請勿重複", "请勿重复", "重复签", "重複簽")


def _default_request(method, url, *, headers, payload):
    from app.sdk.network import RequestUtils

    util = RequestUtils(timeout=20, headers=headers, content_type="application/json")
    if method == "GET":
        return util.get_res(url=url, raise_exception=True)
    return util.post_res(url=url, json=payload, raise_exception=True)


def _envelope(response):
    if response is None:
        return None
    try:
        data = json.loads(response.text)
    except (TypeError, ValueError, AttributeError):
        return None
    return data if isinstance(data, dict) else None


def _message(envelope):
    value = envelope.get("message")
    return value.strip() if isinstance(value, str) else ""


def _api_key(info, config):
    return str((config or {}).get('hdarea_apikey') or (info or {}).get('hdarea_apikey') or '').strip()


def run_hdarea_api(site, info, *, config=None, cancel=None, read_only=False, request=None):
    """API 通道签到；read_only 只做 profile 核验，绝不提交签到。"""
    apikey = _api_key(info, config)
    if not apikey:
        # 执行边界只在有 Key 时分派；此返回是防御位，不触发任何请求。
        return SignResult(SignStatus.SKIPPED, '未配置 hdarea_apikey，不走 API 通道')
    request = request or _default_request
    headers = {"X-API-Key": apikey, "Accept": "application/json"}
    if cancel is not None and cancel.is_set():
        return SignResult(SignStatus.CANCELLED, '已停止，未访问')

    def _auth(code):
        return SignResult(SignStatus.AUTH_FAILED,
                          f'好大 API Key 无效或缺 user/read 权限（HTTP {code}）')

    if read_only:
        try:
            response = request("GET", site.url + PROFILE_PATH, headers=headers, payload=None)
        except Exception as exc:
            return SignResult(SignStatus.NETWORK_ERROR, f'好大 API 不可达：{type(exc).__name__}')
        code = getattr(response, 'status_code', None)
        envelope = _envelope(response)
        if code in (401, 403):
            return _auth(code)
        if code == 429:
            return SignResult(SignStatus.PROTOCOL_PENDING, '好大 API 限流（HTTP 429），待下轮重试')
        if envelope is None:
            return SignResult(SignStatus.UNCONFIRMED, f'好大 API 核验不可读（HTTP {code}，非 JSON 包裹）')
        if envelope.get("success") is True:
            # profile 不含签到状态：诚实返回未确认，不冒充核验结论。
            return SignResult(SignStatus.UNCONFIRMED, '好大 API Key 有效（只读核验未提交，签到状态未知）')
        return SignResult(SignStatus.AUTH_FAILED,
                          f'好大 API 核验被拒（{_message(envelope)[:60] or "无消息"}）')

    try:
        response = request("POST", site.url + SIGN_PATH, headers=headers, payload={})
    except Exception as exc:
        return SignResult(SignStatus.NETWORK_ERROR, f'好大 API 不可达：{type(exc).__name__}')
    code = getattr(response, 'status_code', None)
    envelope = _envelope(response)
    if code in (401, 403):
        return _auth(code)
    if code == 429:
        return SignResult(SignStatus.PROTOCOL_PENDING, '好大 API 限流（HTTP 429），待下轮重试')
    if envelope is None:
        return SignResult(SignStatus.UNCONFIRMED, f'好大签到响应不可读（HTTP {code}，非 JSON 包裹）')
    if envelope.get("success") is True:
        text = _message(envelope)
        return SignResult(SignStatus.SUCCESS, '签到成功（API）' + (f'（{text[:60]}）' if text else ''))
    text = _message(envelope)
    if any(marker in text for marker in ALREADY_MARKERS):
        return SignResult(SignStatus.ALREADY, '今日已签到（API）')
    return SignResult(SignStatus.UNCONFIRMED,
                      f'好大签到被拒（API）：{text[:80] or "服务端未给出消息"}')

def verify_hdarea_login(site, info, *, config=None, request=None):
    """API Key 探活（登录轨分流）：GET profile 验证账号+Key 通道健康。

    语义说明（实测 2026-11-11）：API 调用不刷新站点「最近动向」，也不续期
    Web Cookie；此处成功仅代表 Key 与账号有效，不冒充 Web 登录保活。
    """
    from ..core.models import LoginResult, LoginStatus
    apikey = _api_key(info, config)
    if not apikey:
        return LoginResult(LoginStatus.UNCONFIRMED, '未配置 hdarea_apikey，登录轨走 Cookie（防御位）')
    request = request or _default_request
    headers = {"X-API-Key": apikey, "Accept": "application/json"}
    try:
        response = request("GET", site.url + PROFILE_PATH, headers=headers, payload=None)
    except Exception as exc:
        return LoginResult(LoginStatus.UNCONFIRMED, f'好大 API 不可达：{type(exc).__name__}')
    code = getattr(response, 'status_code', None)
    envelope = _envelope(response)
    if code in (401, 403):
        return LoginResult(LoginStatus.AUTH_FAILED,
                           f'好大 API Key 无效或缺 read 权限（HTTP {code}）')
    if code == 429:
        return LoginResult(LoginStatus.UNCONFIRMED, '好大 API 限流（HTTP 429），待下轮重试')
    if envelope is None:
        return LoginResult(LoginStatus.UNCONFIRMED,
                           f'好大 API 探活响应不可读（HTTP {code}，非 JSON 包裹）')
    if envelope.get("success") is not True:
        return LoginResult(LoginStatus.AUTH_FAILED,
                           f'好大 API 探活被拒（{_message(envelope)[:60] or "无消息"}）')
    username = str((envelope.get("data") or {}).get("username") or '').strip()
    who = f'：{username}' if username else ''
    return LoginResult(LoginStatus.LOGIN_OK, f'API 探活成功{who}（Key 有效，账号通道健康）')
