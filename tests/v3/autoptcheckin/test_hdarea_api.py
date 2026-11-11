"""好大官方 REST API 双通道：API Key 分类 + run_native 分流与无 Key 回退。

只做离线 stub；request 注入替代网络，不访问 hdarea.club。
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / 'plugins.v3'))

from autoptcheckin.core import native
from autoptcheckin.core.credentials import Credential
from autoptcheckin.core.models import LoginPage, SignResult, SignStatus
from autoptcheckin.core.registry import get_native_module
from autoptcheckin.core.runner import SignRunner
from autoptcheckin.core.sitemodel import SignContext
from autoptcheckin.integrations import hdarea


class StubResponse:
    def __init__(self, status_code, text):
        self.status_code = status_code
        self.text = text


def envelope(success=True, message="OK", code=0):
    return StubResponse(200, json.dumps(
        {"success": success, "code": code, "http_code": 200, "message": message, "data": {}}))


class Site:
    id = "hdarea"
    name = "好大"
    url = "https://hdarea.club/"


def make_request(responses):
    """按调用顺序返回 stub 响应并记录调用。"""
    calls = []

    def request(method, url, *, headers, payload):
        calls.append({"method": method, "url": url, "headers": headers, "payload": payload})
        item = responses[len(calls) - 1]
        if isinstance(item, Exception):
            raise item
        return item
    return request, calls


def run(**kwargs):
    kwargs.setdefault("config", {"hdarea_apikey": "k" * 32})
    kwargs.setdefault("info", {})
    return hdarea.run_hdarea_api(Site(), kwargs.pop("info"), **kwargs)


# ---- 集成分类 ----

def test_sign_success_uses_api_key_header_and_post():
    request, calls = make_request([envelope(True, "签到成功")])
    result = run(request=request)
    assert result.status == SignStatus.SUCCESS
    assert calls[0]["method"] == "POST"
    assert calls[0]["url"] == "https://hdarea.club/api/v1/user/signin"
    assert calls[0]["headers"]["X-API-Key"] == "k" * 32
    assert calls[0]["payload"] == {}


def test_sign_already_requires_declared_marker_not_any_false():
    request, _ = make_request([envelope(False, "今日已签到，请勿重复提交")])
    assert run(request=request).status == SignStatus.ALREADY
    request, _ = make_request([envelope(False, "签到活动未开放")])
    assert run(request=request).status == SignStatus.UNCONFIRMED


def test_sign_auth_rate_and_transport_shapes():
    request, _ = make_request([StubResponse(401, '{"message":"invalid api key"}')])
    result = run(request=request)
    assert result.status == SignStatus.AUTH_FAILED and "401" in result.message
    request, _ = make_request([StubResponse(429, "")])
    assert run(request=request).status == SignStatus.PROTOCOL_PENDING
    request, _ = make_request([StubResponse(200, "<html>cloudflare</html>")])
    result = run(request=request)
    assert result.status == SignStatus.UNCONFIRMED and "非 JSON" in result.message
    request, _ = make_request([ConnectionError("boom")])
    assert run(request=request).status == SignStatus.NETWORK_ERROR


def test_read_only_profiles_never_posts_signin():
    request, calls = make_request([envelope(True, "OK")])
    result = run(request=request, read_only=True)
    assert result.status == SignStatus.UNCONFIRMED and "只读核验" in result.message
    assert calls[0]["method"] == "GET"
    assert calls[0]["url"].endswith("api/v1/user/profile")
    assert all(call["method"] != "POST" for call in calls)


def test_missing_key_is_skipped_without_request():
    request, calls = make_request([])
    result = run(request=request, config={}, info={})
    assert result.status == SignStatus.SKIPPED and calls == []


# ---- run_native 分流 ----

@pytest.fixture
def storage():
    data = {"cookies.table": {}}
    runner = SignRunner()
    runner.get_data = data.get
    runner.save_data = data.__setitem__
    return runner, data


def stub_hdarea_site():
    return SimpleNamespace(id="hdarea", name="好大", url="https://hdarea.club/",
                           signin=lambda ctx: pytest.fail("API 模式不应执行 Cookie 表单签到"))


def test_run_native_dispatches_to_api_when_key_configured(storage, monkeypatch):
    runner, data = storage
    calls = []

    def fake_run(site, info, *, config, cancel, read_only, request=None):
        calls.append({"config": config, "read_only": read_only})
        return SignResult(SignStatus.SUCCESS, "签到成功（API）")

    monkeypatch.setattr("autoptcheckin.integrations.hdarea.run_hdarea_api", fake_run)
    result = native.run_native(runner, stub_hdarea_site(), {"cookie": "session=x"},
                               config={"hdarea_apikey": "k" * 32})
    assert result.status == SignStatus.SUCCESS
    assert result.metadata["transport"] == "api"
    assert calls and calls[0]["config"]["hdarea_apikey"] == "k" * 32
    assert data.get("cookies.table", {}).get("hdarea") is None  # API 通道不写 Cookie 表


def test_run_native_falls_back_to_cookie_form_without_key(storage, monkeypatch):
    runner, data = storage
    monkeypatch.setattr("autoptcheckin.integrations.hdarea.run_hdarea_api",
                        lambda *a, **k: pytest.fail("未配置 Key 不应走 API 通道"))
    monkeypatch.setattr(native, "native_cloak_client", lambda site, http, info, config: http)
    seen = {"get": [], "post": []}
    pages = [LoginPage('<span id="sign_in_done" style="display: none">未签到</span>', "https://hdarea.club/"),
             LoginPage('<h2>此次签到您获得 100 魔力</h2>', "https://hdarea.club/")]

    class Http:
        cookies = {'session': 'managed'}

        def get(self, url):
            seen["get"].append(url)
            return pages[len(seen["get"]) - 1] if len(seen["get"]) <= len(pages) else pages[-1]

        def post(self, url, *, data=None, headers=None, referer=None, allow_redirects=None):
            seen["post"].append(url)
            return LoginPage('<h2>此次签到您获得 100 魔力</h2>', url)

        def close(self):
            pass

    def factory(site, credential, info, locks, stop):
        return SignContext(site.id, credential, Http())

    from autoptcheckin.sites.native import generic
    site_cls = next(cls for cls in generic.build_generic_sites() if cls.id == "hdarea")
    result = native.run_native(runner, site_cls(), {"cookie": "session=managed"},
                               config={}, context_factory=factory)
    assert result.status in (SignStatus.SUCCESS, SignStatus.ALREADY)
    assert any(url.endswith("sign_in.php") for url in seen["post"])
    assert result.metadata.get("transport") != "api"
    entry = (data.get("cookies.table") or {}).get("hdarea")
    assert entry and entry["cookie"] == "session=managed"  # 回退通道照常回写 Cookie 表


# ---- 登录轨 API 探活（配置 Key 后分流） ----

def verify(**kwargs):
    kwargs.setdefault("config", {"hdarea_apikey": "k" * 32})
    kwargs.setdefault("info", {})
    return hdarea.verify_hdarea_login(Site(), kwargs.pop("info"), **kwargs)


def profile_envelope(username="wuyaos"):
    return StubResponse(200, json.dumps(
        {"success": True, "code": 0, "http_code": 200, "message": "OK",
         "data": {"username": username}, "timestamp": 0}))


def test_verify_login_success_reports_username():
    request, calls = make_request([profile_envelope("wuyaos")])
    result = verify(request=request)
    assert result.status.value == "login_ok"
    assert "wuyaos" in result.message and "探活" in result.message
    assert calls[0]["method"] == "GET" and calls[0]["url"].endswith("api/v1/user/profile")
    assert calls[0]["headers"]["X-API-Key"] == "k" * 32


def test_verify_login_auth_and_transport_shapes():
    request, _ = make_request([StubResponse(401, '{"message":"invalid"}')])
    assert verify(request=request).status.value == "auth_failed"
    request, _ = make_request([ConnectionError("boom")])
    assert verify(request=request).status.value == "unconfirmed"
    request, _ = make_request([StubResponse(429, "")])
    assert verify(request=request).status.value == "unconfirmed"


def test_verify_without_key_never_requests():
    request, calls = make_request([])
    result = verify(request=request, config={})
    assert result.status.value == "unconfirmed" and calls == []


def test_run_native_login_dispatches_to_api_probe(storage, monkeypatch):
    runner, data = storage
    seen = {}

    def fake_verify(site, info, *, config, request=None):
        seen["config"] = config
        from autoptcheckin.core.models import LoginResult, LoginStatus
        return LoginResult(LoginStatus.LOGIN_OK, "API 探活成功：wuyaos")

    monkeypatch.setattr("autoptcheckin.integrations.hdarea.verify_hdarea_login", fake_verify)
    from autoptcheckin.core.models import LoginResult, LoginStatus
    result = native.run_native_login(runner, stub_hdarea_site(), {"cookie": "session=x"},
                                     config={"hdarea_apikey": "k" * 32})
    assert isinstance(result, LoginResult) and result.status == LoginStatus.LOGIN_OK
    assert result.metadata["transport"] == "api"
    assert seen["config"]["hdarea_apikey"] == "k" * 32


def test_config_keys_and_defaults_declare_hdarea_apikey():
    from autoptcheckin import AutoPtCheckin
    defaults = json.loads((Path(__file__).parents[3] / "plugins.v3" / "autoptcheckin" /
                           "config_defaults.json").read_text(encoding="utf-8"))
    assert "hdarea_apikey" in AutoPtCheckin.SITE_KEYS
    assert defaults["hdarea_apikey"] == ""
    source = (Path(__file__).parents[3] / "frontend.v3" / "autoptcheckin" / "src" /
              "Config.vue").read_text(encoding="utf-8")
    assert "hdarea_apikey" in source and "credentialFields" in source
