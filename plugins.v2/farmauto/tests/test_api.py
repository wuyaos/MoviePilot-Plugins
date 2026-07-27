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
ActionResult = sys.modules[f"{PACKAGE_NAME}.core.models"].ActionResult
SiteRunReport = sys.modules[f"{PACKAGE_NAME}.core.models"].SiteRunReport


class FakeResponse:
    def __init__(self, text="成功"):
        self.text = text

    def raise_for_status(self):
        return None


class FakeHttpClient:
    def __init__(self):
        self.urls = []
        self.posts = []
        self.post_responses = []

    def get(self, url, cookies):
        self.urls.append(url)
        return FakeResponse("出售成功" if "action=sell" in url else "农场首页")

    def post(self, url, cookies, data=None, **_kwargs):
        self.posts.append((url, data))
        if self.post_responses:
            return FakeResponse(self.post_responses.pop(0))
        return FakeResponse('{"success":true,"msg":"成功"}')


def build_plugin():
    plugin = FarmAuto()
    plugin._enabled = True
    plugin._dry_run = False
    plugin._site_ids = ["playlet"]
    plugin._interval_minutes = 60
    plugin._stats = plugin._empty_stats()
    plugin._market_prices = {}
    return plugin


def test_manual_siqi_interaction_notification_filters_skips_and_deduplicates_limit():
    plugin = build_plugin()
    plugin._notify = True
    sent = []
    stored = {}
    plugin.post_message = lambda **kwargs: sent.append(kwargs)
    plugin.get_data = lambda key: stored.get(key)
    plugin.save_data = lambda key, value: stored.__setitem__(key, dict(value))

    plugin._notify_siqi_interaction(
        "buy_slot", True, "魔力不足", skipped=True, reason="insufficient_bonus"
    )
    assert sent == []

    plugin._notify_siqi_interaction(
        "like", True, "今日点赞额度已用完", skipped=True, reason="daily_exhausted"
    )
    plugin._notify_siqi_interaction(
        "like", True, "今日点赞额度已用完", skipped=True, reason="daily_exhausted"
    )
    plugin._notify_siqi_interaction("visit", False, "访问失败")

    assert len(sent) == 2
    assert "首次达到上限" in sent[0]["text"]
    assert "访问：❌ 失败" in sent[1]["text"]


def test_siqi_daily_flags_only_successful_actions():
    plugin = build_plugin()
    plugin._siqi_options = {"auto_steal": True, "auto_like": True}
    saved = []
    plugin.get_data = lambda _key: {"date": "2099-01-01", "steal": False, "like": False}
    plugin.save_data = lambda key, value: saved.append((key, dict(value)))
    plugin._siqi_daily_state = lambda: {"date": "2099-01-01", "steal": False, "like": False}
    executor = types.SimpleNamespace(run_siqi_extras=lambda *_args, **_kwargs: [
        ActionResult("steal", "目标A", False, message="偷菜失败"),
        ActionResult("like", "目标B", True, message="点赞成功"),
    ])
    site = types.SimpleNamespace(site_id="siqi")
    report = SiteRunReport("siqi", "思齐")

    plugin._run_siqi_extras(executor, site, "cookie", {}, report)

    assert saved == [("siqi_daily", {
        "date": "2099-01-01", "steal": False, "like": True,
    })]
    assert report.status == "partial"
    assert report.trades_count == 1


def test_siqi_skipped_social_action_does_not_count_or_consume_daily_limit():
    plugin = build_plugin()
    plugin._siqi_options = {"auto_steal": True}
    saved = []
    plugin._siqi_daily_state = lambda: {
        "date": "2099-01-01", "steal": False, "like": False,
    }
    plugin.save_data = lambda key, value: saved.append((key, dict(value)))
    executor = types.SimpleNamespace(run_siqi_extras=lambda *_args, **_kwargs: [
        ActionResult("steal", "随机农场", True, skipped=True, message="无可偷菜目标，跳过"),
    ])
    site = types.SimpleNamespace(site_id="siqi")
    report = SiteRunReport("siqi", "思齐")

    plugin._run_siqi_extras(executor, site, "cookie", {}, report)

    assert report.trades_count == 0
    assert saved == []
    assert report.status == "completed"


def test_siqi_extras_preserve_existing_failed_report_status():
    plugin = build_plugin()
    plugin._siqi_options = {"auto_like": True}
    plugin._siqi_daily_state = lambda: {
        "date": "2099-01-01", "steal": False, "like": False,
    }
    plugin.save_data = lambda *_args: None
    executor = types.SimpleNamespace(run_siqi_extras=lambda *_args, **_kwargs: [
        ActionResult("like", "目标B", True, message="点赞成功"),
    ])
    site = types.SimpleNamespace(site_id="siqi")
    report = SiteRunReport(
        "siqi", "思齐", status="failed", message="认证失败",
    )

    plugin._run_siqi_extras(executor, site, "cookie", {}, report)

    assert report.status == "failed"
    assert report.message == "认证失败"
    assert report.trades_count == 1


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
    assert "mode" not in data
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


def test_api_site_detail_keeps_newest_actions_first_and_limits_twenty():
    plugin = build_plugin()
    persisted = [
        {"time": float(index), "action": "plant", "target": str(index)}
        for index in range(1, 26)
    ]
    plugin._stats = {
        **plugin._empty_stats(),
        "action_history": {"playlet": persisted},
        "last_result": {
            "site_reports": [{
                "site_id": "playlet",
                "actions": [{
                    "time": 26.0, "action": "sell", "target": "最新动作",
                    "success": True,
                }],
            }],
        },
    }

    actions = plugin._api_site_detail("playlet")["data"]["recent_actions"]

    assert len(actions) == 20
    assert [item["time"] for item in actions[:3]] == [26.0, 25.0, 24.0]
    assert actions[-1]["time"] == 7.0


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


def test_api_site_action_rejects_request_while_task_is_running():
    plugin = build_plugin()
    requested = []
    plugin._build_http_client = lambda policy: requested.append(policy)
    assert type(plugin)._run_lock.acquire(blocking=False) is True

    try:
        response = plugin._api_site_action(
            "playlet", {"action": "harvest", "crop_key": "crop_1"}
        )
    finally:
        type(plugin)._run_lock.release()

    assert response == {
        "success": False,
        "message": "农场任务正在运行，请稍后重试",
        "action": "harvest",
        "target": "小麦",
        "dry_run": False,
    }
    assert requested == []


def test_api_site_action_releases_lock_after_request_error():
    plugin = build_plugin()
    plugin._build_http_client = lambda _policy: (_ for _ in ()).throw(
        RuntimeError("client failed")
    )

    response = plugin._api_site_action(
        "playlet", {"action": "harvest", "crop_key": "crop_1"}
    )

    assert response["success"] is False
    assert response["message"] == "client failed"
    assert type(plugin)._run_lock.acquire(blocking=False) is True
    type(plugin)._run_lock.release()


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


def test_siqi_interaction_actions_use_post_form_protocol():
    plugin = build_plugin()
    client = FakeHttpClient()
    plugin._build_http_client = lambda _policy: client
    plugin._get_site_cookie = lambda _site_config: "session=secret"

    client.post_responses = ['{"success":true,"usernames":["alice","bob"]}']
    targets = plugin._api_site_action("siqi", {"action": "get_like_targets"})
    assert targets["targets"] == ["alice", "bob"]
    assert client.posts[-1] == (
        "https://si-qi.xyz/plant_game.php", {"action": "random_like_targets"},
    )

    liked = plugin._api_site_action("siqi", {
        "action": "like", "usernames": "alice\nbob",
    })
    assert liked["success"] is True
    assert client.posts[-1] == (
        "https://si-qi.xyz/plant_game.php",
        {"action": "like_farm_batch", "usernames": "alice\nbob"},
    )

    visited = plugin._api_site_action("siqi", {"action": "visit", "random": True})
    assert visited["success"] is True
    assert client.posts[-1] == (
        "https://si-qi.xyz/plant_game.php", {"action": "view_random_farm"},
    )


def test_siqi_target_queries_use_cache_and_daily_guard():
    plugin = build_plugin()
    client = FakeHttpClient()
    plugin._build_http_client = lambda _policy: client
    plugin._get_site_cookie = lambda _site_config: "session=secret"
    daily = {"date": "2099-01-01", "steal": False, "like": False}
    plugin._siqi_daily_state = lambda: daily

    client.post_responses = ['{"success":true,"usernames":["alice"]}']
    first = plugin._api_site_action("siqi", {"action": "get_like_targets"})
    second = plugin._api_site_action("siqi", {"action": "get_like_targets"})
    assert first["targets"] == ["alice"]
    assert second["cached"] is True
    assert len(client.posts) == 1

    daily["like"] = True
    cached_after_quota = plugin._api_site_action("siqi", {"action": "get_like_targets"})
    assert cached_after_quota["cached"] is True
    assert cached_after_quota["targets"] == ["alice"]
    assert len(client.posts) == 1


def test_siqi_visit_has_backend_cooldown():
    plugin = build_plugin()
    client = FakeHttpClient()
    plugin._build_http_client = lambda _policy: client
    plugin._get_site_cookie = lambda _site_config: "session=secret"

    first = plugin._api_site_action("siqi", {"action": "visit", "random": True})
    second = plugin._api_site_action("siqi", {"action": "visit", "random": True})
    assert first["success"] is True
    assert second["skipped"] is True
    assert second["reason"] == "cooldown"
    assert len(client.posts) == 1


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
