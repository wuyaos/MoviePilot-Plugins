"""Synthetic, secret-free fixtures: no production DOM certification."""
import asyncio
from dataclasses import replace
from types import SimpleNamespace
import pytest
from forum_under_test import ForumSignin
from forum_under_test.core.credentials import Credential, resolve
from forum_under_test.core.registry import get_site, get_registry
from forum_under_test.core.models import Evidence, SignStatus, SignResult
from forum_under_test.core.verification import normalize_evidence
from forum_under_test.core.runner import run_page, sanitize_sample
from forum_under_test.core.history import HistoryStore
from forum_under_test.integrations.ssdforum import SSDForum
from forum_under_test.integrations.yaowan import Yaowan
from forum_under_test.integrations.fengchao import Fengchao
from forum_under_test.http_client import HttpClient

DAY = "2026-10-20"

def page(status="未签到", uid="42", day=DAY):
    return f'''<html><script>{{"userId":42,"csrfToken":"synthetic"}}</script>
    <a title="访问我的空间" href="home.php?mod=space&amp;uid={uid}">test</a>
    <input name="formhash" value="synthetic"><button>今日签到</button><table>
    <tr><td><a href="home.php?mod=space&amp;uid={uid}">test</a></td>
    <td>{day}</td><td>{status}</td><td>大洋：17</td><td>累计签到：3 天</td></tr></table></html>'''

class Client:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.closed = False
    def request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item if hasattr(item, "text") else SimpleNamespace(text=item if isinstance(item, str) else "", json=lambda: item)
    def close(self):
        self.closed = True

@pytest.mark.parametrize("status,expected", [("已签到", "success"), ("未签到", "failed"), ("未知", "unconfirmed")])
def test_state_machine(status, expected):
    assert normalize_evidence(Evidence("签到", "42", DAY, status), "42", DAY).status == expected

@pytest.mark.parametrize("field,value", [("date", "2026-10-19"), ("button_text", ""), ("source", "other")])
def test_missing_or_conflicting_evidence(field, value):
    assert normalize_evidence(replace(Evidence("签到", "42", DAY, "已签到"), **{field: value}), "42", DAY).status == "unconfirmed"

@pytest.mark.parametrize("adapter_type", [SSDForum])
@pytest.mark.parametrize("submission", ["ok", RuntimeError("status_code=503"), TimeoutError()])
def test_unconditional_readback(adapter_type, submission):
    client = Client([page(), submission, page("已签到")])
    result = run_page(adapter_type(client), business_date=DAY)
    assert result.status == "success"
    assert [call[0] for call in client.calls] == ["GET", "POST", "GET"]
    if adapter_type is SSDForum:
        assert result.reward.current_balance == "17"
        assert "3" in result.reward.recent_activity
        payload = client.calls[1][2]["data"]
        assert payload["formhash"] == "synthetic"
        assert 6 <= len(payload["todaysay"]) <= 50
    else:
        assert client.calls[1][1] == "/api/checkin"
        assert client.calls[1][2]["headers"]["x-csrf-token"] == "synthetic"

@pytest.mark.parametrize("after,expected", [
    ("<html>签到成功</html>", "unconfirmed"),
    (TimeoutError(), "network_error"),
    (page("已签到", day="2026-10-19"), "failed"),
    (page("已签到", uid="43"), "failed"),
])
def test_readback_states(after, expected):
    item = after if isinstance(after, Exception) else after
    result = run_page(SSDForum(Client([page(), "ok", item])), business_date=DAY)
    assert result.status == expected

def test_ambiguous_ssd_message_not_already():
    client = Client(["<html>您今天已经签到过了或者签到时间还未开始</html>"])
    assert run_page(SSDForum(client), business_date=DAY).status == "unconfirmed"
    assert len(client.calls) == 1

def test_ssd_signed_message_without_row_confirms_already():
    signed_page = ('<html><a title="访问我的空间" href="home.php?mod=space&amp;uid=42">test</a>'
                   "<p>您今天已经签到过了</p></html>")
    client = Client([signed_page])
    result = run_page(SSDForum(client), business_date=DAY)
    assert result.status == "already"
    assert result.evidence.uid == "42" and result.evidence.date == DAY
    assert len(client.calls) == 1

def test_ssd_form_without_today_row_submits_once():
    fresh_page = ('<html><a title="访问我的空间" href="home.php?mod=space&amp;uid=42">test</a>'
                  '<input name="formhash" value="synthetic"><button>今日签到</button></html>')
    client = Client([fresh_page, "ok", page("已签到")])
    result = run_page(SSDForum(client), business_date=DAY)
    assert result.status == "success"
    assert [call[0] for call in client.calls] == ["GET", "POST", "GET"]

def test_readonly_and_already_do_not_submit():
    for readonly, state in [(True, "未签到"), (False, "已签到")]:
        client = Client([page(state)])
        run_page(SSDForum(client), readonly=readonly, business_date=DAY)
        assert len(client.calls) == 1

def api(data):
    return {"code": 0, "data": data}

@pytest.mark.parametrize("already,expected", [(True, "already"), (False, "success")])
def test_fengchao_api_evidence_and_readback(already, expected):
    client = Client([api({"alreadyCheckedIn": already, "reward": 0, "points": 17}), TimeoutError()])
    result = Fengchao(client).run()
    assert result.status == expected
    assert result.evidence.source == "api"
    assert result.reward.reported == "0"
    assert [call[1].split("/")[-1] for call in client.calls] == ["check-in", "status"]

def test_fengchao_unknown_not_success():
    assert Fengchao(Client([api({}), api({})])).run().status == "unconfirmed"

def test_sync_only_reads_and_preserves_zero():
    client = Client([api({"userId": "42"}), api({"account": {"uid": "42", "points": 0,
                      "unreadNotificationCount": 2}, "checkIn": {"currentStreak": 0}})])
    info, identity = Fengchao(client).sync()
    assert info["points"] == 0 and info["unreadNotificationCount"] == 2
    assert identity["userId"] == "42"
    assert all(call[0] == "GET" for call in client.calls)

def test_credentials_sources_and_ambiguity():
    site = {**get_site("yaowan"), "domain": "forum.invalid"}
    config = {"yaowan_cookie": "synthetic-local"}
    rows = [{"id": 1, "url": "https://forum.invalid", "cookie": "synthetic-managed"}]
    assert resolve(site, config, rows).source == "managed_site"
    assert resolve(site, config).source == "local_cookie"
    with pytest.raises(ValueError):
        resolve(site, config, rows * 2)
    assert resolve(get_site("fengchao"), {}) is None
    assert "synthetic" not in repr(Credential("local_cookie", "synthetic"))

@pytest.mark.parametrize("response", [None, SimpleNamespace(status_code=503)])
def test_http_error_is_not_str_plus_int(response):
    client = HttpClient("https://forum.invalid", Credential("local_cookie", "synthetic"))
    client.session = SimpleNamespace(request=lambda *a, **k: response)
    with pytest.raises(RuntimeError, match="no_response|HTTP 503"):
        client.request("POST", "/checkin")

def test_http_error_carries_server_message():
    response = SimpleNamespace(status_code=409, json=lambda: {"code": 409, "message": "快照批次冲突"})
    client = HttpClient("https://forum.invalid", Credential("local_cookie", "synthetic"))
    client.session = SimpleNamespace(request=lambda *a, **k: response)
    with pytest.raises(RuntimeError, match=r"HTTP 409: 快照批次冲突"):
        client.request("PUT", "/status")

def test_host_contract_and_gating():
    plugin = ForumSignin()
    plugin.init_plugin()
    assert plugin.get_render_mode() == ("vue", "dist/assets")
    assert plugin.get_form()[0] is None and plugin.get_page() is None
    assert all(route["auth"] == "bear" and route["endpoint"].__self__ is plugin and route["methods"] for route in plugin.get_api())
    assert len(get_registry()) == 3
    assert {site["id"]: site["login_capable"] for site in get_registry()} == {"fengchao": False, "yaowan": True, "ssdforum": False}
    assert plugin._execute("ssdforum")["data"]["status"] == "skipped"
    plugin.init_plugin({"enabled": True, "enabled_sites": ["ssdforum"]})
    assert plugin._execute("ssdforum")["data"]["status"] == "auth_failed"
    assert asyncio.run(plugin.api_history())["data"]["total"] == 2

def test_sync_scheduler_only_and_cleanup():
    plugin = ForumSignin()
    plugin.init_plugin({"enabled": True, "timed_update_enabled": True})
    assert [service["id"] for service in plugin.get_service()] == ["ForumSigninInfoUpdate"]
    instance_id = plugin._get("fengchao_instance_id")
    plugin.init_plugin({"enabled": True, "timed_update_enabled": True, "timed_update_cron": "bad"})
    assert plugin.get_service() == []
    assert plugin._get("fengchao_instance_id") == instance_id
    plugin.stop_service()
    assert not plugin.get_state()

def test_sync_failure_retains_cache_and_history(monkeypatch):
    plugin = ForumSignin()
    plugin.init_plugin({"enabled": True})
    plugin._save("fengchao_user_info", {"points": 17})
    plugin._save("fengchao_user_info_updated_at", "previous")
    client = Client([TimeoutError(), TimeoutError()])
    monkeypatch.setattr(plugin, "_client", lambda site: client)
    assert plugin.update_info()["success"] is False
    assert plugin._get("fengchao_user_info_updated_at") == "previous"
    assert plugin._get("fengchao_user_info") == {"points": 17}
    assert plugin._history.list()["total"] == 0
    assert client.closed

def test_history_pagination_and_status():
    store = HistoryStore()
    store.append(SignResult(SignStatus.ALREADY, site_id="ssdforum"))
    assert store.list()["items"][0]["status"] == "signed"
    assert store.today_counts()["signed"] == 1


@pytest.mark.parametrize("status,expected", [
    ({}, False),
    ({"account": {"uid": "42", "points": 17}}, True),
    ({"account": {"points": 17}, "checkIn": {"currentStreak": 3}}, False),
    ({"account": {"uid": "42"}, "checkIn": {"currentStreak": 3}}, True),
])
def test_sync_uses_defaults_when_business_fields_are_missing(monkeypatch, status, expected):
    plugin = ForumSignin()
    plugin.init_plugin({"enabled": True})
    client = Client([TimeoutError(), api(status)])
    monkeypatch.setattr(plugin, "_client", lambda site: client)
    response = asyncio.run(plugin.api_update_info())
    assert response["success"] is expected
    if expected:
        assert response["data"]["points"] == status.get("account", {}).get("points", 0)


def test_sync_empty_status_uses_cached_identity_business_values(monkeypatch):
    plugin = ForumSignin()
    plugin.init_plugin({"enabled": True})
    identity = {"userId": "42", "account": {"uid": "42", "points": 17}}
    plugin._save("_fengchao_identity", identity)
    plugin._save("fengchao_user_info", {"uid": "42", "points": 17})
    plugin._save("fengchao_user_info_updated_at", "previous")
    client = Client([api(identity), api({})])
    monkeypatch.setattr(plugin, "_client", lambda site: client)
    assert plugin.update_info()["success"] is True
    assert plugin._get("fengchao_user_info")["uid"] == "42"
    assert plugin._get("fengchao_user_info_updated_at") != "previous"
    assert plugin._get("_fengchao_identity") == identity


@pytest.mark.parametrize("readonly", [False, True])
def test_execute_close_error_keeps_history_and_api_result(monkeypatch, readonly):
    plugin = ForumSignin()
    plugin.init_plugin({"enabled": True, "enabled_sites": ["fengchao"]})
    client = Client([api({"alreadyCheckedIn": False, "reward": 0}), api({})])
    def broken_close():
        raise RuntimeError("synthetic close failure")
    client.close = broken_close
    monkeypatch.setattr(plugin, "_client", lambda site: client)
    endpoint = plugin.api_verify_site if readonly else plugin.api_signin_by_domain
    response = asyncio.run(endpoint("fengchao"))
    assert response["success"] is True
    assert response["data"]["site_id"] == "fengchao"
    assert response["data"]["metadata"]["trigger"] == ("verify" if readonly else "manual")
    records = plugin._history.list()
    assert response["data"]["status"] == ("unconfirmed" if readonly else "success")
    assert records["total"] == 1
    assert records["items"][0]["site"] == "fengchao"
    assert not plugin._locks["fengchao"].locked()


@pytest.mark.parametrize("close_raises", [False, True])
def test_sync_cached_identity_and_zero_values_commit(monkeypatch, close_raises):
    plugin = ForumSignin()
    plugin.init_plugin({"enabled": True})
    plugin._save("_fengchao_identity", {"account": {"uid": "42"}})
    plugin._save("fengchao_user_info_updated_at", "previous")
    client = Client([TimeoutError(), api({"account": {"points": 0},
                                         "checkIn": {"currentStreak": 0}})])
    if close_raises:
        def broken_close():
            raise RuntimeError("synthetic close failure")
        client.close = broken_close
    monkeypatch.setattr(plugin, "_client", lambda site: client)
    response = asyncio.run(plugin.api_update_info())
    assert response["success"] is True
    assert response["data"]["uid"] == "42"
    assert response["data"]["points"] == 0
    assert response["data"]["currentStreak"] == 0
    assert plugin._get("fengchao_user_info") == response["data"]
    assert plugin._get("fengchao_user_info_updated_at") != "previous"
    assert plugin._get("fengchao_sync_status")["success"] is True
    assert not plugin._locks["fengchao"].locked()
    assert plugin._history.list()["total"] == 0


def test_yaowan_account_login_and_cookie_refresh():
    credential = Credential("local_cookie", "", username="synthetic-user", password="synthetic-password")
    initial = SimpleNamespace(text='{"csrfToken":"initial"}', cookies={"flarum_session":"session-1"})
    login = SimpleNamespace(text="{}", cookies={"flarum_remember":"remember-1", "flarum_session":"session-2"})
    home = SimpleNamespace(text=page(), cookies={})
    unauth = SimpleNamespace(text='{"userId":0}', cookies={})
    client = Client([unauth, initial, login, home])
    client.credential = credential
    adapter = Yaowan(client)
    client.responses.append({"data": {"id": "42", "attributes": {"canCheckin": True, "lastCheckinTime": ""}}})
    assert adapter.fetch_page().startswith(home.text)
    assert client.credential.value == "flarum_remember=remember-1; flarum_session=session-2"
    assert [(call[0], call[1]) for call in client.calls] == [("GET", "/"), ("GET", "/"), ("POST", "/login"), ("GET", "/"), ("GET", "/api/users/42")]
    assert "synthetic-password" not in repr(client.credential)


def test_registry_declares_dynamic_credential_fields():
    sites = get_registry()
    assert {site["id"] for site in sites} == {"fengchao", "yaowan", "ssdforum"}
    yaowan = next(site for site in sites if site["id"] == "yaowan")
    assert {field["key"] for field in yaowan["credential"]["fields"]} == {
        "yaowan_cookie", "yaowan_username", "yaowan_password"
    }


def test_clean_cache_preserves_history():
    plugin = ForumSignin()
    plugin.init_plugin({"enabled": True})
    plugin._history.append(SignResult(SignStatus.SUCCESS, site_id="yaowan"))
    for key in ("identity.yaowan", "_fengchao_identity", "fengchao_user_info", "icon.cache",
                "sample.yaowan.html", "sample.ssdforum.html"):
        plugin._save(key, {"synthetic": True})
    result = plugin.clean_cache()
    assert result["success"] is True
    assert all(plugin._get(key) is None for key in ("identity.yaowan", "_fengchao_identity", "fengchao_user_info",
                                                       "icon.cache", "sample.yaowan.html", "sample.ssdforum.html"))
    assert plugin._history.list()["total"] == 1
    assert {route["path"] for route in plugin.get_api()} >= {"/run_once", "/clean_cache"}

def test_cookiecloud_fallback_when_local_cookie_missing():
    """本地 Cookie 缺失时 _client 走 CookieCloud 并回写配置；已有本地 Cookie 不触发。"""
    from unittest.mock import patch
    from forum_under_test.core.credentials import cookiecloud_cookie

    plugin = ForumSignin()
    plugin.get_data = lambda key=None: {}
    plugin.save_data = lambda key, value: None
    plugin.update_config = lambda config: None
    site = get_site("ssdforum")
    assert site is not None

    calls = []
    def fake_cookiecloud(url):
        calls.append(url)
        return "synthetic=1"

    with patch("forum_under_test.cookiecloud_cookie", side_effect=fake_cookiecloud):
        credential = plugin._client(site).credential
    assert calls == [site["adapter"].base]
    assert credential.source == "cookiecloud" and credential.value == "synthetic=1"
    assert plugin._config.get("ssdforum_cookie") == "synthetic=1"

    plugin._config["ssdforum_cookie"] = "local=1"
    calls.clear()
    with patch("forum_under_test.cookiecloud_cookie", side_effect=fake_cookiecloud):
        credential = plugin._client(site).credential
    assert calls == [] and credential.source == "local_cookie" and credential.value == "local=1"


def test_cookiecloud_unavailable_keeps_auth_failed():
    from unittest.mock import patch
    plugin = ForumSignin()
    plugin.get_data = lambda key=None: {}
    plugin.save_data = lambda key, value: None
    plugin.update_config = lambda config: None
    site = get_site("ssdforum")
    with patch("forum_under_test.cookiecloud_cookie", return_value=""):
        assert plugin._client(site) is None


def test_run_once_aggregates_results_and_flushes_notify():
    """立即运行：全链路跑通（_execute_with_retry 操作 SignResult），一轮一条聚合通知。"""
    from forum_under_test import ForumSignin
    from forum_under_test.core.models import SignResult, SignStatus
    from unittest.mock import patch

    plugin = ForumSignin()
    plugin.get_data = lambda key=None: {}
    plugin.save_data = lambda key, value: None
    plugin.update_config = lambda config: None
    posted = []
    plugin.post_message = lambda **kwargs: posted.append(kwargs)
    plugin._config["enabled_sites"] = ["ssdforum"]
    plugin._config["notify"] = True

    def fake_result(domain, readonly=False, trigger=None, record=True):
        r = SignResult(SignStatus.SUCCESS, "连续签到 5 天")
        r.site_id = "ssdforum"
        plugin._history.append(r)
        # 真实 _execute_result 尾部会把结果放进通知缓冲（此处一并模拟）。
        plugin._notify_buffer.append(("ssdforum", r))
        return r

    with patch.object(ForumSignin, "_execute_result", side_effect=fake_result):
        response = plugin.run_once()
    assert response["success"] and len(response["data"]) == 1
    assert "论坛：SSD" in posted[0]["text"] and "✅ 签到成功" in posted[0]["text"]
    assert len(posted) == 1  # 一轮一条


def test_ssdforum_legacy_cookie_config_migrates():
    plugin = ForumSignin()
    persisted = []
    plugin.update_config = lambda config: persisted.append(config.copy())
    plugin._config = {"ssdforumsignin_cookie": "synthetic-cookie", "ssdforum_cookie": ""}
    plugin._migrate_legacy_invites()
    assert plugin._config["ssdforum_cookie"] == "synthetic-cookie"
    assert "ssdforumsignin_cookie" not in plugin._config
    assert persisted[-1]["ssdforum_cookie"] == "synthetic-cookie"


@pytest.mark.parametrize("success,state", [(True, "🔄 同步完成"), (False, "❌ 同步失败")])
def test_sync_api_notifies_result(monkeypatch, success, state):
    plugin = ForumSignin()
    plugin._config["notify"] = True
    posted = []
    plugin.post_message = lambda **kwargs: posted.append(kwargs)
    monkeypatch.setattr(plugin, "update_info", lambda: {
        "success": success, "message": "synthetic-result" if not success else ""
    })

    response = asyncio.run(plugin.api_update_info())

    assert response["success"] is success
    assert len(posted) == 1
    assert posted[0]["title"] == "【论坛签到】"
    assert "论坛：蜂巢" in posted[0]["text"]
    assert f"状态：{state}" in posted[0]["text"]
    assert "时间：" in posted[0]["text"]
    if not success:
        assert "说明：synthetic-result" in posted[0]["text"]


def test_readback_sample_is_sanitized_and_latest_callback():
    raw = '<html><head><title>签到页</title><script>cookie="secret-cookie"</script></head><body><input name="formhash" value="secret-formhash"><div>签到</div></body></html>'
    sample = sanitize_sample(raw)
    assert '<script' not in sample and 'secret-cookie' not in sample
    assert 'secret-formhash' not in sample and '[redacted]' in sample
    assert '<title>签到页</title>' in sample


def test_fengchao_sync_reads_identity_then_status():
    client = Client([api({'userId': '42', 'account': {'uid': '42'}}),
                     api({'account': {'uid': '42', 'displayName': 'synthetic-user', 'points': 18},
                          'checkIn': {'currentStreak': 4}})])
    info, identity = Fengchao(client).sync()
    assert [call[1] for call in client.calls] == ['/api/integrations/moviepilot/v1/me', '/api/integrations/moviepilot/v1/status']
    assert info['uid'] == '42' and info['points'] == 18 and info['currentStreak'] == 4
    assert identity['userId'] == '42'


def test_yaowan_api_state_confirms_today_without_dom_checkin_marker():
    api_state = {"data": {"id": "42", "attributes": {
        "canCheckin": False, "lastCheckinTime": DAY + " 08:30:00",
        "totalContinuousCheckIn": 12}}}
    client = Client([page("未签到"), api_state])
    result = Yaowan(client).run(readonly=True, business_date=DAY)
    assert result.status == "already"
    assert result.evidence.source == "api"
    assert [call[1] for call in client.calls] == ["/", "/api/users/42"]


def test_yaowan_submit_once_then_recheck_by_api_state():
    api_before = {"data": {"id": "42", "attributes": {"canCheckin": True, "lastCheckinTime": ""}}}
    api_after = {"data": {"id": "42", "attributes": {"canCheckin": False, "lastCheckinTime": DAY + " 09:00:00"}}}
    client = Client([page("未签到"), api_before, {}, page("未签到"), api_after])
    result = Yaowan(client).run(business_date=DAY)
    assert result.status == "success"
    assert result.evidence.source == "api"
    assert [call[1] for call in client.calls] == ["/", "/api/users/42", "/api/checkin", "/", "/api/users/42"]


def test_yaowan_session_rotation_is_absorbed_before_submit():
    """服务器轮换 flarum_session 后，提交请求必须带新 session（csrf 配对）。"""
    rotated = page("未签到")
    home = SimpleNamespace(text=rotated, cookies={"flarum_session": "session-rotated"})
    api_state = {"data": {"id": "42", "attributes": {"canCheckin": True, "lastCheckinTime": ""}}}
    api_after = {"data": {"id": "42", "attributes": {"canCheckin": False, "lastCheckinTime": DAY + " 09:00:00"}}}
    client = Client([home, api_state, {}, page("已签到"), api_after])
    adapter = Yaowan(client)
    client.credential = Credential(source="local_cookie", value="flarum_remember=r1; flarum_session=stale")
    result = adapter.run(business_date=DAY)
    assert result.status == "success"
    # 提交时 HttpClient 用 credential.value 作 Cookie 头；轮换 session 必须在提交前同步进 credential
    assert "flarum_remember=r1" in adapter._credential().value
    assert "flarum_session=session-rotated" in adapter._credential().value
    # 合并语义：其它键保留，仅替换 flarum_session；重复同步幂等
    adapter._sync_session(SimpleNamespace(text="", cookies={"flarum_session": "session-rotated"}))
    assert adapter._credential().value == "flarum_remember=r1; flarum_session=session-rotated"


def test_yaowan_submit_error_is_surfaced_when_recheck_still_unsigned():
    api_state = {"data": {"id": "42", "attributes": {"canCheckin": True, "lastCheckinTime": ""}}}
    client = Client([page("未签到"), api_state, RuntimeError("HTTP 400: csrf_token_mismatch"), page("未签到"), api_state])
    result = Yaowan(client).run(business_date=DAY)
    assert result.status == "failed"
    assert "提交响应" in result.message and "csrf_token_mismatch" in result.message

def test_ssdforum_signed_message_is_a_valid_marker_when_record_is_present():
    sample = page("未知")
    sample = sample.replace("<input name=\"formhash\" value=\"synthetic\">", "<input name=\"formhash\" value=\"synthetic\"><p>您今天已经签到过了或者签到时间还未开始</p>")
    evidence = SSDForum.verifier.parse(sample, "42", DAY)
    assert evidence.status == "已签到"


def test_fengchao_sync_prefers_me_status_and_defaults_missing_values():
    client = Client([api({"userId": "3161", "status": {
        "account": {"uid": "3161", "username": "synthetic-user", "points": 83},
        "checkIn": {"checkedInToday": True, "currentStreak": 24, "maxStreak": 46,
                    "lastCheckInDate": "2026-10-24"}}}), api({"account": None, "checkIn": None})])
    info, _ = Fengchao(client).sync()
    assert info["uid"] == "3161" and info["points"] == 83
    assert info["currentStreak"] == 24 and info["maxStreak"] == 46
    assert info["checkedInToday"] is True


def test_network_connection_failure_is_retryable_network_error():
    result = run_page(SSDForum(Client([ConnectionError("synthetic connection failure")])), business_date=DAY)
    assert result.status == "network_error"


def test_http_status_error_is_not_classified_as_network_error():
    error = RuntimeError("status_code=503")
    result = run_page(SSDForum(Client([error])), business_date=DAY)
    assert result.status == "unconfirmed"


def test_invalid_local_cookie_refreshes_cookiecloud_once(monkeypatch):
    from unittest.mock import patch
    from forum_under_test.core.credentials import Credential

    plugin = ForumSignin()
    plugin.init_plugin({"enabled": True, "enabled_sites": ["ssdforum"], "ssdforum_cookie": "old=1"})
    plugin.get_data = lambda key=None: {}
    plugin.save_data = lambda key, value: None
    def assert_locked(config):
        assert plugin._config_lock._is_owned()
    plugin.update_config = assert_locked
    clients = []
    class FakeClient:
        def __init__(self, base, credential, *args):
            self.credential = credential
            self.closed = False
            clients.append(self)
        def close(self):
            self.closed = True
    results = iter([SignResult(SignStatus.AUTH_FAILED, "expired"), SignResult(SignStatus.SUCCESS, "ok")])
    monkeypatch.setattr("forum_under_test.HttpClient", FakeClient)
    monkeypatch.setattr("forum_under_test.run_page", lambda *args, **kwargs: next(results))
    with patch("forum_under_test.cookiecloud_cookie", return_value="new=1") as cookiecloud:
        result = plugin._execute_result("ssdforum")
    assert result.status == SignStatus.SUCCESS
    assert cookiecloud.call_count == 1
    assert [client.credential.value for client in clients] == ["old=1", "new=1"]
    assert clients[0].closed and clients[1].closed
    assert plugin._config["ssdforum_cookie"] == "new=1"
    assert not plugin._locks["ssdforum"].locked()


def test_execute_result_network_error_is_not_http_status_error(monkeypatch):
    from unittest.mock import patch
    plugin = ForumSignin()
    plugin.init_plugin({"enabled": True, "enabled_sites": ["ssdforum"], "ssdforum_cookie": "synthetic=1"})
    client = Client([])
    client.credential = Credential("local_cookie", "synthetic=1")
    monkeypatch.setattr(plugin, "_client", lambda site: client)
    with patch("forum_under_test.run_page", return_value=SignResult(SignStatus.NETWORK_ERROR, "connection")):
        result = plugin._execute_result("ssdforum")
    assert result.status == SignStatus.NETWORK_ERROR
    assert result.status != SignStatus.UNCONFIRMED


def test_favicon_link_rel_href_order_is_irrelevant(monkeypatch):
    import sys
    from types import ModuleType
    calls = []
    class Response:
        status_code = 200
        headers = {"Content-Type": "image/png"}
        content = b"x" * 32
        def __init__(self, text=""):
            self.text = text
    class RequestUtils:
        def __init__(self, **kwargs):
            pass
        def get_res(self, url, **kwargs):
            calls.append(url)
            return Response('<link href="/custom-icon.png" rel="shortcut icon">') if url.endswith("/") else Response()
    network = ModuleType("app.sdk.network")
    network.RequestUtils = RequestUtils
    monkeypatch.setitem(sys.modules, "app.sdk.network", network)
    result = ForumSignin()._resolve_favicon("https://forum.invalid")
    assert result.startswith("data:image/png;base64,")
    assert calls == ["https://forum.invalid/", "https://forum.invalid/custom-icon.png"]


def test_init_removes_legacy_nested_fengchao_cache():
    plugin = ForumSignin()
    saved = []
    plugin.get_data = lambda key=None: {"data": {"attributes": {"points": 8}}} if key == "fengchao_user_info" else None
    plugin.save_data = lambda key, value: saved.append((key, value))
    plugin.init_plugin({"enabled": False})
    assert ("fengchao_user_info", None) in saved


def test_native_wording_notes_flow_to_message():
    from forum_under_test.verifiers.fengchao import verify as fc_verify
    from forum_under_test.core.verification import normalize_evidence

    res = fc_verify({"userId": "3161", "points": 83,
                     "checkIn": {"checkedInToday": True, "lastCheckinTime": DAY + " 07:02:00",
                                 "currentStreak": 24}})
    assert res.message == "连续签到24天"

    api_state = {"data": {"id": "42", "attributes": {
        "canCheckin": False, "lastCheckinTime": DAY + " 08:30:00", "totalContinuousCheckIn": 12}}}
    result = Yaowan(Client([page("未签到"), api_state])).run(readonly=True, business_date=DAY)
    assert result.message == "已签到 12 天"

    sample = page("未知").replace('<input name="formhash" value="synthetic">',
                                  '<input name="formhash" value="synthetic">'
                                  '<p>您今天已经签到过了或者签到时间还未开始</p>'
                                  '<p>您本月已累计签到:22 天</p><p>您上次签到时间:2026-10-24 07:02</p>')
    ev = SSDForum.verifier.parse(sample, "42", DAY)
    assert ev.note == "已累计签到22天，上次签到 2026-10-24"
    assert normalize_evidence(ev, "42", DAY).message == "已累计签到22天，上次签到 2026-10-24"


def test_verify_site_routes_fengchao_to_sync(monkeypatch):
    import asyncio
    plugin = ForumSignin()
    called = {}

    async def fake_update_info(domain="fengchao.chat"):
        called["domain"] = domain
        return plugin._response({"uid": "3161"})

    plugin.api_update_info = fake_update_info
    monkeypatch.setattr(plugin, "_execute",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("execute called")))
    result = asyncio.run(plugin.api_verify_site("fengchao.chat"))
    assert called.get("domain") == "fengchao.chat"
    assert result.get("success") is True
