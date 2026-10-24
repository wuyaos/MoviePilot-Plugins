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
    obj.init_plugin({'enabled_sites': [sid], 'login_sites': [sid], 'unlock_all_sites': True, **config})
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
    obj = plugin(sid)
    result = asyncio.run(obj.api_login_by_domain(sid))['data']
    if sid == 'mteam':
        assert result['status'] == 'auth_failed'
        assert offline == calls == []
    else:
        assert result['status'] == 'login_ok'
        assert len(offline) == len(calls) == 2
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
    def unverified(*args):
        data = real(*args)
        for site in data['sites']:
            if site['id'] == 'hdsky':
                site.update(verified=False, hook_implemented=False)
        return data
    monkeypatch.setattr(entry, 'get_registry', unverified)
    assert plugin('hdsky', unlock_all_sites=False)._execute_site('hdsky', action='login')['status'] == 'login_ok'
    assert len(offline) == 2


@pytest.mark.parametrize('source', ['cookiecloud', 'managed_site', 'local_cookie'])
def test_native_login_cookie_candidates(source, offline, monkeypatch):
    if source == 'cookiecloud':
        monkeypatch.setattr(native, 'cookiecloud_candidate', lambda url: CredentialResolution(Credential(source, 'synthetic'), 'valid'))
    if source in ('local_cookie', 'cookiecloud'):
        monkeypatch.setattr(entry, 'managed_site', lambda sid: {})
    obj = plugin('darkland', custom_sites_data=[{'id': 'local', 'url': 'https://darkland.top/', 'cookie': 'synthetic' if source == 'local_cookie' else ''}])
    assert obj._execute_site('darkland', action='login')['status'] == 'login_ok'
    assert [s for _, s in offline] == [source, source]


@pytest.mark.parametrize('pages,uid,status', [
    ([TimeoutError(), LoginPage('<p>ok</p>')], '', 'login_ok'),
    ([LoginPage('<p>ok</p>'), LoginPage('login', 'https://fixture.invalid/login.php')], '', 'auth_failed'),
    ([LoginPage('<p>ok</p>'), None], '', 'unconfirmed'),
    ([LoginPage('<div id="info_block"><a href="userdetails.php?id=41">me</a></div>'), LoginPage('<div id="info_block"><a href="userdetails.php?id=42">me</a></div>')], '', 'unconfirmed'),
    ([LoginPage('<div id="info_block"><a href="userdetails.php?id=41">me</a></div>'), LoginPage('<div id="info_block"><a href="userdetails.php?id=42">me</a></div>')], '42', 'unconfirmed'),
])
def test_unconditional_reread_and_identity(pages, uid, status, offline, monkeypatch):
    calls = []
    def get(self, url):
        value = pages[len(calls)]
        calls.append(url)
        if isinstance(value, Exception):
            raise value
        return value
    monkeypatch.setattr(native.NativeHttpClient, 'get', get)
    obj = plugin('darkland')
    obj._bound_uids['darkland'] = uid
    result = obj._execute_site('darkland', action='login')
    assert len(calls) == 2
    assert result['status'] == status


def test_busy_cancelled_missing_cookie_do_not_read(offline, monkeypatch):
    obj = plugin('darkland')
    with obj._runner.locks.acquire(('darkland', '')):
        assert obj._execute_site('darkland', action='login')['status'] == 'skipped'
    obj._runner.stop.set()
    assert obj._execute_site('darkland', action='login')['status'] == 'cancelled'
    obj._runner.stop.clear()
    monkeypatch.setattr(entry, 'managed_site', lambda sid: {})
    assert obj._execute_site('darkland', action='login')['status'] == 'auth_failed'
    assert not offline


@pytest.mark.parametrize('by', ['60001', 'custom.invalid'])
def test_custom_login_api_routes_and_gates(by, offline):
    obj = plugin('60001', unlock_all_sites=False, custom_sites_data=[{
        'id': '60001', 'name': 'fixture', 'url': 'https://custom.invalid/', 'cookie': 'synthetic'}])
    result = asyncio.run(obj.api_login_by_domain(by))['data']
    assert result['status'] == 'login_ok'
    assert len(offline) == 2
    obj._config['login_sites'] = []
    assert asyncio.run(obj.api_login_by_domain(by))['data']['metadata']['reason'] == 'login_not_selected'
    assert len(offline) == 2


def test_custom_login_rejects_login_form(offline, monkeypatch):
    monkeypatch.setattr(native.NativeHttpClient, 'get', lambda self, url: LoginPage('<input type="password">', url))
    obj = plugin('custom-fixture', custom_sites_data=[{'id': 'custom-fixture', 'url': 'https://custom.invalid/', 'cookie': 'synthetic'}])
    assert obj._execute_site('custom-fixture', action='login')['status'] == 'auth_failed'


@pytest.mark.parametrize('registered', [True, False])
def test_non_native_domain_requires_configured_managed_host(registered, offline, monkeypatch):
    oper = ModuleType('app.db.oper')
    monkeypatch.setitem(sys.modules, 'app.db.oper', oper)
    row = SimpleNamespace(url='https://filelist.invalid/', name='fixture', cookie='synthetic', ua=None, proxy=False)
    monkeypatch.setattr(oper, 'SiteOper', lambda: SimpleNamespace(list_order_by_pri=lambda: [row] if registered else []), raising=False)
    monkeypatch.setattr(entry, 'managed_site', registry.managed_site)
    obj = plugin('filelist.invalid')
    result = asyncio.run(obj.api_login_by_domain('https://filelist.invalid/'))['data']
    assert result['status'] == ('login_ok' if registered else 'unconfirmed')
    assert len(offline) == (2 if registered else 0)
    assert asyncio.run(obj.api_login_by_domain('arbitrary.invalid'))['success'] is False


def test_non_native_registry_id_uses_matcher(offline, monkeypatch):
    oper = ModuleType('app.db.oper')
    monkeypatch.setitem(sys.modules, 'app.db.oper', oper)
    real = entry.get_registry
    def with_legacy(*args):
        data = real(*args)
        data['sites'].append({'id': 'legacy_fixture', 'native': False, 'login_capable': True})
        return data
    monkeypatch.setattr(registry, 'get_registry', with_legacy)
    monkeypatch.setattr(entry, 'get_registry', with_legacy)
    monkeypatch.setitem(registry._MATCHERS, 'legacy_fixture', lambda url: registry.hostname(url) == 'legacy.invalid')
    row = SimpleNamespace(url='https://legacy.invalid/', name='fixture', cookie='synthetic', ua=None, proxy=False)
    monkeypatch.setattr(oper, 'SiteOper', lambda: SimpleNamespace(list_order_by_pri=lambda: [row]), raising=False)
    monkeypatch.setattr(entry, 'managed_site', registry.managed_site)
    assert asyncio.run(plugin('legacy_fixture').api_login_by_domain('legacy.invalid'))['data']['status'] == 'login_ok'
    assert len(offline) == 2


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
