"""Synthetic default-chain contracts, not production selector calibration."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / 'plugins.v3'))
from autoptcheckin.core.credentials import Credential
from autoptcheckin.core.models import LoginPage
from autoptcheckin.core.nexus import NexusSignin
from autoptcheckin.core.registry import get_native_module
from autoptcheckin.core.sitemodel import RecordSpec, SignContext


CONTAINERS = [
    '<div class="alert">{}</div>',
    '<div class="layui-layer">{}</div>',
    '<div id="msg">{}</div>',
    '<div class="message">{}</div>',
    '<table class="t1"><tr><td>{}</td></tr></table>',
    '<div id="main"><font>{}</font></div>',
]


def context(site):
    return SignContext(site.id, Credential('test', 'synthetic'), None)


@pytest.mark.parametrize('container', CONTAINERS)
@pytest.mark.parametrize('text,state', [('签到成功', 'signed'), ('已签到', 'signed'),
                                        ('未签到', 'unsigned'), ('签到状态未知', 'unconfirmed')])
def test_default_message_selector_states(container, text, state):
    site = get_native_module('baozi')
    page = LoginPage(container.format(text), site.url)
    ctx = context(site)
    assert ctx.read_record(page, site.message_spec()).status == state
    assert site.read_before(ctx, page).status == {
        'signed': 'already', 'unsigned': 'failed', 'unconfirmed': 'unconfirmed'}[state]
    assert site.read_after(ctx, page).status == {
        'signed': 'success', 'unsigned': 'failed', 'unconfirmed': 'unconfirmed'}[state]


@pytest.mark.parametrize('markup,summary,state', [
    ('<div class="alert">未知消息</div><div id="msg">签到成功</div>', '未知消息', 'unconfirmed'),
    ('<div class="alert"></div><div id="msg">签到成功</div>', '签到成功', 'signed'),
    ('<div class="alert">签到成功</div>' * 2, '', 'unconfirmed'),
    ('<main>签到成功</main>', '', 'unconfirmed'),
    ('<p id="batch2-message-pending-calibration">签到成功</p>', '', 'unconfirmed'),
])
def test_default_message_first_unique_nonempty_node(markup, summary, state):
    site = get_native_module('baozi')
    evidence = context(site).read_record(LoginPage(markup, site.url), site.message_spec())
    assert (evidence.raw_summary, evidence.status) == (summary, state)


def test_default_message_preserves_site_mapping_and_success_texts():
    site = NexusSignin()
    site.record_spec = RecordSpec('//*[@id="batch2-message-pending-calibration"]',
                                 {'站点已签': 'signed', '已签到': 'unsigned'}, uid='//a', date='//time')
    site.success_texts = ('Custom success',)
    spec = site.message_spec()
    assert spec.message == site.DEFAULT_MESSAGE_XPATHS
    assert spec.status_map['站点已签'] == spec.status_map['Custom success'] == 'signed'
    assert spec.status_map['已签到'] == 'unsigned'
    assert (spec.uid, spec.date) == ('//a', '//time')


def test_explicit_message_selector_does_not_use_default_chain():
    site = NexusSignin()
    site.record_spec = RecordSpec('//p[@id="receipt"]', {'本站成功': 'signed'})
    spec = site.message_spec()
    assert spec.message == '//p[@id="receipt"]'
    assert context(site).read_record(LoginPage('<div class="alert">签到成功</div>', 'https://fixture.invalid/'), spec).status == 'unconfirmed'


@pytest.mark.parametrize('container', CONTAINERS)
def test_btschool_opts_out_of_unaudited_positive_messages(container):
    site = get_native_module('btschool')
    page = LoginPage(container.format('签到成功'), site.url)
    ctx = context(site)
    assert site.use_default_message is False
    assert site.read_before(ctx, page).status == site.read_after(ctx, page).status == 'unconfirmed'
    # Scoped entry logic does not promote arbitrary success text, even with default chaining enabled.
    site.use_default_message = True
    assert site.read_after(ctx, page).status == 'unconfirmed'


def test_default_message_login_redirect_is_not_sign_evidence():
    site = get_native_module('baozi')
    page = LoginPage('<div class="alert">签到成功</div>', site.url + 'login.php')
    assert site.read_before(context(site), page).status == 'unconfirmed'
    assert site.read_after(context(site), page).status == 'unconfirmed'
