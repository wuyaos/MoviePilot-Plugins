"""BrowserQL native routing and lost-response recovery, without network access."""
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from urllib.error import URLError

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / 'plugins.v3'))
from autoptcheckin.core import browserless, native, registry
from autoptcheckin.core.credentials import CredentialResolution
from autoptcheckin.core.models import LoginPage
from autoptcheckin.core.nexus import NexusSignin
from autoptcheckin.core.runner import SignRunner
from autoptcheckin.core.sitemodel import RecordSpec

CONFIG = {'browserless_enabled': True, 'browserless_url': 'http://browser.invalid', 'browserless_token': '', 'site_browserless': ['synthetic', 'pt_0ff']}
INFO = {'url': 'https://site.invalid/', 'cookie': 'synthetic=session', 'ua': 'test-agent'}
FORM = '<form method="post" action="/attendance.php"><input name="action" value="sign"><button>签到</button></form>'
SIGNED = '<h2>签到成功</h2>'


class Site(NexusSignin):
    id = 'synthetic'
    url = INFO['url']
    browserless = True
    record_spec = RecordSpec('//h2', {'签到成功': 'signed'})


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(native, 'cookiecloud_candidate', lambda url: CredentialResolution(None, 'unavailable'))
    monkeypatch.setattr(browserless, 'urlopen', lambda *a, **k: pytest.fail('unexpected BQL call'))
    monkeypatch.setattr(native.NativeHttpClient, 'get', lambda *a, **k: pytest.fail('unexpected HTTP call'))
    monkeypatch.setattr(native.NativeHttpClient, 'post', lambda *a, **k: pytest.fail('unexpected HTTP action'))


def mock_bql(monkeypatch, results):
    calls = []
    responses = iter(results)
    def request(req, timeout):
        payload = json.loads(req.data)
        calls.append((req.full_url, payload, timeout))
        value = next(responses)
        if isinstance(value, Exception):
            raise value
        return io.BytesIO(json.dumps(value).encode())
    monkeypatch.setattr(browserless, 'urlopen', request)
    return calls


def page(text=FORM, status=200, cookies=None, submit=None):
    # /function 契约：服务端 Puppeteer 返回的对象即为响应体
    return {'html': text, 'location': INFO['url'] + 'attendance.php', 'status': status,
            'jar': cookies or [], 'submitResult': submit}


def run(site=None, **kwargs):
    return native.run_native(SignRunner(), site or Site(), INFO, config=CONFIG, **kwargs)




def test_native_submit_and_cookie_roundtrip(monkeypatch):
    response = page(cookies=[{'name': 'cf_clearance', 'value': 'synthetic', 'domain': 'site.invalid'},
                             {'name': 'foreign', 'value': 'ignored', 'domain': 'other.invalid'}])
    action = page(submit={'text': 'not evidence', 'status': 200})
    calls = mock_bql(monkeypatch, [response, action, page(SIGNED)])
    result = run()
    assert result.status == 'success'
    assert result.metadata['transport'] == 'browserql'
    assert len(calls) == 3
    assert calls[0][0] == 'http://browser.invalid/function'
    code = calls[1][1]['code']
    assert calls[1][0].endswith('/function')
    assert 'test-agent' in code
    assert '"synthetic"' in code and 'cf_clearance' in code
    assert 'action=sign' in code
    assert '"script":' not in calls[2][1]['code']
    assert calls[0][2] == 75


@pytest.mark.parametrize('fresh,expected', [(SIGNED, 'success'), ('<html>unknown</html>', 'unconfirmed')])


def test_lost_action_response_only_readback(monkeypatch, fresh, expected):
    calls = mock_bql(monkeypatch, [page(), TimeoutError(), page(fresh)])
    assert run().status == expected
    assert sum('"script":' in call[1]['code'] for call in calls) == 1
    assert len(calls) == 3


@pytest.mark.parametrize('flag,enabled', [(False, True), (True, False)])


def test_http_routing_without_opt_in(monkeypatch, flag, enabled):
    site = Site()
    site.browserless = flag
    calls = []
    monkeypatch.setattr(native.NativeHttpClient, 'get', lambda self, url: calls.append(url) or LoginPage(SIGNED, url))
    result = native.run_native(SignRunner(), site, INFO, config={**CONFIG, 'browserless_enabled': enabled})
    assert result.status == 'already'
    assert len(calls) == 1
    assert 'transport' not in result.metadata


@pytest.mark.parametrize('status,expected', [(403, 'network_error'), (500, 'network_error')])


def test_initial_connection_failure_preserves_http_classification(monkeypatch, status, expected):
    mock_bql(monkeypatch, [URLError('unavailable')])
    monkeypatch.setattr(native.NativeHttpClient, 'get', lambda self, url: LoginPage('unavailable', url, status))
    assert run().status == expected




def test_readback_failure_never_falls_back_or_retries_action(monkeypatch):
    calls = mock_bql(monkeypatch, [page(), TimeoutError(), TimeoutError()])
    assert run().status == 'unconfirmed'
    assert len(calls) == 3


def test_slider_stays_pending_without_submit(monkeypatch):
    calls = mock_bql(monkeypatch, [page()])
    assert run(registry.get_native_module('pt_0ff')).status == 'protocol_pending'
    assert len(calls) == 1




def test_read_only_bql(monkeypatch):
    calls = mock_bql(monkeypatch, [page(SIGNED)])
    assert run(read_only=True).status == 'already'
    assert len(calls) == 1




def test_timeout_cap_and_existing_endpoint():
    http = SimpleNamespace(cookies={})
    client = browserless.BrowserQLClient(http, INFO, CONFIG, wait_ms=999999)
    assert client.timeout == 300
    assert browserless.bql_endpoint('https://browser.invalid') == 'https://browser.invalid/function'




def test_pt_0ff_already_is_safe(monkeypatch):
    mock_bql(monkeypatch, [page('<h2>签到成功</h2>')])
    assert run(registry.get_native_module('pt_0ff')).status == 'already'




def test_partial_bql_step_error_keeps_page_evidence(monkeypatch):
    response = page(SIGNED)
    response['errors'] = [{'path': ['solve'], 'message': 'synthetic timeout'}]
    mock_bql(monkeypatch, [response])
    assert run().status == 'already'




def test_bql_rejection_is_network_error_not_failed(monkeypatch):
    mock_bql(monkeypatch, [{'errors': [{'message': 'synthetic rejected query'}]}])
    assert run().status == 'network_error'
