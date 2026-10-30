"""B1-7 source-derived evidence fixtures; no live requests or host credentials."""
import importlib
import json
import sys
from pathlib import Path
from urllib.parse import urljoin

from unittest.mock import patch
import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / "plugins.v3"))
from autoptcheckin.core.credentials import Credential
from autoptcheckin.core.models import LoginPage, SignResult, SignStatus
from autoptcheckin.core.registry import discover_sites, get_native_module
from autoptcheckin.core.sitemodel import SignContext

IDS = 'darkland digitalcore playlet ptzone shaobaoyuan soulvoice tjupt ttg tu88 u2 vclib yema yzyy zhuque'.split()
C34 = ["ttg", "u2", "yema", "zhuque"]
CAPTCHA = 'playlet shaobaoyuan soulvoice tu88 vclib'.split()


class Http:
    def __init__(self, pages=(), error=False):
        self.pages = iter(pages)
        self.calls = []
        self.error = error

    def get(self, url):
        self.calls.append(('get', url))
        return LoginPage(next(self.pages), url)

    def post(self, url, *, data):
        self.calls.append(('post', url, data))
        if self.error:
            raise TimeoutError()
        return LoginPage('untrusted submission reply', url)


def context(site, http):
    return SignContext(site.id, Credential('managed_site', 'fixture'), http)


def message(text):
    return f'<div class="alert">{text}</div>'


@pytest.mark.parametrize('site_id', CAPTCHA + ['ptzone', 'ttg'])
def test_declared_message_three_states(site_id):
    site = get_native_module(site_id)
    ctx = context(site, Http())
    for word, state in site.record_spec.status_map.items():
        assert ctx.read_record(LoginPage(message(word), site.url), site.message_spec()).status == state
    for text in [message('unknown'), '<main>签到成功</main>', message('签到成功') * 2]:
        assert ctx.read_record(LoginPage(text, site.url), site.message_spec()).status == 'unconfirmed'


@pytest.mark.parametrize('site_id,path,signed,unsigned', [
    ('tjupt', 'attendance.php', '今日已签到', '签到'),
    ('u2', 'showup.php', '已签到', '签到'),
])
def test_anchor_evidence_without_invented_unsigned(site_id, path, signed, unsigned):
    site = get_native_module(site_id)
    for text, state in [(signed, 'signed'), (unsigned, 'unconfirmed'), ('unknown', 'unconfirmed')]:
        page = LoginPage(f'<a href="{path}">{text}</a>', site.url)
        assert context(site, Http()).read_record(page, site.record_spec).status == state
    for word in site.record_spec.status_map:
        http = Http([f'<a href="{path}">{word}</a>'])
        assert site.signin(context(site, http)).status == 'already', (site_id, word)
        assert len(http.calls) == 1
    page = LoginPage("<script>window.location.href = 'showup.php';</script>", site.url)
    assert context(site, Http()).read_record(page, site.record_spec).status == 'unconfirmed'


def test_u2_unsigned_reports_missing_form_without_submitting():
    # 口径（2026-10-28）：未签就照常走提交链，没有表单即 protocol_pending，不再按小时暂缓。
    site = get_native_module('u2')
    http = Http(['<main>未签到</main>'])
    result = site.signin(context(site, http))
    assert result.status == 'protocol_pending'
    assert result.message == '未发现唯一签到表单'
    assert http.calls == [('get', site.url + 'showup.php')]


def test_nexus_unconfirmed_defer_gate_does_not_change_default_flow():
    site = get_native_module('u2')
    ctx = context(site, Http(['<main>unknown</main>']))
    deferred = ctx.result(status='unconfirmed', message='deferred')
    deferred.metadata['defer_submission'] = True
    with patch.object(site, 'read_before', return_value=deferred), \
            patch.object(site, 'discover_form') as discover:
        result = site.signin(ctx)
    discover.assert_not_called()
    assert result is deferred
    assert ctx.http.calls == [('get', site.url + 'showup.php')]

    ctx = context(site, Http(['<main>unknown</main>']))
    ordinary = ctx.result(status='unconfirmed', message='ordinary')
    with patch.object(site, 'read_before', return_value=ordinary), \
            patch.object(site, 'discover_form', return_value=None) as discover:
        result = site.signin(ctx)
    discover.assert_called_once()
    assert result.status == 'protocol_pending'
    assert result.message == '未发现唯一签到表单'


@pytest.mark.parametrize('site_id,page_html', [
    ('u2', '<a href="showup.php">已签到</a>'),
    ('retrotoon', '<div class="rt-form-card"><span>Daily Reward already claimed</span></div>'),
])
def test_reset_hour_before_window_only_rewords_message(site_id, page_html):
    # reset_hour 只改证据归属与消息：状态仍是 already（跳过本轮、不提交），恢复小时前后都照常判定。
    site = get_native_module(site_id)
    assert site.reset_hour == 9
    with patch('autoptcheckin.core.nexus.datetime') as fake_dt:
        fake_dt.now.return_value.hour = 8
        early = site.signin(context(site, Http([page_html])))
    assert early.status == 'already'
    assert early.message == '昨日已签，站点 9 点后刷新'

    with patch('autoptcheckin.core.nexus.datetime') as fake_dt:
        fake_dt.now.return_value.hour = 10
        late = site.signin(context(site, Http([page_html])))
    assert late.status == 'already'
    assert late.message != '昨日已签，站点 9 点后刷新'


def test_reset_hour_not_declared_keeps_page_message():
    site = get_native_module('tjupt')
    assert site.reset_hour is None
    with patch('autoptcheckin.core.nexus.datetime') as fake_dt:
        fake_dt.now.return_value.hour = 3
        result = site.signin(context(site, Http(['<a href="attendance.php">今日已签到</a>'])))
    assert result.status == 'already'
    assert result.message == '今日已签到'


def test_ttg_safe_homepage_marker():
    site = get_native_module('ttg')
    http = Http(['<b style="color:green;">已签到</b>'])
    assert site.signin(context(site, http)).status == 'already'
    assert http.calls == [('get', site.url)]


def test_yzyy_scoped_button_three_states():
    site = get_native_module('yzyy')
    ctx = context(site, Http())
    for text, state in [('今日已打卡', 'signed'), ('点击打卡', 'unsigned'), ('unknown', 'unconfirmed')]:
        page = LoginPage(f'<div class="signbtn">{text}</div>', site.url)
        assert ctx.read_record(page, site.record_spec).status == state
    assert ctx.read_record(LoginPage('<main>今日已打卡</main>', site.url), site.record_spec).status == 'unconfirmed'


@pytest.mark.parametrize('site_id', ['darkland', 'digitalcore'])
def test_login_only_never_invents_signin_or_sends_requests(site_id):
    site = get_native_module(site_id)
    http = Http()
    ctx = context(site, http)
    assert site.login_capable
    for text in ['<form action="logout"></form>', '{"user":{"id":1}}', 'unknown']:
        assert ctx.read_record(LoginPage(text, site.url), site.record_spec).status == 'unconfirmed'
        result = site.signin(ctx)
        assert result.status == 'skipped'
        assert result.metadata['reason'] == 'signin_not_applicable'
    assert http.calls == []


def test_yema_uses_cloak_page_actions_not_api_receipt():
    site = get_native_module('yema')
    assert getattr(site, 'signin_capable', True) and site.cloak_steps == ('altcha', 'sign_button')
    assert site.record_spec.source == 'page_message'



def test_zhuque_skill_receipt_exact_status_not_homepage():
    site = get_native_module('zhuque')
    for value, state in [(200, 'signed'), (403, 'unconfirmed'), (None, 'unconfirmed'), ('200', 'unconfirmed'), (True, 'unconfirmed')]:
        payload = json.dumps({'status': value, 'data': {'code': 'FIRE_GENSHIN_CHARACTER_MAGIC_SUCCESS', 'bonus': 0}})
        assert context(site, Http()).read_record(LoginPage(payload, site.url), site.record_spec).status == state
        http = Http([payload])
        assert site.signin(context(site, http)).status == 'protocol_pending'
        assert http.calls == [('get', site.url)]


@pytest.mark.parametrize('error', [False, True])
def test_ptzone_unconditional_fresh_readback(error):
    site = get_native_module('ptzone')
    form = '<form method="post" action="attendance.php"><button>簽到</button></form>'
    for text, status in [('簽到成功', 'success'), ('未签到', 'failed'), ('unknown', 'unconfirmed')]:
        http = Http([form, message(text)], error)
        assert site.signin(context(site, http)).status == status
        assert [call[0] for call in http.calls] == ['get', 'post', 'get']
        assert http.calls[0][1] == http.calls[-1][1] == urljoin(site.url, '/attendance.php')


@pytest.mark.parametrize('read_only', [False, True])
def test_new_sites_enabled_and_selected_execute_without_verified_gate(monkeypatch, read_only):
    """能力声明只决定 UI 选项：启用并勾选即执行；仅登录声明站在凭据前拦截。"""
    module = importlib.import_module('autoptcheckin')
    plugin = module.AutoPtCheckin()
    rows = {row['id']: row for row in discover_sites()['sites']}
    monkeypatch.setattr(module, 'managed_site', lambda sid: {})
    called = []
    monkeypatch.setattr(module, 'run_native',
                        lambda runner, site, info, **kwargs: called.append(site.id) or SignResult(SignStatus.SUCCESS, 'ok'))
    for site_id in IDS:
        row = rows[site_id]
        assert row['native']
        assert row['hook_implemented'] == (site_id in CAPTCHA + ['ptzone', 'tjupt', 'darkland', 'digitalcore', 'yzyy'] + C34)
        plugin._config = {'enabled_sites': [site_id], 'sign_sites': [site_id]}
        result = plugin._execute_site(site_id, read_only=read_only, trigger="scheduler")
        if site_id in ['darkland', 'digitalcore']:
            assert result['metadata']['reason'] == 'signin_not_applicable'
            assert site_id not in called
        elif site_id in ['tjupt', 'zhuque']:
            # 答题站风险声明（2026-10-22）与朱雀技能动作非每日签到（2026-10-29 用户裁决）：均 signin_capable=False，仅登录。
            assert result['status'] == 'skipped' and result['metadata']['reason'] == 'signin_not_supported'
            assert site_id not in called
        else:
            assert result['status'] == 'signed'
            assert site_id in called
