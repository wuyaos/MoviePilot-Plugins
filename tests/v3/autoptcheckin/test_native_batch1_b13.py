"""B1-3 synthetic fixtures: no production HTML claims and no network requests."""
import importlib
import sys
from pathlib import Path
from urllib.parse import urljoin

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / "plugins.v3"))
from autoptcheckin.core.credentials import Credential
from autoptcheckin.core.models import LoginPage
from autoptcheckin.core.registry import discover_sites
from autoptcheckin.core.sitemodel import SignContext
from autoptcheckin.sites.native.hdbao import HDBao
from autoptcheckin.sites.native.hdchina import HDChina
from autoptcheckin.sites.native.generic import GenericHdcity as HDCity
from autoptcheckin.sites.native.generic import GenericHdupt as HDUpt
from autoptcheckin.sites.native.generic import GenericHhanclub as Hhanclub

SITES = [HDBao, HDChina, HDCity, HDUpt, Hhanclub]
SPECIAL = [HDChina, HDCity, HDUpt, Hhanclub]


class Http:
    def retain_cookies(self, names):
        pass

    def __init__(self, pages, *, error=False):
        self.pages = iter(pages)
        self.calls = []
        self.error = error

    def get(self, url, *, referer=None):
        self.calls.append(("get", url))
        if url.endswith("/sign") or url.endswith("/attendance.php") and "hhanclub" in url:
            if self.error:
                raise TimeoutError()
            return LoginPage("untrusted reply", url)
        return LoginPage(next(self.pages), url)

    def post(self, url, *, data):
        self.calls.append(("post", url, data))
        if self.error:
            raise TimeoutError()
        return LoginPage("untrusted reply", url)


def context(site, http):
    return SignContext(site.id, Credential("managed_site", "fixture"), http)


def page(site, message, *, form=False):
    node = (f'<a class="label label-default" href="#">{message}</a>'
            if isinstance(site, HDChina) else
            f'<div class="alert">{message}</div>')
    # Synthetic form exercises inherited flow only, not a claim about special-site protocols.
    if form:
        node += f'<form action="{site.attendance_path}" method="post"><button>签到</button></form>'
    return node


@pytest.mark.parametrize("site_cls", [HDBao, HDCity])
def test_b13_native_fixture_three_states(site_cls):
    site = site_cls()
    signed = next(iter(site.record_spec.status_map))
    http = Http([page(site, signed)])
    assert site.signin(context(site, http)).status == "already"
    assert len(http.calls) == 1
    http = Http(["<main>已签到 签到成功</main>"])
    assert site.signin(context(site, http)).status == ("protocol_pending" if site_cls is HDBao else "unconfirmed")
    assert len(http.calls) == (1 if site_cls is HDBao else 3)
    http = Http([page(site, "未签到", form=True), page(site, signed)])
    result = site.signin(context(site, http))
    assert result.status == "success"
    assert result.evidence.raw_summary == signed
    assert [call[0] for call in http.calls] == (["get", "post", "get"] if site_cls is HDBao else ["get"] * 3)


@pytest.mark.parametrize("site_cls", [HDBao, HDCity])
@pytest.mark.parametrize("error", [False, True])
def test_b13_readback_missing_message_is_unconfirmed(site_cls, error):
    site = site_cls()
    http = Http([page(site, "未签到", form=True), "<main>签到成功</main>"], error=error)
    assert site.signin(context(site, http)).status == "unconfirmed"
    assert [call[0] for call in http.calls] == (["get", "post", "get"] if site_cls is HDBao else ["get"] * 3)


@pytest.mark.parametrize("site_cls,safe_path", [(HDCity, "/")])  # hhanclub 动作页即结果页（见 test_generic_behavior_d1）
def test_b13_special_pre_read_and_readback_use_safe_page(site_cls, safe_path):
    site = site_cls()
    assert site.hook_implemented is True
    assert site.attendance_path == safe_path
    http = Http([page(site, "未签到", form=True), page(site, next(iter(site.record_spec.status_map)))])
    site.signin(context(site, http))
    assert [http.calls[0][1], http.calls[-1][1]] == [urljoin(site.url, safe_path)] * 2
    assert http.calls[1][1] == urljoin(site.url, site.action_path)


def test_b13_registry_declares_all_unverified():
    rows = {row["id"]: row for row in discover_sites()["sites"]}
    for cls in SITES:
        assert rows[cls.id]["native"] and not rows[cls.id]["verified"]
        assert not rows[cls.id]["pilot_enabled"]
    for cls in SPECIAL:
        assert rows[cls.id]["hook_implemented"] is True


@pytest.mark.parametrize("site_cls", [HDBao, HDCity])
@pytest.mark.parametrize("read_only", [False, True])
def test_b13_unverified_execution_never_reads_credentials(monkeypatch, site_cls, read_only):
    module = importlib.import_module("autoptcheckin")
    plugin = module.AutoPtCheckin()
    def forbidden(*args, **kwargs):
        pytest.fail("gate must run before credentials or network resources")
    monkeypatch.setattr(module, "managed_site", forbidden)
    monkeypatch.setattr(module, "run_native", forbidden)
    result = plugin._execute_site(site_cls.id, read_only=read_only)
    assert result["status"] == "skipped"
    assert result["metadata"]["reason"] == "native_unverified"


@pytest.mark.parametrize("site_cls", SPECIAL)
@pytest.mark.parametrize("read_only", [False, True])
def test_b13_verified_without_hook_is_still_blocked(monkeypatch, site_cls, read_only):
    module = importlib.import_module("autoptcheckin")
    plugin = module.AutoPtCheckin()
    monkeypatch.setattr(module, "get_registry", lambda *args: {"sites": [
        dict(id=site_cls.id, native=True, verified=True, hook_implemented=False)]})
    def forbidden(*args, **kwargs):
        pytest.fail("unimplemented hook must never create requests")
    monkeypatch.setattr(module, "managed_site", forbidden)
    monkeypatch.setattr(module, "run_native", forbidden)
    result = plugin._execute_site(site_cls.id, read_only=read_only)
    assert result["status"] == "skipped"
    assert result["metadata"]["reason"] == "hook_not_implemented"


def test_hdchina_only_v2_proven_message_is_mapped():
    site = HDChina()
    assert site.pre_read_spec.status_map == {"已签到": "signed"}
    for markup in ('<a href="#">已签到</a>', '<a class="label label-default" href="/other">已签到</a>', page(site, "未知文本")):
        assert site.signin(context(site, Http([markup]))).status == 'protocol_pending'


def test_hdupt_empty_marker_or_numeric_reply_is_not_a_message():
    site = HDUpt()
    for markup in ('<span id="other"></span>', '<main>.23</main>'):
        assert site.signin(context(site, Http([markup]))).status == "unconfirmed"
