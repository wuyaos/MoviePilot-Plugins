"""Offline consumer tests: real action runner through generic submit/stash/readback."""
from types import SimpleNamespace
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[3] / "plugins.v3"))

import pytest

from autoptcheckin.core import cloak
from autoptcheckin.core.models import LoginPage
from autoptcheckin.core.registry import get_native_module
from test_attendance_captcha_c1 import context


class Locator:
    def __init__(self, page, kind):
        self.page, self.kind = page, kind
        self.first = self

    def count(self):
        if self.kind == 'slider':
            return int(self.page.opened and self.page.elapsed >= 1500)
        return int(self.kind != 'absent')

    def click(self):
        if self.kind == 'link':
            self.page.opened = True
            if self.page.navigate:
                self.page.url = 'https://fixture.invalid/52bakatestdate.php'
        elif self.kind == 'verify-error':
            raise RuntimeError('verification control detached')
        else:
            self.page.clicked += 1

    def inner_text(self): return '提交签到' if self.kind == 'sign' else ''
    def is_enabled(self): return True
    def input_value(self): return 'fixture-token' if self.page.verify == 'token' else ''
    def bounding_box(self): return dict(x=0, y=0, width=300 if self.kind == 'track' else 30, height=30)
    def locator(self, selector): return Locator(self.page, 'track')


class Page:
    url = 'https://fixture.invalid/torrents.php'

    def __init__(self, sid, verify='absent', navigate=False):
        self.sid, self.verify, self.navigate = sid, verify, navigate
        self.opened = False
        self.elapsed = self.clicked = self.drags = 0
        self.waits = []
        self.mouse = SimpleNamespace(move=lambda *a, **k: None, down=lambda: None, up=self.drag)

    def drag(self): self.drags += 1
    def locator(self, selector):
        kind = 'absent'
        if selector == 'input[name="cf-turnstile-response"]' and self.verify in ('token', 'timeout'):
            kind = 'token'
        elif selector == 'text=人工验证' and self.verify == 'error':
            kind = 'verify-error'
        elif selector == 'a[href*="bakatest"]' and self.sid == '52pt':
            kind = 'link'
        elif '#dragHandler' in selector and self.sid == '52pt':
            kind = 'slider'
        elif selector == 'button:not([disabled]):has-text("提交签到")':
            kind = 'sign'
        return Locator(self, kind)

    def wait_for_timeout(self, ms):
        self.waits.append(ms)
        self.elapsed += ms
    def wait_for_load_state(self, *a, **k): pass
    def title(self): return '签到'
    def content(self):
        assert self.clicked == 1
        if self.sid == 'audiences':
            return '<h2 class="attendance-card__title">今天已签到</h2>'
        return '<h2>签到已得100</h2>'


@pytest.mark.parametrize('sid', ['audiences', 'mua_xloli', 'vclib'])
@pytest.mark.parametrize('verify', ['absent', 'token', 'timeout', 'error'])
def test_human_verify_continues_to_sign_and_stashed_readback(sid, verify, monkeypatch):
    site = get_native_module(sid)
    assert site.cloak_steps == ['human_verify', 'sign_button']
    page = Page(sid, verify)
    session = SimpleNamespace(page=page, human_verify_timeout=90000 if sid == 'vclib' else 60000)
    results = []
    real_action = cloak.run_page_action
    def action(session, steps):
        results.extend(real_action(session, steps))
    monkeypatch.setattr(cloak, 'run_page_action', action)
    http = SimpleNamespace(
        session=session,
        run_page_action=lambda steps: cloak.run_page_action(session, list(steps)),
        page_snapshot=lambda: (page.content(), page.url),
        get=lambda *a, **k: LoginPage('<main>待签到</main>', page.url, 200))
    result = site.signin(context(site, http, None))
    expected = {'absent': 'absent', 'token': 'turnstile-ok', 'timeout': 'turnstile-timeout', 'error': 'error'}[verify]
    assert results == [('human_verify', expected), ('sign_button', 'clicked')]
    assert result.status == 'success'
    assert page.clicked == 1
    # human_verify 重写后 absent/error 也走 CF iframe poke 轮询，每轮等 1500ms；token 直通不等待
    assert page.waits.count(1500) == ((60 if sid == 'vclib' else 40) if verify != 'token' else 0)


@pytest.mark.parametrize('navigate', [False, True])
def test_52pt_attendance_link_waits_for_delayed_slider_then_stashes(navigate, monkeypatch):
    site = get_native_module('52pt')
    assert site.cloak_steps == ['attendance_link', 'slider', 'sign_button']
    page = Page('52pt', navigate=navigate)
    results = []
    real_action = cloak.run_page_action
    def action(session, steps): results.extend(real_action(session, steps))
    monkeypatch.setattr(cloak, 'run_page_action', action)
    session52 = SimpleNamespace(page=page)
    http = SimpleNamespace(
        session=session52,
        run_page_action=lambda steps: cloak.run_page_action(session52, list(steps)),
        page_snapshot=lambda: (page.content(), page.url),
        get=lambda *a, **k: LoginPage('<a href="52bakatestdate.php">签到赚魔力</a>', page.url, 200))
    result = site.signin(context(site, http, None))
    assert results == [('attendance_link', 'clicked'), ('slider', 'dragged'), ('sign_button', 'clicked')]
    assert page.waits[:3] == [500, 500, 500]
    assert page.drags == page.clicked == 1
    assert result.status == 'success' and result.message == '签到已得100'


def test_human_verify_timeout_is_per_site_even_in_shared_session(monkeypatch):
    class Session:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
    monkeypatch.setattr(cloak, 'CloakSession', Session)
    http = SimpleNamespace(cookies={})
    shared = SimpleNamespace(context=SimpleNamespace(cookies=lambda url: []))
    for sid, timeout in [('vclib', 90000), ('mua_xloli', 60000), ('audiences', 60000)]:
        site = get_native_module(sid)
        for session in (None, shared):
            client = cloak.CloakHttpClient(http, {'url': 'https://fixture.invalid/'}, site, shared=session)
            assert client.session.human_verify_timeout == timeout
