"""D5 login dispatch: no legacy submission adapter, no real network."""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[3] / 'plugins.v3'))
from types import SimpleNamespace, ModuleType

import pytest

import autoptcheckin as entry
from autoptcheckin.core import native, registry
from autoptcheckin.core.credentials import Credential, CredentialCheck, CredentialResolution
from autoptcheckin.core.models import LoginPage
from autoptcheckin.core.runner import SignRunner


@pytest.fixture
def offline(monkeypatch):
    calls = []
    monkeypatch.setattr(native, 'cookiecloud_candidate', lambda url: CredentialResolution(None, 'unavailable'))
    monkeypatch.setattr(entry, 'managed_site', lambda sid: {'cookie': 'synthetic'})
    def get(self, url):
        calls.append((url, self.credential.source))
        return LoginPage('<html>reachable</html>', url)
    monkeypatch.setattr(native.NativeHttpClient, 'get', get)
    monkeypatch.setattr(native.NativeHttpClient, 'post', lambda *a, **k: pytest.fail('login submitted'))
    return calls


def plugin(sid, **config):
    obj = entry.AutoPtCheckin()
    obj.init_plugin({'enabled_sites': [sid], 'login_sites': [sid], **config})
    return obj


@pytest.mark.parametrize('sid', ['hdsky', 'haitang', 'darkland', 'digitalcore', 'mteam', '52pt', 'chdbits'])
def test_native_api_dispatch_without_bridge(sid, offline, monkeypatch):
    site = registry.get_native_module(sid)
    calls = []
    original = site.parse_login
    def parse(page, credential=None):
        calls.append(page)
        return original(page, credential)
    site.parse_login = parse
    monkeypatch.setattr(entry, 'get_native_module', lambda _: site)
    # 52pt 内置声明 emulate=true；HTTP 分发契约用显式 site_emulate=false 关闭仿真。
    obj = plugin(sid, site_emulate={'52pt': False})
    result = asyncio.run(obj.api_login_by_domain(sid))['data']
    if sid == 'mteam':
        assert result['status'] == 'failed' and result['reason'] == 'auth_failed'
        assert offline == calls == []
    else:
        assert result['status'] == 'login_ok'
        assert len(offline) == len(calls) == 1
        assert all(url.endswith('/') for url, _ in offline)
    assert result['metadata']['action'] == 'login'
    assert obj._history.list()['total'] == 1
    assert not any(obj._history.today_counts().values())


@pytest.mark.parametrize('config,reason', [
    ({'enabled_sites': []}, 'site_disabled'),
    ({'login_sites': []}, 'login_not_selected'),
])
def test_native_login_gates(config, reason, offline):
    result = plugin('darkland', **config)._execute_site('darkland', action='login')
    assert result['metadata']['reason'] == reason
    assert not offline


def test_signin_gates_do_not_block_login(offline, monkeypatch):
    real = entry.get_registry
    def unverified(*args, **kwargs):
        data = real(*args, **kwargs)
        for site in data['sites']:
            if site['id'] == 'hdsky':
                site.update(verified=False, hook_implemented=False)
        return data
    monkeypatch.setattr(entry, 'get_registry', unverified)
    assert plugin('hdsky')._execute_site('hdsky', action='login')['status'] == 'login_ok' 
    assert len(offline) == 1


@pytest.mark.parametrize('source', ['cookiecloud', 'managed_site', 'local_cookie'])
def test_native_login_cookie_candidates(source, offline, monkeypatch):
    if source == 'cookiecloud':
        monkeypatch.setattr(native, 'cookiecloud_candidate', lambda url: CredentialResolution(Credential(source, 'synthetic'), 'valid'))
    if source in ('local_cookie', 'cookiecloud'):
        monkeypatch.setattr(entry, 'managed_site', lambda sid: {})
    obj = plugin('darkland', custom_sites_data=[{'id': 'local', 'url': 'https://darkland.top/', 'cookie': 'synthetic' if source == 'local_cookie' else ''}])
    assert obj._execute_site('darkland', action='login')['status'] == 'login_ok'
    assert [s for _, s in offline] == [source]


@pytest.mark.parametrize('pages,status,calls_expected', [
    ([TimeoutError(), LoginPage('<p>ok</p>')], 'login_ok', 2),
    ([LoginPage('<p>ok</p>'), LoginPage('login', 'https://fixture.invalid/login.php')], 'login_ok', 1),
    ([LoginPage('login', 'https://fixture.invalid/login.php'), LoginPage('<p>ok</p>')], 'failed', 1),
    ([None, LoginPage('<p>ok</p>')], 'login_ok', 2),
])
def test_login_rereads_only_after_unconfirmed_first_read(pages, status, calls_expected, offline, monkeypatch):
    calls = []
    def get(self, url):
        value = pages[len(calls)]
        calls.append(url)
        if isinstance(value, Exception):
            raise value
        return value
    monkeypatch.setattr(native.NativeHttpClient, 'get', get)
    result = plugin('darkland')._execute_site('darkland', action='login')
    assert len(calls) == calls_expected
    assert result['status'] == status

def test_busy_cancelled_missing_cookie_do_not_read(offline, monkeypatch):
    obj = plugin('darkland')
    with obj._runner.locks.acquire(('darkland', '')):
        assert obj._execute_site('darkland', action='login')['status'] == 'skipped'
    obj._runner.stop.set()
    assert obj._execute_site('darkland', action='login')['status'] == 'cancelled'
    obj._runner.stop.clear()
    monkeypatch.setattr(entry, 'managed_site', lambda sid: {})
    result = obj._execute_site('darkland', action='login')
    assert result['status'] == 'failed' and result['reason'] == 'auth_failed'
    assert not offline


@pytest.mark.parametrize('by', ['60001', 'custom.invalid'])
def test_custom_login_api_routes_and_gates(by, offline):
    obj = plugin('60001', custom_sites_data=[{
        'id': '60001', 'name': 'fixture', 'url': 'https://custom.invalid/', 'cookie': 'synthetic'}])
    result = asyncio.run(obj.api_login_by_domain(by))['data']
    assert result['status'] == 'login_ok'
    assert len(offline) == 1
    obj._config['login_sites'] = []
    assert asyncio.run(obj.api_login_by_domain(by))['data']['metadata']['reason'] == 'login_not_selected'
    assert len(offline) == 1


def test_custom_login_rejects_login_form(offline, monkeypatch):
    monkeypatch.setattr(native.NativeHttpClient, 'get', lambda self, url: LoginPage('<input type="password">', url))
    obj = plugin('custom-fixture', custom_sites_data=[{'id': 'custom-fixture', 'url': 'https://custom.invalid/', 'cookie': 'synthetic'}])
    result = obj._execute_site('custom-fixture', action='login')
    assert result['status'] == 'failed' and result['reason'] == 'auth_failed'


@pytest.mark.parametrize('registered', [True, False])
def test_non_native_domain_requires_configured_managed_host(registered, offline, monkeypatch):
    oper = ModuleType('app.db.oper')
    monkeypatch.setitem(sys.modules, 'app.db.oper', oper)
    row = SimpleNamespace(url='https://filelist.invalid/', name='fixture', cookie='synthetic', ua=None, proxy=False)
    monkeypatch.setattr(oper, 'SiteOper', lambda: SimpleNamespace(list_order_by_pri=lambda: [row] if registered else []), raising=False)
    monkeypatch.setattr(entry, 'managed_site', registry.managed_site)
    obj = plugin('filelist.invalid')
    result = asyncio.run(obj.api_login_by_domain('https://filelist.invalid/'))['data']
    assert result['status'] == ('login_ok' if registered else 'pending')
    if not registered:
        assert result['reason'] == 'result_unknown'
    assert len(offline) == (1 if registered else 0)
    assert asyncio.run(obj.api_login_by_domain('arbitrary.invalid'))['success'] is False


def test_non_native_registry_id_uses_matcher(offline, monkeypatch):
    oper = ModuleType('app.db.oper')
    monkeypatch.setitem(sys.modules, 'app.db.oper', oper)
    real = entry.get_registry
    def with_legacy(*args, **kwargs):
        data = real(*args, **kwargs)
        data['sites'].append({'id': 'legacy_fixture', 'native': False, 'login_capable': True})
        return data
    monkeypatch.setattr(registry, 'get_registry', with_legacy)
    monkeypatch.setattr(entry, 'get_registry', with_legacy)
    monkeypatch.setitem(registry._MATCHERS, 'legacy_fixture', lambda url: registry.hostname(url) == 'legacy.invalid')
    row = SimpleNamespace(url='https://legacy.invalid/', name='fixture', cookie='synthetic', ua=None, proxy=False)
    monkeypatch.setattr(oper, 'SiteOper', lambda: SimpleNamespace(list_order_by_pri=lambda: [row]), raising=False)
    monkeypatch.setattr(entry, 'managed_site', registry.managed_site)
    assert asyncio.run(plugin('legacy_fixture').api_login_by_domain('legacy.invalid'))['data']['status'] == 'login_ok'
    assert len(offline) == 1


def test_mteam_missing_login_credentials(offline):
    site = registry.get_native_module('mteam')
    result = native.run_native_login(SignRunner(), site, {}, config={})
    assert result.status == 'auth_failed'
    assert result.message == '缺少 M-Team 账号或密码'
    assert result.metadata['transport'] == 'cloak'
    assert not offline

class _MTeamLocator:
    def __init__(self, page, selector, present=True):
        self.page = page
        self.selector = selector
        self.present = present

    @property
    def first(self):
        return self

    def count(self):
        return int(self.present)

    def click(self):
        self.page.clicked = self.selector
        self.page.url = 'https://kp.m-team.cc/index'


class _MTeamOtpPage:
    url = 'https://kp.m-team.cc/login'

    def __init__(self, present_selector=None, auto_submit=False):
        self.present_selector = present_selector
        self.auto_submit = auto_submit
        self.clicked = None
        self.entered = False

    def wait_for_url(self, _pattern, timeout):
        if self.auto_submit or '/index' in self.url:
            self.url = 'https://kp.m-team.cc/index'
            return
        raise TimeoutError(timeout)

    def locator(self, selector):
        return _MTeamLocator(self, selector, selector == self.present_selector)

    class _Keyboard:
        def __init__(self, page): self.page = page
        def press(self, key):
            assert key == 'Enter'
            self.page.entered = True
            self.page.url = 'https://kp.m-team.cc/index'

    @property
    def keyboard(self):
        return self._Keyboard(self)


def test_mteam_otp_waits_for_auto_submit_before_clicking():
    from autoptcheckin.sites.native.mteam import _submit_mteam_otp

    page = _MTeamOtpPage(auto_submit=True)
    assert _submit_mteam_otp(page) is True
    assert page.clicked is None
    assert page.entered is False


def test_mteam_otp_clicks_non_button_login_element():
    from autoptcheckin.sites.native.mteam import _MTEAM_OTP_SUBMIT_SELECTORS, _submit_mteam_otp

    selector = _MTEAM_OTP_SUBMIT_SELECTORS[3]
    page = _MTeamOtpPage(present_selector=selector)
    assert _submit_mteam_otp(page) is True
    assert page.clicked == selector
    assert page.entered is False


def test_mteam_otp_falls_back_to_enter():
    from autoptcheckin.sites.native.mteam import _submit_mteam_otp

    page = _MTeamOtpPage()
    assert _submit_mteam_otp(page) is True
    assert page.clicked is None
    assert page.entered is True


@pytest.mark.parametrize('payload,expected,part', [
    ((True, 'M-Team 保活登录成功'), 'login_ok', '保活登录成功'),
    ((False, '登录未到达 /index：检测到邮箱验证码'), 'unconfirmed', '邮箱验证码'),
    ((False, '登录未到达 /index：未知页面'), 'auth_failed', '未知页面'),
])
def test_mteam_keepalive_login_classification(offline, monkeypatch, tmp_path, payload, expected, part):
    # 线程隔离修复后的分类语义不变：run_isolated 透传 launch 结果，三分支照旧。
    from autoptcheckin.core import cloak
    site = registry.get_native_module('mteam')
    monkeypatch.setattr(cloak, 'state_path', lambda sid: tmp_path / f'{sid}.json')
    monkeypatch.setattr(cloak, 'run_isolated', lambda fn: payload)
    result = native.run_native_login(SignRunner(), site,
                                     {'mteam_username': 'u', 'mteam_password': 'p'}, config={})
    assert result.status == expected
    assert part in result.message


def test_mteam_launch_exception_maps_to_unconfirmed(offline, monkeypatch, tmp_path):
    # qnap 00:46 实况：宿主线程带 running loop 时 Sync Playwright 抛错——
    # 异常经 run_isolated 透传，归类 UNCONFIRMED（下轮重试）而非整轨崩溃。
    from autoptcheckin.core import cloak
    site = registry.get_native_module('mteam')
    monkeypatch.setattr(cloak, 'state_path', lambda sid: tmp_path / f'{sid}.json')

    def boom(fn):
        raise RuntimeError('It looks like you are using Playwright Sync API inside the asyncio loop.')
    monkeypatch.setattr(cloak, 'run_isolated', boom)
    result = native.run_native_login(SignRunner(), site,
                                     {'mteam_username': 'u', 'mteam_password': 'p'}, config={})
    assert result.status == 'unconfirmed'
    assert 'CloakBrowser 登录异常' in result.message


class _MTeamInertLocator:
    def __init__(self, page, selector):
        self.page = page
        self.selector = selector

    @property
    def first(self):
        return self

    def count(self):
        return int(self.selector in (self.page.inert, self.page.working))

    def click(self):
        self.page.clicks.append(self.selector)
        if self.selector == self.page.working:
            self.page.url = 'https://kp.m-team.cc/index'


class _MTeamInertPage:
    """命中但点不动（容器）的选择器在前，真正提交的在后的 2FA 页。"""

    url = 'https://kp.m-team.cc/login'

    def __init__(self, inert, working):
        self.inert = inert
        self.working = working
        self.clicks = []

    def wait_for_url(self, _pattern, timeout):
        raise TimeoutError(timeout)

    def locator(self, selector):
        return _MTeamInertLocator(self, selector)

    class _Keyboard:
        def press(self, key):
            raise AssertionError('不应退化到 Enter：有效按钮存在')

    @property
    def keyboard(self):
        return self._Keyboard()


def test_mteam_otp_retries_next_selector_when_first_click_is_inert():
    # qnap 2026-10-29 实况根因：text= 命中外层容器，点了等于点空处，码填了没提交。
    from autoptcheckin.sites.native.mteam import _MTEAM_OTP_SUBMIT_SELECTORS, _submit_mteam_otp

    inert = next(s for s in _MTEAM_OTP_SUBMIT_SELECTORS if s.startswith('text='))
    working = next(s for s in _MTEAM_OTP_SUBMIT_SELECTORS if s.startswith('xpath='))
    assert _MTEAM_OTP_SUBMIT_SELECTORS.index(inert) < _MTEAM_OTP_SUBMIT_SELECTORS.index(working)

    page = _MTeamInertPage(inert=inert, working=working)
    assert _submit_mteam_otp(page) is True
    assert page.clicks == [inert, working]


def test_mteam_otp_selector_priority_prefers_real_buttons():
    from autoptcheckin.sites.native.mteam import _MTEAM_OTP_SUBMIT_SELECTORS

    assert _MTEAM_OTP_SUBMIT_SELECTORS[0] == 'button[type="submit"]'
    assert _MTEAM_OTP_SUBMIT_SELECTORS[1] == 'input[type="submit"]'


def test_mteam_otp_input_selector_covers_modal_and_autocomplete():
    from autoptcheckin.sites.native.mteam import _MTEAM_OTP_INPUT

    assert '#otp-code' in _MTEAM_OTP_INPUT
    assert 'one-time-code' in _MTEAM_OTP_INPUT


@pytest.mark.parametrize('message,expected', [
    ('登录未到达 /index：检测到邮箱验证码', True),
    ('双重认证未通过（已自动填入 mteam_totp 并提交，仍停留 2FA 页）', True),
    ('请输入郵箱驗證碼', True),
    ('登录未到达 /index（当前 https://kp.m-team.cc/login）', False),
    ('', False),
    (None, False),
])
def test_mteam_needs_manual_2fa_covers_traditional_and_simplified(message, expected):
    # 繁体页（郵/驗證碼）曾被当成普通登录失败 → 每轮重试 4 次刷失败记录。
    from autoptcheckin.sites.native.mteam import _needs_manual_2fa

    assert _needs_manual_2fa(message) is expected


class _MTeamSignalBrowser:
    def __init__(self, signal):
        self._signal = signal
        self.gotos = []
        self.page = SimpleNamespace(wait_for_timeout=lambda _ms: None)

    def goto(self, url):
        self.gotos.append(url)

    def evaluate(self, _js):
        return self._signal


@pytest.mark.parametrize('signal,expected', [
    ({'authed': True, 'url': 'https://kp.m-team.cc/index', 'logout': False}, True),
    ({'authed': True, 'url': 'https://kp.m-team.cc/login', 'logout': False}, False),
    ({'authed': False, 'url': 'https://kp.m-team.cc/index', 'logout': False}, False),
    ({'authed': False, 'url': 'https://kp.m-team.cc/index', 'logout': True}, True),
])
def test_mteam_logged_in_needs_token_and_no_login_bounce(signal, expected):
    # 三态实测：未登录访问 /index 不跳转（只看 URL 会误判），失效 token 会被弹回 /login。
    from autoptcheckin.sites.native.mteam import _mteam_logged_in

    browser = _MTeamSignalBrowser(signal)
    assert _mteam_logged_in(browser, 'https://kp.m-team.cc/') is expected
    assert browser.gotos == ['https://kp.m-team.cc/index']


def test_mteam_logged_in_false_when_signal_unavailable():
    from autoptcheckin.sites.native.mteam import _mteam_logged_in

    class _Boom(_MTeamSignalBrowser):
        def evaluate(self, _js):
            raise RuntimeError('no js')

    assert _mteam_logged_in(_Boom({}), 'https://kp.m-team.cc/') is False


def test_mteam_cooldown_returns_unconfirmed_without_relogin(offline, monkeypatch, tmp_path):
    # 冷却期不再重试（旧行为 AUTH_FAILED × retry_count = 每轮 4 条同样失败记录）。
    from autoptcheckin.core import cloak

    site = registry.get_native_module('mteam')
    monkeypatch.setattr(cloak, 'state_path', lambda sid: tmp_path / f'{sid}.json')
    (tmp_path / 'mteam.json.cooldown').write_text('otp-rejected', encoding='utf-8')
    attempts = []
    monkeypatch.setattr(cloak, 'run_isolated', lambda fn: attempts.append(1) or (True, ''))

    result = native.run_native_login(SignRunner(), site,
                                     {'mteam_username': 'u', 'mteam_password': 'p'}, config={})
    assert result.status == 'unconfirmed'
    assert '双重认证' in result.message and 'mteam_totp' in result.message
    assert attempts == []
