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
from forum_under_test.core.runner import run_page
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

@pytest.mark.parametrize("field,value", [("uid", "43"), ("date", "2026-10-19"), ("button_text", ""), ("source", "api")])
def test_missing_or_conflicting_evidence(field, value):
    assert normalize_evidence(replace(Evidence("签到", "42", DAY, "已签到"), **{field: value}), "42", DAY).status == "unconfirmed"

@pytest.mark.parametrize("adapter_type", [Yaowan, SSDForum])
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

@pytest.mark.parametrize("after", ["<html>签到成功</html>", TimeoutError(), page("已签到", day="2026-10-19"), page("已签到", uid="43")])
def test_readback_unconfirmed(after):
    assert run_page(SSDForum(Client([page(), "ok", after])), business_date=DAY).status == "unconfirmed"

def test_ambiguous_ssd_message_not_already():
    client = Client(["<html>您今天已经签到过了或者签到时间还未开始</html>"])
    assert run_page(SSDForum(client), business_date=DAY).status == "unconfirmed"
    assert len(client.calls) == 1

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
    with pytest.raises(RuntimeError, match="no_response|status_code=503"):
        client.request("POST", "/checkin")

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


@pytest.mark.parametrize("status", [
    {},
    {"account": {"uid": "42", "points": 17}},
    {"account": {"points": 17}, "checkIn": {"currentStreak": 3}},
    {"account": {"uid": "42"}, "checkIn": {"currentStreak": 3}},
])
def test_sync_invalid_business_data_preserves_cache(monkeypatch, status):
    plugin = ForumSignin()
    plugin.init_plugin({"enabled": True})
    previous = {"uid": "42", "points": 17, "currentStreak": 3}
    plugin._save("fengchao_user_info", previous)
    plugin._save("fengchao_user_info_updated_at", "previous")
    client = Client([TimeoutError(), api(status)])
    monkeypatch.setattr(plugin, "_client", lambda site: client)
    response = asyncio.run(plugin.api_update_info())
    assert response["success"] is False and response["message"] == "sync_unconfirmed"
    assert plugin._get("fengchao_user_info") == previous
    assert plugin._get("fengchao_user_info_updated_at") == "previous"
    assert plugin._get("fengchao_sync_status")["message"] == "sync_unconfirmed"
    assert plugin._history.list()["total"] == 0
    assert client.closed and not plugin._locks["fengchao"].locked()


def test_sync_empty_status_cannot_reuse_stale_business_values(monkeypatch):
    plugin = ForumSignin()
    plugin.init_plugin({"enabled": True})
    identity = {"userId": "42", "account": {"uid": "42", "points": 17}}
    plugin._save("_fengchao_identity", identity)
    plugin._save("fengchao_user_info", {"uid": "42", "points": 17})
    plugin._save("fengchao_user_info_updated_at", "previous")
    client = Client([api(identity), api({})])
    monkeypatch.setattr(plugin, "_client", lambda site: client)
    assert plugin.update_info()["success"] is False
    assert plugin._get("fengchao_user_info") == {"uid": "42", "points": 17}
    assert plugin._get("fengchao_user_info_updated_at") == "previous"
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
    assert adapter.fetch_page() == home.text
    assert client.credential.value == "flarum_remember=remember-1; flarum_session=session-2"
    assert [(call[0], call[1]) for call in client.calls] == [("GET", "/"), ("GET", "/"), ("POST", "/login"), ("GET", "/")]
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
    for key in ("identity.yaowan", "_fengchao_identity", "fengchao_user_info"):
        plugin._save(key, {"synthetic": True})
    result = plugin.clean_cache()
    assert result["success"] is True
    assert all(plugin._get(key) is None for key in ("identity.yaowan", "_fengchao_identity", "fengchao_user_info"))
    assert plugin._history.list()["total"] == 1
    assert {route["path"] for route in plugin.get_api()} >= {"/run_once", "/clean_cache"}
