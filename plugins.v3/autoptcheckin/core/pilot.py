"""试点桥：固定站点地址，不接受用户提供的请求 URL。"""
from importlib import import_module
from urllib.parse import urlsplit
from .credentials import Credential, CredentialResolver
from ..verifiers.hdsky import HDSkyVerifier
from ..verifiers.haitang import HaitangVerifier

PILOTS = {
    'hdsky': {'domain': 'hdsky.me', 'url': 'https://hdsky.me/index.php', 'class': 'HDSky', 'verifier': HDSkyVerifier},
    'haitang': {'domain': 'www.htpt.cc', 'url': 'https://www.htpt.cc/attendance.php', 'class': 'Haitang', 'verifier': HaitangVerifier},
}


def hostname(value):
    return (urlsplit(value if '://' in value else 'https://' + value).hostname or '').lower().removeprefix('www.')


def site_id_for_domain(value):
    for site_id, spec in PILOTS.items():
        if value == site_id or hostname(value) == hostname(spec['domain']):
            return site_id
    from .registry import get_registry, get_native_module
    for item in get_registry()['sites']:
        if item.get('native'):
            native_url = get_native_module(item['id']).url
            if value == item['id'] or (native_url and hostname(value) == hostname(native_url)):
                return item['id']
    return None


def managed_site(site_id):
    from app.db.oper import SiteOper
    from .registry import get_native_module
    domain = PILOTS[site_id]['domain'] if site_id in PILOTS else get_native_module(site_id).url
    for site in SiteOper().list_order_by_pri():
        if hostname(site.url) == hostname(domain):
            return {key: getattr(site, key, None) for key in ('name', 'url', 'cookie', 'ua', 'proxy')}
    return {}


class PilotBridge:
    def __init__(self, site_id, site_info):
        self.site_id, self.info = site_id, dict(site_info)
        self.spec = PILOTS[site_id]
        self.verifier = self.spec['verifier']()
        self.adapter = None

    def resolve(self):
        # 不实例化旧适配器就能拒绝空凭证；本地验收不会触发任何站点 IO。
        cookie = self.info.get('cookie') or ''
        return CredentialResolver().select_cookie({
            'managed_site': Credential('managed_site', cookie, str(self.info.get('uid') or ''))})

    def _adapter(self):
        if self.adapter is None:
            module = import_module('..sites.' + self.site_id, __package__)
            self.adapter = getattr(module, self.spec['class'])()
        return self.adapter

    def fetch_page(self):
        return self._adapter().get_page_source(url=self.spec['url'], cookie=self.info['cookie'],
            ua=self.info.get('ua'), proxy=self.info.get('proxy', False), render=False, timeout=20)

    def fetch_login_page(self):
        from app.sdk.config import settings
        from app.sdk.network import RequestUtils
        from .models import LoginPage
        response = RequestUtils(cookies=self.info['cookie'], ua=self.info.get('ua'),
            proxies=settings.PROXY if self.info.get('proxy') else None,
            timeout=20).get_res(url=self.spec['url'])
        if response is None:
            return None
        return LoginPage(response.text, response.url, response.status_code)

    def submit(self):
        adapter = self._adapter()
        info = {**self.info, 'url': self.spec['url'], 'timeout': 20}
        if self.site_id == 'haitang':
            # 只提交一次；外层 finally 负责所有响应（包括异常）的无条件回读。
            from app.sdk.config import settings
            request = adapter._build_request(info['cookie'], info.get('ua'),
                settings.PROXY if info.get('proxy') else None, 20)
            response = request.post_res(url=adapter._signin_url, data=dict(adapter._post_data))
            return response is not None and response.status_code == 200, ''
        outcome = adapter._try_engine('ddddocr', info.get('name', 'HDSky'), info['cookie'],
            info.get('ua'), info.get('proxy', False), info['url'], 20)
        # 未识别出验证码时没有签到提交，才允许换引擎；不重试已经提交的验证码。
        if outcome == 'no_result':
            outcome = adapter._try_engine('ocrhelper', info.get('name', 'HDSky'), info['cookie'],
                info.get('ua'), info.get('proxy', False), info['url'], 20)
        return outcome in ('success', 'already'), ''
