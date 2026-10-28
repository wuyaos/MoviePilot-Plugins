"""C7 omissions: synthetic protocol/readback fixtures, no station requests."""
from datetime import date
from types import SimpleNamespace
from threading import Event

import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[3] / "plugins.v3"))

from autoptcheckin.core.credentials import Credential
from autoptcheckin.core.models import LoginPage
from autoptcheckin.core.registry import get_native_module
from autoptcheckin.core.sitemodel import SignContext
from autoptcheckin.core.native import NativeHttpClient, run_native

QUIZ = '<form><table><tr><td class="text">请问：测试？</td></tr></table><input name="questionid" value="42"><input name="choice[]" value="7"><input name="choice[]" value="8"></form>'


def message(text):
    return f'<div class="alert">{text}</div>'


def discuz(button='点击打卡', row='未打卡', uid='42'):
    return (f'<div id="um"><a href="space-uid-{uid}.html">自己</a></div>'
            f'<div class="signbtn"><a href="plugin.php?id=zqlj_sign&amp;sign=abcd1234">{button}</a></div>'
            f'<table><tbody id="tb_my"><tr><td><a href="space-uid-{uid}.html">自己</a></td>'
            f'<td>{date.today().isoformat()} 08:00:00</td><td>{row}</td></tr></tbody></table>')


class Http:
    def __init__(self, pages, receipt='获得12点魔力值'):
        self.pages = iter(pages)
        self.receipt = receipt
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(('get', url, kwargs))
        value = next(self.pages)
        if isinstance(value, Exception):
            raise value
        return LoginPage(value, url)

    def post(self, url, **kwargs):
        self.calls.append(('post', url, kwargs))
        if isinstance(self.receipt, Exception):
            raise self.receipt
        return LoginPage(self.receipt, url)


def context(site, http):
    return SignContext(site.id, Credential('test', 'synthetic'), http)


@pytest.mark.parametrize('site_id', ['chdbits'])
@pytest.mark.parametrize('text,status', [('今天已经签过到了', 'success'), ('未签到', 'failed'), ('未知内容', 'unconfirmed')])
def test_bakatest_three_states_and_random_choice(site_id, text, status):
    site = get_native_module(site_id)
    http = Http([QUIZ, message(text)])
    result = site.signin(context(site, http))
    assert site.hook_implemented and result.status == status
    assert result.reward.reported == '12'
    assert [call[0] for call in http.calls] == ['get', 'post', 'get']
    data = dict(http.calls[1][2]['data'])
    assert data.pop('choice[]') in ('7', '8')
    assert data == {'questionid': '42', 'usercomment': '太难了！', 'wantskip': '不会'}


@pytest.mark.parametrize('site_id', ['chdbits'])
def test_bakatest_repeat_timeout_and_missing_form(site_id):
    site = get_native_module(site_id)
    http = Http([message('今天已经签过到了')])
    assert site.signin(context(site, http)).status == 'already'
    assert len(http.calls) == 1
    http = Http([QUIZ, message('今天已经签过到了')], TimeoutError())
    assert site.signin(context(site, http)).status == 'success'
    assert [c[0] for c in http.calls] == ['get', 'post', 'get']
    http = Http([QUIZ.replace('questionid', 'other')])
    assert site.signin(context(site, http)).status == 'unconfirmed'
    assert len(http.calls) == 1
    http = Http([QUIZ, TimeoutError()])
    assert site.signin(context(site, http)).status == 'unconfirmed'


@pytest.mark.parametrize('button,row,status', [('今日已打卡', '今日已打卡', 'success'), ('点击打卡', '未打卡', 'failed'), ('未知', '未知', 'unconfirmed')])
def test_yzyy_three_states_fresh_button_and_own_row(button, row, status):
    site = get_native_module('yzyy')
    http = Http([discuz(), '<p>打卡成功</p>', discuz(button, row)])
    result = site.signin(context(site, http))
    assert result.status == status
    assert result.evidence.button_text == button
    assert result.evidence.uid == '42' and result.evidence.date == date.today().isoformat()
    assert len(http.calls) == 3
    assert http.calls[1][1].endswith('plugin.php?id=zqlj_sign&sign=abcd1234')
    assert http.calls[1][2]['referer'].endswith('plugin.php?id=zqlj_sign')


def test_yzyy_action_exception_still_reads_and_never_uses_receipt():
    site = get_native_module('yzyy')
    http = Http([discuz(), TimeoutError(), discuz('今日已打卡', '今日已打卡')])
    assert site.signin(context(site, http)).status == 'success'
    assert len(http.calls) == 3
    http = Http([discuz(), '<div class="signbtn">今日已打卡</div>', TimeoutError()])
    assert site.signin(context(site, http)).status == 'unconfirmed'
    assert len(http.calls) == 3


def test_yzyy_repeat_and_foreign_action():
    site = get_native_module('yzyy')
    http = Http([discuz('今日已打卡', '今日已打卡')])
    assert site.signin(context(site, http)).status == 'already'
    assert len(http.calls) == 1
    ctx = context(site, Http([]))
    assert site.read_after(ctx, LoginPage(discuz('今日已打卡', '未打卡'))).status == 'unconfirmed'
    ctx.credential = Credential('test', 'synthetic', '99')
    assert site.read_after(ctx, LoginPage(discuz('今日已打卡', '今日已打卡'))).status == 'success'
    http = Http([discuz().replace('href="plugin.php', 'href="https://other.invalid/plugin.php')])
    assert site.signin(context(site, http)).status == 'protocol_pending'
    assert len(http.calls) == 1


@pytest.mark.parametrize('raises', [False, True])
def test_yzyy_session_lifecycle_inside_site_lock(monkeypatch, raises):
    import requests
    from contextlib import contextmanager
    active = []
    sessions = []
    class Session:
        def __init__(self):
            assert active == ['locked']
            self.closed = False
            sessions.append(self)
        def close(self):
            assert active == ['locked']
            self.closed = True
    class Locks:
        @contextmanager
        def acquire(self, key):
            active.append('locked')
            yield True
            active.pop()
    monkeypatch.setattr(requests, 'Session', Session)
    site = get_native_module('yzyy')
    def signin(ctx):
        assert ctx.http.session is sessions[0] and not sessions[0].closed
        if raises:
            raise RuntimeError('synthetic')
        return ctx.result(status='unconfirmed')
    monkeypatch.setattr(site, 'signin', signin)
    runner = SimpleNamespace(locks=Locks(), stop=Event(), history=None, notify=None)
    assert run_native(runner, site, {'cookie': 'fixture=value'}).status == 'unconfirmed'
    assert sessions[0].closed and active == []


def test_yzyy_session_cookie_refresh(monkeypatch):
    import sys
    jar = SimpleNamespace(get_dict=lambda: {'sid': 'fresh'})
    session = SimpleNamespace(cookies=jar)
    seen = []
    class Request:
        def __init__(self, **kwargs):
            seen.append(kwargs)
        def get_res(self, **kwargs):
            return SimpleNamespace(content=b'page', headers={}, url=kwargs['url'], status_code=200, cookies=jar)
    monkeypatch.setitem(sys.modules, 'app.sdk.network', SimpleNamespace(RequestUtils=Request))
    monkeypatch.setitem(sys.modules, 'app.sdk.config', SimpleNamespace(settings=SimpleNamespace(PROXY=None)))
    http = NativeHttpClient(Credential('test', 'sid=old'), {}, session=session)
    http.get('https://example.invalid/')
    http.get('https://example.invalid/')
    assert all(call['session'] is session for call in seen)
    assert http.cookies['sid'] == 'fresh'


def test_yzyy_uid_does_not_block_submission():
    site = get_native_module('yzyy')
    http = Http([discuz()])
    ctx = context(site, http)
    ctx.credential = Credential('test', 'synthetic', '99')
    assert site.signin(ctx).status == 'unconfirmed'
    assert len(http.calls) == 3


def test_c7_inventory_all_b18_ids_are_accounted_for():
    from autoptcheckin.core.registry import discover_sites
    ids = set('chdbits baozi dongying kelu naturept novahd oshen phoenixpt playlet shaobaoyuan soulvoice tu88 vclib lajidui siqi btschool haidan hdarea hdcity hdupt hhanclub nexushd pttime tjupt ttg u2 yzyy darkland digitalcore mteam yema hdchina opencd pterclub zhuque'.split())
    rows = {row['id']: row for row in discover_sites()['sites']}
    assert len(ids) == 35 and ids <= rows.keys()
    unverified = set('baozi dongying kelu naturept novahd oshen phoenixpt playlet shaobaoyuan soulvoice tu88 vclib haidan hdarea hdcity hdupt hhanclub nexushd'.split())
    for site_id in ids:
        assert rows[site_id]['hook_implemented'] is (site_id != 'mteam')
    # verified 审批元数据已移除；mteam 保活/答题站仅登录改为显式能力声明。
    assert rows['mteam']['signin_capable'] is False
    assert rows['chdbits']['signin_capable'] is False and rows['tjupt']['signin_capable'] is False
    assert rows['chdbits']['signin_capable'] is False
    for site_id in ['darkland', 'digitalcore']:
        assert get_native_module(site_id).signin_capable is False
    site = get_native_module('mteam')
    assert site.signin(context(site, Http([]))).status == 'skipped'
