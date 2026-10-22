import asyncio
import pytest
from test_pilot_runner import page, DATE
from autoptcheckin import AutoPtCheckin
from autoptcheckin.core.models import Evidence, LoginPage, LoginResult, LoginStatus
from autoptcheckin.core.verification import normalize_evidence, verify_login
from autoptcheckin.core.runner import SignRunner
from autoptcheckin.core.credentials import Credential, CredentialResolution, CredentialCheck
from autoptcheckin.core.history import HistoryStore
from autoptcheckin.verifiers.hdsky import HDSkyVerifier
from autoptcheckin.verifiers.haitang import HaitangVerifier
from autoptcheckin.integrations.rousi import RousiProtocol
from autoptcheckin.integrations.sunnypt import SunnyPtProtocol

@pytest.mark.parametrize('state,expected', [('success','success'), ('failed','failed')])
def test_record_without_button_confirms(state, expected):
    assert normalize_evidence(Evidence(uid='42', date=DATE, status=state), '42', DATE).status == expected
    assert normalize_evidence(Evidence(uid='99', date=DATE, status=state), '42', DATE).status == 'unconfirmed'
    assert normalize_evidence(Evidence(uid='42', date='2000-01-01', status=state), '42', DATE).status == 'unconfirmed'

@pytest.mark.parametrize('verifier', [HDSkyVerifier(), HaitangVerifier()])
@pytest.mark.parametrize('value,expected,uid', [
    (page(), 'login_ok', '42'), ('<html>reachable</html>', 'login_ok', None),
    (LoginPage('login', 'https://fixture.invalid/login.php'), 'auth_failed', None),
    (LoginPage('error', status_code=503), 'unconfirmed', None), ('', 'unconfirmed', None)])
def test_login_three_states(verifier, value, expected, uid):
    result = verify_login(lambda: value, verifier, '')
    assert result.status == expected
    if result.evidence:
        assert result.evidence.uid == uid

def test_login_exception_is_unconfirmed():
    def fail(): raise TimeoutError()
    assert verify_login(fail, HDSkyVerifier(), '').status == 'unconfirmed'

@pytest.mark.parametrize('first', [TimeoutError(), page()])
def test_login_always_rereads_and_records_action(first):
    values = iter([first, page()]); calls = []
    def fetch():
        calls.append(1); value = next(values)
        if isinstance(value, Exception): raise value
        return value
    store = HistoryStore()
    result = SignRunner(history=store.append).run_login('hdsky', resolve=lambda: CredentialResolution(Credential('managed_site','fixture'), 'valid'), fetch_page=fetch, verifier=HDSkyVerifier())
    assert len(calls) == 2 and result.status == 'login_ok'
    assert store.list()['items'][0]['action'] == 'login'
    assert result.account == '42' and 'business_date' not in result.metadata
    store.append(LoginResult(LoginStatus.AUTH_FAILED, site_id='hdsky', metadata={'action':'login'}))
    assert not any(store.today_counts().values())

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
    monkeypatch.setattr(module, 'PilotBridge', lambda *args: pytest.fail('native login must not construct legacy bridge'))
    monkeypatch.setattr(module, 'managed_site', lambda sid: {'cookie': 'fixture'})
    def fetch(self, url):
        calls.append('get')
        return LoginPage(page(), url)
    monkeypatch.setattr(NativeHttpClient, 'get', fetch)
    plugin = AutoPtCheckin()
    plugin.init_plugin({'enabled_sites':['hdsky'], 'login_sites':['hdsky']})
    result = plugin._execute_all()[0]
    assert result['status'] == 'login_ok' and calls == ['get','get']
    assert plugin._history.list()['items'][0]['action'] == 'login'
    assert asyncio.run(plugin.api_login_by_domain('hdsky'))['data']['status'] == 'login_ok'
    row = plugin._site_results()[0]
    assert row['login_selected'] and row['can_login'] and not row['sign_selected']
    # D4 后 /sites 最新记录含模拟登录：hdsky 仅登录时卡片状态同步为 login_ok
    assert row['status'] == 'login_ok' and row['action'] == 'login'
    assert next(r for r in plugin.get_api() if r['path'] == '/login_by_domain')['auth'] == 'bear'
    dispatched = []
    monkeypatch.setattr(plugin, '_execute_site', lambda sid, **kw: dispatched.append((sid,kw['action'])))
    plugin._config.update(enabled_sites=['hdsky','haitang','rousi'],sign_sites=['hdsky'],login_sites=['hdsky','haitang','rousi'])
    plugin._execute_all()
    assert dispatched == [('hdsky','sign'),('haitang','login'),('rousi','login')]


def test_login_uid_conflict_and_shared_lock():
    assert verify_login(lambda: page(), HDSkyVerifier(), '99').status == 'unconfirmed'
    runner = SignRunner()
    with runner.locks.acquire(('hdsky', '')):
        result = runner.run_login('hdsky', resolve=lambda: pytest.fail('busy'),
            fetch_page=lambda: pytest.fail('busy'), verifier=HDSkyVerifier())
    assert result.status == 'skipped' and result.metadata['action'] == 'login'


def test_login_nonpilot_never_reads_host(monkeypatch):
    import autoptcheckin as module
    monkeypatch.setattr(module, 'managed_site', lambda sid: pytest.fail('pilot gate'))
    plugin = AutoPtCheckin()
    plugin.init_plugin({'enabled_sites':['rousi'], 'login_sites':['rousi']})
    result = plugin._execute_all()[0]
    assert result['status'] == 'skipped'
    assert result['metadata']['reason'] == 'pilot_not_enabled'
    assert plugin._history.list()['items'][0]['action'] == 'login'


def test_login_parser_failure_does_not_veto_reachability():
    class BrokenVerifier:
        def parse_login(self, page): raise ValueError()
    assert verify_login(lambda: '<html>reachable</html>', BrokenVerifier(), '').status == 'login_ok'
