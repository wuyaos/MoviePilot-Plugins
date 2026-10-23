"""B1-7 source-derived evidence fixtures; no live requests or host credentials."""
import importlib
import json
import sys
from pathlib import Path
from urllib.parse import urljoin

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / "plugins.v3"))
from autoptcheckin.core.credentials import Credential
from autoptcheckin.core.models import LoginPage
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
        assert site.signin(context(site, http)).status == 'already'
        assert len(http.calls) == 1
    page = LoginPage("<script>window.location.href = 'showup.php';</script>", site.url)
    assert context(site, Http()).read_record(page, site.record_spec).status == 'unconfirmed'


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
    assert site.signin_capable and site.cloak_steps == ['altcha', 'sign_button']
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
@pytest.mark.parametrize('verified', [False, True])
def test_new_sites_registry_and_hook_gates(monkeypatch, read_only, verified):
    module = importlib.import_module('autoptcheckin')
    plugin = module.AutoPtCheckin()
    rows = {row['id']: row for row in discover_sites()['sites']}
    def forbidden(*args, **kwargs):
        pytest.fail('gate must precede credential lookup and requests')
    monkeypatch.setattr(module, 'managed_site', forbidden)
    monkeypatch.setattr(module, 'run_native', forbidden)
    for site_id in IDS:
        row = rows[site_id]
        assert row['native'] and not row['verified']
        assert row['hook_implemented'] == (site_id in CAPTCHA + ['ptzone', 'tjupt', 'darkland', 'digitalcore', 'yzyy'] + C34)
        if verified and site_id in CAPTCHA + ['ptzone', 'tjupt', 'darkland', 'digitalcore', 'yzyy'] + C34:
            continue
        monkeypatch.setattr(module, 'get_registry', lambda *args: {'sites': [dict(row, verified=verified)]})
        result = plugin._execute_site(site_id, read_only=read_only, trigger="scheduler")
        assert result['status'] == 'skipped'
        assert result['metadata']['reason'] == ('signin_not_applicable' if site_id in ['darkland', 'digitalcore'] else 'hook_not_implemented' if verified else 'native_unverified')


@pytest.mark.parametrize('site_id', ['ttg', 'zhuque', 'yzyy'])
def test_side_effect_endpoints_not_used_for_pre_read(site_id):
    site = get_native_module(site_id)
    http = Http(['<main>unknown</main>'])
    assert site.signin(context(site, http)).status == ('protocol_pending' if site_id in {'ttg', 'zhuque', 'yzyy'} else 'unconfirmed')
    safe = ('get', urljoin(site.url, site.attendance_path))
    assert http.calls == ([safe, ('get', site.url + 'api/consumer/checkIn'), safe] if site_id == 'yema' else [safe])
    assert site.attendance_path in {'/', '/plugin.php?id=zqlj_sign'}
