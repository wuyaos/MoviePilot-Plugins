"""Offline custom-site consumer regressions; no attendance requests."""
import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / 'plugins.v3'))
from autoptcheckin import AutoPtCheckin
from autoptcheckin.core.models import LoginPage

custom_module = importlib.import_module('autoptcheckin.core.custom')


@pytest.fixture
def probe(monkeypatch):
    calls = []
    page = [LoginPage('<main>account home</main>', 'https://custom.invalid/')]

    class Http:
        def __init__(self, credential, info):
            assert credential.value == 'synthetic-cookie'

        def get(self, url):
            calls.append(url)
            if isinstance(page[0], Exception):
                raise page[0]
            return page[0]

    monkeypatch.setattr(custom_module, 'NativeHttpClient', Http)
    plugin = AutoPtCheckin()
    plugin.init_plugin({'custom_sites_data': [{'id': 'custom-60005', 'name': 'Fixture',
                        'url': 'https://custom.invalid/', 'cookie': 'synthetic-cookie'}],
                        'enabled_sites': ['custom-60005'], 'sign_sites': ['custom-60005']})
    return plugin, calls, page


def test_custom_verify_bypasses_native_gate_without_claiming_attendance(probe):
    plugin, calls, _ = probe
    result = plugin._execute_site('custom-60005', read_only=True)
    assert result['status'] == 'login_ok'
    assert result['metadata']['action'] == 'login'
    assert calls == ['https://custom.invalid/']
    assert plugin._history.list(1, 10)['items'][0]['action'] == 'login'


@pytest.mark.parametrize('page,status', [
    (LoginPage('<form>Login</form>', 'https://custom.invalid/login.php'), 'auth_failed'),
    (LoginPage('<input type="password">', 'https://custom.invalid/'), 'auth_failed'),
    (LoginPage('denied', 'https://custom.invalid/', 403), 'auth_failed'),
    (LoginPage('error', 'https://custom.invalid/', 500), 'unconfirmed'),
    (None, 'unconfirmed'), (TimeoutError(), 'unconfirmed'),
])
def test_custom_verify_unreachable_and_login_pages(probe, page, status):
    plugin, calls, pages = probe
    pages[0] = page
    assert plugin._execute_site('custom-60005', read_only=True)['status'] == status
    assert len(calls) == 1


@pytest.mark.parametrize('site_id', ['60005', 60005, 'fixture-key'])
def test_custom_configured_ids(probe, site_id):
    plugin, calls, _ = probe
    plugin._config['custom_sites_data'][0]['id'] = site_id
    plugin._config['enabled_sites'] = [site_id]
    assert plugin._execute_site(site_id, read_only=True)['status'] == 'login_ok'
    assert len(calls) == 1


def test_custom_without_attendance_does_not_submit(probe):
    plugin, calls, _ = probe
    result = plugin._execute_site('custom-60005')
    assert result['status'] == 'protocol_pending'
    assert result['message'] == '未发现唯一签到表单'
    assert calls == ['https://custom.invalid/attendance.php']


@pytest.mark.parametrize('condition,status', [('disabled', 'skipped'), ('cookie', 'auth_failed'), ('cancel', 'cancelled'), ('busy', 'skipped')])
def test_custom_guards_do_not_request(probe, condition, status):
    plugin, calls, _ = probe
    if condition == 'disabled':
        plugin._config['enabled_sites'] = []
    elif condition == 'cookie':
        plugin._config['custom_sites_data'][0]['cookie'] = ''
    elif condition == 'cancel':
        plugin._runner.stop.set()
    if condition == 'busy':
        with plugin._runner.locks.acquire(('custom-60005', '')):
            result = plugin._execute_site('custom-60005', read_only=True)
    else:
        result = plugin._execute_site('custom-60005', read_only=True)
    assert result['status'] == status
    assert calls == []


def test_custom_verify_api_read_only(probe):
    import asyncio
    plugin, calls, _ = probe
    plugin._config['unlock_all_sites'] = True
    result = asyncio.run(plugin.api_verify_site(domain='custom-60005'))
    assert result['success'] is True
    assert result['data']['status'] == 'login_ok'
    assert calls == ['https://custom.invalid/']
