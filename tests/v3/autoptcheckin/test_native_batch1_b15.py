"""B1-5 synthetic fixtures; all special submission protocols remain gated."""
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
from autoptcheckin.sites.native.generic import GenericNaturept as NaturePT
from autoptcheckin.sites.native.generic import GenericNexushd as NexusHD
from autoptcheckin.sites.native.generic import GenericNovahd as NovaHD
from autoptcheckin.sites.native.opencd import OpenCD
from autoptcheckin.sites.native.generic import GenericOshen as OshenPT

SITES = [NaturePT, NexusHD, NovaHD, OpenCD, OshenPT]
MESSAGE_SITES = [NaturePT, NexusHD, NovaHD, OshenPT]


class Http:
    def __init__(self, pages, *, error=False):
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


def page(site, message, *, form=False):
    node = f'<div class="alert">{message}</div>'
    # Inherited flow only: this form is not evidence of any real special-site protocol.
    if form:
        node += f'<form action="{site.attendance_path}" method="post"><input name="imagehash" value="fixture"><img src="image.php?imagehash=fixture"><input name="imagestring"><button>签到</button></form>'
    return node


@pytest.mark.parametrize("site_cls", MESSAGE_SITES)
def test_b15_native_fixture_three_states(site_cls):
    site = site_cls()
    signed = next(iter(site.record_spec.status_map))
    for message, expected in [(signed, "signed"), ("未签到", "unsigned"), ("未知状态", "unconfirmed")]:
        ctx = context(site, Http([]))
        assert ctx.read_record(LoginPage(page(site, message), site.url), site.message_spec()).status == expected
    http = Http([page(site, signed)])
    assert site.signin(context(site, http)).status == "already"
    assert len(http.calls) == 1
    http = Http(["<main>签到成功 本次签到获得</main>"])
    assert site.signin(context(site, http)).status == ("unconfirmed" if site.id == "nexushd" else "protocol_pending")
    http = Http([page(site, "未签到", form=True), page(site, signed)])
    assert site.signin(context(site, http)).status == "success"
    assert [call[0] for call in http.calls] == ["get", "post", "get"]


@pytest.mark.parametrize("site_cls", MESSAGE_SITES)
@pytest.mark.parametrize("error", [False, True])
def test_b15_readback_missing_message_is_unconfirmed(site_cls, error):
    site = site_cls()
    http = Http([page(site, "未签到", form=True), "<main>签到成功</main>"], error=error)
    assert site.signin(context(site, http)).status == "unconfirmed"
    assert [call[0] for call in http.calls] == ["get", "post", "get"]
    assert [call[1] for call in http.calls if call[0] == "get"] == [urljoin(site.url, site.attendance_path)] * 2


@pytest.mark.parametrize("site_cls", [NexusHD, OpenCD])
def test_b15_special_pre_read_is_homepage(site_cls):
    site = site_cls()
    assert site.attendance_path == "/"
    http = Http(["<main>unknown</main>"])
    assert site.signin(context(site, http)).status == ("protocol_pending" if site_cls is OpenCD else "unconfirmed")
    assert http.calls[0] == ("get", site.url)
    assert len(http.calls) == (3 if site_cls is NexusHD else 2)


def test_b15_registry_declares_verification_by_site():
    rows = {row["id"]: row for row in discover_sites()["sites"]}
    for cls in SITES:
        assert rows[cls.id]["native"]
        assert rows[cls.id]["verified"] is (cls is OpenCD)
        assert rows[cls.id]["hook_implemented"] is True


@pytest.mark.parametrize("site_cls", SITES)
@pytest.mark.parametrize("read_only", [False, True])
@pytest.mark.parametrize("verified", [False, True])
def test_b15_double_gate_before_credentials_or_network(monkeypatch, site_cls, read_only, verified):
    module = importlib.import_module("autoptcheckin")
    plugin = module.AutoPtCheckin()
    monkeypatch.setattr(module, "get_registry", lambda *args: {"sites": [
        dict(id=site_cls.id, native=True, verified=verified, hook_implemented=False)]})
    def forbidden(*args, **kwargs):
        pytest.fail("gate must run before credentials or network resources")
    monkeypatch.setattr(module, "managed_site", forbidden)
    monkeypatch.setattr(module, "run_native", forbidden)
    result = plugin._execute_site(site_cls.id, read_only=read_only, trigger="scheduler")
    assert result["status"] == "skipped"
    assert result["metadata"]["reason"] == ("hook_not_implemented" if verified else "native_unverified")
