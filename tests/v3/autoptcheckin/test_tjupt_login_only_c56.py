"""Synthetic C5/C6 consumer paths; no network clients are invoked."""
import importlib
from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image

from autoptcheckin.core.credentials import Credential
from autoptcheckin.core.models import LoginPage
from autoptcheckin.core.native import run_native
from autoptcheckin.core.registry import discover_sites, get_native_module
from autoptcheckin.core.sitemodel import SignContext
from autoptcheckin.sites.native.tjupt import Tjupt

SIGNED = '<a href="attendance.php">今日已签到</a>'
QUIZ = '<table class="captcha"><tr><td><img src="/quiz.png"></td></tr></table><input name="answer" value="7">Movie'


def image_bytes():
    stream = BytesIO()
    Image.new('L', (10, 10)).save(stream, format='PNG')
    return stream.getvalue()


class Http:
    def __init__(self, fresh=SIGNED, receipt='这是您的首次签到，本次签到获得12个魔力值。'):
        self.pages = iter([QUIZ, fresh])
        self.receipt = receipt
        self.calls = []

    def get(self, url):
        self.calls.append('get')
        page = next(self.pages)
        if isinstance(page, Exception):
            raise page
        return LoginPage(page, url)

    def get_bytes(self, url):
        self.calls.append('image')
        return image_bytes()

    def post(self, url, *, data):
        self.calls.append('post')
        assert data == [('answer', '7'), ('submit', '提交')]
        if isinstance(self.receipt, Exception):
            raise self.receipt
        return LoginPage(self.receipt, url)


def context(http, cached=True):
    cache = {'0' * 100: 'Movie'} if cached else {}
    saves = []
    ctx = SignContext('tjupt', Credential('test', 'synthetic'), http,
                      get_data=lambda key: cache if key == 'tjupt.answer' else None,
                      save_data=lambda key, data: saves.append((key, data)))
    return ctx, saves


@pytest.mark.parametrize('text,state', [(SIGNED, 'signed'), ('<a href="attendance.php">未签到</a>', 'unconfirmed'), ('<main>今日已签到</main>', 'unconfirmed')])
def test_tjupt_three_state_fixture(text, state):
    ctx, _ = context(Http())
    assert ctx.read_record(LoginPage(text), Tjupt.record_spec).status == state


@pytest.mark.parametrize('receipt', ['这是您的首次签到，本次签到获得12个魔力值。', '签到成功，这是您的第2次签到，已连续签到2天，本次签到获得12个魔力值。', '重新签到成功，本次签到获得12个魔力值'])
def test_tjupt_cache_hit_reward_and_readback(receipt):
    http = Http(receipt=receipt)
    ctx, saves = context(http)
    ctx.public_get = lambda *a, **kw: pytest.fail('cache must avoid external requests')
    result = Tjupt().signin(ctx)
    assert result.status == 'success' and result.reward.reported == '12'
    assert result.evidence.button_text == '今日已签到'
    assert saves == [('tjupt.answer', {'0' * 100: 'Movie'})]
    assert http.calls == ['get', 'image', 'post', 'get']


@pytest.mark.parametrize('receipt', ['答案错误', TimeoutError()])
def test_tjupt_wrong_or_timeout_always_reads_no_cache(receipt):
    http = Http(fresh='<a href="attendance.php">请签到</a>', receipt=receipt)
    ctx, saves = context(http)
    assert Tjupt().signin(ctx).status == 'unconfirmed'
    assert saves == [] and http.calls[-2:] == ['post', 'get']


def test_tjupt_external_match_populates_empty_cache():
    http = Http()
    ctx, saves = context(http, cached=False)
    calls = []
    def public(url, **kwargs):
        calls.append((url, kwargs))
        return SimpleNamespace(status_code=200, text='[{"img":"https://img.doubanio.com/a.png"}]', content=image_bytes())
    ctx.public_get = public
    assert Tjupt().signin(ctx).status == 'success'
    assert len(calls) == 2 and saves[0][1] == {'0' * 100: 'Movie'}


def test_tjupt_unknown_image_does_not_guess():
    http = Http()
    ctx, saves = context(http, cached=False)
    ctx.public_get = lambda *a, **kw: SimpleNamespace(status_code=200, text='[]')
    assert Tjupt().signin(ctx).status == 'unconfirmed'
    assert http.calls == ['get', 'image'] and not saves


def test_tjupt_receipt_cannot_replace_unavailable_readback():
    ctx, _ = context(Http(fresh=TimeoutError()))
    assert Tjupt().signin(ctx).status == 'unconfirmed'


@pytest.mark.parametrize('site_id', ['darkland', 'digitalcore'])
@pytest.mark.parametrize('read_only', [False, True])
def test_login_only_gates_before_credentials(monkeypatch, site_id, read_only):
    """仅登录站能力声明（signin_capable=False）在凭据与网络资源之前拦截。"""
    module = importlib.import_module('autoptcheckin')
    plugin = module.AutoPtCheckin()
    row = next(row for row in discover_sites()['sites'] if row['id'] == site_id)
    assert row['hook_implemented'] and row['signin_capable'] is False
    monkeypatch.setattr(module, 'get_registry', lambda *a: {'sites': [dict(row)]})
    monkeypatch.setattr(module, 'managed_site', lambda *a: pytest.fail('must not resolve credentials'))
    result = plugin._execute_site(site_id, read_only=read_only)
    assert result['status'] == 'skipped' and result['metadata']['reason'] == 'signin_not_applicable'
    runner = SimpleNamespace(history=None, notify=None)
    result = run_native(runner, get_native_module(site_id), {}, read_only=read_only)
    assert result.status == 'skipped' and result.metadata['reason'] == 'signin_not_applicable'
