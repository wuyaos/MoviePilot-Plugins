"""Unified Cookie persistence and fallback, using synthetic sessions only."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / 'plugins.v3'))
from autoptcheckin.core import native
from autoptcheckin.core.credentials import Credential, CredentialResolution, CredentialSpec
from autoptcheckin.core.models import LoginPage, LoginResult, SignResult
from autoptcheckin.core.runner import SignRunner
from autoptcheckin.integrations import rousi, sunnypt, yzyy


@pytest.fixture
def storage(monkeypatch):
    data = {'cookies.table': {'fixture': {'cookie': 'session=stored', 'source': 'refreshed', 'updated': 'old'}}}
    runner = SignRunner()
    runner.get_data = data.get
    runner.save_data = data.__setitem__
    runner.del_data = lambda key: data.pop(key, None)
    monkeypatch.setattr(native, 'cookiecloud_candidate', lambda url: CredentialResolution(Credential('cookiecloud', 'session=cloud'), 'valid'))
    return runner, data


def login_site(site_id='fixture'):
    return SimpleNamespace(id=site_id, url='https://fixture.invalid/', credential=CredentialSpec(),
                           parse_login=lambda page, credential: LoginResult(page.text))


@pytest.mark.parametrize('action', ['sign', 'login'])
@pytest.mark.parametrize('stored_status,expected_source', [('success', 'stored_cookie'), ('auth_failed', 'managed_site')])
def test_stored_priority_fallback_and_rotated_cookie_write(storage, monkeypatch, action, stored_status, expected_source):
    runner, data = storage
    calls = []
    site = login_site()
    def outcome(credential, http):
        calls.append(credential.source)
        status = stored_status if credential.source == 'stored_cookie' else 'success'
        if status == 'success':
            http.cookies = {'session': 'rotated'}
        return status
    if action == 'sign':
        site.signin = lambda ctx: SignResult(outcome(ctx.credential, ctx.http))
        def context(site, credential, info, lock, cancel):
            return SimpleNamespace(credential=credential, http=native.NativeHttpClient(credential, info))
        result = native.run_native(runner, site, {'cookie': 'session=managed'}, context_factory=context)
    else:
        def get(http, url):
            status = outcome(http.credential, http)
            return LoginPage('login_ok' if status == 'success' else status, url)
        monkeypatch.setattr(native.NativeHttpClient, 'get', get)
        result = native.run_native_login(runner, site, {'cookie': 'session=managed'})
    expected = ['stored_cookie'] + (['managed_site'] if expected_source == 'managed_site' else [])
    assert result.metadata['cookie_sources'] == expected
    assert calls == [source for source in expected for _ in range(2 if action == 'login' else 1)]
    stored_cookie_entry = data['cookies.table']['fixture']
    assert stored_cookie_entry['cookie'] == 'session=rotated'
    assert stored_cookie_entry['source'] == expected_source
    assert stored_cookie_entry['updated'] != 'old'


@pytest.mark.parametrize('status', ['unconfirmed', 'network_error', 'maintenance', 'failed'])
def test_uncertain_or_non_auth_failure_never_switches_or_overwrites(storage, status):
    runner, data = storage
    site = login_site()
    site.signin = lambda ctx: SignResult(status)
    result = native.run_native(runner, site, {'cookie': 'session=managed'}, context_factory=lambda *args: SimpleNamespace(http=SimpleNamespace(cookies={'session': 'not-proven'})))
    assert result.metadata['cookie_sources'] == ['stored_cookie']
    assert data['cookies.table']['fixture']['updated'] == 'old'


def test_all_sources_exhausted_in_order(storage, monkeypatch):
    runner, data = storage
    monkeypatch.setattr(native.NativeHttpClient, 'get', lambda self, url: LoginPage('auth_failed', url))
    result = native.run_native_login(runner, login_site(), {'cookie': 'session=managed'}, custom_cookie='session=local')
    assert result.status == 'auth_failed'
    assert result.metadata['cookie_sources'] == ['stored_cookie', 'managed_site', 'local_cookie', 'cookiecloud']
    assert data['cookies.table']['fixture']['updated'] == 'old'


@pytest.mark.parametrize('site_id', ['rousi', 'sunnypt'])
@pytest.mark.parametrize('delete_available', [True, False])
def test_legacy_migration_preserves_new_table_and_removes_or_marks_old_key(storage, monkeypatch, site_id, delete_available):
    runner, data = storage
    data['cookies.refreshed'] = {site_id: 'session=legacy', 'fixture': 'session=obsolete'}
    if not delete_available:
        runner.del_data = None
    integration = rousi if site_id == 'rousi' else sunnypt
    monkeypatch.setattr(integration, 'login', lambda *args: LoginResult('unconfirmed'))
    native.run_integration(runner, site_id, site_id, {}, {}, action='login')
    assert data['cookies.table'][site_id]['source'] == 'refreshed'
    assert data['cookies.table'][site_id]['cookie'] == 'session=legacy'
    assert data['cookies.table']['fixture']['cookie'] == 'session=stored'
    if delete_available:
        assert 'cookies.refreshed' not in data
    else:
        assert data['cookies.refreshed.migrated'] is True


@pytest.mark.parametrize('site_id', ['rousi', 'yzyy'])
def test_password_is_last_resort_and_persists_even_if_sign_is_unconfirmed(storage, monkeypatch, site_id):
    runner, data = storage
    data['cookies.table'][site_id] = {'cookie': 'session=expired'}
    integration = rousi if site_id == 'rousi' else yzyy
    calls = []
    def login(http, info):
        calls.append(http.credential.source)
        if http.credential.source != 'password_login':
            assert not info
            return LoginResult('auth_failed')
        http.cookies = {'session': 'password-refreshed'}
        return LoginResult('login_ok')
    monkeypatch.setattr(integration, 'login', login)
    if site_id == 'rousi':
        def signin(http, info):
            if http.credential.source == 'password_login':
                return SignResult('unconfirmed')
            return SignResult(login(http, info).status)
        monkeypatch.setattr(rousi, 'signin', signin)
        result = native.run_integration(runner, site_id, site_id, {'cookie': 'session=managed'}, {}, action='sign')
    else:
        site = login_site(site_id)
        site.signin = lambda ctx: SignResult('unconfirmed' if ctx.credential.source == 'password_login' else 'auth_failed')
        result = native.run_native(runner, site, {'cookie': 'session=managed'})
    assert result.status == 'unconfirmed'
    assert result.metadata['cookie_sources'] == ['stored_cookie', 'managed_site', 'cookiecloud', 'password_login']
    assert data['cookies.table'][site_id]['source'] == 'password_login'
    assert data['cookies.table'][site_id]['cookie'] == 'session=password-refreshed'


@pytest.mark.parametrize('status', ['success', 'signed', 'already'])
def test_success_family_cookie_persistence(storage, status):
    runner, data = storage
    native.persist_cookie_result(SignResult(status), SimpleNamespace(cookies={'session': 'fresh'}), 'fixture', 'local_cookie', runner.get_data, runner.save_data)
    assert data['cookies.table']['fixture']['source'] == 'local_cookie'


def test_mteam_storage_state_does_not_touch_cookie_table(storage):
    runner, data = storage
    runner.get_data = lambda key: pytest.fail('M-Team accessed Cookie table')
    runner.save_data = lambda *args: pytest.fail('M-Team wrote Cookie table')
    site = login_site('mteam')
    site.keepalive_login = lambda info: LoginResult('login_ok')
    assert native.run_native_login(runner, site, {}).status == 'login_ok'


def test_sunnypt_without_cookie_does_not_create_cookie_entry(storage, monkeypatch):
    runner, data = storage
    monkeypatch.setattr(native, 'cookiecloud_candidate', lambda url: CredentialResolution(None, 'unavailable'))
    monkeypatch.setattr(sunnypt, 'login', lambda http, info: LoginResult('login_ok'))
    assert native.run_integration(runner, 'sunnypt', 'sunnypt', {}, {}, action='login').status == 'login_ok'
    assert 'sunnypt' not in data['cookies.table']


def test_plugin_login_connects_storage_callbacks(storage, monkeypatch):
    import autoptcheckin as entry
    runner, data = storage
    plugin = entry.AutoPtCheckin()
    plugin.get_data, plugin.save_data, plugin.del_data = runner.get_data, runner.save_data, runner.del_data
    plugin.init_plugin({'enabled_sites': ['darkland'], 'login_sites': ['darkland']})
    monkeypatch.setattr(entry, 'managed_site', lambda site_id: {'cookie': 'session=managed'})
    monkeypatch.setattr(native.NativeHttpClient, 'get', lambda self, url: LoginPage('<p>reachable</p>', url))
    assert plugin._execute_site('darkland', action='login')['status'] == 'login_ok'
    assert data['cookies.table']['darkland']['source'] == 'managed_site'


@pytest.mark.parametrize('action', ['login', 'sign'])
def test_sunnypt_actual_cookie_records_password_source(storage, monkeypatch, action):
    runner, data = storage
    def operation(http, info):
        http.cookies = {'session': 'new-cookie'}
        http.cookie_source = 'password_login'
        return LoginResult('login_ok') if action == 'login' else SignResult('success')
    monkeypatch.setattr(sunnypt, 'login' if action == 'login' else 'signin', operation)
    result = native.run_integration(runner, 'sunnypt', 'sunnypt', {'cookie': 'session=managed'}, {}, action=action)
    assert result.metadata['cookie_sources'] == ['password_login']
    assert data['cookies.table']['sunnypt']['source'] == 'password_login'
    assert data['cookies.table']['sunnypt']['cookie'] == 'session=new-cookie'


def test_yzyy_login_uses_stored_then_managed_without_password(storage, monkeypatch):
    runner, data = storage
    data['cookies.table']['yzyy'] = {'cookie': 'session=expired'}
    def login(http, info):
        assert not info
        if http.credential.source == 'stored_cookie':
            return LoginResult('auth_failed')
        http.cookies = {'session': 'renewed'}
        return LoginResult('login_ok')
    monkeypatch.setattr(yzyy, 'login', login)
    result = native.run_native_login(runner, login_site('yzyy'), {'cookie': 'session=managed'})
    assert result.metadata['cookie_sources'] == ['stored_cookie', 'managed_site']
    assert data['cookies.table']['yzyy']['source'] == 'managed_site'


def test_record_cookie_identical_session_preserves_updated():
    row = {'cookie': 'session=synthetic', 'source': 'managed_site', 'updated': 'original'}
    table = {'fixture': row}
    assert native.record_cookie(table, 'fixture', 'session=synthetic', 'managed_site') is table
    assert table['fixture'] is row
    assert row['updated'] == 'original'
    native.record_cookie(table, 'fixture', 'session=synthetic', 'local_cookie')
    assert table['fixture']['updated'] != 'original'


@pytest.mark.parametrize('table', ['broken', [], {'fixture': 'broken'}, {'fixture': ['broken']}])
def test_corrupt_cookie_table_falls_back_to_managed(storage, monkeypatch, table):
    runner, data = storage
    data['cookies.table'] = table
    monkeypatch.setattr(native.NativeHttpClient, 'get', lambda self, url: LoginPage('login_ok', url))
    result = native.run_native_login(runner, login_site(), {'cookie': 'session=managed'})
    assert result.status == 'login_ok'
    assert result.metadata['cookie_sources'] == ['managed_site']
    assert data['cookies.table']['fixture']['source'] == 'managed_site'


@pytest.mark.parametrize('legacy', [{}, 'broken', ['broken'], {'rousi': ['broken']}])
@pytest.mark.parametrize('delete_available', [True, False])
def test_empty_or_corrupt_legacy_is_migrated_once(storage, monkeypatch, legacy, delete_available):
    runner, data = storage
    data['cookies.refreshed'] = legacy
    if not delete_available:
        runner.del_data = None
    monkeypatch.setattr(rousi, 'login', lambda *args: LoginResult('unconfirmed'))
    assert native.run_integration(runner, 'rousi', 'rousi', {}, {}, action='login').status == 'unconfirmed'
    assert data['cookies.refreshed.migrated'] is True
    if delete_available:
        assert 'cookies.refreshed' not in data
    original_get = runner.get_data
    def get(key):
        assert key != 'cookies.refreshed'
        return original_get(key)
    runner.get_data = get
    assert native.run_integration(runner, 'rousi', 'rousi', {}, {}, action='login').status == 'unconfirmed'


@pytest.mark.parametrize('action', ['login', 'sign'])
def test_sunnypt_jwt_does_not_consume_or_persist_input_cookie(storage, monkeypatch, action):
    runner, data = storage
    monkeypatch.setattr(native, 'cookie_candidates', lambda *args: pytest.fail('JWT consumed Cookie candidates'))
    def operation(http, info):
        assert http.cookies == {}
        return LoginResult('login_ok') if action == 'login' else SignResult('success')
    monkeypatch.setattr(sunnypt, 'login' if action == 'login' else 'signin', operation)
    result = native.run_integration(runner, 'sunnypt', 'sunnypt', {'cookie': 'session=unproven'}, {}, action=action)
    assert result.status in ('login_ok', 'success')
    assert result.metadata['cookie_sources'] == []
    assert 'sunnypt' not in data['cookies.table']


@pytest.mark.parametrize('body,expected', [('Log out', 'login_ok'), ('Please login', 'auth_failed')])
def test_browser_login_uses_real_session_signature(storage, monkeypatch, body, expected):
    from autoptcheckin.core import cloak
    runner, data = storage
    calls = []
    class Context:
        def new_page(self):
            return SimpleNamespace(goto=lambda *a, **k: None,
                                   locator=lambda selector: SimpleNamespace(inner_text=lambda: body))
        def add_cookies(self, cookies): calls.extend(cookies)
        def close(self): calls.append('closed')
    monkeypatch.setattr(cloak, 'launch_context', lambda **kwargs: Context())
    site = login_site()
    site.browser_login = True
    runner.get_data = lambda key: pytest.fail('browser login read Cookie table')
    assert native.run_native_login(runner, site, {'cookie': 'session=synthetic'}).status == expected
    assert calls[0]['name'] == 'session'
    assert calls[-1] == 'closed'


def test_cloak_cleanup_error_preserves_sign_result_and_history(storage, monkeypatch):
    runner, data = storage
    results = []
    runner.history = results.append
    class BrokenClose(native.CloakHttpClient):
        def __init__(self, http): self.http = http
        def close(self): raise RuntimeError('synthetic close failure')
    monkeypatch.setattr(native, 'native_cloak_client', lambda site, http, *args, **kwargs: BrokenClose(http))
    site = login_site()
    site.signin = lambda ctx: SignResult('success')
    result = native.run_native(runner, site, {})
    assert result.status == 'success'
    assert results == [result]
    assert data['cookies.table']['fixture']['source'] == 'stored_cookie'
    with runner.locks.acquire(('fixture', '')) as acquired:
        assert acquired


def test_login_unexpected_error_carries_exception_detail(storage, monkeypatch):
    # 登录路径异常透传（与签到路径同格式），不再是无详情固定文案。
    runner, data = storage

    def boom(_fn, _site, _uid, _credential):
        raise ConnectionError('mock network down')

    monkeypatch.setattr(native, 'read_login_twice', boom)
    result = native.run_native_login(runner, login_site(), {'cookie': 'session=managed'})
    assert result.status == 'unconfirmed'
    assert 'ConnectionError' in result.message and 'mock network down' in result.message
    assert len(result.message) <= 100
    assert result.metadata['cookie_sources'] == ['stored_cookie']
    assert data['cookies.table']['fixture']['updated'] == 'old'


def test_login_cloak_client_closed_even_on_close_error(storage, monkeypatch):
    # 登录路径 finally 资源回收：非共享 CloakHttpClient 必须被关闭，close 抛错不影响结果。
    runner, data = storage
    closed = []

    class BrokenClose(native.CloakHttpClient):
        def __init__(self, http):
            self.http = http
            self.shared = False

        def get(self, url, **kwargs):
            return LoginPage('login_ok', url)

        def close(self):
            closed.append('attempted')
            raise RuntimeError('synthetic close failure')

    monkeypatch.setattr(native, 'native_cloak_client', lambda site, http, *args, **kwargs: BrokenClose(http))
    result = native.run_native_login(runner, login_site(), {'cookie': 'session=managed'})
    assert result.status == 'login_ok'
    assert closed == ['attempted']


def test_login_shared_cloak_client_not_closed(storage, monkeypatch):
    # 共享轮次会话（shared=True）归轮次生命周期所有，登录轨不得关闭。
    runner, data = storage
    closed = []

    class SharedClient(native.CloakHttpClient):
        # 不覆盖 close：走真实 close 的 shared 自保分支（shared=True 直接 return）。
        def __init__(self, http):
            self.http = http
            self.shared = True
            self.session = SimpleNamespace(close=lambda: closed.append('browser-closed'))

        def get(self, url, **kwargs):
            return LoginPage('login_ok', url)

    monkeypatch.setattr(native, 'native_cloak_client', lambda site, http, *args, **kwargs: SharedClient(http))
    result = native.run_native_login(runner, login_site(), {'cookie': 'session=managed'})
    assert result.status == 'login_ok'
    assert closed == []
