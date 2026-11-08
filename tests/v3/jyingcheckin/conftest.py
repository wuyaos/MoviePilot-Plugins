import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("jying_under_test", ROOT / "plugins.v3/jyingcheckin/__init__.py",
    submodule_search_locations=[str(ROOT / "plugins.v3/jyingcheckin")])
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    import socket

    original = socket.socket.connect

    def forbidden(sock, address):
        if address[0] in ("127.0.0.1", "::1"):
            return original(sock, address)
        raise AssertionError("Offline tests forbid network")

    monkeypatch.setattr(socket.socket, "connect", forbidden)


@pytest.fixture
def factory():
    """构造离线插件实例：内存存储 + 可注入的 fake client。"""
    plugin = MODULE.JyingCheckin()

    memory: dict = {}

    store = MODULE.Store(memory.get, lambda k, v: memory.__setitem__(k, v))
    plugin._store = store

    def make(config: dict | None = None, client=None):
        plugin._config = {**json.loads((Path(MODULE.__file__).parent / "config_defaults.json").read_text(encoding="utf-8"))}
        plugin._config.update(config or {})
        if client is not None:
            plugin._client = client
        plugin._memory = memory
        return plugin

    make.memory = memory
    return make


@pytest.fixture
def notify_spy(monkeypatch):
    """捕获 post_message 调用。"""
    sent: list[tuple] = []

    def fake_post(self, title="", text=""):
        sent.append((title, text))

    monkeypatch.setattr(MODULE._PluginBase, "post_message", fake_post, raising=False)
    return sent
