import importlib.util
import sys
import types
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "farmauto_test_plugin"


def load_plugin_class():
    if PACKAGE_NAME in sys.modules:
        return sys.modules[PACKAGE_NAME].FarmAuto

    apscheduler = types.ModuleType("apscheduler")
    apscheduler_triggers = types.ModuleType("apscheduler.triggers")
    apscheduler_interval = types.ModuleType("apscheduler.triggers.interval")

    class IntervalTrigger:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    apscheduler_interval.IntervalTrigger = IntervalTrigger
    sys.modules.setdefault("apscheduler", apscheduler)
    sys.modules.setdefault("apscheduler.triggers", apscheduler_triggers)
    sys.modules.setdefault("apscheduler.triggers.interval", apscheduler_interval)

    app = types.ModuleType("app")
    app_core = types.ModuleType("app.core")
    app_event = types.ModuleType("app.core.event")

    class Event:
        event_data = {}

    class EventManager:
        @staticmethod
        def register(_event_type):
            return lambda function: function

    app_event.Event = Event
    app_event.eventmanager = EventManager()

    app_db = types.ModuleType("app.db")
    app_site_oper = types.ModuleType("app.db.site_oper")
    app_site_oper.SiteOper = type("SiteOper", (), {})

    app_log = types.ModuleType("app.log")
    app_log.logger = types.SimpleNamespace(
        info=lambda *args, **kwargs: None,
        warning=lambda *args, **kwargs: None,
        debug=lambda *args, **kwargs: None,
        error=lambda *args, **kwargs: None,
    )

    app_plugins = types.ModuleType("app.plugins")

    class PluginBase:
        def __init__(self):
            pass

    app_plugins._PluginBase = PluginBase

    app_schemas = types.ModuleType("app.schemas")
    app_schemas.NotificationType = types.SimpleNamespace(SiteMessage="site")
    app_schema_types = types.ModuleType("app.schemas.types")
    app_schema_types.EventType = types.SimpleNamespace(PluginAction="plugin_action")

    modules = {
        "app": app,
        "app.core": app_core,
        "app.core.event": app_event,
        "app.db": app_db,
        "app.db.site_oper": app_site_oper,
        "app.log": app_log,
        "app.plugins": app_plugins,
        "app.schemas": app_schemas,
        "app.schemas.types": app_schema_types,
    }
    for name, module in modules.items():
        sys.modules.setdefault(name, module)

    spec = importlib.util.spec_from_file_location(
        PACKAGE_NAME,
        PLUGIN_ROOT / "__init__.py",
        submodule_search_locations=[str(PLUGIN_ROOT)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[PACKAGE_NAME] = module
    spec.loader.exec_module(module)
    return module.FarmAuto


FarmAuto = load_plugin_class()


class FakeResponse:
    def __init__(self, text="成功"):
        self.text = text

    def raise_for_status(self):
        return None


class FakeHttpClient:
    def __init__(self):
        self.urls = []

    def get(self, url, cookies):
        self.urls.append(url)
        return FakeResponse("出售成功" if "action=sell" in url else "农场首页")


def build_plugin():
    plugin = FarmAuto()
    plugin._enabled = True
    plugin._mode = "smart"
    plugin._dry_run = False
    plugin._site_ids = ["playlet"]
    plugin._interval_minutes = 60
    plugin._harvest_interval_minutes = 60
    plugin._stats = plugin._empty_stats()
    plugin._market_prices = {}
    return plugin


def test_api_status_returns_global_and_site_summary():
    plugin = build_plugin()
    plugin._stats = {
        "total_profit": 123,
        "total_trades": 4,
        "last_run": 1000,
        "history": [{
            "time": 1000,
            "site": "PlayLet",
            "action": "完成 4 个操作",
            "profit": 123,
            "status": "completed",
        }],
        "last_result": {
            "site_reports": [{
                "site_id": "playlet",
                "site_name": "PlayLet",
                "market_prices": {"crop_1": 120},
                "crop_status": {"crop_1": {"can_harvest": True}},
                "warehouse": [
                    {"crop_key": "crop_1", "quantity": 2},
                    {"crop_key": "crop_2", "quantity": 1},
                ],
                "actions": [{"action": "harvest", "success": True}],
                "bonus": "999",
            }]
        },
    }
    plugin._market_prices = {"playlet": {"crop_1": 120}}
    plugin._trend_store.record("playlet", {"crop_1": 110}, ts=900)
    plugin._trend_store.record("playlet", {"crop_1": 120}, ts=1000)

    response = plugin._api_status()

    assert response["success"] is True
    data = response["data"]
    assert data["enabled"] is True
    assert data["mode"] == "smart"
    assert data["dry_run"] is False
    assert data["selected_site_ids"] == ["playlet"]
    assert data["next_run"] is not None
    assert data["total_profit"] == 123
    assert data["total_trades"] == 4
    assert data["last_run"] is not None
    # 全部已注册站点都会出现在列表中
    sites = data["sites"]
    playlet_site = next((s for s in sites if s["site_id"] == "playlet"), None)
    assert playlet_site is not None
    assert playlet_site == {
        "site_id": "playlet",
        "site_name": "PlayLet",
        "currency": "魔力",
        "bonus": "999",
        "prices_count": 1,
        "harvestable": ["crop_1"],
        "warehouse_count": 2,
        "trend_points": 2,
        "recent_action": "harvest",
    }
    assert len(sites) >= 1


def test_api_site_detail_embeds_crop_images_without_cookie():
    plugin = build_plugin()

    response = plugin._api_site_detail("playlet")

    assert response["success"] is True
    assert response["data"]["crops"]["crop_1"]["image"].startswith(
        "data:image/png;base64,"
    )
    assert "cookie" not in response["data"]


def test_api_site_detail_fills_prices_for_common_sites():
    plugin = build_plugin()
    plugin._stats = {
        **plugin._empty_stats(),
        "last_result": {
            "site_reports": [{
                "site_id": "playlet",
                "market_prices": {"crop_1": 120},
                "crop_status": {"crop_1": {"can_harvest": True}},
                "warehouse": [{"crop_key": "crop_1", "quantity": 2}],
            }]
        },
    }

    data = plugin._api_site_detail("playlet")["data"]

    assert data["crop_status"]["crop_1"] == {
        "can_harvest": True,
        "remaining_minutes": None,
        "state": "ripe",
        "price": 120,
    }
    assert data["warehouse"][0]["unit_price"] == 120
    assert data["warehouse"][0]["total_price"] == 240


def test_api_site_action_dry_run_does_not_build_client_or_request():
    plugin = build_plugin()
    plugin._dry_run = True
    requested = []
    plugin._build_http_client = lambda policy: requested.append(policy)
    plugin._get_site_cookie = lambda site_config: "session=secret"

    response = plugin._api_site_action(
        "playlet", {"action": "harvest", "crop_key": "crop_1"}
    )

    assert response == {
        "success": True,
        "message": "dry-run：仅记录计划",
        "action": "harvest",
        "target": "小麦",
        "dry_run": True,
    }
    assert requested == []


def test_api_site_action_sell_fetches_farm_and_calls_sell_url():
    plugin = build_plugin()
    client = FakeHttpClient()
    plugin._build_http_client = lambda policy: client
    plugin._get_site_cookie = lambda site_config: "session=secret"

    response = plugin._api_site_action(
        "playlet", {"action": "sell", "crop_key": "crop_1"}
    )

    assert response["success"] is True
    assert response["action"] == "sell"
    assert response["target"] == "小麦"
    assert response["dry_run"] is False
    assert client.urls[0].endswith("/magic_fram.php")
    assert client.urls[1].endswith("action=sell&key=crop_1")


def test_api_site_action_harvest_calls_corresponding_url():
    plugin = build_plugin()
    client = FakeHttpClient()
    plugin._build_http_client = lambda policy: client
    plugin._get_site_cookie = lambda site_config: "session=secret"

    response = plugin._api_site_action(
        "playlet", {"action": "harvest", "crop_key": "crop_1"}
    )

    assert response["action"] == "harvest"
    assert response["dry_run"] is False
    assert client.urls == [
        "https://playlet.cc/magic_fram.php?action=harvest&type=crop&id=1"
    ]
