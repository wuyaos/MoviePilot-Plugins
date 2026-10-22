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


_MATCHERS = {}
_NATIVE_MODULES = {}

def credential(spec: CredentialSpec) -> dict:
    return {"kind": spec.kind, "sources": list(spec.cookie_sources), "refresh": spec.refresh}


def discover_sites(package_name: str | None = None) -> dict:
    package_name = package_name or __package__.rsplit(".", 1)[0] + ".sites"
    sites, skipped = [], []
    package = None
    for candidate in (package_name, "app.plugins." + package_name):
        try:
            package = importlib.import_module(candidate)
            package_name = candidate
            base = package._ISiteSigninHandler
            modules = list(pkgutil.iter_modules(package.__path__))
            break
        except Exception as exc:
            skipped.append({"module": candidate, "error": type(exc).__name__})
    else:
        modules = []
        base = None
    for info in modules:
        if info.name == "native":
            continue
        module_name = f"{package_name}.{info.name}"
        try:
            module = importlib.import_module(module_name)
            for _, cls in inspect.getmembers(module, inspect.isclass):
                if base is None or cls is base or cls.__module__ != module_name or not issubclass(cls, base) or inspect.isabstract(cls):
                    continue
                site_id = getattr(cls, "site_id", None) or info.name
                if callable(getattr(cls, "match", None)):
                    _MATCHERS[site_id] = cls.match
                sites.append({"id": getattr(cls, "site_id", None) or info.name,
                              "name": getattr(cls, "site_name", None) or getattr(cls, "name", None) or info.name,
                              "login_capable": bool(getattr(cls, "login_capable", True)),
                              "credential": credential(CredentialSpec()), "cf": "unknown", "source": "插件适配"})
        except Exception as exc:
            skipped.append({"module": module_name, "error": type(exc).__name__})
    adapter_count = len(sites)
    # 只在整个 registry 无可用适配器时使用旧静态清单，不掩盖单站导入失败。
    if not sites and skipped:
        fallback = json.loads((Path(__file__).parents[1] / "sites_fallback.json").read_text(encoding="utf-8"))
        sites = [{"id": item["id"], "name": item["name"], "login_capable": item.get("login_capable", True),
                  "credential": credential(CredentialSpec()), "cf": "unknown", "source": "插件适配"}
                 for item in fallback if item["id"] not in ("rousi", "sunnypt")]
    for site_id, name, spec in (("rousi", "肉丝 PeerGo", ROUSI_CREDENTIALS),
                                ("sunnypt", "SunnyPT", SUNNYPT_CREDENTIALS)):
        sites.append({"id": site_id, "name": name, "login_capable": False,
                      "credential": credential(spec), "cf": "unknown", "source": "插件适配"})
    for item in sites:
        item['native'] = False
        item['verified'] = False
    # Native metadata replaces the same legacy ID, while the adapter stays on disk.
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
                    # API-only declarations retain the legacy multi-domain matcher.
                    if cls.url:
                        _MATCHERS[cls.id] = lambda url, base=cls.url: (urlsplit(url).hostname or '').removeprefix('www.') == (urlsplit(base).hostname or '').removeprefix('www.')
                    sites = [item for item in sites if item['id'] != cls.id]
                    sites.append({'id': cls.id, 'name': cls.name, 'native': True,
                                  'verified': bool(getattr(cls, 'verified', False)),
                                  'login_capable': cls.login_capable, 'url': cls.url or '', 'credential': credential(cls.credential),
                                  'cf': 'unknown' if cls.cf is None else cls.cf, 'source': '插件适配', 'hook_implemented': bool(getattr(cls, 'hook_implemented', True))})
            except Exception as exc:
                skipped.append({'module': module_name, 'error': type(exc).__name__})
    for item in sites:
        item['signin_capable'] = item['id'] not in ('darkland', 'digitalcore')
        # 签到不适用：登录专用站、mteam（保活语义）、答题/滑块类（chdbits/tjupt 答题误答风险；
        # 52pt 已改滑块签到，HTTP 无法完成，须 Browserless 实现，均仅保留模拟登录）
        quiz = {'52pt', 'chdbits', 'tjupt'}
        item['signin_applicable'] = item['signin_capable'] and item['id'] != 'mteam' and item['id'] not in quiz and (
            not item.get('native') or item.get('hook_implemented', True) or item.get('verified', False))
        if item['id'] in quiz:
            item['signin_note'] = '答题类签到不建议使用（误答有账号风险），仅保留模拟登录'
        item['pilot_enabled'] = (item['verified'] and item.get('hook_implemented', True)) if item['native'] else item['id'] in ('hdsky', 'haitang')
    for item in skipped:
        logging.getLogger(__name__).warning("跳过站点适配器 %s (%s)", item["module"], item["error"])
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
    for item in custom_sites_data or []:
        if not isinstance(item, dict) or not item.get('id') or item['id'] in known:
            continue
        registry['sites'].append({'id': item['id'], 'name': item.get('name', ''),
            'url': item.get('url', ''), 'emulate': bool(item.get('emulate', False)),
            'source': '自定义站点', 'icon': '', 'native': False, 'verified': False,
            'pilot_enabled': False, 'login_capable': True, 'signin_capable': True,
            'credential': credential(CredentialSpec()), 'cf': 'unknown'})
        known.add(item['id'])
    return registry
