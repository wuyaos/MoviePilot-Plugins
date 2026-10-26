"""B1-4 synthetic fixtures; API keepalive must not invent sign-state evidence."""
import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / "plugins.v3"))
from autoptcheckin.core.credentials import Credential
from autoptcheckin.core.models import LoginPage, SignResult, SignStatus
from autoptcheckin.core.registry import discover_sites
from autoptcheckin.core.sitemodel import SignContext, SiteModule
from autoptcheckin.core.nexus import NexusSignin
from autoptcheckin.sites.native.generic import GenericKelu as Kelu
from autoptcheckin.sites.native.lajidui import LaJiDui
from autoptcheckin.sites.native.luckpt import LuckPT
from autoptcheckin.sites.native.mteam import MTorrent
from autoptcheckin.sites.native.muxuege import Muxuege

HTML_SITES = [Kelu, LaJiDui, LuckPT, Muxuege]
SITES = HTML_SITES + [MTorrent]
SPECIAL = [Kelu, LaJiDui, MTorrent]


class Http:
    def __init__(self, pages=(), *, error=False):
        self.pages = iter(pages)
        self.calls = []
        self.error = error

    def get(self, url):
        self.calls.append(("get", url))
        return LoginPage(next(self.pages), url)

    def post(self, url, *, data, referer=None):
        self.calls.append(("post", url, data))
        if self.error:
            raise TimeoutError()
        return LoginPage("untrusted reply", url)


def context(site, http):
    return SignContext(site.id, Credential("managed_site", "fixture"), http, ocr=lambda **kwargs: "Ab1234")


def page(message, *, form=False):
    node = f'<div class="alert">{message}</div>'
    if form:
        node += '<form action="/attendance.php" method="post"><input name="imagehash" value="fixture"><img src="image.php?imagehash=fixture"><input name="imagestring"><button>签到</button></form>'
    return node


@pytest.mark.parametrize("site_cls", HTML_SITES)
def test_b14_native_fixture_three_states(site_cls):
    site = site_cls()
    http = Http([page("已经签到")])
    assert site.signin(context(site, http)).status == "already"
    assert len(http.calls) == 1
    http = Http(["<main>已经签到 签到成功</main>"])
    assert site.signin(context(site, http)).status == 'protocol_pending'
    assert len(http.calls) == 1
    # Synthetic CAPTCHA inputs exercise the implemented hook without production claims.
    http = Http([page("未签到", form=True), page("签到成功")])
    result = site.signin(context(site, http))
    assert result.status == "success"
    assert result.evidence.raw_summary == "签到成功"
    assert [call[0] for call in http.calls] == ["get", "post", "get"]
    assert all(call[1] == site.url + "attendance.php" for call in http.calls)


@pytest.mark.parametrize("site_cls", HTML_SITES)
@pytest.mark.parametrize("error", [False, True])
def test_b14_readback_missing_message_is_unconfirmed(site_cls, error):
    site = site_cls()
    http = Http([page("未签到", form=True), "<main>签到成功</main>"], error=error)
    assert site.signin(context(site, http)).status == "unconfirmed"
    assert [call[0] for call in http.calls] == ["get", "post", "get"]


@pytest.mark.parametrize("message", ["签到成功", "未签到", "未知状态"])
def test_mteam_three_state_inputs_never_imply_sign_state(message):
    site = MTorrent()
    http = Http()
    ctx = context(site, http)
    assert ctx.read_record(LoginPage(page(message), "https://fixture.invalid/"), site.record_spec).status == "unconfirmed"
    result = site.signin(ctx)
    assert result.status == "skipped"
    assert result.metadata["reason"] == "hook_not_implemented"
    assert http.calls == []
    assert isinstance(site, SiteModule) and not isinstance(site, NexusSignin)
    assert site.credential.kind == "password" and site.credential.cookie_sources == ()
    assert site.url == "https://kp.m-team.cc/" and site.login_capable and not site.record_spec.status_map


def test_b14_registry_declares_verification_by_site():
    rows = {row["id"]: row for row in discover_sites()["sites"]}
    for cls in SITES:
        assert rows[cls.id]["native"]
    for cls in SPECIAL:
        assert rows[cls.id]["hook_implemented"] == (cls in (Kelu, LaJiDui))
    assert rows["mteam"]["credential"] == {"kind": "password", "sources": [], "refresh": None}


@pytest.mark.parametrize("site_cls", SITES)
@pytest.mark.parametrize("read_only", [False, True])
def test_b14_unverified_enabled_and_selected_executes(monkeypatch, site_cls, read_only):
    """verified 不再是运行时门控：启用并勾选即执行。"""
    module = importlib.import_module("autoptcheckin")
    plugin = module.AutoPtCheckin()
    plugin._config = {"enabled_sites": [site_cls.id], "sign_sites": [site_cls.id]}
    monkeypatch.setattr(module, "get_registry", lambda *args: {"sites": [
        dict(id=site_cls.id, native=True, verified=False, hook_implemented=True,
             signin_capable=True, signin_applicable=True)]})
    monkeypatch.setattr(module, "managed_site", lambda sid: {})
    called = []
    monkeypatch.setattr(module, "run_native",
                        lambda runner, site, info, **kwargs: called.append(site.id) or SignResult(SignStatus.SUCCESS, "ok"))
    result = plugin._execute_site(site_cls.id, read_only=read_only, trigger="scheduler")
    assert result["status"] == "signed"
    assert called == [site_cls.id]


@pytest.mark.parametrize("site_cls", SPECIAL)
@pytest.mark.parametrize("read_only", [False, True])
def test_b14_hook_attribute_no_longer_blocks_execution(monkeypatch, site_cls, read_only):
    """hook_not_implemented 运行时门控已移除；实际防护由站点 signin 自守。"""
    module = importlib.import_module("autoptcheckin")
    plugin = module.AutoPtCheckin()
    plugin._config = {"enabled_sites": [site_cls.id], "sign_sites": [site_cls.id]}
    monkeypatch.setattr(module, "get_registry", lambda *args: {"sites": [
        dict(id=site_cls.id, native=True, verified=True, hook_implemented=False,
             signin_capable=True, signin_applicable=False)]})
    monkeypatch.setattr(module, "managed_site", lambda sid: {})
    called = []
    monkeypatch.setattr(module, "run_native",
                        lambda runner, site, info, **kwargs: called.append(site.id) or SignResult(SignStatus.SUCCESS, "ok"))
    result = plugin._execute_site(site_cls.id, read_only=read_only, trigger="scheduler")
    assert result["status"] == "signed"
    assert called == [site_cls.id]


def test_mteam_preserves_legacy_multi_domain_matcher(monkeypatch):
    registry = importlib.import_module("autoptcheckin.core.registry")
    # Offline discovery may skip legacy imports without the host. Seed its exact match contract.
    legacy_match = lambda url: "m-team" in url.split(".")
    monkeypatch.setitem(registry._MATCHERS, "mteam", legacy_match)
    discover_sites()
    match = registry._MATCHERS["mteam"]
    assert match("https://kp.m-team.cc/")
    assert match("https://kp.m-team.io/")
    assert not match("https://pt.luckpt.de/")
    assert not match("https://m-team-impostor.invalid/")


@pytest.mark.parametrize("value", ["", "https://", "/", "https://unrelated.invalid/"])
def test_mteam_empty_url_does_not_match_missing_hostname(value):
    from autoptcheckin.core.registry import site_id_for_domain
    assert site_id_for_domain(value) is None
    assert site_id_for_domain("mteam") == "mteam"
