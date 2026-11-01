"""同步删除失败重试、下载器身份隔离与无身份歧义的生产入口反例。"""
import importlib.util
import sys
import threading
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

PLUGIN = Path(__file__).resolve().parents[3] / 'plugins.v3/downloadmanagerlocal'
PREFIX = 'app.plugins.downloadmanagerlocal'


@pytest.fixture
def runtime(monkeypatch):
    def module(name, path=None, **attrs):
        result = types.ModuleType(name)
        if path is not None:
            result.__path__ = [str(path)]
        result.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, result)
        return result

    module('app')
    module('app.sdk')
    module('app.sdk.logging', logger=Mock())
    module('app.plugins')
    module(PREFIX, PLUGIN)
    module(PREFIX + '.modules', PLUGIN / 'modules')
    module(PREFIX + '.modules.cleanup', PLUGIN / 'modules/cleanup')
    module(PREFIX + '.modules.hr')
    guard = Mock()
    guard.should_skip.return_value = False
    module(PREFIX + '.modules.hr.guard', HrGuard=Mock(return_value=guard), SKIP_PATH_SYNC_DELETE='sync_delete')
    services = {}
    module(PREFIX + '.adapter')
    module(PREFIX + '.adapter.moviepilot', get_downloader_services=lambda **kwargs: services)
    sys.modules[PREFIX + '.adapter.moviepilot'].get_download_hash_by_fullpath = lambda path: ''
    module(PREFIX + '.modules.transfer')
    module(PREFIX + '.modules.transfer.tasks', load_transfer_tasks=lambda plugin: [])
    module(PREFIX + '.utils')
    module(PREFIX + '.utils.config', observe_skip=lambda *args: False)
    spec = importlib.util.spec_from_file_location(PREFIX + '.modules.cleanup.service', PLUGIN / 'modules/cleanup/service.py')
    service = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, service)
    spec.loader.exec_module(service)
    data = {}
    plugin = SimpleNamespace(_syncdel=True, _fromdownloader='', _sync_delete_recent={},
                             _sync_delete_inflight=set(), _seed_recheck_lock=threading.RLock(),
                             get_data=lambda key=None: list(data) if key is None else data.get(key),
                             save_data=lambda key, value: data.__setitem__(key, value))
    target = Mock()
    target.is_inactive.return_value = False
    target.delete_torrents.return_value = True
    services['target'] = SimpleNamespace(instance=target)
    return SimpleNamespace(service=service, plugin=plugin, data=data, target=target, guard=guard, services=services)


def record(r, source='qb', target='one'):
    r.data[f'{source}-abc'] = {'to_download': 'target', 'to_download_id': target}


@pytest.mark.parametrize('failure', ['false', 'exception', 'missing', 'guard'])
def test_failed_sync_delete_does_not_suppress_retry(runtime, failure):
    r = runtime
    record(r)
    if failure == 'false':
        r.target.delete_torrents.return_value = False
    elif failure == 'exception':
        r.target.delete_torrents.side_effect = RuntimeError('network')
    elif failure == 'missing':
        r.services.clear()
    else:
        r.guard.should_skip.return_value = True
    first = r.service.cleanup_by_hash(r.plugin, 'abc', 'qb')
    assert first['transfer_deleted'] == 0
    assert not r.plugin._sync_delete_recent
    r.target.delete_torrents.return_value = True
    r.target.delete_torrents.side_effect = None
    r.services['target'] = SimpleNamespace(instance=r.target)
    r.guard.should_skip.return_value = False
    second = r.service.cleanup_by_hash(r.plugin, 'abc', 'qb')
    assert second['transfer_deleted'] == 1
    assert second['skipped'] is False
    assert r.service.cleanup_by_hash(r.plugin, 'abc', 'qb')['skipped'] is True


def test_same_hash_two_sources_both_cleanup(runtime):
    r = runtime
    record(r, 'qb', 'one')
    record(r, 'tr', 'two')
    assert r.service.cleanup_by_hash(r.plugin, 'abc', 'qb')['transfer_deleted'] == 1
    assert r.service.cleanup_by_hash(r.plugin, 'abc', 'tr')['transfer_deleted'] == 1
    assert [call.kwargs['ids'] for call in r.target.delete_torrents.call_args_list] == [['one'], ['two']]


@pytest.mark.parametrize("legacy_source", ["", "qb"])
def test_missing_record_and_ambiguous_identity_are_not_cached(runtime, legacy_source):
    r = runtime
    r.plugin._fromdownloader = legacy_source
    r.plugin._selected_downloaders = lambda: ["qb", "tr"]
    assert r.service.cleanup_by_hash(r.plugin, 'abc')['transfer_deleted'] == 0
    assert not r.plugin._sync_delete_recent
    record(r, 'qb', 'one')
    record(r, 'tr', 'two')
    assert r.service.cleanup_by_hash(r.plugin, 'abc')['transfer_deleted'] == 0
    r.target.delete_torrents.assert_not_called()
    assert not r.plugin._sync_delete_recent
    assert r.service.cleanup_by_hash(r.plugin, 'abc', 'tr')['transfer_deleted'] == 1
