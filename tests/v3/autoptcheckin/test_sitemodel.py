"""Synthetic HTML only: native site consumer contract, no host or network."""
from pathlib import Path
import sys
from threading import Event

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / "plugins.v3"))
from autoptcheckin.core.credentials import Credential, CredentialSpec
from autoptcheckin.core.models import Evidence, LoginPage, LoginStatus, RewardSummary, SignStatus
from autoptcheckin.core.nexus import NexusSignin
from autoptcheckin.core.sitemodel import RecordSpec, SignContext

URL = "https://fixture.invalid/attendance.php"
FORM = '<form method="post" action="attendance.php"><input name="action" value="sign"><button name="submit" value="yes">签到</button></form>'
SPEC = RecordSpec('//*[@id="message"]', {"未签到": "unsigned", "已签到": "signed"},
                  uid='//*[@id="uid"]/text()', date='//*[@id="date"]/text()')


def page(message="未签到", form=FORM):
    return LoginPage(f'<html><body><p id="message">{message}</p>{form}</body></html>', URL)


class FakeHttp:
    def __init__(self, *pages, post_error=None):
        self.pages = iter(pages)
        self.calls = []
        self.post_error = post_error

    def get(self, url):
        assert url == URL
        self.calls.append(("get", url))
        value = next(self.pages)
        if isinstance(value, Exception):
            raise value
        return value

    def post(self, url, *, data):
        assert url == URL
        self.calls.append(("post", url, data))
        if self.post_error:
            raise self.post_error
        return page("已签到")  # This reply alone must never confirm success.


class FixtureSite(NexusSignin):
    id = "fixture"
    name = "Synthetic site"
    url = "https://fixture.invalid/"
    record_spec = SPEC
    success_texts = ("签到成功",)


def context(http=None, **kwargs):
    return SignContext("fixture", Credential("managed_site", "synthetic", "42"),
                       http or FakeHttp(), **kwargs)


@pytest.mark.parametrize("message,state", [("已签到", "signed"), ("未签到", "unsigned"), ("维护中", "unconfirmed")])
def test_record_spec_three_states(message, state):
    assert context().read_record(page(message), SPEC).status == state


def test_record_spec_first_match_and_optional_display():
    record = context().read_record(page("未签到，历史已签到", '<b id="uid">42</b><i id="date">2026-01-01</i>'), SPEC)
    assert (record.status, record.uid, record.date) == ("unsigned", "42", "2026-01-01")
    assert context().read_record(page("已签到"), SPEC).uid is None
    assert context().record_result(page("已签到"), SPEC).status == "success"


@pytest.mark.parametrize("content", [
    '<p>已签到</p>', '<p id="message">维护</p><aside>已签到</aside>',
    '<p id="message">已签到</p><p id="message">未签到</p>',
])
def test_record_never_matches_whole_page_or_ambiguous_element(content):
    assert context().read_record(LoginPage(content), SPEC).status == "unconfirmed"


def test_record_rejects_document_and_invalid_selectors():
    assert context().read_record(page("已签到"), RecordSpec('//body', {"已签到": "signed"})).status == "unconfirmed"
    assert context().read_record(page("已签到"), RecordSpec('[[[')).status == "unconfirmed"
    assert context().read_record(page("已签到"), RecordSpec(SPEC.message, SPEC.status_map, uid='[[[')).status == "signed"
    # 空 message＝未声明专用选择器，由 NexusSignin.message_spec 回退默认链。
    assert RecordSpec("").message == ""
    with pytest.raises(ValueError):
        RecordSpec("//p", {"": "signed"})


def test_context_injected_resources_and_result():
    lock, browser, ocr = object(), object(), object()
    ctx = context(site_lock=lock, page=browser, ocr=ocr)
    assert ctx.credential.source == "managed_site" and ctx.credential.uid == "42"
    assert (ctx.site_lock, ctx.page, ctx.ocr) == (lock, browser, ocr)
    reward = RewardSummary(reported="12")
    evidence = Evidence(status="signed")
    result = ctx.result(status="success", message="done", evidence=evidence, reward=reward)
    assert result.status is SignStatus.SUCCESS
    assert (result.site_id, result.account, result.evidence, result.reward) == ("fixture", "42", evidence, reward)
    assert "synthetic" not in repr(ctx)


@pytest.mark.parametrize("value,status", [(page(), "login_ok"), (None, "unconfirmed"),
    (LoginPage("", URL), "unconfirmed"), (LoginPage("error", URL, 503), "unconfirmed"),
    (LoginPage("login", "https://fixture.invalid/login.php"), "auth_failed")])
def test_site_module_parse_login(value, status):
    assert FixtureSite().parse_login(value).status == status


def test_nexus_form_submit_and_fresh_message():
    http = FakeHttp(page(), page("签到成功"))
    result = FixtureSite().signin(context(http))
    assert result.status == "success" and result.message == "签到成功"
    assert result.evidence.status == "signed"
    assert http.calls == [("get", URL), ("post", URL, [("action", "sign"), ("submit", "yes")]), ("get", URL)]
    assert FixtureSite.record_spec.status_map == SPEC.status_map
    assert "签到成功" not in SPEC.status_map


def test_nexus_already_before_submit():
    http = FakeHttp(page("已签到", ""))
    assert FixtureSite().signin(context(http)).status == "already"
    assert http.calls == [("get", URL)]


@pytest.mark.parametrize("fresh,expected", [(page("未签到"), "failed"), (page("unknown"), "unconfirmed"),
    (LoginPage('<aside>已签到</aside>', URL), "unconfirmed"), (TimeoutError(), "unconfirmed"),
    (LoginPage("已签到", "https://fixture.invalid/login.php"), "unconfirmed")])
@pytest.mark.parametrize("post_error", [None, TimeoutError()])
def test_nexus_always_rereads_even_after_submit_error(fresh, expected, post_error):
    http = FakeHttp(page(), fresh, post_error=post_error)
    assert FixtureSite().signin(context(http)).status == expected
    assert [call[0] for call in http.calls] == ["get", "post", "get"]


@pytest.mark.parametrize("form", ["", FORM + FORM,
    '<form method="post" action="/logout.php"></form>',
    '<form method="post" action="https://other.invalid/attendance.php"></form>'])
def test_nexus_does_not_guess_form(form):
    http = FakeHttp(page(form=form))
    assert FixtureSite().signin(context(http)).status == 'protocol_pending'
    assert http.calls == [("get", URL)]


def test_nexus_empty_action_and_form_values():
    form = '<form method="post"><input name="a" value="1"><input name="a" value="2"><input name="disabled" disabled value="no"></form>'
    found = FixtureSite().discover_form(context(), page(form=form))
    assert found.action == URL and found.data == [("a", "1"), ("a", "2")]


def test_nexus_captcha_and_two_step_override():
    class TwoStep(FixtureSite):
        def solve_captcha(self, ctx, page, form):
            assert ctx.credential.uid == "42"
            form.data.append(("answer", ctx.ocr()))
            return True

        def submit(self, ctx, form):
            super().submit(ctx, form)
            super().submit(ctx, form)

    http = FakeHttp(page(), page("已签到"))
    assert TwoStep().signin(context(http, ocr=lambda: "synthetic-answer")).status == "success"
    assert [call[0] for call in http.calls] == ["get", "post", "post", "get"]
    assert http.calls[1][2][-1] == ("answer", "synthetic-answer")


def test_nexus_captcha_failure_and_cancel_before_submit():
    class Captcha(FixtureSite):
        def solve_captcha(self, ctx, page, form):
            ctx.cancel.set()
            return True

    http = FakeHttp(page())
    assert Captcha().signin(context(http)).status == "cancelled"
    assert http.calls == [("get", URL)]
    cancel = Event()
    cancel.set()
    http = FakeHttp()
    assert FixtureSite().signin(context(http, cancel=cancel)).status == "cancelled"
    assert not http.calls


def test_nexus_cancel_during_submit_still_rereads():
    class CancelDuringPost(FixtureSite):
        def submit(self, ctx, form):
            ctx.cancel.set()
            super().submit(ctx, form)

    http = FakeHttp(page(), page("已签到"))
    assert CancelDuringPost().signin(context(http)).status == "success"
    assert [call[0] for call in http.calls] == ["get", "post", "get"]


def test_record_empty_document_is_unconfirmed():
    assert context().read_record(LoginPage("   "), SPEC).status == "unconfirmed"


def test_parse_login_redirect_message_depends_on_credential_kind():
    site = FixtureSite()
    redirected = LoginPage("login", "https://fixture.invalid/login.php")
    cookie = site.parse_login(redirected, CredentialSpec(kind="cookie"))
    password = site.parse_login(redirected, CredentialSpec(kind="password"))
    assert cookie.status is password.status is LoginStatus.AUTH_FAILED
    assert cookie.message == "Cookie 已失效（跳转登录页）"
    assert password.message == "页面转向登录或认证失败"
