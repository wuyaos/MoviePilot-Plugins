"""CookieCloud 离线契约：所有宿主 IO/解密均由合成边界替代。"""
import hashlib
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / 'plugins.v3'))
from autoptcheckin.core.credentials import Credential, CredentialResolver, cookiecloud_candidate
from autoptcheckin.core import native
from autoptcheckin.core.models import SignResult
from autoptcheckin.core.runner import SignRunner


@pytest.fixture
def cloud(monkeypatch, tmp_path):
    settings = SimpleNamespace(COOKIECLOUD_KEY='synthetic-key', COOKIECLOUD_PASSWORD='synthetic-password',
                               COOKIECLOUD_HOST='https://cloud.example.invalid', COOKIECLOUD_ENABLE_LOCAL=False,
                               COOKIE_PATH=tmp_path)
    response = Mock(status_code=200)
    response.json.return_value = {'encrypted': 'synthetic-ciphertext'}
    request = Mock()
    request.return_value.get_res.return_value = response
    decrypt = Mock(return_value=json.dumps({'cookie_data': {'irrelevant-group': [
        {'domain': '.example.invalid', 'name': 'session', 'value': 'synthetic-cloud'}
    ]}}).encode())
    for name, attrs in [('app.sdk.config', {'settings': settings}),
                        ('app.sdk.network', {'RequestUtils': request}),
                        ('app.sdk.utilities', {'CryptoJsUtils': SimpleNamespace(decrypt=decrypt)})]:
        module = ModuleType(name)
        module.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, module)
    return SimpleNamespace(settings=settings, request=request, response=response, decrypt=decrypt)


def test_remote_cookiecloud_follows_local_candidates_and_closes_response(cloud):
    result = cookiecloud_candidate('https://pt.example.invalid/attendance.php')
    assert result.status == 'valid'
    assert result.credential.source == 'cookiecloud'
    selected = CredentialResolver().select_cookie({'cookiecloud': result.credential,
        'managed_site': Credential('managed_site', 'synthetic-managed'),
        'local_cookie': Credential('local_cookie', 'synthetic-local')})
    assert selected.credential.source == 'managed_site'
    cloud.request.assert_called_once_with(timeout=20, content_type='application/json')
    cloud.request.return_value.get_res.assert_called_once_with(
        url='https://cloud.example.invalid/get/synthetic-key', allow_redirects=False, raise_exception=True)
    cloud.decrypt.assert_called_once_with('synthetic-ciphertext',
        hashlib.md5(b'synthetic-key-synthetic-password').hexdigest()[:16].encode())
    cloud.response.close.assert_called_once()


def test_local_cookiecloud_uses_file_without_network(cloud):
    cloud.settings.COOKIECLOUD_ENABLE_LOCAL = True
    path = cloud.settings.COOKIE_PATH / 'synthetic-key.json'
    path.write_text(json.dumps({'encrypted': 'synthetic-ciphertext'}))
    before = path.read_bytes()
    assert cookiecloud_candidate('https://pt.example.invalid').status == 'valid'
    assert path.read_bytes() == before
    cloud.request.assert_not_called()


@pytest.mark.parametrize('domain,valid', [('.example.invalid', True), ('pt.example.invalid', True),
    ('example.invalid', False), ('.other.invalid', False), ('.example.invalid.attacker.invalid', False),
    ('.t.example.invalid', False)])
def test_cookiecloud_domain_boundary(cloud, domain, valid):
    cloud.decrypt.return_value = json.dumps({'group': [{'domain': domain, 'name': 'session',
                                                       'value': 'synthetic'}]}).encode()
    assert (cookiecloud_candidate('https://pt.example.invalid').credential is not None) == valid


@pytest.mark.parametrize('failure', ['missing-key', 'missing-password', 'missing-host', 'missing-local',
    'bad-local-key', 'network', 'status', 'decrypt', 'malformed', 'cf-only'])
def test_cookiecloud_unavailable_is_silent_and_falls_back(cloud, failure, caplog, capsys):
    if failure.startswith('missing-') and failure != 'missing-local':
        setattr(cloud.settings, 'COOKIECLOUD_' + failure.removeprefix('missing-').upper(), '')
    elif failure in {'missing-local', 'bad-local-key'}:
        cloud.settings.COOKIECLOUD_ENABLE_LOCAL = True
        if failure == 'bad-local-key':
            cloud.settings.COOKIECLOUD_KEY = '../synthetic-key'
    elif failure == 'network':
        cloud.request.return_value.get_res.side_effect = TimeoutError('synthetic-key synthetic-password')
    elif failure == 'status':
        cloud.response.status_code = 503
    elif failure == 'decrypt':
        cloud.decrypt.side_effect = ValueError('synthetic-key synthetic-password')
    elif failure == 'malformed':
        cloud.decrypt.return_value = b'[]'
    elif failure == 'cf-only':
        cloud.decrypt.return_value = json.dumps({'group': [{'domain': '.example.invalid',
            'name': 'cf_clearance', 'value': 'synthetic'}]}).encode()
    result = cookiecloud_candidate('https://pt.example.invalid')
    assert result.credential is None and result.status == 'cookiecloud_unavailable'
    fallback = Credential('managed_site', 'synthetic-managed')
    assert CredentialResolver().select_cookie({'managed_site': fallback}).credential == fallback
    if failure.startswith('missing-') or failure == 'bad-local-key':
        cloud.request.assert_not_called()
    assert not caplog.records
    assert capsys.readouterr() == ('', '')


@pytest.mark.parametrize('available', [True, False])
def test_run_native_defers_cookiecloud_when_managed_cookie_succeeds(cloud, available):
    if not available:
        cloud.settings.COOKIECLOUD_KEY = ''
    site = SimpleNamespace(id='synthetic-site', url='https://pt.example.invalid',
                           signin=lambda ctx: SignResult('success'))
    seen = []
    def context(site, credential, info, lock, cancel):
        seen.append(credential.source)
        return SimpleNamespace(http=SimpleNamespace())
    result = native.run_native(SignRunner(), site, {'url': site.url, 'cookie': 'synthetic-managed'},
                               context_factory=context)
    assert result.status == 'success'
    assert seen == ['managed_site']
    assert cloud.request.return_value.get_res.call_count == 0
