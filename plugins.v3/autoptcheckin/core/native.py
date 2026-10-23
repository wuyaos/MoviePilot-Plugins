"""Native execution boundary: credentials and resources stay outside site declarations."""
from urllib.parse import urljoin, urlsplit
from email.message import Message
from http.cookies import SimpleCookie
from uuid import uuid4

from .browserless import BrowserQLClient, native_browser_client
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

    def get(self, url, *, referer=None):
        kwargs = {'referer': referer} if referer is not None else {}
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
            ctx.http = native_browser_client(site, ctx.http, info, config or {})
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
            if isinstance(ctx.http, BrowserQLClient) and not ctx.http.fallback:
                result.metadata['transport'] = 'browserql'
        except Exception:
            result = SignResult(SignStatus.UNCONFIRMED, '原生签到执行未确认')
        finally:
            if session is not None:
                session.close()
        return finish(result)


def read_login_twice(fetch_page, site, uid="", credential=None):
    """A failed first visit never suppresses reread; explicit identities cannot switch."""
    def read(expected):
        try:
            page = fetch_page()
            result = site.parse_login(page, credential) if credential is not None else site.parse_login(page)
        except Exception:
            return LoginResult(LoginStatus.UNCONFIRMED, '登录回读页面不可达')
        if expected and result.evidence and result.evidence.uid and result.evidence.uid != expected:
            return LoginResult(LoginStatus.UNCONFIRMED, '页面账号冲突，已停止判定', evidence=result.evidence)
        return result
    first = read(uid)
    observed = first.evidence.uid if first.evidence else ''
    result = read(uid or observed or '')
    if uid and observed and uid != observed:
        result = first
    result.account = (uid or (result.evidence.uid if result.confirmed and result.evidence else '') or '')
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
        if site.credential.kind in ('api_key', 'password'):
            from ..integrations.login import CredentialLoginProtocol
            return finish(CredentialLoginProtocol(credential_check).login(info, uid))
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
