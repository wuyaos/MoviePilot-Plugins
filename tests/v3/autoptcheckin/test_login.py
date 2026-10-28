import asyncio
import pytest
from pathlib import Path
DATE = '2026-10-17'
FIXTURES = Path(__file__).parent / 'fixtures'
def page(site='hdsky', state='success'):
    return (FIXTURES / f'{site}_{state}.html').read_text(encoding='utf8')
from autoptcheckin import AutoPtCheckin
from autoptcheckin.core.models import LoginPage, LoginResult, LoginStatus
from autoptcheckin.core.native import read_login_twice
from autoptcheckin.core.credentials import CredentialCheck
from autoptcheckin.integrations.rousi import RousiProtocol
from autoptcheckin.integrations.sunnypt import SunnyPtProtocol


class _Site:
    """登录回读用的最小站点桩：只提供 parse_login。"""

    def __init__(self, result=None, error=None):
        self._result, self._error = result, error

    def parse_login(self, page, credential=None):
        if self._error:
            raise self._error
        return self._result


def test_login_reads_twice_only_after_unconfirmed_first_read():
    values = iter([TimeoutError(), LoginPage(page(), 'https://fixture.invalid/')])
    calls = []

    def fetch():
        calls.append(1)
        value = next(values)
        if isinstance(value, Exception):
            raise value
        return value

    result = read_login_twice(fetch, _Site(LoginResult(LoginStatus.LOGIN_OK, '已登录')))
    assert len(calls) == 2 and result.status == 'login_ok'


def test_login_first_read_confirmed_short_circuits():
    calls = []
    result = read_login_twice(lambda: calls.append(1) or LoginPage(page(), 'https://fixture.invalid/'),
                              _Site(LoginResult(LoginStatus.LOGIN_OK, '已登录')))
    assert len(calls) == 1 and result.status == 'login_ok'


def test_login_parser_failure_is_unconfirmed():
    result = read_login_twice(lambda: LoginPage(page(), 'https://fixture.invalid/'),
                              _Site(error=ValueError()))
    assert result.status == 'unconfirmed' and result.evidence is None


def test_login_unreachable_page_is_unconfirmed():
    def fail(): raise TimeoutError()
    assert read_login_twice(fail, _Site()).status == 'unconfirmed'


@pytest.mark.parametrize('protocol', [RousiProtocol, SunnyPtProtocol])
def test_integrations_require_real_checker(protocol):
    assert protocol().login().message == 'login_check_not_available'
    assert protocol(lambda ctx: CredentialCheck('valid')).login().status == 'login_ok'
    assert protocol(lambda ctx: CredentialCheck('invalid')).login().status == 'auth_failed'
    assert protocol(lambda ctx: CredentialCheck('timeout')).login().status == 'unconfirmed'

def test_login_only_dispatch_and_api(monkeypatch):
    import autoptcheckin as module
    calls = []
    from autoptcheckin.core.native import NativeHttpClient
    monkeypatch.setattr(module, 'managed_site', lambda sid: {'cookie': 'fixture'})
    def fetch(self, url):
        calls.append('get')
        return LoginPage(page(), url)
    monkeypatch.setattr(NativeHttpClient, 'get', fetch)
    plugin = AutoPtCheckin()
    plugin.init_plugin({'enabled_sites':['hdsky'], 'login_sites':['hdsky']})
    result = plugin._execute_all()[0]
    assert result['status'] == 'login_ok' and calls == ['get']
    assert plugin._history.list()['items'][0]['action'] == 'login'
    assert asyncio.run(plugin.api_login_by_domain('hdsky'))['data']['status'] == 'login_ok'
    row = plugin._site_rows()[0]
    assert row['login_selected'] and row['can_login'] and not row['sign_selected']
    # D4 后 /sites 最新记录含模拟登录：hdsky 仅登录时卡片状态同步为 login_ok
    assert row['login_state'] == 'success'
    assert next(r for r in plugin.get_api() if r['path'] == '/login_by_domain')['auth'] == 'bear'
    dispatched = []
    monkeypatch.setattr(plugin, '_execute_site', lambda sid, **kw: dispatched.append((sid,kw['action'])))
    plugin._config.update(enabled_sites=['hdsky','haitang','rousi'],sign_sites=['hdsky'],login_sites=['hdsky','haitang','rousi'])
    plugin._execute_all()
    assert dispatched == [('hdsky','sign'),('haitang','login'),('rousi','login')]


def test_login_integration_is_enabled_by_default(monkeypatch):
    import autoptcheckin as module
    monkeypatch.setattr(module, 'managed_site', lambda sid: {'cookie': ''})
    monkeypatch.setattr(module, 'run_integration', lambda *a, **kw: LoginResult(LoginStatus.LOGIN_OK))
    plugin = AutoPtCheckin()
    plugin.init_plugin({'enabled_sites':['rousi'], 'login_sites':['rousi']})
    result = plugin._execute_site('rousi', action='login')
    assert result['status'] == 'login_ok'
    assert plugin._track_store().state_of('rousi', 'login') == 'pending'  # mocked dispatcher does not persist
