import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3] / "plugins.v3"))
cloak = importlib.import_module("autoptcheckin.core.cloak")


class Context:
    def __init__(self): self.calls = []
    def new_page(self): return object()
    def add_cookies(self, cookies): self.calls.append(cookies)
    def storage_state(self, path): self.calls.append(path)
    def close(self): self.calls.append("closed")


def test_cloak_session_launch_cookie_and_resource_cleanup(monkeypatch, tmp_path):
    context = Context()
    seen = {}
    def launch(**kwargs):
        seen.update(kwargs)
        return context
    monkeypatch.setattr(cloak, "launch_context", launch)
    state = tmp_path / "state.json"
    state.write_text("{}")
    with cloak.CloakSession(state=state, cookie="sid=abc; x=y", url="https://pt.example/"):
        pass
    assert seen == {"headless": True, "humanize": True, "locale": "zh-CN", "storage_state": str(state)}
    assert context.calls[0] == [
        {"name": "sid", "value": "abc", "domain": "pt.example", "path": "/"},
        {"name": "x", "value": "y", "domain": "pt.example", "path": "/"},
    ]
    assert context.calls[-1] == "closed"


class _Body:
    def __init__(self, page): self.page = page
    def inner_text(self): return next(self.page.bodies)


class _Page:
    def __init__(self, titles, bodies):
        self.titles = iter(titles)
        self.bodies = iter(bodies)
        self.waits = []
    def title(self): return next(self.titles)
    def locator(self, selector):
        assert selector == "body"
        return _Body(self)
    def wait_for_timeout(self, milliseconds): self.waits.append(milliseconds)


def test_slider_waits_until_gate_page_redirects():
    page = _Page(["滑动认证", "Farmm :: 签到"], ["拖动滑块验证", "签到已得325"])
    assert cloak._wait_for_slider_page_exit(page) is True
    assert page.waits == [1500, 2000]


def test_slider_wait_reports_gate_timeout_without_stability_wait():
    page = _Page(["滑动认证"] * 16, ["拖动滑块验证"] * 16)
    assert cloak._wait_for_slider_page_exit(page) is False
    assert page.waits == [1500] * 16
