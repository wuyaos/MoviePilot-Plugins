"""猪猪 HTTP 会话边界：SRP 登录、JWT/Cookie 存档、临时 HMAC sign。

不读取旧浏览器存档，不在网络异常时重登，不重放任何签到 POST。
调用方持有 runner 站点锁；此处锁同时保护直接调用的恢复/刷新/原子保存。
"""
import hashlib
import hmac
import json
import os
import re
import secrets
import tempfile
import time
from http.cookiejar import Cookie
from pathlib import Path
from threading import RLock

from ..core.models import Evidence, LoginResult, LoginStatus, SignResult, SignStatus
from ..core.siteconf import cloak_proxy, resolve
from ..sites.native.piggo import calendar_today
from .piggo_srp import proof

ORIGIN = 'https://piggo.me'
BASE = '/v1/web'
_LOCK = RLock()
_SIGN = re.compile(r'[0-9a-fA-F]{64}\Z')
_ALLOWED = {('GET', '/auth/guest-config'), ('POST', '/auth/srp/challenge'),
            ('POST', '/auth/srp/login'), ('GET', '/auth/sign'),
            ('GET', '/calendar'), ('POST', '/calendar/attendance'),
            ('POST', '/me/lab-unlock/srp/challenge'), ('POST', '/me/lab-unlock/srp')}


class PiggoError(Exception):
    def __init__(self, message, *, auth=False, signature=False, locked=False):
        super().__init__(message)
        self.auth, self.signature, self.locked = auth, signature, locked


def state_path():
    from app.sdk.config import settings
    return Path(settings.PLUGIN_DATA_PATH) / 'AutoPtCheckin' / 'http_state' / 'piggo.json'


def new_session(proxy):
    from curl_cffi import requests
    # 显式关闭环境代理继承，避免站点关闭代理后仍被环境变量偷偷开启。
    return requests.Session(impersonate='chrome', trust_env=False, proxy=proxy)


def signed_headers(sign, method, path, timestamp, nonce):
    canonical = path.split('?', 1)[0].strip('/').lower()
    payload = '\n'.join((method.upper(), canonical, timestamp, nonce))
    signature = hmac.new(sign.encode('ascii'), payload.encode(), hashlib.sha256).hexdigest()
    return {'X-Spa-Nonce': nonce, 'X-Spa-Hmac': signature}


def load_state(path, account):
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError, UnicodeError):
        return None
    if (not isinstance(data, dict) or data.get('version') != 1 or data.get('account') != account
            or not isinstance(data.get('token'), str) or not data['token']
            or not isinstance(data.get('cookies'), list)):
        return None
    return data


def save_state(path, account, client):
    """一次提交完整快照；临时文件和目标均 0600，不输出凭据。"""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    cookies = [{'name': c.name, 'value': c.value, 'domain': c.domain, 'path': c.path,
                'secure': c.secure, 'expires': c.expires, 'rest': dict(c._rest)}
               for c in client.session.cookies.jar]
    data = {'version': 1, 'account': account, 'token': client.token,
            'visitor': client.visitor, 'cookies': cookies, 'updated': int(time.time())}
    fd, temporary = tempfile.mkstemp(prefix='.piggo-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False)
            file.flush()
            os.fsync(file.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class PiggoClient:
    def __init__(self, session, cancel=None, diagnostics=None):
        self.session, self.cancel = session, cancel
        self.token, self.sign = "", ""
        self.visitor = secrets.token_hex(16)
        self.diagnostics = diagnostics if diagnostics is not None else []

    def check_cancel(self):
        if self.cancel is not None and self.cancel.is_set():
            raise PiggoError('已停止，未继续请求')

    def restore(self, state):
        self.token = state['token']
        self.visitor = str(state.get('visitor') or self.visitor)
        for c in state['cookies']:
            # 会话只绑定固定站点；不会向配置 URL 或重定向目标发送认证数据。
            if c['domain'].lstrip('.') not in ('piggo.me',):
                continue
            self.session.cookies.jar.set_cookie(Cookie(
                version=0, name=c['name'], value=c['value'], port=None, port_specified=False,
                domain=c['domain'], domain_specified=bool(c['domain']),
                domain_initial_dot=c['domain'].startswith('.'), path=c['path'], path_specified=True,
                secure=c['secure'], expires=c['expires'], discard=c['expires'] is None,
                comment=None, comment_url=None, rest=c.get('rest', {}), rfc2109=False))

    def request(self, method, path, *, payload=None, signed=False):
        self.check_cancel()
        if (method, path) not in _ALLOWED:
            raise PiggoError('拒绝未登记的猪猪请求')
        event = {'phase': {'/auth/guest-config': 'guest_config', '/auth/srp/challenge': 'srp_challenge',
                           '/auth/srp/login': 'srp_login', '/auth/sign': 'sign_key',
                           '/calendar': 'calendar_read', '/calendar/attendance': 'attendance_submit',
                           '/me/lab-unlock/srp/challenge': 'unlock_challenge',
                           '/me/lab-unlock/srp': 'unlock_proof'}[path],
                 'method': method, 'path': BASE + path}
        self.diagnostics.append(event)
        def reject(message, category, *, auth=False, signature=False, locked=False):
            event['category'] = category
            raise PiggoError(message, auth=auth, signature=signature, locked=locked)
        timestamp = str(int(time.time()))
        headers = {'Accept': 'application/json', 'Origin': ORIGIN, 'Referer': ORIGIN + '/calendar',
                   'X-Requested-With': 'XMLHttpRequest', 'visitorId': self.visitor,
                   'ts': timestamp, 'version': '1.0.0', 'webversion': '1'}
        if self.token:
            headers['Authorization'] = 'Bearer ' + self.token
        if signed:
            if not _SIGN.fullmatch(self.sign):
                reject('猪猪请求签名不可用', 'signature')
            headers.update(signed_headers(self.sign, method, BASE + path, timestamp, secrets.token_hex(16)))
        try:
            response = self.session.request(method, ORIGIN + BASE + path, json=payload, headers=headers,
                                            timeout=25, allow_redirects=False)
        except Exception as exc:
            event.update(category='network', exception_type=type(exc).__name__)
            raise PiggoError('猪猪请求异常，未重复登录或提交') from None
        status = response.status_code
        event['http'] = status
        if status >= 500 or status == 429 or 300 <= status < 400:
            reject(f'猪猪接口 HTTP {status}，未重复登录或提交', 'network')
        try:
            body = response.json()
        except (ValueError, TypeError) as exc:
            event['exception_type'] = type(exc).__name__
            if status == 401:
                reject('猪猪认证已失效', 'auth', auth=True)
            reject('猪猪接口不是有效 JSON', 'invalid_json')
        if not isinstance(body, dict):
            if status == 401:
                reject('猪猪认证已失效', 'auth', auth=True)
            reject('猪猪接口结构未确认', 'structure')
        code = body.get('code')
        # 只记录数字或已知锁屏码，不反射任意远端字符串/凭据。
        event['api_code'] = (code if type(code) is int else str(code)
                             if isinstance(code, str) and re.fullmatch(r'-?\d{1,12}|idle_locked', code) else None)
        if status == 401 and code == 'idle_locked':
            reject('猪猪会话已锁定，需要当前密码解锁', 'idle_locked', locked=True)
        if status == 401 or code in (401, '401'):
            reject('猪猪认证已失效', 'auth', auth=True)
        if status != 200 or code != 0:
            message = str(body.get('msg') or body.get('message') or '')
            signature = signed and status == 403 and bool(re.search(r'签名|signature|hmac', message, re.I))
            if re.search(r'验证码|驗證碼|captcha|two.factor|双重|雙重|totp', message, re.I):
                reject('猪猪需要验证码或额外认证，已停止本轮登录', 'challenge')
            reject('猪猪接口拒绝请求，未重复提交',
                   'signature' if signature else 'access_denied' if status in (403, 423) else 'business',
                   signature=signature)
        data = body.get('data')
        if not isinstance(data, dict):
            reject('猪猪接口数据未确认', 'structure')
        event['category'] = 'ok'
        return data

    def get_sign(self):
        sign = self.request('GET', '/auth/sign').get('sign')
        if not isinstance(sign, str) or not _SIGN.fullmatch(sign):
            raise PiggoError('猪猪签名响应未确认')
        self.sign = sign

    def calendar(self):
        if not self.sign:
            self.get_sign()
        try:
            data = self.request('GET', '/calendar', signed=True)
        except PiggoError as exc:
            if not exc.signature:
                raise
            # 只有明确签名错误才刷新 sign，且仅重试安全 GET 一次。
            self.get_sign()
            data = self.request('GET', '/calendar', signed=True)
        state = calendar_today(data)
        if not state:
            raise PiggoError('猪猪今日签到状态回读未确认')
        return state

    def unlock(self, username, password):
        """空闲锁屏不是登录失效：保留现有 JWT/Cookie，单次 SRP 二次验证。"""
        challenge = self.request('POST', '/me/lab-unlock/srp/challenge')
        if not all(isinstance(challenge.get(k), str) and challenge[k] for k in ('s', 'B', 'ticket')):
            raise PiggoError('猪猪解锁 SRP 挑战未确认')
        if len(challenge['B']) > 512 or len(challenge['s']) > 512:
            raise PiggoError('猪猪解锁 SRP 挑战长度异常')
        calculated = proof(str(challenge.get('i') or username), password, challenge['s'], challenge['B'])
        verified = self.request('POST', '/me/lab-unlock/srp', payload={
            'ticket': challenge['ticket'], 'a': calculated['a'], 'm1': calculated['m1']})
        if not hmac.compare_digest(str(verified.get('m2') or '').lower(), calculated['m2']):
            self.diagnostics[-1]['category'] = 'proof_mismatch'
            raise PiggoError('猪猪服务端解锁证据校验失败，未保存凭据')

    def login(self, username, password):
        self.token = self.sign = ''
        self.session.cookies.clear()
        self.request('GET', '/auth/guest-config')
        challenge = self.request('POST', '/auth/srp/challenge', payload={'username': username})
        if not all(isinstance(challenge.get(k), str) and challenge[k] for k in ('s', 'B', 'ticket')):
            raise PiggoError('猪猪 SRP 挑战未确认')
        if len(challenge['B']) > 512 or len(challenge['s']) > 512:
            raise PiggoError('猪猪 SRP 挑战长度异常')
        calculated = proof(str(challenge.get('i') or username), password, challenge['s'], challenge['B'])
        auth = self.request('POST', '/auth/srp/login', payload={
            'ticket': challenge['ticket'], 'a': calculated['a'], 'm1': calculated['m1']})
        if not hmac.compare_digest(str(auth.get('m2') or '').lower(), calculated['m2']):
            raise PiggoError('猪猪服务端登录证据校验失败，未保存凭据')
        if not isinstance(auth.get('token'), str) or not auth['token']:
            raise PiggoError('猪猪登录凭证缺失')
        self.token = auth['token']
        sign = auth.get('sign')
        if isinstance(sign, str) and _SIGN.fullmatch(sign):
            self.sign = sign
        return self.calendar()


def run_piggo(site, info, *, action, config=None, cancel=None, read_only=False, authenticated=None):
    config = config or {}
    diagnostics = []
    submit_error = None
    def pending(message):
        return (LoginResult(LoginStatus.UNCONFIRMED, message) if action == 'login'
                else SignResult(SignStatus.UNCONFIRMED, message))
    def cancelled():
        return cancel is not None and cancel.is_set()
    def execute():
        nonlocal submit_error
        username = str(config.get('piggo_username') or info.get('piggo_username') or '').strip()
        password = str(config.get('piggo_password') or info.get('piggo_password') or '')
        if cancelled():
            return SignResult(SignStatus.CANCELLED, '已停止，未访问')
        if not username or not password:
            return pending('缺少猪猪账号或密码，未提交登录')
        account = hashlib.sha256((username + '\0' + password).encode()).hexdigest()
        path = state_path()
        state = load_state(path, account)
        if read_only and state is None:
            return pending('猪猪无匹配的 HTTP 登录态，请先执行登录；只读核验不提交账号密码')
        flags = resolve(site.id, config, mp_proxy=bool(info.get('proxy')))
        with new_session(cloak_proxy(flags['proxy'], config)) as session:
            client = PiggoClient(session, cancel, diagnostics=diagnostics)
            restored = state is not None
            unlocked = False
            # 仅首次读状态允许恢复登录/解锁；提交后的回读不经过这里。
            try:
                if restored:
                    client.restore(state)
                    try:
                        before = client.calendar()
                    except PiggoError as exc:
                        if not exc.auth or read_only:
                            raise
                        before = client.login(username, password)
                        restored = False
                else:
                    before = client.login(username, password)
            except PiggoError as exc:
                if not exc.locked or read_only or not client.token:
                    raise
                client.unlock(username, password)
                unlocked = True
                # 解锁完成仍须新 GET 确认；再次锁定不循环解锁/重登。
                before = client.calendar()
            if not read_only:
                save_state(path, account, client)
                if authenticated is not None:
                    authenticated(LoginResult(LoginStatus.LOGIN_OK, '猪猪会话已确认'),
                                  {c.name: c.value for c in session.cookies.jar})
            if action == 'login':
                message = ('猪猪会话已解锁' if unlocked else
                           '已恢复猪猪登录态' if restored else '猪猪账号密码登录成功')
                return LoginResult(LoginStatus.LOGIN_OK, message)
            if before['status'] == 'checked':
                return SignResult(SignStatus.ALREADY, '今日已签到', evidence=Evidence(
                    date=before['date'], status='checked', source='calendar'))
            if read_only:
                return pending('今日尚未签到（只读核验，未提交）')
            # 写请求永远不自动重放；即使连接在服务端受理后中断也必须新 GET 判定。
            try:
                client.request('POST', '/calendar/attendance', payload={'ymd': before['date']}, signed=True)
            except Exception as exc:
                submit_error = type(exc).__name__
            if cancelled():
                return SignResult(SignStatus.CANCELLED, '已停止，签到结果待下轮回读')
            after = client.calendar()
            save_state(path, account, client)
            if after['date'] == before['date'] and after['status'] == 'checked':
                return SignResult(SignStatus.SUCCESS, '签到成功', evidence=Evidence(
                    date=after['date'], status='checked', source='calendar'))
            return pending('猪猪已提交签到，但新请求未确认今日已签到')
    try:
        with _LOCK:
            result = execute()
    except Exception as exc:
        if cancelled():
            result = SignResult(SignStatus.CANCELLED, '已停止，未继续请求')
        else:
            # 第三方异常可能包含密码/Token/签名，不拼接异常文本。
            result = pending(str(exc) if isinstance(exc, PiggoError) else '猪猪 HTTP 执行未确认：' + type(exc).__name__)
    if diagnostics:
        result.metadata["piggo"] = diagnostics
        if result.status in (LoginStatus.UNCONFIRMED, SignStatus.UNCONFIRMED):
            last = diagnostics[-1]
            result.message += (f"（{last['phase']} {last['path']}"
                               f"；HTTP {last.get('http', '-')}；code {last.get('api_code', '-')}）")
    if submit_error:
        result.metadata["submit_error"] = submit_error
    result.metadata['transport'] = 'http'
    return result
