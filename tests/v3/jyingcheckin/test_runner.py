"""run_once 状态机编排离线测试（FakeClient 模拟站点响应，不触真实站点）。"""
import time

import types

from jying_under_test.client import ApiResult, LoginResult


def make_fake_client(stats=None, login=None, do=None, luck=None, calls=None):
    """构造 FakeClient：每个方法可给 ApiResult/LoginResult 或可调用（返回值）。"""
    calls = calls if calls is not None else {}

    def wrap(attr, spec, name):
        if spec is None:
            return lambda *a, **k: ApiResult(ok=False, error=f"unexpected {name}")
        if isinstance(spec, (ApiResult, LoginResult)):
            calls[name] = calls.get(name, 0) + 1
            return lambda *a, **k: spec
        calls[name] = calls.get(name, 0) + 1
        return spec

    return types.SimpleNamespace(
        stats=wrap("stats", stats, "stats"),
        login=wrap("login", login, "login"),
        do_checkin=wrap("do", do, "do"),
        luck_draw=wrap("luck", luck, "luck"),
    ), calls


def run(factory, config, client, preset_session=True):
    plugin = factory(config=config, client=client)
    if preset_session:
        plugin._store.save_session("PRESET", 1, time.time() + 3600)
    plugin._notify = lambda *a, **k: None  # 通知单独测
    return plugin.run_once(trigger="manual"), plugin


def ok_stats(checked=False, days=6):
    return ApiResult(ok=True, status="success",
                     data={"status": "success", "checked_today": checked,
                           "can_checkin": not checked, "my_total_days": days, "reward_points": 5})


def ok_do(days=7):
    return ApiResult(ok=True, status="success",
                     data={"status": "success", "my_total_days": days, "reward_points": 5})


# ---- 五态分支 -------------------------------------------------------------

def test_missing_credentials_auth_failed(factory):
    result, _ = run(factory, {"username": "", "password": ""}, None)
    assert result["status"] == "auth_failed"
    assert result.get("token") is None  # 无凭据泄露


def test_already_via_stats(factory):
    client, calls = make_fake_client(stats=ok_stats(checked=True))
    result, _ = run(factory, {"username": "u", "password": "p"}, client)
    assert result["status"] == "already"
    assert "do" not in calls  # 已签不提交
    assert not result.get("token_refreshed")


def test_success_normal(factory):
    client, calls = make_fake_client(stats=ok_stats(checked=False), do=ok_do(),
                                     login=LoginResult(ok=True, token="T", user_id=5))
    result, _ = run(factory, {"username": "u", "password": "p"}, client)
    assert result["status"] == "success"
    assert "do" in calls and "luck" not in calls
    assert result["mode"] == "normal"


def test_auth_fail_then_relogin_success(factory):
    """stats 401 → 整段重登 → 签到成功，token_refreshed=True。"""
    seq = {"n": 0}

    def stats_side(*a, **k):
        seq["n"] += 1
        if seq["n"] == 1:
            return ApiResult(ok=False, auth_expired=True, http_status=401)
        return ok_stats(checked=False)

    def login_side(username, password):
        assert (username, password) == ("u", "p")
        return LoginResult(ok=True, token="NEW", user_id=7)

    client, calls = make_fake_client(stats=stats_side, login=login_side, do=ok_do())
    plugin = factory(config={"username": "u", "password": "p"}, client=client)
    plugin._notify = lambda *a, **k: None
    result = plugin.run_once(trigger="manual")
    assert result["status"] == "success"
    assert result["token_refreshed"] is True
    assert plugin._store.get_session()["token"] == "NEW"  # 新 token 回写插件数据
    assert plugin._store.get_session()["user_id"] == 7


def test_login_bad_credentials_no_retry(factory):
    client, _ = make_fake_client(login=LoginResult(ok=False, message="用户名或密码错误"))
    result, _ = run(factory, {"username": "u", "password": "p"}, client, preset_session=False)
    assert result["status"] == "auth_failed"  # 账密错误不进 pending 重试


def test_do_network_error_is_pending(factory):
    client, _ = make_fake_client(stats=ok_stats(checked=False),
                                 do=ApiResult(ok=False, error="network: ConnectionError"))
    result, _ = run(factory, {"username": "u", "password": "p"}, client)
    assert result["status"] == "pending"


def test_do_already_message_is_already(factory):
    client, _ = make_fake_client(stats=ok_stats(checked=False),
                                 do=ApiResult(ok=False, status="error", message="今日已签到"))
    result, _ = run(factory, {"username": "u", "password": "p"}, client)
    assert result["status"] == "already"


def test_unknown_site_response(factory):
    client, _ = make_fake_client(stats=ok_stats(checked=False),
                                 do=ApiResult(ok=False, status="error", message="活动未开始"))
    result, _ = run(factory, {"username": "u", "password": "p"}, client)
    assert result["status"] == "unknown"
    assert result["message"] == "活动未开始"


def test_lucky_mode_degrades_without_user_id(factory):
    client, calls = make_fake_client(stats=ok_stats(checked=False), do=ok_do(),
                                     login=LoginResult(ok=True, token="T", user_id=None))
    result, _ = run(factory, {"username": "u", "password": "p", "lucky_mode": True}, client, preset_session=False)
    assert result["status"] == "success" and "luck" not in calls
    assert "降级" in result["message"]


def test_lucky_mode_uses_luck_draw(factory):
    client, calls = make_fake_client(stats=ok_stats(checked=False),
                                     luck=ok_do(),
                                     login=LoginResult(ok=True, token="T", user_id=5))
    result, _ = run(factory, {"username": "u", "password": "p", "lucky_mode": True}, client, preset_session=False)
    assert result["status"] == "success" and "luck" in calls and "do" not in calls
    assert result["mode"] == "lucky" and result["lucky"] is True


# ---- 幂等 / 终态落盘 / API -------------------------------------------------

def test_terminal_recorded_once(factory):
    client, _ = make_fake_client(stats=ok_stats(checked=False), do=ok_do(),
                                 login=LoginResult(ok=True, token="T", user_id=5))
    plugin = factory(config={"username": "u", "password": "p", "notify": False}, client=client)
    plugin._store.save_session("PRESET", 1, __import__("time").time() + 3600)
    plugin.run_once(trigger="manual")
    latest = plugin._store.get_latest()
    assert latest["status"] == "success" and latest["days"] == 7
    assert len(plugin._store.get_history()) == 1
    assert "token" not in latest and "raw" not in latest  # 白名单键级断言（token_refreshed 合法）


def test_api_checkin_envelope(factory):
    client, _ = make_fake_client(stats=ok_stats(checked=True))
    plugin = factory(config={"enabled": True, "username": "u", "password": "p"}, client=client)
    plugin._notify = lambda *a, **k: None
    plugin._store.save_session("PRESET", 1, __import__("time").time() + 3600)
    resp = plugin.api_checkin()
    assert resp["success"] is True and resp["data"]["status"] == "already"

    plugin._config["enabled"] = False
    resp = plugin.api_checkin()
    assert resp["success"] is False and "未启用" in resp["message"]


def test_api_status_never_exposes_token(factory):
    client, _ = make_fake_client(stats=ok_stats(checked=True))
    plugin = factory(config={"enabled": True, "username": "u", "password": "p"}, client=client)
    plugin._notify = lambda *a, **k: None
    plugin._store.save_session("PRESET", 1, __import__("time").time() + 3600)
    plugin.run_once(trigger="manual")
    import json as _json
    body = _json.dumps(plugin.api_status(), ensure_ascii=False)
    assert "PRESET" not in body  # 真实 token 值不出现在状态 API


def test_notify_on_terminal(factory, notify_spy):
    client, _ = make_fake_client(stats=ok_stats(checked=False), do=ok_do(),
                                 login=LoginResult(ok=True, token="T", user_id=5))
    plugin = factory(config={"username": "u", "password": "p", "notify": True}, client=client)
    plugin.run_once(trigger="manual")
    assert notify_spy and notify_spy[0][0] == "【聚影签到】"


def test_no_notify_when_disabled(factory, notify_spy):
    client, _ = make_fake_client(stats=ok_stats(checked=True))
    plugin = factory(config={"username": "u", "password": "p", "notify": False}, client=client)
    plugin.run_once(trigger="manual")
    assert notify_spy == []


def test_retry_budget_exhausted_pending_terminal(factory, monkeypatch):
    """pending 超出 retry_count → 终态落盘。"""
    client, _ = make_fake_client(stats=ok_stats(checked=False),
                                 do=ApiResult(ok=False, error="network: Timeout"))
    plugin = factory(config={"username": "u", "password": "p", "retry_count": 0}, client=client)
    plugin._store.save_session("PRESET", 1, __import__("time").time() + 3600)
    plugin._notify = lambda *a, **k: None
    result = plugin.run_once(trigger="manual")
    assert result["status"] == "pending"  # 额度 0 → 直接终态落盘
    assert plugin._store.get_latest()["status"] == "pending"


def test_onlyonce_consumed_on_run(factory):
    """onlyonce 开跑即回写 false（update_config 被调用）。"""
    calls = []

    class _WithUpdate:
        def update_config(self, cfg):
            calls.append(dict(cfg))
            return True

    client, _ = make_fake_client(stats=ok_stats(checked=True))
    plugin = factory(config={"username": "u", "password": "p", "onlyonce": True}, client=client)
    plugin.update_config = _WithUpdate().update_config
    plugin.run_once(trigger="manual")
    assert calls and calls[-1]["onlyonce"] is False
    assert plugin._config["onlyonce"] is False


def test_onlyonce_kept_when_absent(factory):
    """未开 onlyonce 时不触发回写。"""
    calls = []
    client, _ = make_fake_client(stats=ok_stats(checked=True))
    plugin = factory(config={"username": "u", "password": "p"}, client=client)
    plugin.update_config = lambda cfg: calls.append(cfg) or True
    plugin.run_once(trigger="manual")
    assert calls == []


def test_init_plugin_onlyonce_smoke(factory):
    """init_plugin onlyonce 分支冒烟：能注册单次任务（捕获 datetime 未导入类错误）。"""
    plugin = factory(config={"enabled": True, "onlyonce": True, "username": "u", "password": "p"})
    plugin.init_plugin({"enabled": True, "onlyonce": True, "username": "u", "password": "p"})
    assert plugin._services and plugin._services[0]["id"] == "JyingCheckinRunOnce"
    trigger = plugin._services[0]["trigger"]
    assert trigger.run_date is not None  # DateTrigger 带未来时间缓冲
