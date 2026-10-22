"""B1-6 and full declaration audit: offline receipts, safe reads, and execution gates."""
import importlib
import json
import sys
from pathlib import Path
from urllib.parse import urljoin

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / "plugins.v3"))
from autoptcheckin.core.credentials import Credential
from autoptcheckin.core.models import LoginPage
from autoptcheckin.core.registry import discover_sites
from autoptcheckin.core.sitemodel import RecordSpec, SignContext
from autoptcheckin.sites.native.opencd import OpenCD
from autoptcheckin.sites.native.pterclub import PTerClub
from autoptcheckin.sites.native.generic import GenericPhoenixpt as PhoenixPT
from autoptcheckin.sites.native.pttime import PTTime
from autoptcheckin.sites.native.retrotoon import RetroToon
from autoptcheckin.sites.native.siqi import SiQi
from autoptcheckin.sites.native.hdchina import HDChina
from autoptcheckin.sites.native.generic import GenericHdupt as HDUpt
from autoptcheckin.sites.native.generic import GenericHaidan as HaiDan
from autoptcheckin.sites.native.btschool import BTSchool

NEW = [OpenCD, PTerClub, PhoenixPT, PTTime, RetroToon, SiQi]
JSON_SITES = [(OpenCD, "state", "success"), (PTerClub, "status", "1"),
              (HDChina, "state", "success")]


class Http:
    def retain_cookies(self, names):
        pass

    def __init__(self, pages, error=False):
        self.pages = iter(pages)
        self.calls = []
        self.error = error

    def get(self, url, **kwargs):
        self.calls.append(("get", url))
        return LoginPage(next(self.pages), url)

    def post(self, url, *, data):
        self.calls.append(("post", url, data))
        if self.error:
            raise TimeoutError()
        return LoginPage("untrusted reply", url)


def context(site, http):
    return SignContext(site.id, Credential("managed_site", "fixture"), http)


def message(text):
    return f'<div class="alert">{text}</div>'


@pytest.mark.parametrize("cls,field,value", JSON_SITES)
def test_response_json_exact_receipt_not_homepage(cls, field, value):
    site = cls()
    payload = json.dumps({field: value})
    ctx = context(site, Http([]))
    assert site.credential.kind == "cookie"
    assert site.record_spec.source == "response_json"
    assert ctx.read_record(LoginPage(payload, site.url), site.record_spec).status == "signed"
    assert ctx.record_result(LoginPage(payload, site.url), site.record_spec).status == "success"
    for data in [{field: False}, {field: "failed"}, {field: "successfully"},
                 {field: "0"}, {field: 1}, {}, [], {field: {"state": "success"}}]:
        assert ctx.read_record(LoginPage(json.dumps(data), site.url), site.record_spec).status == "unconfirmed"
    for text in ["broken JSON", '<p>success</p>', payload]:
        http = Http([text])
        assert site.signin(context(site, http)).status == ("protocol_pending" if cls in (OpenCD, HDChina) else "unconfirmed")
        assert http.calls[0] == ("get", urljoin(site.url, site.attendance_path))


@pytest.mark.parametrize("cls,markup", [
    (OpenCD, '<a href="/plugin_sign-in.php?cmd=show-log">签到记录</a>'),
    (HDUpt, '<span id="yiqiandao"></span>'),
    (HaiDan, '<input value="已经打卡">'),
    (HDChina, '<a class="label label-default" href="#">已签到</a>'),
])
def test_audited_pre_read_positive_marker(cls, markup):
    site = cls()
    http = Http([markup])
    assert site.signin(context(site, http)).status == ("skipped" if cls is PhoenixPT else "already")
    assert len(http.calls) == (0 if cls is PhoenixPT else 1)
    for text in ['<main>已签到 show-log yiqiandao success</main>', '<main>unknown</main>']:
        http = Http([text])
        assert site.signin(context(site, http)).status == ("protocol_pending" if cls in (OpenCD, HDChina) else "unconfirmed")
        assert len(http.calls) == (3 if cls in (HDUpt, HaiDan) else 2 if cls is OpenCD else 1)


@pytest.mark.parametrize("cls", [PhoenixPT, SiQi])
def test_new_message_three_states(cls):
    site = cls()
    signed = next(k for k, v in site.record_spec.status_map.items() if v == "signed")
    for text, state in [(signed, "signed"), ("未签到", "unsigned"), ("unknown", "unconfirmed")]:
        ctx = context(site, Http([]))
        assert ctx.read_record(LoginPage(message(text), site.url), site.message_spec()).status == state
    http = Http([message(signed)])
    assert site.signin(context(site, http)).status == ("skipped" if cls is PhoenixPT else "already")
    assert len(http.calls) == (0 if cls is PhoenixPT else 1)


def reward(text):
    return f'<section class="rt-form-card"><h2>Daily Reward</h2><p>{text}</p></section>'


def claim(csrf=True):
    return ('<form action="/attendance.php" method="post">'
            + ('<input name="csrf_token" value="fixture-csrf">' if csrf else '')
            + '<input type="submit" name="claim" value="yes"></form>')


@pytest.mark.parametrize("error", [False, True])
def test_retrotoon_three_states_and_unconditional_readback(error):
    site = RetroToon()
    http = Http([reward("already claimed")])
    assert site.signin(context(site, http)).status == "already"
    http = Http([claim(), reward("reward claimed")], error)
    assert site.signin(context(site, http)).status == "success"
    assert [x[0] for x in http.calls] == ["get", "post", "get"]
    assert dict(http.calls[1][2]) == {"csrf_token": "fixture-csrf", "claim": "yes"}
    http = Http([claim(), '<main>reward claimed</main>'], error)
    assert site.signin(context(site, http)).status == "unconfirmed"
    assert [x[0] for x in http.calls] == ["get", "post", "get"]
    http = Http([claim(False)])
    assert site.signin(context(site, http)).status == 'protocol_pending'
    assert len(http.calls) == 1


@pytest.mark.parametrize("cls", [OpenCD, PTerClub, PTTime, BTSchool, HDUpt, HDChina, HaiDan])
def test_action_endpoints_never_used_for_pre_read(cls):
    site = cls()
    assert site.attendance_path in {"/", "/index.php", "/attendance.php?type=list"}
    http = Http(["<main>unknown</main>"])
    assert site.signin(context(site, http)).status == ("protocol_pending" if cls in (OpenCD, HDChina, BTSchool) else "unconfirmed")
    safe = ("get", urljoin(site.url, site.attendance_path))
    assert http.calls[0] == safe
    if cls is OpenCD:
        assert http.calls == [safe, ("get", site.url + "plugin_sign-in.php")]
    elif cls is BTSchool:
        assert http.calls == [safe]
    elif getattr(site, "action_path", ""):
        assert http.calls == [safe, ("get", urljoin(site.url, site.action_path)), safe]
    else:
        assert http.calls == [safe]


@pytest.mark.parametrize("read_only", [False, True])
@pytest.mark.parametrize("verified", [False, True])
def test_all_unimplemented_hooks_double_gate(monkeypatch, read_only, verified):
    module = importlib.import_module("autoptcheckin")
    plugin = module.AutoPtCheckin()
    rows = discover_sites()["sites"]
    special = [row for row in rows if row.get("native") and row.get("hook_implemented") is False]
    assert {"chdbits"}.isdisjoint({r["id"] for r in special})  # 52pt 已改滑块、hook=False 归入 special
    def forbidden(*args, **kwargs):
        pytest.fail("gate must precede credentials and network")
    monkeypatch.setattr(module, "managed_site", forbidden)
    monkeypatch.setattr(module, "run_native", forbidden)
    for row in special:
        monkeypatch.setattr(module, "get_registry", lambda *args: {"sites": [dict(row, verified=verified)]})
        result = plugin._execute_site(row["id"], read_only=read_only)
        assert result["status"] == "skipped"
        assert result["metadata"]["reason"] == ("hook_not_implemented" if verified else "native_unverified")


def test_new_registry_unverified_and_record_spec_validation():
    rows = {r["id"]: r for r in discover_sites()["sites"]}
    for cls in NEW:
        assert rows[cls.id]["native"] and not rows[cls.id]["verified"]
        assert not rows[cls.id]["pilot_enabled"]
    for kwargs in [dict(source="response_json"), dict(source="api_key"),
                   dict(source="response_json", response_field="code", status_map={0.5: "signed"})]:
        with pytest.raises(ValueError):
            RecordSpec(**kwargs)
