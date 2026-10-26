"""Custom consumer path using synthetic attendance pages, never live sites."""
import importlib
import json
from contextlib import contextmanager

import pytest

from test_custom_verify import probe
from test_cookiecloud_credentials import cloud
from autoptcheckin.core.models import LoginPage
from autoptcheckin.core.registry import get_registry

custom = importlib.import_module('autoptcheckin.core.custom')
URL = 'https://custom.invalid/attendance.php'
FORM = '<form method="post" action="attendance.php"><input name="csrf" value="fixture"><button>签到</button></form>'
SIGNED = '<h1>今天已经签到</h1>'


@pytest.fixture
def attendance(probe, monkeypatch):
    plugin, _, _ = probe
    calls, pages = [], [FORM, SIGNED]
    error = []

    class Http:
        def __init__(self, credential, info):
            assert credential.source == 'local_cookie'
            assert credential.value == 'synthetic-cookie'

        def get(self, url):
            calls.append(('GET', url))
            value = pages.pop(0)
            if isinstance(value, Exception):
                raise value
            return LoginPage(value, url) if value is not None else None

        def post(self, url, **kwargs):
            calls.append(('POST', url))
            assert kwargs['data'] == [('csrf', 'fixture')]
            if error:
                raise error[0]
            return LoginPage('<h1>签到成功</h1>', url)

    monkeypatch.setattr(custom, 'NativeHttpClient', Http)
    return plugin, calls, pages, error


@pytest.mark.parametrize('before,after,status,reason,methods', [
    (FORM, SIGNED, 'signed', None, ['GET', 'POST', 'GET']),
    (SIGNED, None, 'signed', 'already_signed', ['GET']),
    (FORM, '<main>unknown</main>', 'pending', 'result_unknown', ['GET', 'POST', 'GET']),
    (FORM, None, 'pending', 'result_unknown', ['GET', 'POST', 'GET']),
    ('<main>not Nexus</main>', None, 'pending', 'protocol_pending', ['GET']),
])
def test_custom_signin_three_states(attendance, before, after, status, reason, methods):
    plugin, calls, pages, _ = attendance
    pages[:] = [before, after]
    result = plugin._execute_site('custom-60005')
    assert result['status'] == status
    assert result.get('reason') == reason
    assert calls == [(method, URL) for method in methods]
    assert result['metadata']['action'] == 'sign'
    records = plugin._history.list(1, 10)['items']
    assert len(records) == 1 and records[0]['action'] == 'sign'


@pytest.mark.parametrize('after,status,reason', [(SIGNED, 'signed', None), (TimeoutError(), 'pending', 'result_unknown')])
def test_custom_submit_exception_always_reads_again(attendance, after, status, reason):
    plugin, calls, pages, error = attendance
    error.append(TimeoutError())
    pages[:] = [FORM, after]
    result = plugin._execute_site('custom-60005')
    assert result['status'] == status and result.get('reason') == reason
    assert calls == [('GET', URL), ('POST', URL), ('GET', URL)]


@pytest.mark.parametrize('selected', [False, True])
def test_custom_selection_gate(attendance, selected):
    plugin, calls, _, _ = attendance
    plugin._config['sign_sites'] = ['custom-60005'] if selected else []
    assert plugin._execute_site('custom-60005')['status'] == ('signed' if selected else 'skipped')
    assert bool(calls) == selected


@pytest.mark.parametrize('site_id', [60005, '60005', 'custom-60005'])
def test_custom_signin_id_types(attendance, site_id):
    plugin, _, _, _ = attendance
    plugin._config['custom_sites_data'][0]['id'] = site_id
    plugin._config['enabled_sites'] = [site_id]
    plugin._config['sign_sites'] = [site_id]
    assert plugin._execute_site(site_id)['status'] == 'signed'


@pytest.mark.parametrize('entry_emulate,override,expected', [
    (True, None, True), (False, None, False), (True, False, False), (False, True, True),
])
def test_custom_emulate_map_overrides_entry(attendance, monkeypatch, entry_emulate, override, expected):
    """custom 条目 emulate 填写值为无覆盖时的默认；site_emulate 覆盖表显式 bool 最高优先。"""
    plugin, calls, _, _ = attendance
    plugin._config['custom_sites_data'][0]['emulate'] = entry_emulate
    if override is not None:
        plugin._config['site_emulate'] = {'custom-60005': override}
    seen = {}

    @contextmanager
    def client(credential, info, config, proxy=None):
        seen['emulate'] = info['emulate']
        seen['proxy'] = proxy
        yield custom.NativeHttpClient(credential, info)

    monkeypatch.setattr(custom, 'custom_client', client)
    result = plugin._execute_site('custom-60005')
    assert seen['emulate'] is expected
    assert (result['metadata'].get('transport') == 'cloak') is expected
    # HTTP 轨照常走 Nexus 三段调用；仿真轨由 stub 承载。
    assert result['status'] == 'signed'
    row = next(row for row in get_registry(plugin._config['custom_sites_data'])['sites']
               if row['id'] == 'custom-60005')
    assert row['signin_applicable'] is True
    # 注册表声明不被有效值反写污染（响应副本才携带有效 emulate）。
    assert row['emulate'] is entry_emulate


def test_custom_emulate_hybrid_get_post_get(attendance, monkeypatch):
    plugin, calls, _, _ = attendance
    plugin._config['site_emulate'] = {'custom-60005': True}
    plugin._config['custom_sites_data'][0]['emulate'] = True
    events = []

    @contextmanager
    def client(credential, info, config, proxy=None):
        assert info['emulate'] and config['site_emulate'] == {'custom-60005': True}
        assert proxy is None  # 显式覆盖表只开仿真，未开代理：无 PROXY_HOST 兜底
        events.append('open')
        try:
            yield custom.NativeHttpClient(credential, info)
        finally:
            events.append('close')

    monkeypatch.setattr(custom, 'custom_client', client)
    result = plugin._execute_site('custom-60005')
    assert result['status'] == 'signed'
    assert result['metadata']['transport'] == 'cloak'
    assert calls == [('GET', URL), ('POST', URL), ('GET', URL)]
    assert events == ['open', 'close']


def test_cloak_custom_client_lifecycle(probe, monkeypatch):
    from types import SimpleNamespace
    from autoptcheckin.core import cloak
    from autoptcheckin.core.credentials import Credential
    events = []
    class Page:
        url = URL
        def goto(self, *args, **kwargs): events.append("goto"); return SimpleNamespace(status=200)
        def wait_for_timeout(self, _): pass
        def content(self): return SIGNED
    class Context:
        def new_page(self): return Page()
        def add_cookies(self, cookies): events.append("cookies")
        def cookies(self, url): return [{"name": "session", "value": "refreshed"}]
        def close(self): events.append("close")
    monkeypatch.setattr(cloak, "launch_context", lambda **kwargs: Context())
    class Http:
        cookies = {"sid": "x"}
        def __init__(self, credential, info): pass
        def get_bytes(self, url): return b""
        def retain_cookies(self, names): pass
        def post(self, url, **kwargs): return None
    monkeypatch.setattr(custom, "NativeHttpClient", Http)
    info = {"url": URL, "id": "custom-60005", "emulate": True}
    with custom.custom_client(Credential("local_cookie", "synthetic-cookie"), info,
                              {"site_emulate": {}}) as client:
        assert client.get(URL).text == SIGNED
    assert events == ["cookies", "goto", "close"]


@pytest.mark.parametrize('condition,status', [('disabled', 'skipped'), ('cookie', 'failed'),
                                             ('cancel', 'cancelled'), ('busy', 'skipped')])
def test_custom_sign_guards(attendance, condition, status):
    plugin, calls, _, _ = attendance
    if condition == 'disabled':
        plugin._config['enabled_sites'] = []
    elif condition == 'cookie':
        plugin._config['custom_sites_data'][0]['cookie'] = ''
    elif condition == 'cancel':
        plugin._runner.stop.set()
    if condition == 'busy':
        with plugin._runner.locks.acquire(('custom-60005', '')):
            result = plugin._execute_site('custom-60005')
    else:
        result = plugin._execute_site('custom-60005')
    assert result['status'] == status
    assert not calls


@pytest.mark.parametrize('site_id', ['custom-60005', '60005', 60005])
def test_custom_sign_api_without_global_unlock(attendance, site_id):
    import asyncio
    plugin, calls, _, _ = attendance
    plugin._config['custom_sites_data'][0]['id'] = site_id
    plugin._config['enabled_sites'] = [site_id]
    plugin._config['sign_sites'] = [site_id]
    result = asyncio.run(plugin.api_signin_by_domain(domain=str(site_id)))
    assert result['success'] and result['data']['status'] == 'signed'
    assert calls == [('GET', URL), ('POST', URL), ('GET', URL)]


def test_custom_entry_matching_adapter_domain_dedupes():
    """与适配器同域的自定义条目只作为 Cookie 来源，不再单列为自定义站点。"""
    carrier = {'id': 'custom-hdwing', 'name': 'HDWing', 'url': 'https://hdwing.org/', 'cookie': 'fixture'}
    sites = get_registry([carrier])['sites']
    assert not any(row['id'] == 'custom-hdwing' for row in sites)
    assert any(row['id'] == 'hdwing' and row['source'] == '插件适配' for row in sites)
    independent = get_registry([{'id': 'custom-x', 'name': 'X', 'url': 'https://unregistered.invalid/'}])['sites']
    assert any(row['id'] == 'custom-x' for row in independent)


def test_custom_empty_cookie_falls_back_to_cookiecloud_and_persists(probe, cloud, monkeypatch):
    """条目 Cookie 为空：候选链落到 CookieCloud，成功后回写统一 Cookie 表。"""
    plugin, _, _ = probe
    plugin._config['custom_sites_data'][0]['cookie'] = ''
    store = {}
    plugin.get_data = store.get
    plugin.save_data = lambda key, value: store.update({key: value})
    cloud.decrypt.return_value = json.dumps({'cookie_data': {'group': [
        {'domain': '.custom.invalid', 'name': 'session', 'value': 'synthetic-cloud'}]}}).encode()

    class Http:
        def __init__(self, credential, info):
            assert credential.source == 'cookiecloud'
            assert 'session=synthetic-cloud' in credential.value
            self.cookies = {}
            self.pages = [FORM, '<h1>今天已经签到</h1>']

        def get(self, url):
            text = self.pages.pop(0) if self.pages else '<h1>今天已经签到</h1>'
            return LoginPage(text, url)

        def post(self, url, **kwargs):
            self.cookies['session'] = 'synthetic-cloud'
            return LoginPage('<h1>签到成功</h1>', url)

    monkeypatch.setattr(custom, 'NativeHttpClient', Http)
    result = plugin._execute_site('custom-60005')
    assert result['status'] == 'signed'
    entry = store['cookies.table']['custom-60005']
    assert entry['source'] == 'cookiecloud'
    assert 'session=synthetic-cloud' in entry['cookie']
