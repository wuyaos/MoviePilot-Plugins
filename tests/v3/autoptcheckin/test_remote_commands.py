"""远程命令（get_command / PluginAction）离线契约。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3] / 'plugins.v3'))
from autoptcheckin import AutoPtCheckin


def test_get_command_offline_returns_empty():
    # 无宿主（EventType 为 None）时不注册命令
    assert AutoPtCheckin.get_command() == []


def test_remote_command_force_clears_and_runs():
    import autoptcheckin as mod

    class _FakeEventType:
        PluginAction = "PluginAction"

    plugin = AutoPtCheckin()
    plugin._round_active = False
    plugin._config = {}
    called = {}

    class FakeEvent:
        event_data = {"action": "checkin_force"}

    import threading
    orig = threading.Thread
    orig_et = mod.EventType

    def fake_thread(target=None, daemon=None, name=None):
        called['started'] = True
        class _T:
            def start(self): target()
        return _T()

    threading.Thread = fake_thread
    mod.EventType = _FakeEventType
    try:
        plugin._history = type('H', (), {'clear_today': staticmethod(lambda: called.setdefault('clean', True))})()
        plugin._track_store = lambda: type('S', (), {'clear_transient': staticmethod(lambda: called.setdefault('clear', True))})()
        plugin._round_lock = threading.Lock()
        plugin._execute_all = lambda trigger, **kwargs: called.setdefault('run', trigger)
        plugin._handle_remote_command(FakeEvent())
    finally:
        threading.Thread = orig
        mod.EventType = orig_et
    assert called.get('clean') and called.get('clear') and called.get('run')
    assert called['run'] == 'manual'
    assert 'onlyonce' not in plugin._config
    assert not plugin._round_lock.locked()


def test_force_command_does_not_clear_when_stopped_or_busy(monkeypatch):
    import threading
    from types import SimpleNamespace
    import autoptcheckin as mod
    monkeypatch.setattr(mod, 'EventType', SimpleNamespace(PluginAction='PluginAction'))
    class InlineThread:
        def __init__(self, target, **kwargs):
            self.target = target
        def start(self):
            self.target()
    monkeypatch.setattr(threading, 'Thread', InlineThread)
    for stopped in (True, False):
        p = AutoPtCheckin()
        calls = []
        p._history.clear_today = lambda: calls.append('clear')
        p._execute_all = lambda *a, **kw: calls.append('run')
        if stopped:
            p._runner.stop.set()
        else:
            p._round_lock.acquire()
        p._handle_remote_command(SimpleNamespace(event_data={'action': 'checkin_force'}))
        assert calls == []
        if not stopped:
            p._round_lock.release()
        assert not p._round_lock.locked()


def test_remote_command_unknown_action_ignored():
    plugin = AutoPtCheckin.__new__(AutoPtCheckin)
    plugin._round_active = False
    # 无宿主 EventType 为 None 直接忽略，不抛异常
    plugin._handle_remote_command(type('E', (), {'event_data': {"action": "checkin_force"}})())
    plugin._handle_remote_command(None)
