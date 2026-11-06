"""hxpt FluxTorrent API 回归：全部合成 JSON，禁止真实外网。"""
import json
import sys
from pathlib import Path
from threading import Event

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / "plugins.v3"))
from autoptcheckin.core.credentials import Credential
from autoptcheckin.core.models import LoginPage, SignStatus
from autoptcheckin.core.sitemodel import SignContext
from autoptcheckin.sites.native import hxpt as hxpt_module
from autoptcheckin.sites.native.hxpt import Hxpt

BASE = "https://www.hxpt.org/"
STATUS = BASE + "api/v1/attendance"
CHECKIN = BASE + "api/v1/attendance/checkin"


def envelope(code=0, *, checked=None, message="ok", reward=None, streak=None):
    data = {}
    if checked is not None:
        data["checked_today"] = checked
    if reward is not None:
        data["reward"] = reward
    if streak is not None:
        data["streak"] = streak
    return json.dumps({"code": code, "message": message, "data": data})


class Http:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(("get", url))
        return self.responses.pop(0)

    def post(self, url, *, data=None, json=None, headers=None, referer=None):
        self.calls.append(("post", url, json))
        return self.responses.pop(0)


def ctx(http):
    return SignContext("hxpt", Credential("managed_site", "fixture"), http,
                       cancel=Event())


def page(body, status=200):
    return LoginPage(body, STATUS, status_code=status)


def calls_of(http):
    return [(method, url) for method, url, *_ in http.calls]


def test_registry_replaces_generic_declaration():
    from autoptcheckin.core import registry
    sites = registry.discover_sites()["sites"]
    entry = [item for item in sites if item["id"] == "hxpt"]
    assert len(entry) == 1 and entry[0]["native"] is True
    assert entry[0]["name"] == "好学"
    # generic 声明已收敛，不再生成 Generic_Hxpt
    assert not hasattr(hxpt_module, "Generic_Hxpt")


def test_already_before_submit():
    http = Http([page(envelope(checked=True))])
    result = Hxpt().signin(ctx(http))
    assert result.status is SignStatus.ALREADY
    assert calls_of(http) == [("get", STATUS)]


def test_success_confirmed_by_reread_with_reward():
    http = Http([page(envelope(checked=False)),
                 page(envelope(reward=100, streak=3)),
                 page(envelope(checked=True))])
    result = Hxpt().signin(ctx(http))
    assert result.status is SignStatus.SUCCESS
    assert result.message == "签到成功（+100 魔力，连续 3 天）"
    assert calls_of(http) == [("get", STATUS), ("post", CHECKIN), ("get", STATUS)]


def test_success_without_receipt_fields():
    http = Http([page(envelope(checked=False)),
                 page(envelope(message="done")),
                 page(envelope(checked=True))])
    result = Hxpt().signin(ctx(http))
    assert result.status is SignStatus.SUCCESS and result.message == "签到成功"


@pytest.mark.parametrize("post_body", [page("<html>blocked</html>"), page(envelope(code=1001, message="err"))])
def test_post_failure_but_reread_confirms(post_body):
    http = Http([page(envelope(checked=False)), post_body, page(envelope(checked=True))])
    result = Hxpt().signin(ctx(http))
    assert result.status is SignStatus.SUCCESS


@pytest.mark.parametrize("after", [page("<html>boom</html>"), page(envelope(checked=False))])
def test_submitted_without_reread_proof_is_unconfirmed(after):
    http = Http([page(envelope(checked=False)), page(envelope()), after])
    result = Hxpt().signin(ctx(http))
    assert result.status is SignStatus.UNCONFIRMED


def test_reread_read_error_is_unconfirmed():
    http = Http([page(envelope(checked=False)), page(envelope()), page(None, status=502)])
    result = Hxpt().signin(ctx(http))
    assert result.status is SignStatus.UNCONFIRMED
    assert "状态接口不可读" in result.message


def test_status_endpoint_unreadable_is_network_error():
    http = Http([page("<html>login</html>")])
    result = Hxpt().signin(ctx(http))
    assert result.status is SignStatus.NETWORK_ERROR


def test_pre_read_401_is_auth_failed():
    http = Http([page("", status=401)])
    result = Hxpt().signin(ctx(http))
    assert result.status is SignStatus.AUTH_FAILED


def test_pre_read_transport_error_is_network_error():
    class Boom:
        def get(self, url, **kwargs):
            raise OSError("down")

        def post(self, url, **kwargs):
            raise AssertionError("must not post")

    result = Hxpt().signin(ctx(Boom()))
    assert result.status is SignStatus.NETWORK_ERROR


def test_nonzero_code_before_submit_is_unconfirmed():
    http = Http([page(envelope(code=403, message="forbidden"))])
    result = Hxpt().signin(ctx(http))
    assert result.status is SignStatus.UNCONFIRMED
    assert "403" in result.message


def test_cancel_before_pre_read():
    event = Event()
    event.set()
    context = SignContext("hxpt", Credential("managed_site", "fixture"),
                          Http([]), cancel=event)
    assert Hxpt().signin(context).status is SignStatus.CANCELLED


def test_malformed_bool_checked_is_not_already():
    # JSON false 不得匹配 True；code==0 且 false → 照常提交
    http = Http([page('{"code":0,"data":{"checked_today":false}}'),
                 page(envelope()), page(envelope(checked=True))])
    assert Hxpt().signin(ctx(http)).status is SignStatus.SUCCESS
