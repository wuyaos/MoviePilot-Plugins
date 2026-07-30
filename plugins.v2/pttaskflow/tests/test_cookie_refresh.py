"""Cookie 失效识别与单次刷新契约测试。"""
import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).parents[1]
PACKAGE = "pttaskflow_cookie_test"


def package(name, path):
    module = types.ModuleType(name)
    module.__path__ = [str(path)]
    sys.modules[name] = module


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


package(PACKAGE, ROOT)
package(f"{PACKAGE}.core", ROOT / "core")
models = load(f"{PACKAGE}.core.models", ROOT / "core/models.py")
shoutbox = load(f"{PACKAGE}.core.shoutbox", ROOT / "core/shoutbox.py")
app = types.ModuleType("app"); app.__path__ = []; sys.modules["app"] = app
app_db = types.ModuleType("app.db"); app_db.__path__ = []; sys.modules["app.db"] = app_db
site_oper = types.ModuleType("app.db.site_oper"); site_oper.SiteOper = type("SiteOper", (), {})
sys.modules["app.db.site_oper"] = site_oper
app_log = types.ModuleType("app.log")
app_log.logger = types.SimpleNamespace(error=lambda *a, **k: None, warning=lambda *a, **k: None)
sys.modules["app.log"] = app_log
site_module = load(f"{PACKAGE}.core.site", ROOT / "core/site.py")
cookie_cache = load(f"{PACKAGE}.core.cookie_cache", ROOT / "core/cookie_cache.py")


class Response:
    def __init__(self, status=200, text="ok", url="https://example.org/index.php"):
        self.status_code = status
        self.text = text
        self.url = url


class Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.headers = {}
        self.calls = 0

    def request(self, *_args, **_kwargs):
        self.calls += 1
        return self.responses.pop(0)


class CookieCacheTests(unittest.TestCase):
    def test_cache_reuses_cookie_without_second_load(self):
        cache = cookie_cache.CookieCache()
        loads = []
        loader = lambda: loads.append(1) or {"example.org": "secret"}
        self.assertEqual(cache.get("https://example.org", loader), "secret")
        self.assertEqual(cache.get("https://example.org", loader), "secret")
        self.assertEqual(loads, [1])

    def test_refresh_reloads_and_replaces_cookie(self):
        cache = cookie_cache.CookieCache()
        values = iter(({"example.org": "old"}, {"example.org": "new"}))
        loader = lambda: next(values)
        self.assertEqual(cache.get("https://example.org", loader), "old")
        self.assertEqual(cache.get("https://example.org", loader, refresh=True), "new")

    def test_subdomain_matches_cookiecloud_domain(self):
        cache = cookie_cache.CookieCache()
        self.assertEqual(cache.get("https://pt.example.org", lambda: {".example.org": "secret"}),
                         "secret")

    def test_no_cookie_does_not_cache_empty_value(self):
        cache = cookie_cache.CookieCache()
        loads = []
        loader = lambda: loads.append(1) or {}
        self.assertEqual(cache.get("https://example.org", loader), "")
        self.assertEqual(cache.get("https://example.org", loader), "")
        self.assertEqual(loads, [1, 1])


class CookieRefreshTests(unittest.TestCase):
    def make_site(self, responses, refresher=None):
        instance = object.__new__(site_module.Site)
        instance.site_name = "测试站"
        instance.url = "https://example.org"
        instance.cookie = "old"
        instance.cookie_refresher = refresher
        instance.request_error = ""
        instance.session = Session(responses)
        return instance

    def test_mp_cookie_expired_returns_error_without_refresh(self):
        site = self.make_site([Response(403)])
        self.assertIsNone(site.get("/index.php"))
        self.assertEqual(site.request_error, "MP Cookie 已失效")
        self.assertEqual(site.session.calls, 1)

    def test_cookiecloud_refreshes_once_and_succeeds(self):
        refreshes = []
        site = self.make_site([Response(403), Response()], lambda: refreshes.append(1) or "new")
        self.assertIsNotNone(site.get("/index.php"))
        self.assertEqual(site.session.headers["Cookie"], "new")
        self.assertEqual(refreshes, [1])
        self.assertEqual(site.session.calls, 2)

    def test_cookiecloud_refresh_failure_returns_error(self):
        site = self.make_site([Response(403)], lambda: "")
        self.assertIsNone(site.get("/index.php"))
        self.assertEqual(site.request_error, "CookieCloud Cookie 获取失败")
        self.assertEqual(site.session.calls, 1)

    def test_refreshed_cookie_still_expired_returns_error(self):
        site = self.make_site([Response(403), Response(403)], lambda: "new")
        self.assertIsNone(site.get("/index.php"))
        self.assertEqual(site.request_error, "CookieCloud Cookie 已失效")
        self.assertEqual(site.session.calls, 2)

    def test_login_html_is_expired(self):
        html = '<html><form action="login.php"><input type="password"></form></html>'
        self.assertTrue(site_module.Site._cookie_expired(Response(text=html)))
        self.assertFalse(site_module.Site._cookie_expired(Response(text="<html>正常首页</html>")))


if __name__ == "__main__":
    unittest.main()
