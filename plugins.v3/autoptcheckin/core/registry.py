"""发现适配器元数据；导入期间不实例化适配器、不发送站点请求。"""
from copy import deepcopy
import importlib
import inspect
import json
import logging
import pkgutil
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit
from .sitemodel import SiteModule
from .credentials import CredentialSpec
from ..integrations.rousi import ROUSI_CREDENTIALS
from ..integrations.sunnypt import SUNNYPT_CREDENTIALS
from ..integrations.rousi import BASE as ROUSI_BASE
from ..integrations.sunnypt import API as SUNNYPT_API


_MATCHERS = {}
_NATIVE_MODULES = {}

def hostname(value):
    return (urlsplit(value if '://' in value else 'https://' + str(value or '')).hostname or '').lower().removeprefix('www.')


def managed_site(site_id):
    from app.db.oper import SiteOper
    get_registry()
    match = _MATCHERS.get(site_id)
    for site in SiteOper().list_order_by_pri():
        if (match and match(site.url)) or (not match and hostname(site.url) == hostname(site_id)):
            return {key: getattr(site, key, None) for key in ('name', 'url', 'cookie', 'ua', 'proxy')}
    return {}


def site_id_for_domain(value, *, include_legacy=False):
    _discovery()
    normalized = hostname(value)
    for site_id, module in _NATIVE_MODULES.items():
        if value == site_id or (module.url and hostname(module.url) == normalized):
            return site_id
    if value in ('rousi', 'sunnypt'):
        return value
    for site_id, matcher in _MATCHERS.items():
        if value == site_id:
            return site_id
        try:
            if matcher(value if '://' in str(value) else 'https://' + str(value)):
                return site_id
        except Exception:
            continue
    return None

def credential(spec: CredentialSpec) -> dict:
    return {"kind": spec.kind, "sources": list(spec.cookie_sources), "refresh": spec.refresh}

def shield_of(cls):
    """站点徽标：CF 盾仿真站=cloud，其余仿真站=emulate，非仿真站=None。"""
    if not getattr(cls, 'emulate', False):
        return None
    return 'cloud' if 'human_verify' in tuple(getattr(cls, 'cloak_steps', ()) or ()) else 'emulate'

def discover_sites(package_name: str | None = None) -> dict:
    package_name = package_name or __package__.rsplit(".", 1)[0] + ".sites"
    sites, skipped = [], []
    package = None
    for candidate in (package_name, "app.plugins." + package_name):
        try:
            package = importlib.import_module(candidate)
            package_name = candidate
            break
        except Exception as exc:
            skipped.append({"module": candidate, "error": type(exc).__name__})
    native_path = Path(package.__file__).parent / "native" if package else None
    if native_path and native_path.is_dir():
        for info in pkgutil.iter_modules([str(native_path)]):
            module_name = f"{package_name}.native.{info.name}"
            try:
                module = importlib.import_module(module_name)
                for _, cls in inspect.getmembers(module, inspect.isclass):
                    if cls.__module__ != module_name or not issubclass(cls, SiteModule) or inspect.isabstract(cls):
                        continue
                    _NATIVE_MODULES[cls.id] = cls
                    if cls.url:
                        matcher = cls.match if callable(getattr(cls, 'match', None)) else (lambda url, base=cls.url: hostname(url) == hostname(base))
                        _MATCHERS[cls.id] = matcher
                    sites = [item for item in sites if item['id'] != cls.id]
                    sites.append({'id': cls.id, 'name': cls.name, 'native': True,
                                  'verified': bool(getattr(cls, 'verified', False)),
                                  'login_capable': cls.login_capable, 'url': cls.url or '', 'credential': credential(cls.credential),
                                  'cf': 'unknown' if cls.cf is None else cls.cf, 'source': '插件适配', 'impersonate': bool(getattr(cls, 'impersonate', False)), 'hook_implemented': bool(getattr(cls, 'hook_implemented', True)),
                                  'emulate': bool(getattr(cls, 'emulate', False)), 'notice': getattr(cls, 'login_notice', '') or '',
                                  'shield': shield_of(cls)})
            except Exception as exc:
                skipped.append({'module': module_name, 'error': type(exc).__name__})
    adapter_count = len(sites)
    _MATCHERS['rousi'] = lambda url: hostname(url) == hostname(ROUSI_BASE)
    _MATCHERS['sunnypt'] = lambda url: hostname(url) in {hostname(SUNNYPT_API), 'sunnypt.top'}
    for site_id, name, spec in (("rousi", "肉丝 PeerGo", ROUSI_CREDENTIALS),
                                ("sunnypt", "SunnyPT", SUNNYPT_CREDENTIALS)):
        sites.append({"id": site_id, "name": name, "native": False, "verified": False, "login_capable": True,
                      "credential": credential(spec), "cf": "unknown", "source": "插件适配"})
    for item in sites:
        item['signin_capable'] = (getattr(_NATIVE_MODULES[item['id']], 'signin_capable', True)
                                  if item.get('native') else item['id'] not in ('darkland', 'digitalcore'))
        # 签到不适用：登录专用站、mteam（保活语义）、答题/滑块类（chdbits/tjupt 答题误答风险；
        # 52pt 使用 CloakBrowser 滑块动作；答题站仍仅保留模拟登录）
        quiz = {'chdbits', 'tjupt'}
        item['signin_applicable'] = item['signin_capable'] and item['id'] != 'mteam' and item['id'] not in quiz and (
            not item.get('native') or item.get('hook_implemented', True) or item.get('verified', False))
        if item['id'] in quiz:
            item['signin_note'] = '答题类签到不建议使用（误答有账号风险），仅保留模拟登录'
    for item in skipped:
        logging.getLogger(__name__).warning("跳过原生站点模块 %s (%s)", item["module"], item["error"])
    return {"sites": sorted(sites, key=lambda item: item["id"]), "skipped": skipped,
            "sources": {"adapters": adapter_count, "integrations": 2}}


@lru_cache(maxsize=1)
def _discovery() -> dict:
    return discover_sites()


def managed_sites():
    """仅读取宿主登记名及已缓存图标，不获取远程 favicon。"""
    try:
        from app.db.oper import SiteOper
        oper = SiteOper()
        rows = []
        for site in oper.list_order_by_pri():
            icon = oper.get_icon_by_domain(site.domain)
            cached = getattr(icon, 'base64', '') or ''
            rows.append({'url': site.url, 'name': site.name,
                         'icon': cached if cached.startswith('data:image/') else ''})
        return rows
    except ImportError:
        return []


def get_native_module(site_id):
    _discovery()
    return _NATIVE_MODULES[site_id]()


def get_registry(custom_sites_data=None) -> dict:
    registry = deepcopy(_discovery())
    try:
        managed = managed_sites()
    except Exception:
        logging.getLogger(__name__).warning('无法读取站点管理来源，保留插件适配标记')
        managed = []
    for site in registry['sites']:
        site['icon'] = ''
        match = _MATCHERS.get(site['id'])
        if not match:
            continue
        try:
            registered = next((item for item in managed if match(item['url'])), None)
            if registered:
                site['source'] = 'MP 站点'
                site['name'] = registered['name'] or site['name']
                site['icon'] = registered['icon']
        except Exception:
            logging.getLogger(__name__).warning('站点来源匹配失败：%s', site['id'])
    known = {site['id'] for site in registry['sites']}

    def _host(url):
        try:
            return (urlsplit(url or '').hostname or '').lower().removeprefix('www.')
        except Exception:
            return ''
    known_hosts = {host for host in (_host(site.get('url')) for site in registry['sites']) if host}
    for item in custom_sites_data or []:
        if not isinstance(item, dict) or not item.get('id') or item['id'] in known:
            continue
        # 与适配器/宿主站点同域的自定义条目不再单列为自定义站点，
        # 仅作为该域名的 Cookie 来源（执行链按域名桥接 custom_cookie）。
        host = _host(item.get('url'))
        if host and host in known_hosts:
            continue
        registry['sites'].append({'id': item['id'], 'name': item.get('name', ''),
            'url': item.get('url', ''), 'emulate': bool(item.get('emulate', False)),
            'source': '自定义站点', 'icon': '', 'native': False, 'verified': False,
            'login_capable': True, 'signin_capable': True,
            'signin_applicable': True,
            'credential': credential(CredentialSpec()), 'cf': 'unknown',
            'shield': 'emulate' if bool(item.get('emulate', False)) else None})
        known.add(item['id'])
    return registry
