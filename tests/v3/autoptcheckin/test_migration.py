"""S6 配置迁移：所有来源均为合成夹具，宿主/站点网络不参与测试。"""
import asyncio
from copy import deepcopy
import importlib
import json
from pathlib import Path
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / 'plugins.v3'))
m = importlib.import_module('autoptcheckin.core.migration')
Plugin = importlib.import_module('autoptcheckin').AutoPtCheckin
REGISTRY = {'sites': [{'id': 'hdsky'}, {'id': 'haitang'}]}


@pytest.fixture
def sources():
    configs = json.loads((Path(__file__).parent / 'fixtures/migration_configs.json').read_text())
    return {key: {'status': 'ready', 'config': value} for key, value in configs.items()}


@pytest.fixture
def plugin(sources):
    obj = Plugin()
    obj.data, obj.config_writes = {}, []
    obj.get_data = lambda key: deepcopy(obj.data.get(key))
    obj.save_data = lambda key, value: obj.data.update({key: deepcopy(value)})
    obj.update_config = lambda value: obj.config_writes.append(deepcopy(value))
    obj._migration = m.Migration(obj, lambda: deepcopy(sources), REGISTRY)
    return obj


@pytest.mark.parametrize('key', m.CONFIG_KEYS)
def test_flat_mapping(sources, key):
    plan = m.build_preview(sources, {}, REGISTRY)
    assert plan['changes'][key]['value'] == sources['AutoPtCheckin']['config'][key]


@pytest.mark.parametrize('prefix,source,key', [
    ('rousi', 'RousiCheckin', 'username'), ('rousi', 'RousiCheckin', 'password'),
    ('sunnypt', 'SunnyPTSignin', 'username'), ('sunnypt', 'SunnyPTSignin', 'password'),
    ('sunnypt', 'SunnyPTSignin', 'token')])
def test_credentials_mapping(sources, prefix, source, key):
    plan = m.build_preview(sources, {}, REGISTRY)
    assert plan['changes'][prefix + '_' + key]['value'] == sources[source]['config'][key]
    assert sources[source]['config'][key] not in json.dumps(m.public_preview(plan))


@pytest.mark.parametrize('key,old,new', [
    ('enabled', False, True), ('notify', True, False), ('queue_cnt', 0, 3),
    ('cron', 'old', 'new'), ('sign_sites', ['haitang'], ['hdsky']),
    ('login_sites', ['haitang'], ['hdsky'])])
def test_conflicts_preserve_false_and_zero(sources, key, old, new):
    sources['AutoPtCheckin']['config'][key] = new
    assert m.build_preview(sources, {key: old}, REGISTRY)['changes'][key]['conflict']


@pytest.mark.parametrize('empty', [None, '', [], {}])
def test_empty_target_is_not_conflict(sources, empty):
    assert not m.build_preview(sources, {'cron': empty}, REGISTRY)['changes']['cron']['conflict']


def test_equal_target_not_conflict(sources):
    assert not m.build_preview(sources, {'enabled': True}, REGISTRY)['changes']['enabled']['conflict']


def test_domain_mapping(monkeypatch, sources):
    registry = importlib.import_module('autoptcheckin.core.registry')
    monkeypatch.setitem(registry._MATCHERS, 'hdsky', lambda url: url == 'https://sky.invalid/')
    sources['AutoPtCheckin']['config']['sign_sites'] = ['https://sky.invalid/path', 'sky.invalid']
    assert m.build_preview(sources, {}, REGISTRY)['changes']['sign_sites']['value'] == ['hdsky']


def test_custom_mapping_and_unmapped(sources):
    plan = m.build_preview(sources, {}, REGISTRY)
    changes = plan['changes']
    custom = changes['custom_sites_data']['value']
    assert len(custom) == 2 and custom[0]['emulate'] and not custom[1]['emulate']
    assert changes['sign_sites']['value'] == ['hdsky', custom[0]['id']]
    assert changes['enabled_sites']['value'] == ['hdsky', custom[0]['id'], 'haitang']
    assert plan['unmapped'] == [{'source': 'AutoPtCheckin', 'key': 'sign_sites', 'index': 1, 'value': 'unknown.invalid'}]
    assert all('cookie' not in item for item in custom)
    assert len(plan['data_unavailable']) == 3


@pytest.mark.parametrize('url', ['file:///tmp/a', 'https://user:pass@site.invalid', '', 'no-scheme.invalid'])
def test_bad_custom_url_not_imported(sources, url):
    sources['AutoPtCheckin']['config'] = {'custom_sites_data': [{'name': 'Bad', 'url': url}]}
    plan = m.build_preview(sources, {}, REGISTRY)
    assert plan['changes']['custom_sites_data']['value'] == []
    assert len(plan['unmapped']) == 1


def test_read_missing_never_fetches_configs():
    calls = []
    def get(path):
        calls.append(path)
        return []
    assert all(v['status'] == 'source_missing' for v in m.read_sources(get).values())
    assert calls == ['/installed']


@pytest.mark.parametrize('version', ['3.0.0', '3.4.0', '4.0'])
def test_do_not_read_self_v3(version):
    def get(path):
        if path == '/installed':
            return ['AutoPtCheckin']
        assert path == '/?state=installed'
        return [{'id': 'AutoPtCheckin', 'plugin_version': version}]
    assert m.read_sources(get)['AutoPtCheckin'] == {'status': 'source_missing', 'reason': 'self_v3'}


def test_read_v2_and_missing_independently():
    payloads = {'/installed': ['AutoPtCheckin', 'RousiCheckin'],
                '/?state=installed': [{'id': 'AutoPtCheckin', 'plugin_version': '2.9.0'}],
                '/AutoPtCheckin': {'enabled': True}, '/RousiCheckin': {}}
    result = m.read_sources(payloads.__getitem__)
    assert result['AutoPtCheckin']['config'] == {'enabled': True}
    assert result['RousiCheckin']['status'] == 'ready'
    assert result['SunnyPTSignin']['status'] == 'source_missing'


def test_read_error_not_missing():
    def get(path):
        if path == '/installed':
            return ['RousiCheckin']
        raise TimeoutError('secret must not leak')
    result = m.read_sources(get)
    assert result['RousiCheckin']['status'] == 'source_error'
    assert 'secret' not in json.dumps(result)


@pytest.mark.parametrize('confirm', [False, None, 1, 'true'])
def test_requires_literal_confirmation(plugin, confirm):
    plugin._migration.preview()
    with pytest.raises(m.MigrationError, match='confirmation_required'):
        plugin._migration.execute(confirm)
    assert plugin.data == {}


def test_requires_preview(plugin):
    with pytest.raises(m.MigrationError, match='preview_required'):
        plugin._migration.execute(True)
    assert plugin.data == {}


@pytest.mark.parametrize('change_source', [True, False])
def test_stale_preview(plugin, sources, change_source):
    plugin._migration.preview()
    if change_source:
        sources['RousiCheckin']['config']['username'] = 'changed'
    else:
        plugin._config['enabled'] = False
    with pytest.raises(m.MigrationError, match='stale'):
        plugin._migration.execute(True)
    assert plugin.data == {}


@pytest.mark.parametrize('overwrite', [True, False])
def test_execute_conflicts_and_snapshot(plugin, overwrite):
    plugin._config = {'enabled': False, 'untouched': 42}
    plugin.data['site_config'] = {'rousi_username': 'old-user'}
    plugin._migration.preview()
    assert len(plugin.data) == 1
    result = plugin._migration.execute(True, overwrite)
    assert result['status'] == 'completed'
    assert plugin._config['enabled'] is overwrite
    assert plugin.get_data(m.Migration.BACKUP_KEY)['config'] == {'enabled': False, 'untouched': 42}
    assert plugin.get_data(m.Migration.BACKUP_KEY)['site_config'] == {'rousi_username': 'old-user'}
    assert plugin._config['untouched'] == 42
    assert plugin.get_service() == []


def test_idempotent_across_restart(plugin):
    plugin._migration.preview()
    plugin._migration.execute(True)
    backup = plugin.get_data(m.Migration.BACKUP_KEY)
    migration = m.Migration(plugin, lambda: pytest.fail('must not reread'), REGISTRY)
    assert migration.execute(True)['status'] == 'already_executed'
    assert plugin.get_data(m.Migration.BACKUP_KEY) == backup
    assert len(plugin.config_writes) == 1


def test_failure_keeps_snapshot_and_blocks_retry(plugin):
    plugin.update_config = lambda value: (_ for _ in ()).throw(RuntimeError('write failed'))
    plugin._migration.preview()
    with pytest.raises(RuntimeError):
        plugin._migration.execute(True)
    assert plugin.get_data(m.Migration.BACKUP_KEY)['config'] == {}
    with pytest.raises(m.MigrationError, match='rollback_required'):
        plugin._migration.execute(True)


def test_concurrent_execution_only_writes_once(plugin):
    plugin._migration.preview()
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda _: plugin._migration.execute(True), range(2)))
    assert {result['status'] for result in results} == {'completed', 'already_executed'}
    assert len(plugin.config_writes) == 1


def test_empty_preview_does_not_mark_completed(plugin):
    plugin._migration.sources = lambda: {key: {'status': 'source_missing'} for key in m.SOURCES}
    plugin._migration.preview()
    assert plugin._migration.execute(True)['status'] == 'no_changes'
    assert plugin.data == {}


def test_api_routes_and_error_envelope(plugin):
    routes = {r['path']: r for r in plugin.get_api()}
    for path, method in [('/migrate/preview', 'GET'), ('/migrate/execute', 'POST')]:
        assert routes[path]['auth'] == 'bear' and routes[path]['methods'] == [method]
    error = asyncio.run(plugin.api_migrate_execute({'confirm': False}))
    assert error == {'success': False, 'message': 'confirmation_required', 'data': None}
    assert asyncio.run(plugin.api_migrate_preview())['success']
    assert asyncio.run(plugin.api_migrate_execute({'confirm': True}))['data']['status'] == 'completed'


def test_custom_conflict_skips_dependent_selection(plugin):
    plugin._config['custom_sites_data'] = [{'id': 'custom-existing', 'name': 'Existing', 'url': 'https://old.invalid/'}]
    plugin._migration.preview()
    result = plugin._migration.execute(True)
    assert result['skipped_dependencies'] == ['enabled_sites', 'sign_sites']
    assert 'enabled_sites' not in plugin._config and 'sign_sites' not in plugin._config
    assert plugin._config['custom_sites_data'][0]['id'] == 'custom-existing'


def test_source_error_blocks_writes(plugin):
    plugin._migration.sources = lambda: {'RousiCheckin': {'status': 'source_error'}}
    plugin._migration.preview()
    with pytest.raises(m.MigrationError, match='source_read_error'):
        plugin._migration.execute(True)
    assert not plugin.data


def test_generic_api_error_does_not_leak(plugin):
    plugin._migration.preview = lambda: (_ for _ in ()).throw(RuntimeError('private-value'))
    result = asyncio.run(plugin.api_migrate_preview())
    assert result == {'success': False, 'message': 'migration_preview_failed', 'data': None}


def test_snapshot_restore_recovers_config_and_site_subset(plugin):
    original = {'enabled': False, 'rousi_username': 'original-fixture'}
    plugin.init_plugin(original)
    plugin._migration.preview()
    plugin._migration.execute(True, True)
    backup = plugin.get_data(m.Migration.BACKUP_KEY)
    plugin.update_config(backup['config'])
    plugin.save_data('site_config', backup['site_config'])
    plugin.init_plugin(backup['config'])
    assert plugin._config == original
    assert plugin._site_config == {'rousi_username': 'original-fixture'}
