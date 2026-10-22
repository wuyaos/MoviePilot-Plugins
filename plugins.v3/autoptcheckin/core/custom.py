"""Custom Nexus attendance, with an optional Browserless-read/HTTP-submit transport."""
from contextlib import contextmanager
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

from lxml import html

from .credentials import Credential
from .models import LoginPage, LoginResult, LoginStatus, SignResult, SignStatus
from .native import NativeHttpClient, read_login_twice
from .nexus import NexusSignin
from .sitemodel import RecordSpec, SignContext, login_redirect, page_available


class CustomNexusSignin(NexusSignin):
    record_spec = RecordSpec(NexusSignin.DEFAULT_MESSAGE_XPATHS, NexusSignin.DEFAULT_STATUS_MAP)

    def __init__(self, site_id, info):
        self.id, self.name, self.url = site_id, info.get('name', ''), info['url']

    def parse_login(self, page):
        result = super().parse_login(page)
        if result.status == LoginStatus.LOGIN_OK:
            try:
                if html.fromstring(page.text).xpath('//input[translate(@type,"PASSWORD","password")="password"]'):
                    return LoginResult(LoginStatus.AUTH_FAILED, '页面包含登录表单')
            except (ValueError, html.etree.ParserError):
                pass
        return result

    def solve_captcha(self, ctx, page, form):
        # Custom protocols/captchas need a dedicated adapter; never guess answers.
        tree = html.fromstring(page.text)
        return not tree.xpath('//input[@name="imagehash" or @name="imagestring" or @name="captcha"]')


class BrowserlessReadHttpSubmit:
    """One isolated browser context; the POST response is never attendance evidence."""
    def __init__(self, http, context, page, url):
        self.http, self.context, self.page, self.url = http, context, page, url

    def get(self, url):
        self.context.add_cookies([{'name': key, 'value': value, 'url': self.url}
                                  for key, value in self.http.cookies.items()])
        response = self.page.goto(url, wait_until='domcontentloaded', timeout=20000)
        self.http.cookies.update({cookie['name']: cookie['value']
                                  for cookie in self.context.cookies(self.url)})
        return LoginPage(self.page.content(), self.page.url, response.status if response else 0)

    def post(self, url, **kwargs):
        return self.http.post(url, **kwargs)


@contextmanager
def custom_client(credential, info, config):
    http = NativeHttpClient(credential, info)
    if not info.get('emulate'):
        yield http
        return
    from playwright.sync_api import sync_playwright
    endpoint = urlsplit(config['browserless_url'])
    query = dict(parse_qsl(endpoint.query))
    if config.get('browserless_token'):
        query['token'] = config['browserless_token']
    endpoint = urlunsplit(endpoint._replace(query=urlencode(query)))
    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(endpoint, timeout=20000)
        try:
            context = browser.new_context(**({'user_agent': info['ua']} if info.get('ua') else {}))
            try:
                yield BrowserlessReadHttpSubmit(http, context, context.new_page(), info['url'])
            finally:
                context.close()
        finally:
            browser.close()


def run_custom(runner, site_id, info, *, enabled, selected=False, config=None,
               read_only=False, trigger='manual', action='sign'):
    config = config or {}

    def finish(result):
        try:
            from app.runtime.log import logger
        except Exception:
            from types import SimpleNamespace
            logger = SimpleNamespace(info=lambda *a, **k: None)
        result.site_id, result.run_id = site_id, str(uuid4())
        result.metadata.update(action='login' if read_only else action, trigger=trigger, read_only=read_only)
        if info.get('emulate'):
            result.metadata['transport'] = 'browserless_read_http_submit'
        if result.status == SignStatus.SKIPPED:
            result.metadata['reason'] = result.message
        if runner.history:
            runner.history(result)
        return result

    if not enabled:
        return finish(SignResult.skipped('site_disabled'))
    if not read_only and not selected:
        return finish(SignResult.skipped('login_not_selected' if action == 'login' else 'sign_not_selected'))
    if info.get('emulate'):
        if not config.get('browserless_enabled'):
            return finish(SignResult.skipped('browserless_disabled'))
        if not config.get('browserless_url'):
            return finish(SignResult.skipped('browserless_not_configured'))
    with runner.locks.acquire((site_id, '')) as acquired:
        if not acquired:
            return finish(SignResult.skipped())
        if runner.stop.is_set():
            return finish(SignResult(SignStatus.CANCELLED, '已停止，未访问'))
        cookie = info.get('cookie') or ''
        if not cookie.strip():
            return finish(SignResult(SignStatus.AUTH_FAILED, '缺少 Cookie'))
        try:
            url = info.get('url') or ''
            if urlsplit(url).scheme not in {'http', 'https'} or not urlsplit(url).netloc:
                return finish(SignResult(SignStatus.UNCONFIRMED, '自定义站点地址无效'))
            credential = Credential('local_cookie', cookie)
            with custom_client(credential, info, config) as client:
                if not read_only and action == 'sign':
                    ctx = SignContext(site_id, credential, client, site_lock=runner.locks, cancel=runner.stop)
                    result = CustomNexusSignin(site_id, info).signin(ctx)
                elif action == 'login':
                    result = read_login_twice(lambda: client.get(url), CustomNexusSignin(site_id, info), str(info.get('uid') or ''))
                else:
                    page = client.get(url)
                    if page is not None and login_redirect(page):
                        result = LoginResult(LoginStatus.AUTH_FAILED, '页面转向登录或认证失败')
                    elif not page_available(page):
                        result = LoginResult(LoginStatus.UNCONFIRMED, '站点页面不可达')
                    elif html.fromstring(page.text).xpath('//input[translate(@type,"PASSWORD","password")="password"]'):
                        result = LoginResult(LoginStatus.AUTH_FAILED, '页面包含登录表单')
                    else:
                        result = LoginResult(LoginStatus.LOGIN_OK, '已登录')
        except Exception:
            result = SignResult(SignStatus.UNCONFIRMED, '自定义站点执行未确认')
        return finish(result)
