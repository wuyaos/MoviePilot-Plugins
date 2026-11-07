"""Cookie candidate execution boundaries, synthetic IO only."""
from types import SimpleNamespace

import pytest

from test_custom_verify import probe
from autoptcheckin.core import native
from autoptcheckin.core.models import LoginPage
import importlib

custom = importlib.import_module('autoptcheckin.core.custom')
SID = 'custom-60005'


@pytest.mark.parametrize('terminal', ['valid', 'network', 'challenge', 'unknown', 'post-auth'])
def test_custom_rotates_only_pre_submit_auth_and_persists(probe, monkeypatch, terminal):
    plugin, _, _ = probe
    plugin._config['custom_sites_data'][0]['cookie'] = 'session=local'
    store = {'cookies.table': {SID: {'cookie': 'session=stored', 'source': 'fixture'}}}
    plugin.get_data = store.get
    plugin.save_data = lambda k, v: store.update({k: v})
    events = []
    cloud_calls = []

    def cloud(url):
        cloud_calls.append(url)
        return SimpleNamespace(credential=native.Credential('cookiecloud', 'session=cloud'))

    monkeypatch.setattr(native, 'cookiecloud_candidate', cloud)

    class Http:
        def __init__(self, credential, info):
            self.source = credential.source
            self.cookies = {'session': credential.value.split('=')[1]}
            self.posted = False
            events.append(('open', self.source))

        def get(self, url):
            if self.source == 'stored_cookie' and self.cookies['session'] == 'stored':
                return LoginPage('<form><input type="password"></form>', 'https://custom.invalid/login.php')
            if self.source == 'local_cookie' and terminal == 'valid':
                return LoginPage('<input type="password">', 'https://custom.invalid/login.php')
            if terminal == 'network':
                raise TimeoutError()
            if terminal == 'challenge':
                return LoginPage('challenge', url, 403)
            if terminal == 'unknown':
                return LoginPage('<main>unknown</main>', url)
            if terminal == 'post-auth':
                return LoginPage('<input type="password">' if self.posted else
                                 '<form method="post" action="attendance.php"><button>签到</button></form>',
                                 'https://custom.invalid/login.php' if self.posted else url)
            self.cookies['session'] = 'refreshed'
            return LoginPage('<h1>今天已经签到</h1>', url)

        def post(self, url, **kwargs):
            self.posted = True
            events.append(('POST', self.source))
            return LoginPage('unknown', url)

        def close(self):
            events.append(('close', self.source))

    monkeypatch.setattr(custom, 'NativeHttpClient', Http)
    result = plugin._execute_site(SID)
    sources = result['metadata']['cookie_sources']
    assert sources == ['stored_cookie', 'local_cookie'] + (['cookiecloud'] if terminal == 'valid' else [])
    assert len(cloud_calls) == (1 if terminal == 'valid' else 0)
    assert sum(e[0] == 'open' for e in events) == sum(e[0] == 'close' for e in events)
    assert len(plugin._history.list(1, 100)['items']) == 1
    if terminal == 'valid':
        assert result['status'] == 'signed'
        assert store['cookies.table'][SID]['cookie'] == 'session=refreshed'
        # 次轮消费已验证的表项，不再查询 CookieCloud。
        events.clear()
        plugin._execute_site(SID)
        assert events[0] == ('open', 'stored_cookie')
    else:
        assert result['status'] in ('failed', 'pending')
        assert store['cookies.table'][SID]['cookie'] == 'session=stored'
    if terminal == 'post-auth':
        assert [e for e in events if e[0] == 'POST'] == [('POST', 'local_cookie')]


@pytest.mark.parametrize('reasons,expected', [(['auth_failed'], 1), ([None, 'auth_failed'], 2), ([None] * 4, 4)])
def test_outer_retry_stops_on_auth_but_preserves_normal_failure(probe, monkeypatch, reasons, expected):
    plugin, _, _ = probe
    plugin._config['retry_count'] = 3
    calls = []
    def execute(*args, **kwargs):
        reason = reasons[min(len(calls), len(reasons) - 1)]
        calls.append(reason)
        return {'status': 'failed', 'reason': reason}
    monkeypatch.setattr(plugin, '_execute_site', execute)
    monkeypatch.setattr(plugin, '_track_store', lambda: SimpleNamespace(state_of=lambda *a: 'failed'))
    plugin._run_with_retry(SID, 'sign', 'manual')
    assert len(calls) == expected


@pytest.mark.parametrize('page,expected', [
    ('<form action="takelogin.php"><input name="username"><input type="password"></form>', 'auth_failed'),
    ('<form action="login.php"><input name="email"><input type="password"></form>', 'auth_failed'),
    ('<a href="login.php">登录</a><main>unknown</main>', 'protocol_pending'),
    ('<form action="login.php"><input name="username"><input name="challenge"></form>', 'protocol_pending'),
    ('<div hidden><form action="login.php"><input name="username"><input type="password"></form></div>', 'protocol_pending'),
])
def test_cloud_pre_submit_auth_evidence_only(monkeypatch, page, expected):
    from autoptcheckin.core import cloudsign
    calls = []
    def request(*args, **kwargs):
        calls.append(1)
        return {'after': {'html': page}}
    monkeypatch.setattr(cloudsign, '_bql_request', request)
    result = cloudsign.sign('mua_xloli', 'https://cloud.invalid', 'session=fixture', {'browserless_token': 'fixture'})
    assert result.status == expected
    assert len(calls) == 1


@pytest.mark.parametrize('status', ['success', 'already', 'protocol_pending', 'network_error'])
def test_cloud_candidate_is_persisted_only_if_proven(monkeypatch, status):
    from test_cloudsign_c18 import cloud_site
    from autoptcheckin.core.runner import SignRunner
    from autoptcheckin.core import cloudsign
    store = {'cookies.table': {'mua_xloli': {'cookie': 'session=old', 'source': 'fixture'}}}
    runner = SignRunner()
    runner.get_data, runner.save_data = store.get, store.__setitem__
    monkeypatch.setattr(native, 'cookiecloud_candidate', lambda url: SimpleNamespace(
        credential=native.Credential('cookiecloud', 'session=new')))
    calls = []
    def sign(site_id, url, cookie, config):
        calls.append(cookie)
        if cookie == 'session=old':
            return cloudsign.CloudResult('auth_failed', 'pre-submit only')
        return cloudsign.CloudResult(status, 'fixture')
    monkeypatch.setattr(cloudsign, 'sign', sign)
    native.run_native(runner, cloud_site(), {}, config={'site_cloudsign': ['mua_xloli'], 'browserless_token': 'fixture'})
    assert calls == ['session=old', 'session=new']
    entry = store['cookies.table']['mua_xloli']
    assert entry['cookie'] == ('session=new' if status in ('success', 'already') else 'session=old')
    if status in ('success', 'already'):
        assert entry['source'] == 'cookiecloud'


def test_cloud_post_submit_login_page_never_rotates_or_reposts(monkeypatch):
    from autoptcheckin.core import cloudsign
    calls = []
    def request(*args, **kwargs):
        calls.append(1)
        return ({'after': {'html': '未签到'}, 'solve': {'token': 'fixture'}} if len(calls) == 1 else
                {'after': {'html': '<form action="login.php"><input name="username"><input type="password"></form>'}})
    monkeypatch.setattr(cloudsign, '_bql_request', request)
    result = cloudsign.sign('mua_xloli', 'https://cloud.invalid', 'session=fixture', {'browserless_token': 'fixture'})
    assert result.status == 'protocol_pending'
    assert len(calls) == 2
