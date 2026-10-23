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
