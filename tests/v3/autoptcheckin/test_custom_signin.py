"""Custom consumer path using synthetic attendance pages, never live sites."""
import importlib
from contextlib import contextmanager

import pytest

from test_custom_verify import probe
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


@pytest.mark.parametrize('before,after,status,methods', [
    (FORM, SIGNED, 'success', ['GET', 'POST', 'GET']),
    (SIGNED, None, 'already', ['GET']),
    (FORM, '<main>unknown</main>', 'unconfirmed', ['GET', 'POST', 'GET']),
    (FORM, None, 'unconfirmed', ['GET', 'POST', 'GET']),
    ('<main>not Nexus</main>', None, 'skipped', ['GET']),
])
def test_custom_signin_three_states(attendance, before, after, status, methods):
    plugin, calls, pages, _ = attendance
    pages[:] = [before, after]
    result = plugin._execute_site('custom-60005')
    assert result['status'] == status
    assert calls == [(method, URL) for method in methods]
    assert result['metadata']['action'] == 'sign'
    records = plugin._history.list(1, 10)['items']
    assert len(records) == 1 and records[0]['action'] == 'sign'


@pytest.mark.parametrize('after,status', [(SIGNED, 'success'), (TimeoutError(), 'unconfirmed')])
def test_custom_submit_exception_always_reads_again(attendance, after, status):
    plugin, calls, pages, error = attendance
    error.append(TimeoutError())
    pages[:] = [FORM, after]
    assert plugin._execute_site('custom-60005')['status'] == status
    assert calls == [('GET', URL), ('POST', URL), ('GET', URL)]


@pytest.mark.parametrize('unlock', [False, True])
@pytest.mark.parametrize('selected', [False, True])
def test_custom_selection_gate_even_with_unlock(attendance, unlock, selected):
    plugin, calls, _, _ = attendance
    plugin._config['unlock_all_sites'] = unlock
    plugin._config['sign_sites'] = ['custom-60005'] if selected else []
    assert plugin._execute_site('custom-60005')['status'] == ('success' if selected else 'skipped')
    assert bool(calls) == selected


@pytest.mark.parametrize('site_id', [60005, '60005', 'custom-60005'])
def test_custom_signin_id_types(attendance, site_id):
    plugin, _, _, _ = attendance
    plugin._config['custom_sites_data'][0]['id'] = site_id
    plugin._config['enabled_sites'] = [site_id]
    plugin._config['sign_sites'] = [site_id]
    assert plugin._execute_site(site_id)['status'] == 'success'


@pytest.mark.parametrize('enabled', [False, True])
def test_custom_emulate_gate_and_registry(attendance, enabled):
    plugin, calls, _, _ = attendance
    plugin._config['custom_sites_data'][0]['emulate'] = True
    plugin._config['browserless_enabled'] = enabled
    result = plugin._execute_site('custom-60005')
    assert result['metadata']['reason'] == ('browserless_not_configured' if enabled else 'browserless_disabled')
    assert not calls
    row = next(row for row in get_registry(plugin._config['custom_sites_data'], browserless_enabled=enabled)['sites']
               if row['id'] == 'custom-60005')
    assert row['signin_applicable'] is enabled
    assert row['pilot_enabled'] is True


def test_custom_emulate_hybrid_get_post_get(attendance, monkeypatch):
    plugin, calls, _, _ = attendance
    plugin._config.update(browserless_enabled=True, browserless_url='ws://browser.invalid/')
    plugin._config['custom_sites_data'][0]['emulate'] = True
    events = []

    @contextmanager
    def client(credential, info, config):
        assert info['emulate'] and config['browserless_enabled']
        events.append('open')
        try:
            yield custom.NativeHttpClient(credential, info)
        finally:
            events.append('close')

    monkeypatch.setattr(custom, 'custom_client', client)
    result = plugin._execute_site('custom-60005')
    assert result['status'] == 'success'
    assert result['metadata']['transport'] == 'browserless_read_http_submit'
    assert calls == [('GET', URL), ('POST', URL), ('GET', URL)]
    assert events == ['open', 'close']


def test_hybrid_cookie_sync_and_fresh_page_reads():
    from types import SimpleNamespace
    events = []
    http = SimpleNamespace(cookies={'session': 'fixture'}, post=lambda url, **kw: events.append('post'))
    context = SimpleNamespace(add_cookies=lambda cookies: events.append('cookies'),
                              cookies=lambda url: [{'name': 'session', 'value': 'refreshed'}])
    page = SimpleNamespace(goto=lambda *args, **kw: events.append('goto') or SimpleNamespace(status=200),
                           content=lambda: SIGNED, url=URL)
    client = custom.BrowserlessReadHttpSubmit(http, context, page, URL)
    client.get(URL)
    assert http.cookies['session'] == 'refreshed'
    client.post(URL, data=[])
    assert client.get(URL).text == SIGNED
    assert events == ['cookies', 'goto', 'post', 'cookies', 'goto']


@pytest.mark.parametrize('fail', [False, True])
def test_browserless_context_lifecycle_and_token(probe, monkeypatch, fail):
    import sys
    from types import ModuleType, SimpleNamespace
    from autoptcheckin.core.credentials import Credential
    events = []
    context = SimpleNamespace(new_page=lambda: object(), close=lambda: events.append('context-close'))
    browser = SimpleNamespace(new_context=lambda **kw: context, close=lambda: events.append('browser-close'))

    def connect(endpoint, **kwargs):
        assert endpoint == 'ws://browser.invalid/?token=fixture'
        assert kwargs['timeout'] == 20000
        events.append('connect')
        return browser

    @contextmanager
    def playwright():
        yield SimpleNamespace(chromium=SimpleNamespace(connect_over_cdp=connect))
        events.append('playwright-close')

    module = ModuleType('playwright.sync_api')
    module.sync_playwright = playwright
    monkeypatch.setitem(sys.modules, 'playwright.sync_api', module)
    info = {'url': URL, 'emulate': True}
    try:
        with custom.custom_client(Credential('local_cookie', 'synthetic-cookie'), info,
                                  {'browserless_url': 'ws://browser.invalid/', 'browserless_token': 'fixture'}) as client:
            assert isinstance(client, custom.BrowserlessReadHttpSubmit)
            if fail:
                raise RuntimeError('synthetic')
    except RuntimeError:
        assert fail
    assert events[:3] == ['connect', 'context-close', 'browser-close']


@pytest.mark.parametrize('condition,status', [('disabled', 'skipped'), ('cookie', 'auth_failed'),
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
    assert result['success'] and result['data']['status'] == 'success'
    assert calls == [('GET', URL), ('POST', URL), ('GET', URL)]
