import importlib
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
PLUGIN_ROOT = ROOT / "plugins.v2"
sys.path.insert(0, str(PLUGIN_ROOT))


class FakeLogger:
    def __getattr__(self, _name):
        return lambda *_args, **_kwargs: None


class FakePluginBase:
    def __init__(self):
        self._data = {}
        self._config = {}
        self.messages = []

    def get_data(self, key):
        return self._data.get(key)

    def save_data(self, key, value):
        self._data[key] = value

    def get_config(self):
        return self._config.copy()

    def update_config(self, value):
        self._config = value.copy()

    def post_message(self, **kwargs):
        self.messages.append(kwargs)


@pytest.fixture
def plugin_module(monkeypatch):
    app = types.ModuleType("app")
    app_core = types.ModuleType("app.core")
    app_core_config = types.ModuleType("app.core.config")
    app_core_config.settings = types.SimpleNamespace(TZ="Asia/Shanghai")
    app_log = types.ModuleType("app.log")
    app_log.logger = FakeLogger()
    app_plugins = types.ModuleType("app.plugins")
    app_plugins._PluginBase = FakePluginBase
    app_schemas = types.ModuleType("app.schemas")
    app_schemas.NotificationType = types.SimpleNamespace(Plugin="Plugin")
    apscheduler = types.ModuleType("apscheduler")
    apscheduler_triggers = types.ModuleType("apscheduler.triggers")
    apscheduler_cron = types.ModuleType("apscheduler.triggers.cron")
    apscheduler_cron.CronTrigger = types.SimpleNamespace(from_crontab=lambda *args, **kwargs: (args, kwargs))
    for name, module in {
        "app": app,
        "app.core": app_core,
        "app.core.config": app_core_config,
        "app.log": app_log,
        "app.plugins": app_plugins,
        "app.schemas": app_schemas,
        "apscheduler": apscheduler,
        "apscheduler.triggers": apscheduler_triggers,
        "apscheduler.triggers.cron": apscheduler_cron,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)
    for name in [key for key in sys.modules if key == "rousicheckin" or key.startswith("rousicheckin.")]:
        sys.modules.pop(name, None)
    return importlib.import_module("rousicheckin")


class FakeClient:
    refreshed = False
    attendance_states = []
    claim_calls = 0

    @staticmethod
    def normalize_cookie(value):
        return str(value or "").strip()

    def __init__(self, cookie=""):
        self.cookie = cookie
        self._states = list(type(self).attendance_states)

    def ensure_session(self, username="", password=""):
        return ({
            "csrf_token": "csrf",
            "expires_at": "2026-09-20T00:00:00Z",
            "user": {"username": username or "tester", "display_name": "Tester"},
        }, "__Host-peergo_session=new", type(self).refreshed)

    def get_traffic(self):
        return {"totals": {"credited_uploaded_bytes": 1024, "charged_downloaded_bytes": 512}}

    def get_economy(self):
        return {"magic_balance": "100", "progress": {"level": 2}}

    def get_attendance(self):
        return self._states.pop(0)

    def claim_attendance(self, csrf_token, mode="fixed"):
        assert csrf_token == "csrf" and mode == "fixed"
        type(self).claim_calls += 1
        return {"claimed_today": True}

    def get_notifications(self, limit=20, offset=0):
        return {"items": [], "limit": limit, "offset": offset, "total": 0, "unread_count": 0}


def new_plugin(module, monkeypatch, *, refreshed=False, attendance_states=None):
    FakeClient.refreshed = refreshed
    FakeClient.attendance_states = attendance_states or [{"claimed_today": True, "current_streak": 5}]
    FakeClient.claim_calls = 0
    monkeypatch.setattr(module, "PeerGoClient", FakeClient)
    plugin = module.RousiCheckin()
    plugin.init_plugin({
        "enabled": True,
        "notify": False,
        "message_notify": True,
        "username": "tester",
        "password": "secret",
        "cookie": "__Host-peergo_session=old",
        "cron": "7 9 * * *",
        "random_delay_minutes": 0,
    })
    return plugin


def test_already_claimed_never_posts_attendance(plugin_module, monkeypatch):
    plugin = new_plugin(plugin_module, monkeypatch)
    result = plugin._RousiCheckin__signin(manual=True)
    assert result["status_code"] == "success_already"
    assert FakeClient.claim_calls == 0
    assert plugin.get_data("notifications_initialized") is True


def test_unclaimed_posts_once_then_verifies(plugin_module, monkeypatch):
    plugin = new_plugin(
        plugin_module,
        monkeypatch,
        attendance_states=[
            {"claimed_today": False, "current_streak": 5},
            {"claimed_today": True, "current_streak": 6, "today_record": {"total_reward": "100"}},
        ],
    )
    result = plugin._RousiCheckin__signin(manual=True)
    assert result["status_code"] == "success_new"
    assert "获得 100 魔力值" in result["message"]
    assert FakeClient.claim_calls == 1


def test_refreshed_cookie_is_written_with_credentials_preserved(plugin_module, monkeypatch):
    plugin = new_plugin(plugin_module, monkeypatch, refreshed=True)
    result = plugin._RousiCheckin__signin(manual=True)
    assert result["status_code"] == "success_already"
    assert plugin.get_config()["cookie"] == "__Host-peergo_session=new"
    assert plugin.get_config()["username"] == "tester"
    assert plugin.get_config()["password"] == "secret"
