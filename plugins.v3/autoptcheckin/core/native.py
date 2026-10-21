"""Native execution boundary: credentials and resources stay outside site declarations."""
from urllib.parse import urljoin
from http.cookies import SimpleCookie
from uuid import uuid4

from .credentials import Credential, CredentialResolver
from .models import LoginPage, SignResult, SignStatus
from .sitemodel import SignContext


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
        return LoginPage(response.text, response.url, response.status_code)

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


def run_native(runner, site, info, *, read_only=False, trigger='manual', context_factory=native_context, get_data=None, save_data=None):
    """Same site-level lock as legacy/login; every outcome gets one history entry."""
    def finish(result):
        result.site_id, result.run_id = site.id, str(uuid4())
        result.metadata.update(action='sign', trigger=trigger)
        if runner.history:
            runner.history(result)
        if runner.notify:
            runner.notify(result)
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
        auth = CredentialResolver().select_cookie({'managed_site': Credential(
            'managed_site', info.get('cookie') or '', str(info.get('uid') or ''))})
        if auth.credential is None:
            return finish(SignResult(SignStatus.AUTH_FAILED, auth.reason))
        session = None
        try:
            ctx = context_factory(site, auth.credential, info, runner.locks, runner.stop)
            if site.id == "yzyy" and isinstance(ctx.http, NativeHttpClient):
                import requests
                session = requests.Session()
                ctx.http.session = session
            ctx.get_data, ctx.save_data = get_data, save_data
            if read_only:
                page = ctx.http.get(urljoin(site.url, site.attendance_path))
                login = site.parse_login(page)
                if login.status == 'auth_failed':
                    result = ctx.result(status='auth_failed', message=login.message)
                else:
                    result = site.read_before(ctx, page)
            else:
                result = site.signin(ctx)
        except Exception:
            result = SignResult(SignStatus.UNCONFIRMED, '原生签到执行未确认')
        finally:
            if session is not None:
                session.close()
        return finish(result)
