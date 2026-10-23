"""CloakBrowser 仿真路由离线测试。"""
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / "plugins.v3"))
cloak = importlib.import_module("autoptcheckin.core.cloak")


class FakePage:
    def __init__(self): self.url = "https://site.invalid/"
    def goto(self, url, **kwargs):
        self.url = url
        return SimpleNamespace(status=200)
    def wait_for_timeout(self, _): pass
    def content(self): return "<html>fixture</html>"


class FakeContext:
    def __init__(self): self.page = FakePage(); self.closed = False
    def new_page(self): return self.page
    def add_cookies(self, _): pass
    def cookies(self, _): return [{"name": "sid", "value": "session"}]
    def close(self): self.closed = True


class FakeHttp:
    def __init__(self): self.cookies = {"sid": "session"}
    def get_bytes(self, _): return b""
    def retain_cookies(self, _): pass


class FakeSite:
    id = "ourbits"
    url = "https://site.invalid/"
    emulate = True


def test_declared_and_listed_site_uses_cloak_and_syncs_cookie(monkeypatch):
    context = FakeContext()
    monkeypatch.setattr(cloak, "launch_context", lambda **kwargs: context)
    client = cloak.native_cloak_client(FakeSite(), FakeHttp(), {"url": FakeSite.url},
                                      {"site_browserless": ["ourbits"]})
    response = client.get(FakeSite.url)
    assert response.status_code == 200 and response.text == "<html>fixture</html>"
    assert response.url == FakeSite.url
    assert client.http.cookies["sid"] == "session"
    client.close()
    assert context.closed


def test_undeclared_or_unlisted_site_keeps_http_client(monkeypatch):
    http = FakeHttp()
    monkeypatch.setattr(cloak, "launch_context", lambda **kwargs: pytest.fail("unexpected browser"))
    assert cloak.native_cloak_client(FakeSite(), http, {"url": FakeSite.url}, {"site_browserless": []}) is http
    site = SimpleNamespace(id="elsewhere", url=FakeSite.url, emulate=False)
    assert cloak.native_cloak_client(site, http, {"url": FakeSite.url},
                                     {"site_browserless": ["elsewhere"]}) is http
