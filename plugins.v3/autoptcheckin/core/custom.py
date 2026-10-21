"""Custom verification is a login probe, not evidence of attendance."""
from urllib.parse import urlsplit
from uuid import uuid4

from lxml import html

from .credentials import Credential
from .models import LoginResult, LoginStatus, SignResult, SignStatus
from .native import NativeHttpClient
from .sitemodel import login_redirect, page_available


def run_custom(runner, site_id, info, *, enabled, read_only=False, trigger='manual', action='sign'):
    def finish(result):
        result.site_id, result.run_id = site_id, str(uuid4())
        result.metadata.update(action='login' if read_only else action, trigger=trigger)
        if result.status == SignStatus.SKIPPED:
            result.metadata['reason'] = result.message
        if runner.history:
            runner.history(result)
        return result

    if not enabled:
        return finish(SignResult.skipped('site_disabled'))
    if not read_only:
        return finish(SignResult.skipped('custom_signin_pending' if action == 'sign' else 'custom_login_pending'))
    with runner.locks.acquire((site_id, '')) as acquired:
        if not acquired:
            return finish(SignResult.skipped())
        if runner.stop.is_set():
            return finish(SignResult(SignStatus.CANCELLED, '已停止，未访问'))
        cookie = info.get('cookie') or ''
        if not cookie.strip():
            return finish(LoginResult(LoginStatus.AUTH_FAILED, '缺少 Cookie'))
        try:
            url = info.get('url') or ''
            if urlsplit(url).scheme not in {'http', 'https'} or not urlsplit(url).netloc:
                return finish(LoginResult(LoginStatus.UNCONFIRMED, '自定义站点地址无效'))
            page = NativeHttpClient(Credential('local_cookie', cookie), info).get(url)
            if page is not None and login_redirect(page):
                result = LoginResult(LoginStatus.AUTH_FAILED, '页面转向登录或认证失败')
            elif not page_available(page):
                result = LoginResult(LoginStatus.UNCONFIRMED, '站点页面不可达')
            elif html.fromstring(page.text).xpath('//input[translate(@type,"PASSWORD","password")="password"]'):
                result = LoginResult(LoginStatus.AUTH_FAILED, '页面包含登录表单')
            else:
                result = LoginResult(LoginStatus.LOGIN_OK, '站点页面可达，未检测到登录页（未核验签到）')
        except Exception:
            result = LoginResult(LoginStatus.UNCONFIRMED, '自定义站点核验未确认')
        return finish(result)
