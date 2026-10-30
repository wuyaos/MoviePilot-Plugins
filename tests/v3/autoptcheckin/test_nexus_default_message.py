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


def test_after_unknown_result_explains_post_submit_evidence_gap():
    site = get_native_module('baozi')
    result = site.read_after(context(site), LoginPage('<div class="alert">未知消息</div>', site.url))
    assert result.status == 'unconfirmed'
    assert result.message == '已提交签到，但回读未找到成功或已签证据（页面提示：未知消息）'


def test_after_read_error_explains_post_submit_failure():
    site = get_native_module('baozi')
    ctx = context(site)
    ctx.post_read_error = 'TimeoutError'
    result = site.read_after(ctx, None)
    assert result.status == 'unconfirmed'
    assert result.message == '已提交签到，但回读失败：TimeoutError'


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


def test_traditional_heading_is_read_as_signed():
    """繁体站（老师 NicePT）用「簽到」；只写简体选择器会永远拿不到证据。"""
    site = get_native_module('nicept')
    page = LoginPage('<h2>簽到成功</h2>', site.url)
    ctx = context(site)
    assert ctx.read_record(page, site.message_spec()).status == 'signed'
    assert site.read_before(ctx, page).status == 'already'
    assert site.read_after(ctx, page).status == 'success'


def test_traditional_bare_heading_is_not_a_result_message():
    site = get_native_module('nicept')
    result = site.read_after(context(site), LoginPage('<h2>簽到</h2>', site.url))
    assert result.status == 'unconfirmed'
    assert result.message == '已提交签到，但回读未找到成功或已签证据'


@pytest.mark.parametrize('container', CONTAINERS)
def test_traditional_receipt_in_default_containers(container):
    site = get_native_module('nicept')
    page = LoginPage(container.format('簽到成功'), site.url)
    assert context(site).read_record(page, site.message_spec()).status == 'signed'


def test_default_xpaths_cover_simplified_and_traditional_words():
    joined = ' '.join(NexusSignin.DEFAULT_MESSAGE_XPATHS)
    for word in ('签到', '簽到', '打卡'):
        assert word in joined
