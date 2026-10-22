"""B1-2 native site fixtures; requests are synthetic and offline."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / "plugins.v3"))
from autoptcheckin.core.credentials import Credential
from autoptcheckin.core.models import LoginPage
from autoptcheckin.core.sitemodel import SignContext
from autoptcheckin.sites.native.dongying import Dongying
from autoptcheckin.sites.native.dstudio import DStudio
from autoptcheckin.sites.native.haidan import HaiDan
from autoptcheckin.sites.native.hdarea import HDArea


class Http:
    def __init__(self, pages):
        self.pages = iter(pages)
        self.calls = []

    def get(self, url):
        self.calls.append(("get", url))
        return LoginPage(next(self.pages), url)

    def post(self, url, *, data, referer=None):
        self.calls.append(("post", url, data))
        return LoginPage("submission reply", url)


def context(site, http):
    return SignContext(site.id, Credential("managed_site", "fixture"), http, ocr=lambda **kwargs: "Ab1234")


def page(site, message, *, form=False):
    markup = (
        f'<form action="{site.attendance_path}" method="post">'
        '<input name="imagehash" value="fixture"><img src="image.php?imagehash=fixture"><input name="imagestring"><button type="submit">签到</button></form>' if form else ""
    )
    return f'<div class="alert">{message}</div>{markup}'


@pytest.mark.parametrize("site_cls", [Dongying, DStudio, HDArea])
def test_b12_native_fixture_three_states(site_cls):
    site = site_cls()
    signed = next(key for key, state in site.record_spec.status_map.items() if state == "signed")
    assert site.signin(context(site, Http([page(site, signed)]))).status == "already"

    unknown = site.signin(context(site, Http(["<main>无声明消息</main>"])))
    assert unknown.status == "unconfirmed"

    success = site.signin(context(site, Http([page(site, "未签到", form=True), page(site, signed)])))
    assert success.status == "success"
    assert success.evidence.raw_summary == signed
