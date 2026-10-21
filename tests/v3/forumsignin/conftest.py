import importlib.util
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("forum_under_test", ROOT / "plugins.v3/forumsignin/__init__.py",
    submodule_search_locations=[str(ROOT / "plugins.v3/forumsignin")])
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
