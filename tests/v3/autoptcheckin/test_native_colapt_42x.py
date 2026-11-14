"""ColaPT native 适配契约：探测跳过、CSRF 现取、三态回执（4.2.x）。"""
import json
import sys
from pathlib import Path
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).parents[3] / "plugins.v3"))
from autoptcheckin.core.credentials import Credential
from autoptcheckin.core.models import LoginPage
from autoptcheckin.core.sitemodel import SignContext
from autoptcheckin.sites.native.colapt import Colapt


class Http:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(("get", url))
        return self._next()

    def post(self, url, *, json=None, headers=None, data=None):
        self.calls.append(("post", url, json, headers))
        return self._next()

    def retain_cookies(self, names):
        pass

    def _next(self):
        item = self.responses.pop(0)
        if isinstance(item, LoginPage):
            return item
        if isinstance(item, str):
            return LoginPage(item, "https://www.colapt.com/", 200)
        text, code = item
        return LoginPage(text, "https://www.colapt.com/", code)


def ctx():
    return SignContext("colapt", Credential("cookie", "fixture"), Http([]))


def me_ok(csrf="c" * 64):
    return json.dumps({"id": 492, "username": "fixture", "session": {"csrf_token": csrf}})


def cola_week(amount, today=None, daily_reward=None):
    rules = {"checkin_min": 1, "checkin_max": 30}
    if daily_reward is not None:
        rules["daily_login_reward"] = daily_reward
    payload = {"week": {"checkin_amount": amount, "next_start": "2026-11-02T00:00:00+08:00"},
               "rules": rules}
    if today is not None:
        payload["today"] = today
    return json.dumps(payload)


def test_probe_signed_skips_post_zero_side_effect():
    site = Colapt()
    http = Http([me_ok(), (cola_week(14), 200)])
    r = site.signin(ctx(http) if False else SignContext("colapt", Credential("cookie", "fixture"), http))
    assert r.status == "already" and "+14" in r.message
    assert [c[0] for c in http.calls] == ["get", "get"]


def test_unsigned_then_post_200_earns_reward():
    site = Colapt()
    http = Http([me_ok(), (cola_week(0), 200),
                 (json.dumps({"balance": 17, "currency": "cola", "earned": 14}), 200),
                 (cola_week(14), 200)])
    r = site.signin(SignContext("colapt", Credential("cookie", "fixture"), http))
    assert r.status == "success" and "获得 14 个核子可乐" in r.message and "余额 17" in r.message
    assert [c[0] for c in http.calls] == ["get", "get", "post", "get"]
    method, url, body, headers = http.calls[2]
    assert url == urljoin(site.url, "/api/v1/me/cola/checkin")
    assert body == {} and headers["X-CSRF-Token"] == "c" * 64
    assert headers["Origin"] == "https://www.colapt.com"


def test_post_200_empty_body_readback_zero_stays_unconfirmed():
    http = Http([me_ok(), (cola_week(0), 200),
                 ("<html>ok</html>", 200), (cola_week(0), 200)])
    r = Colapt().signin(SignContext("colapt", Credential("cookie", "fixture"), http))
    assert r.status == "unconfirmed"


def test_post_200_readback_blocked_stays_unconfirmed():
    http = Http([me_ok(), (cola_week(0), 200),
                 (json.dumps({"earned": 14}), 200), ("<html>Just a moment</html>", 200)])
    r = Colapt().signin(SignContext("colapt", Credential("cookie", "fixture"), http))
    assert r.status == "unconfirmed"


def test_post_409_falls_back_to_already():
    site = Colapt()
    http = Http([me_ok(), (cola_week(0), 200),
                 (json.dumps({"error": {"code": "cola_checkin_done"}}), 409)])
    r = site.signin(SignContext("colapt", Credential("cookie", "fixture"), http))
    assert r.status == "already" and "已经签过" in r.message


def test_me_401_reports_credential_failure_without_post():
    site = Colapt()
    http = Http([(json.dumps({"error": {"code": "unauthorized"}}), 401)])
    r = site.signin(SignContext("colapt", Credential("cookie", "fixture"), http))
    assert r.status == "network_error" and "Cookie" in r.message
    assert len(http.calls) == 1


def test_missing_csrf_blocks_submission():
    site = Colapt()
    http = Http([(json.dumps({"id": 492, "session": {}}), 200)])
    r = site.signin(SignContext("colapt", Credential("cookie", "fixture"), http))
    assert r.status == "network_error" and "CSRF" in r.message
    assert len(http.calls) == 1


def test_registry_declares_colapt_native_sign_capable():
    from autoptcheckin.core.registry import discover_sites
    row = next(r for r in discover_sites()["sites"] if r["id"] == "colapt")
    assert row["native"] and row["source"] == "插件适配" and row["url"] == "https://www.colapt.com/"


def _signin(http):
    return Colapt().signin(SignContext("colapt", Credential("cookie", "fixture"), http))


def test_daily_already_from_today_logged_in_no_post():
    http = Http([me_ok(), (cola_week(14, today={"logged_in": True, "login_earned": 3}), 200)])
    r = _signin(http)
    assert r.status == "already"
    assert r.message.startswith("每日登录 +3；本周已签到（+14）")
    assert [c[0] for c in http.calls] == ["get", "get"]


def test_daily_claim_200_merges_into_success():
    http = Http([me_ok(), (cola_week(0, daily_reward=3), 200),
                 (json.dumps({"earned": 3, "balance": 20, "currency": "cola"}), 200),
                 (json.dumps({"earned": 14, "balance": 34, "currency": "cola"}), 200),
                 (cola_week(14), 200)])
    r = _signin(http)
    assert r.status == "success"
    assert r.message.startswith("每日登录 +3；获得 14 个核子可乐")
    posts = [c for c in http.calls if c[0] == "post"]
    assert posts[0][1].endswith("/api/v1/me/cola/daily-login")
    assert posts[0][3]["X-CSRF-Token"] == "c" * 64
    assert posts[0][2] == {}
    assert posts[1][1].endswith("/api/v1/me/cola/checkin")


def test_daily_claim_409_treated_as_already():
    http = Http([me_ok(), (cola_week(0, daily_reward=3), 200),
                 (json.dumps({"error": {"code": "daily_login_done"}}), 409),
                 (json.dumps({"earned": 14, "balance": 34, "currency": "cola"}), 200),
                 (cola_week(14), 200)])
    r = _signin(http)
    assert r.status == "success" and "每日登录已领取" in r.message and "获得 14" in r.message


def test_daily_claim_5xx_degrades_without_blocking_checkin():
    http = Http([me_ok(), (cola_week(0, daily_reward=3), 200),
                 (json.dumps({}), 503),
                 (json.dumps({"earned": 14, "balance": 34, "currency": "cola"}), 200),
                 (cola_week(14), 200)])
    r = _signin(http)
    assert r.status == "success"
    assert "每日登录奖励未确认（HTTP 503）" in r.message and "获得 14" in r.message


def test_daily_reward_disabled_no_claim_post():
    http = Http([me_ok(), (cola_week(14, daily_reward=0), 200)])
    r = _signin(http)
    assert r.status == "already" and "每日登录" not in r.message
    assert [c[0] for c in http.calls] == ["get", "get"]


def test_after_login_hook_claims_when_unsigned():
    site = Colapt()
    http = Http([me_ok(), (cola_week(0, daily_reward=3), 200),
                 (json.dumps({"earned": 3}), 200)])
    msg = site.after_login(http, {})
    assert msg == "每日登录 +3"
    assert [c[0] for c in http.calls] == ["get", "get", "post"]


def test_after_login_hook_already_logged_in_no_post():
    site = Colapt()
    http = Http([me_ok(), (cola_week(0, today={"logged_in": True, "login_earned": 3}), 200)])
    msg = site.after_login(http, {})
    assert msg == "每日登录 +3"
    assert [c[0] for c in http.calls] == ["get", "get"]


def test_after_login_hook_missing_csrf_no_post():
    site = Colapt()
    http = Http([(json.dumps({"id": 1, "username": "x"}), 200)])
    msg = site.after_login(http, {})
    assert msg == "" and not [c for c in http.calls if c[0] == "post"]


def test_after_login_hook_cola_error_degrades_empty():
    site = Colapt()
    http = Http([me_ok(), (json.dumps({"error": {"code": "x"}}), 500)])
    msg = site.after_login(http, {})
    assert msg == ""


def test_run_after_login_gates_and_swallows():
    # native._run_after_login 门禁：仅 LOGIN_OK 调钩子；钩子异常吞掉返回空串
    from types import SimpleNamespace
    from autoptcheckin.core.models import LoginStatus
    from autoptcheckin.core.native import _run_after_login

    class Boom:
        def after_login(self, http, info):
            raise RuntimeError("boom")

    site = Colapt()
    http = Http([])
    ok = SimpleNamespace(status=LoginStatus.LOGIN_OK)
    unconfirmed = SimpleNamespace(status=LoginStatus.UNCONFIRMED)
    assert _run_after_login(site, http, {}, unconfirmed) == ""
    assert _run_after_login(Boom(), http, {}, ok) == ""
    site.after_login = lambda h, i: "每日登录 +3"
    assert _run_after_login(site, http, {}, ok) == "每日登录 +3"

def test_daily_probe_resp_missing_fields_no_claim():
    # /me/cola 响应缺 today/rules（老版接口或字段缺失）：不发 daily-login，签到主流程照常
    http = Http([me_ok(), (json.dumps({"week": {}, "rules": {}}), 200),
                 (json.dumps({"earned": 14, "balance": 34, "currency": "cola"}), 200),
                 (cola_week(14), 200)])
    r = _signin(http)
    assert r.status == "success" and "每日登录" not in r.message
    posts = [c for c in http.calls if c[0] == "post"]
    assert len(posts) == 1 and posts[0][1].endswith("/api/v1/me/cola/checkin")
