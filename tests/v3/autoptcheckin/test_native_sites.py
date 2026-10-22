"""N3/N4 synthetic consumer tests: never make host or real-site requests."""
import asyncio
import importlib
import sys
from pathlib import Path
from threading import Event

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / 'plugins.v3'))
from autoptcheckin.core.credentials import Credential
from autoptcheckin.core.models import LoginPage, SignResult, SignStatus
from autoptcheckin.core.native import run_native
from autoptcheckin.core.registry import discover_sites, get_registry
from autoptcheckin.core.runner import SignRunner
from autoptcheckin.core.sitemodel import SignContext
from autoptcheckin.sites.native.hdsky import HDSky
from autoptcheckin.sites.native.haitang import Haitang


class Http:
    def __init__(self, site, pages, *, error=False):
        self.site, self.pages, self.error = site, iter(pages), error
        self.calls = []

    def get(self, url):
        self.calls.append(('get', url))
        value = next(self.pages)
        if isinstance(value, Exception):
            raise value
        return LoginPage(value, url)

    def post(self, url, *, data):
        self.calls.append(('post', url, data))
        if url.endswith('image_code_ajax.php'):
            return LoginPage('{"success":true,"code":"synthetic-hash"}', url)
        if self.error:
            raise TimeoutError()
        return LoginPage('untrusted submission reply', url)


def markup(site, signed=False):
    if isinstance(site, HDSky):
        return '<button id="showup">' + ('今日已签到' if signed else '签到') + '</button>'
    if signed:
        return '<p id="attendance-message">本次签到获得 10 魔力</p>'
    return '<p id="attendance-message">未签到</p><form action="attendance.php" method="post"><input name="csrf" value="fixture"><button type="submit">签到</button></form>'


def context(site, http, ocr=None):
    return SignContext(site.id, Credential('managed_site', 'synthetic'), http,
                       ocr=ocr or (lambda **kwargs: 'Ab1234'))


@pytest.mark.parametrize('cls', [HDSky, Haitang])
@pytest.mark.parametrize('error', [False, True])
def test_native_sites_submit_once_and_always_read(cls, error):
    site = cls()
    http = Http(site, [markup(site), markup(site, True)], error=error)
    result = site.signin(context(site, http))
    assert result.status == 'success' and result.evidence.raw_summary
    assert [call[0] for call in http.calls].count('get') == 2
    submits = [call for call in http.calls if call[0] == 'post' and not call[1].endswith('image_code_ajax.php')]
    assert len(submits) == 1
    if cls is HDSky:
        assert dict(submits[0][2]) == dict(action='showup', imagehash='synthetic-hash', imagestring='Ab1234')
    else:
        assert dict(submits[0][2]) == dict(action='sign', csrf='fixture')


@pytest.mark.parametrize('cls', [HDSky, Haitang])
def test_native_already_never_submits(cls):
    site = cls()
    http = Http(site, [markup(site, True)])
    assert site.signin(context(site, http)).status == 'already'
    assert len(http.calls) == 1


@pytest.mark.parametrize('cls', [HDSky, Haitang])
@pytest.mark.parametrize('fresh,status', [('<main>已签到</main>', 'unconfirmed'), (TimeoutError(), 'unconfirmed')])
def test_native_missing_readback_is_not_failure(cls, fresh, status):
    site = cls()
    http = Http(site, [markup(site), fresh])
    assert site.signin(context(site, http)).status == status
    assert http.calls[-1][0] == 'get'


def test_hdsky_ocr_parameters_and_fallback_only_before_submission():
    site = HDSky()
    http = Http(site, [markup(site), markup(site, True)])
    calls = []
    def ocr(**kwargs):
        calls.append(kwargs)
        return None if len(calls) == 1 else 'Xy9876'
    assert site.signin(context(site, http, ocr)).status == 'success'
    assert [call['engine'] for call in calls] == ['ddddocr', 'ocrhelper']
    assert all(call['min_len'] == call['max_len'] == 6 and call['charset'] == 'alnum' and call['retry_times'] == 1 for call in calls)
    assert all('action=regimage&imagehash=synthetic-hash' in call['image_url'] for call in calls)
    assert len([call for call in http.calls if call[1].endswith('showup.php')]) == 1


@pytest.mark.parametrize('code', [None, 'short', '!!!123'])
def test_hdsky_unsolved_captcha_never_signs(code):
    site = HDSky()
    http = Http(site, [markup(site)])
    assert site.signin(context(site, http, lambda **kwargs: code)).status == 'protocol_pending'
    assert not any(call[1].endswith('showup.php') for call in http.calls)


def test_registry_native_overrides_legacy_without_duplicate_ids():
    result = discover_sites()
    for sid in ('hdsky', 'haitang'):
        rows = [row for row in result['sites'] if row['id'] == sid]
        assert len(rows) == 1 and rows[0]['native'] and rows[0]['verified'] and rows[0]['pilot_enabled']
    batch1 = {'52pt', 'agsvpt', 'baozi', 'btschool', 'chdbits'}
    expected_native = {path.stem for path in (Path(__file__).parents[3] / 'plugins.v3' / 'autoptcheckin' / 'sites' / 'native').glob('*.py') if path.stem != '__init__'}
    from autoptcheckin.sites.native.generic import build_generic_sites
    expected_native.discard('generic')
    expected_native.update(cls.id for cls in build_generic_sites())
    assert expected_native >= batch1
    assert all(row['native'] and not row['verified'] for row in result['sites'] if row['id'] in expected_native - {'hdsky', 'haitang'})
    assert all(row['native'] and not row['verified'] for row in result['sites'] if row['id'] in batch1)
    assert all(not row['native'] and not row['verified'] for row in result['sites']
               if row['id'] not in {'hdsky', 'haitang', *expected_native})
    assert sum(row['native'] for row in result['sites']) >= 7


def test_native_discovery_default_unverified_and_import_isolation(tmp_path, monkeypatch):
    pkg = tmp_path / 'n3_fixture_sites'
    (pkg / 'native').mkdir(parents=True)
    (pkg / '__init__.py').write_text('class _ISiteSigninHandler: pass\n')
    (pkg / 'native' / '__init__.py').write_text('')
    (pkg / 'native' / 'sample.py').write_text('from autoptcheckin.core.sitemodel import SiteModule\nclass Sample(SiteModule):\n id="n3sample"\n name="Sample"\n url="https://fixture.invalid/"\n def signin(self, ctx): pass\n')
    (pkg / 'native' / 'broken.py').write_text('raise RuntimeError("offline")\n')
    monkeypatch.syspath_prepend(str(tmp_path))
    result = discover_sites('n3_fixture_sites')
    row = next(row for row in result['sites'] if row['id'] == 'n3sample')
    assert row['native'] and not row['verified'] and not row['pilot_enabled']
    assert result['skipped'] == [{'module': 'n3_fixture_sites.native.broken', 'error': 'RuntimeError'}]


def test_sites_api_merges_custom_metadata_without_cache_or_credential_leak(monkeypatch):
    module = importlib.import_module('autoptcheckin')
    plugin = module.AutoPtCheckin()
    plugin._config = {'custom_sites_data': [{'id': 'custom_one', 'name': 'Custom', 'url': 'https://fixture.invalid/', 'emulate': True, 'cookie': 'not-for-api'}, {'id': 'hdsky', 'name': 'collision'}]}
    sites = asyncio.run(plugin.api_sites())['data']['sites']
    row = next(row for row in sites if row['id'] == 'custom_one')
    assert row['source'] == '自定义站点' and row['emulate'] and not row['native'] and not row['verified']
    assert 'cookie' not in row and len([row for row in sites if row['id'] == 'hdsky']) == 1
    assert not any(row['id'] == 'custom_one' for row in get_registry()['sites'])


@pytest.mark.parametrize('native,verified,expected', [(True, True, 'native'), (True, False, 'native_unverified'), (False, False, 'legacy')])
def test_execute_site_dual_track_and_gate(monkeypatch, native, verified, expected):
    module = importlib.import_module('autoptcheckin')
    plugin = module.AutoPtCheckin()
    plugin._config = {'enabled_sites': ['hdsky'], 'sign_sites': ['hdsky']}
    monkeypatch.setattr(module, 'get_registry', lambda *args: {'sites': [dict(id='hdsky', native=native, verified=verified, signin_capable=True, signin_applicable=True, login_capable=True, source='插件适配')]})
    calls = []
    def managed(sid):
        calls.append('managed')
        return {}
    monkeypatch.setattr(module, 'managed_site', managed)
    monkeypatch.setattr(module, 'run_native', lambda *args, **kwargs: SignResult(SignStatus.SUCCESS, 'native'))
    monkeypatch.setattr(plugin._runner, 'run', lambda *args, **kwargs: SignResult(SignStatus.SUCCESS, 'legacy'))
    results = plugin._execute_all()  # 批次已转后台线程，语义断言直接调 _execute_all
    if expected == 'native_unverified':
        assert results == []
        assert plugin._track_store().state_of('hdsky', 'sign') == 'disabled'
        assert not calls and plugin._history.list()['total'] == 0
    else:
        assert results[0]['message'] == expected
        assert calls == ['managed']


@pytest.mark.parametrize('read_only', [False, True])
def test_run_native_context_lock_history_and_readonly(read_only):
    site = Haitang()
    http = Http(site, [markup(site, True)])
    history = []
    runner = SignRunner(history=history.append)
    def factory(site, credential, info, lock, cancel):
        assert lock is runner.locks and cancel is runner.stop
        with lock.acquire((site.id, '')) as acquired:
            assert not acquired
        return SignContext(site.id, credential, http, site_lock=lock, cancel=cancel)
    result = run_native(runner, site, {'cookie': 'synthetic'}, read_only=read_only, context_factory=factory)
    assert result.status == 'already' and len(history) == 1
    assert result.metadata == dict(action='sign', trigger='manual', read_only=read_only) and len(http.calls) == 1


@pytest.mark.parametrize('mode,status', [('busy', 'skipped'), ('missing', 'auth_failed'), ('cancel', 'cancelled')])
def test_run_native_preconditions_do_not_create_resources(mode, status):
    runner = SignRunner()
    if mode == 'cancel':
        runner.stop.set()
    def forbidden(*args):
        pytest.fail('no HTTP/OCR resources before preconditions')
    if mode == 'busy':
        with runner.locks.acquire(('hdsky', '')):
            result = run_native(runner, HDSky(), {}, context_factory=forbidden)
    else:
        result = run_native(runner, HDSky(), {}, context_factory=forbidden)
    assert result.status == status


def test_custom_site_enters_sign_queue_and_gate_skip_writes_disabled():
    """回归：自定义站必须进签到队列（recompute sign 分支豁免 PILOTS 门控）；
    门控类 skip 必须写 disabled 状态表且不被当场重试（避免重复执行噪音）。"""
    module = importlib.import_module('autoptcheckin')
    plugin = module.AutoPtCheckin()
    plugin.get_data = lambda key: {}
    plugin.save_data = lambda key, value: None
    plugin.update_config = lambda value: None
    plugin._config = {'enabled_sites': ['custom-60005'], 'sign_sites': ['custom-60005']}
    monkey_source = module.get_registry
    module.get_registry = lambda *args, **kwargs: {'sites': [dict(
        id='custom-60005', name='自定义站', url='https://c.invalid/', source='自定义站点',
        native=False, signin_capable=True, signin_applicable=True, login_capable=True)]}
    try:
        plugin._recompute_track_states()
        assert plugin._track_store().state_of('custom-60005', 'sign') == 'pending'
        assert plugin._due_for('sign') == ['custom-60005']
    finally:
        module.get_registry = monkey_source

    plugin2 = module.AutoPtCheckin()
    plugin2.get_data = lambda key: {}
    plugin2.save_data = lambda key, value: None
    plugin2._config = {'enabled_sites': ['60009'], 'sign_sites': ['60009'], 'retry_count': 3}
    from autoptcheckin.core.models import SignResult, SignStatus
    calls = []

    def fake_execute(site_id, read_only=False, trigger='manual', action='sign'):
        calls.append(1)
        result = SignResult.skipped('signin_not_supported')
        result.site_id = str(site_id)
        result.metadata.update({'reason': 'signin_not_supported', 'action': action})
        plugin2._record_result(result)
        return {'status': 'skipped', 'site_id': str(site_id)}

    plugin2._execute_site = fake_execute
    plugin2._track_store().apply_result('60009', 'sign', 'failed', message='x', time='2026-10-23T01:00:00')
    plugin2._run_with_retry('60009', 'sign', 'manual')
    assert len(calls) == 1, calls
    assert plugin2._track_store().state_of('60009', 'sign') == 'disabled'
