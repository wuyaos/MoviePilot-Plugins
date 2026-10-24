"""Native execution boundary: credentials and resources stay outside site declarations."""
from urllib.parse import urljoin, urlsplit
from email.message import Message
from http.cookies import SimpleCookie
from uuid import uuid4

from .cloak import native_cloak_client, CloakHttpClient
from .credentials import Credential, CredentialResolver, cookiecloud_candidate
from .models import LoginPage, LoginResult, LoginStatus, SignResult, SignStatus
from .sitemodel import SignContext, page_available, page_maintenance


def decode_response(response):
    """Ignore requests' implicit latin-1 default when HTTP declares no charset."""
    content = response.content
    header = Message()
    header['content-type'] = response.headers.get('Content-Type', '')
    charset = header.get_content_charset()
    if charset:
        # 部分站点（如 TTG）误标 ISO-8859-1/ascii，页面实际是 UTF-8：latin-1 家族先按严格 UTF-8 试。
        if charset.lower() in ("latin-1", "iso-8859-1", "ascii", "us-ascii"):
            try:
                return content.decode("utf-8-sig")
            except UnicodeDecodeError:
                pass
        try:
            return content.decode(charset, errors='replace')
        except LookupError:
            pass
    try:
        return content.decode('utf-8-sig')
    except UnicodeDecodeError:
        # GBK is considered only after strict UTF-8 fails, never via a guess
        # that can reinterpret valid UTF-8 Chinese as another encoding.
        try:
            text = content.decode('gbk')
            if any('\u4e00' <= char <= '\u9fff' for char in text):
                return text
        except UnicodeDecodeError:
            pass
        return content.decode('utf-8', errors='replace')


class NativeHttpClient:
    def __init__(self, credential, site_info, session=None):
        self.session = session
        self.credential = credential
        self.info = site_info
        parsed = SimpleCookie()
        parsed.load(credential.value)
        self.cookies = {key: morsel.value for key, morsel in parsed.items()}

    def retain_cookies(self, names):
        self.cookies = {key: value for key, value in self.cookies.items() if key in names}

    def _request(self, method, url, **kwargs):
        from app.sdk.config import settings
        from app.sdk.network import RequestUtils
        # 浏览器指纹绑定站（如 FileList）：普通 requests 的 TLS 指纹会被判非法会话，
        # 与 MP 站点连通性测试同口径走 curl_cffi chrome 仿真。
        use_cffi = getattr(self.credential, 'impersonate', None) or self.info.get('impersonate')
        if use_cffi:
            try:
                from curl_cffi import requests as cffi_requests
                m = {'get': cffi_requests.get, 'post': cffi_requests.post}[method]
                resp = m(url, headers={'User-Agent': self.info.get('ua') or 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36',
                                       'Referer': kwargs.pop('referer', self.info.get('url') or '')},
                         cookies=self.cookies, timeout=20, impersonate='chrome',
                         allow_redirects=True, proxies=({'https': settings.PROXY, 'http': settings.PROXY} if self.info.get('proxy') and settings.PROXY else None))
                self.cookies.update(resp.cookies.get_dict())
                return LoginPage(decode_response(resp), str(resp.url), resp.status_code)
            except Exception:
                pass  # cffi 失败退回普通通道
        session_args = {"session": self.session} if self.session is not None else {}
        request = RequestUtils(**session_args, cookies=self.cookies, ua=self.info.get('ua'),
                               referer=kwargs.pop('referer', self.info.get('url')), timeout=20,
                               headers=kwargs.pop('headers', None),
                               content_type='application/json; charset=UTF-8' if 'json' in kwargs else 'application/x-www-form-urlencoded; charset=UTF-8',
                               proxies=settings.PROXY if self.info.get('proxy') else None)
        response = getattr(request, method + '_res')(url=url, **kwargs)
        if response is None:
            return None
        self.cookies.update(response.cookies.get_dict())
        if self.session is not None:
            self.cookies.update(self.session.cookies.get_dict())
        return LoginPage(decode_response(response), response.url, response.status_code)

    def get(self, url, *, referer=None, headers=None):
        kwargs = {'referer': referer} if referer is not None else {}
        if headers is not None:
            kwargs['headers'] = headers
        return self._request('get', url, **kwargs)

    def get_bytes(self, url):
        from app.sdk.config import settings
        from app.sdk.network import RequestUtils
        response = RequestUtils(cookies=self.cookies, ua=self.info.get('ua'), timeout=20,
                                proxies=settings.PROXY if self.info.get('proxy') else None).get_res(url=url)
        if response is None or response.status_code != 200:
            raise ValueError('image unavailable')
        return response.content

    def post(self, url, *, data=None, json=None, headers=None, referer=None):
        kwargs = {'referer': referer} if referer is not None else {}
        if headers is not None:
            kwargs['headers'] = headers
        if json is not None:
            kwargs['json'] = json
        else:
            kwargs['data'] = data
        return self._request('post', url, **kwargs)


def native_context(site, credential, info, lock, cancel):
    http = NativeHttpClient(credential, info)
    def ocr(**kwargs):
        # Reuse the existing engines, but never an adapter's submission/retry loop.
        from ..helper.ocr_helper import recognize_captcha
        cookie = "; ".join(f"{key}={value}" for key, value in http.cookies.items())
        return recognize_captcha(cookie=cookie, ua=info.get('ua'),
                                 proxy=info.get('proxy', False), timeout=20, **kwargs)
    def public_get(url, *, referer=None):
        from app.sdk.network import RequestUtils
        return RequestUtils(timeout=20, referer=referer).get_res(url=url)
    return SignContext(site.id, credential, http,
                       page=None, ocr=ocr, site_lock=lock, cancel=cancel, public_get=public_get)


def run_native(runner, site, info, *, read_only=False, trigger='manual', context_factory=native_context, get_data=None, save_data=None, custom_cookie='', config=None):
    """Same site-level lock as legacy/login; every outcome gets one history entry."""
    try:
        from app.runtime.log import logger
    except Exception:
        from types import SimpleNamespace
        logger = SimpleNamespace(info=lambda *a, **k: None)

    def finish(result):
        result.site_id, result.run_id = site.id, str(uuid4())
        result.metadata.update(action='sign', trigger=trigger, read_only=read_only)
        if runner.history:
            runner.history(result)
        if runner.notify:
            runner.notify(result)
        logger.info(f'【PT 签到中心】{getattr(site, 'name', site.id)}（{site.id}）{read_only and "只读核验" or "签到"}结果：{getattr(result.status, 'value', result.status)} | {result.message}')
        return result

    if getattr(site, 'signin_capable', True) is False:
        result = SignResult.skipped('signin_not_applicable')
        result.metadata['reason'] = 'signin_not_applicable'
        return finish(result)

    with runner.locks.acquire((site.id, '')) as acquired:
        if not acquired:
            return finish(SignResult.skipped())
        if runner.stop.is_set():
            return finish(SignResult(SignStatus.CANCELLED, '已停止，未访问'))
        cloud = cookiecloud_candidate(info.get('url') or site.url)
        candidates = {'managed_site': Credential(
            'managed_site', info.get('cookie') or '', ''),
            'local_cookie': Credential('local_cookie', custom_cookie, '')}
        if cloud.credential is not None:
            candidates['cookiecloud'] = cloud.credential
        auth = CredentialResolver().select_cookie(candidates)
        if auth.credential is None:
            return finish(SignResult(SignStatus.AUTH_FAILED, auth.reason))
        session = None
        try:
            ctx = context_factory(site, auth.credential, info, runner.locks, runner.stop)
            if site.id == "yzyy" and isinstance(ctx.http, NativeHttpClient):
                import requests
                session = requests.Session()
                ctx.http.session = session
            ctx.http = native_cloak_client(site, ctx.http, info, config or {}, shared=getattr(runner, "shared_cloak", None))
            ctx.get_data, ctx.save_data = get_data, save_data
            if read_only:
                try:
                    page = ctx.http.get(urljoin(site.url, site.attendance_path))
                except Exception:
                    return finish(SignResult(SignStatus.NETWORK_ERROR, '签到页面不可达：请求异常'))
                if page_maintenance(page):
                    return finish(SignResult(SignStatus.MAINTENANCE, "维护中/已关闭"))
                login = site.parse_login(page, site.credential)
                if login.status == 'auth_failed':
                    result = ctx.result(status='auth_failed', message=login.message)
                elif not page_available(page):
                    result = SignResult(SignStatus.NETWORK_ERROR, '签到页面不可达')
                else:
                    result = site.read_before(ctx, page)
            else:
                result = site.signin(ctx)
            if (site.id == 'yzyy' and not read_only
                    and result.status == SignStatus.AUTH_FAILED):
                # Cookie 失效：Discuz 账密登录刷新 Cookie 后重签一次（用户裁决，全 HTTP）。
                from ..integrations import yzyy
                try:
                    refreshed = yzyy.login(ctx.http, {**info, **(config or {})})
                except Exception:
                    refreshed = None
                if refreshed is not None and refreshed.status == LoginStatus.LOGIN_OK:
                    result = site.signin(ctx)
            if isinstance(ctx.http, CloakHttpClient):
                result.metadata['transport'] = 'cloak'
        except Exception:
            result = SignResult(SignStatus.UNCONFIRMED, '原生签到执行未确认')
        finally:
            if "ctx" in locals() and isinstance(getattr(ctx, "http", None), CloakHttpClient):
                ctx.http.close()
            if session is not None:
                session.close()
        return finish(result)


def read_login_twice(fetch_page, site, uid="", credential=None):
    """A failed first visit never suppresses reread; explicit identities cannot switch."""
    def read(expected):
        try:
            page = fetch_page()
        except Exception:
            return LoginResult(LoginStatus.UNCONFIRMED, '登录页面不可达')
        code = getattr(page, 'status_code', 200) or 0
        if code >= 400 or code == 0:
            # 2026-10-24 口径：403/404/5xx/无响应 = 站点不可达，不得判 login_ok。
            return LoginResult(LoginStatus.UNCONFIRMED, f'登录页面不可达：HTTP {code}' if code else '登录页面不可达：网络超时/无响应')
        try:
            result = site.parse_login(page, credential) if credential is not None else site.parse_login(page)
        except Exception:
            return LoginResult(LoginStatus.UNCONFIRMED, '登录回读页面不可达')
        if expected and result.evidence and result.evidence.uid and result.evidence.uid != expected:
            return LoginResult(LoginStatus.UNCONFIRMED, '页面账号冲突，已停止判定', evidence=result.evidence)
        return result
    # Always perform the second page read.  The first response may be a timeout,
    # stale page, or an intermediate authentication result; only the reread is
    # the final login evidence.
    first = read(uid)
    result = read(uid)
    first_uid = first.evidence.uid if first.evidence else ''
    second_uid = result.evidence.uid if result.evidence else ''
    if first_uid and second_uid and first_uid != second_uid:
        result = LoginResult(LoginStatus.UNCONFIRMED, '页面账号冲突，已停止判定', evidence=result.evidence)
    result.account = uid or (result.evidence.uid if result.evidence else '') or ''
    return result


def run_native_login(runner, site, info, *, custom_cookie='', trigger='manual', credential_check=None, config=None):
    try:
        from app.runtime.log import logger
    except Exception:
        from types import SimpleNamespace
        logger = SimpleNamespace(info=lambda *a, **k: None)

    def finish(result):
        result.site_id, result.run_id = site.id, str(uuid4())
        result.metadata.update(action='login', trigger=trigger)
        if runner.history:
            runner.history(result)
        logger.info(f'【PT 签到中心】{getattr(site, 'name', site.id)}（{site.id}）模拟登录结果：{getattr(result.status, 'value', result.status)} | {result.message}')
        return result

    with runner.locks.acquire((site.id, '')) as acquired:
        if not acquired:
            return finish(SignResult.skipped())
        if runner.stop.is_set():
            return finish(SignResult(SignStatus.CANCELLED, '已停止，未访问'))
        uid = str(info.get('uid') or '')
        if site.id == "mteam":
            try:
                result = site.keepalive_login({**(config or {}), **info})
            except Exception:
                result = LoginResult(LoginStatus.UNCONFIRMED, "M-Team 保活登录未确认")
            result.metadata["transport"] = "cloak"
            return finish(result)
        if site.credential.kind in ('api_key', 'password'):
            from ..integrations.login import CredentialLoginProtocol
            return finish(CredentialLoginProtocol(credential_check).login(info, uid))
        if getattr(site, 'browser_login', False):
            # 会话绑定浏览器指纹的站点（如 FileList）：HTTP 重放 Cookie 必失败，
            # 用 CloakBrowser 真实浏览器带站点管理 Cookie 访问首页，以 logout 标记判定登录态。
            from .cloak import CloakSession
            from urllib.parse import urlsplit as _usp
            url = info.get('url') or site.url
            host = (_usp(url).hostname or '').lstrip('.')
            raw = info.get('cookie') or custom_cookie or ''
            pairs = []
            for part in raw.split(';'):
                k, sep, v = part.strip().partition('=')
                if sep:
                    pairs.append({'name': k, 'value': v, 'domain': host, 'path': '/'})
            try:
                with CloakSession(url=url, cookies=pairs) as browser:
                    browser.goto(url)
                    body = browser.page.locator('body').inner_text()
                    if 'logout' in body.lower() or 'log out' in body.lower():
                        return finish(LoginResult(LoginStatus.LOGIN_OK, '浏览器核验：已登录'))
                    return finish(LoginResult(LoginStatus.AUTH_FAILED, 'Cookie 已失效（浏览器核验跳转登录页）'))
            except Exception as exc:
                return finish(LoginResult(LoginStatus.UNCONFIRMED, f'浏览器登录核验异常：{type(exc).__name__}'))
        if site.id == 'yzyy':
            from ..integrations import yzyy
            try:
                url = info.get('url') or site.url
                cloud = cookiecloud_candidate(url)
                candidates = {'managed_site': Credential('managed_site', info.get('cookie') or ''),
                              'local_cookie': Credential('local_cookie', custom_cookie)}
                if cloud.credential is not None:
                    candidates['cookiecloud'] = cloud.credential
                auth = CredentialResolver().select_cookie(candidates)
                client = NativeHttpClient(auth.credential or Credential('managed_site', ''), info)
                return finish(yzyy.login(client, {**info, **(config or {})}))
            except Exception:
                return finish(LoginResult(LoginStatus.UNCONFIRMED, 'yzyy 登录执行未确认'))
        try:
            url = info.get('url') or site.url
            if urlsplit(url).scheme not in {'http', 'https'} or not urlsplit(url).hostname:
                return finish(LoginResult(LoginStatus.UNCONFIRMED, '登录站点地址未登记'))
            cloud = cookiecloud_candidate(url)
            candidates = {'managed_site': Credential('managed_site', info.get('cookie') or ''),
                          'local_cookie': Credential('local_cookie', custom_cookie)}
            if cloud.credential is not None:
                candidates['cookiecloud'] = cloud.credential
            auth = CredentialResolver().select_cookie(candidates)
            if auth.credential is None:
                return finish(LoginResult(LoginStatus.AUTH_FAILED, auth.reason))
            client = NativeHttpClient(auth.credential, info)
            result = read_login_twice(lambda: client.get(urljoin(url, '/')), site, uid, site.credential)
        except Exception:
            result = LoginResult(LoginStatus.UNCONFIRMED, '原生登录执行未确认')
        return finish(result)


def run_integration(runner, site_id, name, info, config, action='sign', trigger='manual'):
    """Run an API integration with the normal site lock and history boundary."""
    from .credentials import Credential
    from ..integrations import rousi, sunnypt
    integration = {'rousi': rousi, 'sunnypt': sunnypt}[site_id]
    try:
        from app.runtime.log import logger
    except Exception:
        from types import SimpleNamespace
        logger = SimpleNamespace(info=lambda *a, **k: None)
    def finish(result):
        result.site_id, result.run_id = site_id, str(uuid4())
        result.metadata.update(action=action, trigger=trigger)
        if runner.history:
            runner.history(result)
        if runner.notify and action == 'sign':
            runner.notify(result)
        logger.info(f'【PT 签到中心】{name}（{site_id}）{action}结果：{getattr(result.status, "value", result.status)} | {result.message}')
        return result
    with runner.locks.acquire((site_id, '')) as acquired:
        if not acquired:
            return finish(SignResult.skipped())
        if runner.stop.is_set():
            return finish(SignResult(SignStatus.CANCELLED, '已停止，未访问'))
        credential = Credential('managed_site', info.get('cookie') or '')
        http = NativeHttpClient(credential, info)
        credentials = {**info, **config}
        try:
            result = integration.login(http, credentials) if action == 'login' else integration.signin(http, credentials)
        except Exception:
            status = LoginStatus.UNCONFIRMED if action == 'login' else SignStatus.UNCONFIRMED
            result = LoginResult(status, '站点接口执行未确认') if action == 'login' else SignResult(status, '站点接口执行未确认')
        return finish(result)
