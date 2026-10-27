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


def cola_week(amount):
    return json.dumps({"week": {"checkin_amount": amount, "next_start": "2026-11-02T00:00:00+08:00"},
                       "rules": {"checkin_min": 1, "checkin_max": 30}})


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
