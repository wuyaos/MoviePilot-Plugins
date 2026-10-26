"""Custom Nexus attendance with an optional CloakBrowser-read/HTTP-submit transport."""
from contextlib import contextmanager
from urllib.parse import urlsplit
from uuid import uuid4

from lxml import html

from .credentials import Credential
from .models import LoginPage, LoginResult, LoginStatus, SignResult, SignStatus
from .native import NativeHttpClient, cookie_candidates, persist_cookie_result, read_login_twice
from .siteconf import resolve as resolve_site_flags, cloak_proxy
from .nexus import NexusSignin
from .sitemodel import RecordSpec, SignContext, login_redirect, page_available


class CustomNexusSignin(NexusSignin):
    record_spec = RecordSpec(NexusSignin.DEFAULT_MESSAGE_XPATHS, NexusSignin.DEFAULT_STATUS_MAP)

    def __init__(self, site_id, info):
        self.id, self.name, self.url = site_id, info.get('name', ''), info['url']

    def parse_login(self, page, credential=None):
        result = super().parse_login(page, credential)
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


@contextmanager
def custom_client(credential, info, config, proxy=None):
    """custom 条目执行客户端；effective emulate 时走 CloakBrowser 前读/回读 + HTTP 提交。

    仿真与代理按 siteconf 有效配置传入（proxy=None=直连，不做 PROXY_HOST 兜底）。
    """
    http = NativeHttpClient(credential, info)
    if not info.get("emulate"):
        yield http
        return
    from types import SimpleNamespace
    from .cloak import CloakHttpClient
    client = CloakHttpClient(http, info, SimpleNamespace(id=info.get("id", "custom"), url=info["url"]), proxy=proxy)
    class ReadHttpSubmit:
        def get(self, url): return client.get(url)
        def post(self, url, **kwargs): return http.post(url, **kwargs)
        def get_bytes(self, url): return http.get_bytes(url)
        def retain_cookies(self, names): return http.retain_cookies(names)
    try:
        yield ReadHttpSubmit()
    finally:
        client.close()


def run_custom(runner, site_id, info, *, enabled, selected=False, config=None,
               read_only=False, trigger='manual', action='sign'):
    config = config or {}
    # 有效仿真/代理与 /sites、/stats 同源：custom 条目填写 emulate 为默认，site_emulate 可覆盖。
    flags = resolve_site_flags(str(site_id), config, declared_emulate=bool(info.get('emulate')))

    def finish(result):
        try:
            from app.runtime.log import logger
        except Exception:
            from types import SimpleNamespace
            logger = SimpleNamespace(info=lambda *a, **k: None)
        result.site_id, result.run_id = site_id, str(uuid4())
        result.metadata.update(action='login' if read_only else action, trigger=trigger, read_only=read_only)
        if flags['emulate']:
            result.metadata['transport'] = 'cloak'
        if result.status == SignStatus.SKIPPED:
            result.metadata['reason'] = result.message
        if runner.history:
            runner.history(result)
        return result

    if not enabled:
        return finish(SignResult.skipped('site_disabled'))
    if not read_only and not selected:
        return finish(SignResult.skipped('login_not_selected' if action == 'login' else 'signin_not_selected'))
    with runner.locks.acquire((site_id, '')) as acquired:
        if not acquired:
            return finish(SignResult.skipped())
        if runner.stop.is_set():
            return finish(SignResult(SignStatus.CANCELLED, '已停止，未访问'))
        cookie = info.get('cookie') or ''
        credential_source = 'local_cookie'
        if not cookie.strip():
            # 条目 Cookie 为空时走统一候选链：Cookie 表 → CookieCloud（按站点域名取同域 Cookie）。
            for candidate in cookie_candidates(site_id, info, '', getattr(runner, 'get_data', None),
                                               info.get('url') or ''):
                cookie, credential_source = candidate.value, candidate.source
                break
        if not cookie.strip():
            return finish(SignResult(SignStatus.AUTH_FAILED, '缺少 Cookie'))
        try:
            url = info.get('url') or ''
            info["id"] = site_id
            if urlsplit(url).scheme not in {'http', 'https'} or not urlsplit(url).netloc:
                return finish(SignResult(SignStatus.UNCONFIRMED, '自定义站点地址无效'))
            credential = Credential(credential_source, cookie)
            # 仿真对签到与登录一致生效（旧「custom 登录不走仿真」契约由 site_emulate 取代）。
            client_info = {**info, "emulate": flags['emulate'], "proxy": flags['proxy']}
            with custom_client(credential, client_info, config,
                               proxy=cloak_proxy(flags['proxy'], config)) as client:
                if not read_only and action == 'sign':
                    ctx = SignContext(site_id, credential, client, site_lock=runner.locks, cancel=runner.stop)
                    result = CustomNexusSignin(site_id, info).signin(ctx)
                elif action == 'login':
                    result = read_login_twice(lambda: client.get(url), CustomNexusSignin(site_id, info), str(info.get('uid') or ''))
                else:
                    page = client.get(url)
                    if page is not None and login_redirect(page):
                        # custom 条目凭据固定为本条目 Cookie，跳登录页即 Cookie 失效。
                        result = LoginResult(LoginStatus.AUTH_FAILED, 'Cookie 已失效（跳转登录页）')
                    elif not page_available(page):
                        result = LoginResult(LoginStatus.UNCONFIRMED, '站点页面不可达')
                    elif html.fromstring(page.text).xpath('//input[translate(@type,"PASSWORD","password")="password"]'):
                        result = LoginResult(LoginStatus.AUTH_FAILED, '页面包含登录表单')
                    else:
                        result = LoginResult(LoginStatus.LOGIN_OK, '已登录')
                # 成功路径把会话 Cookie 回写统一 Cookie 表（下次优先于 CookieCloud）。
                persist_cookie_result(result, client, site_id, credential.source,
                                      getattr(runner, 'get_data', None), getattr(runner, 'save_data', None))
        except Exception as exc:
            result = SignResult(SignStatus.UNCONFIRMED,
                                f'自定义站点执行未确认：{type(exc).__name__} {str(exc)[:80]}'[:100])
        return finish(result)
