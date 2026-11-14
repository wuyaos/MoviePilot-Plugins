"""真实路由离线验收：清展示快照，不删业务记录、索引、队列或统计。"""
import copy
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from test_manual_run_endpoints import endpoints, PREFIX, _module  # noqa: F401


@pytest.fixture
def history_api(endpoints, monkeypatch):
    data, queue = {}, {}
    plugin = Mock()
    plugin.get_data.side_effect = lambda key=None: copy.deepcopy(data if key is None else data.get(key))
    plugin.save_data.side_effect = lambda key, value: data.__setitem__(key, copy.deepcopy(value))
    _module(monkeypatch, PREFIX + '.modules.transfer.tasks', load_transfer_tasks=lambda plugin: [])
    _module(monkeypatch, PREFIX + '.modules.transfer.recheck',
            load_seed_recheck_queue=lambda plugin: copy.deepcopy(queue),
            _queue_key=lambda name, hash_text: f'{name}::{hash_text.lower()}')
    monkeypatch.setattr(sys.modules[PREFIX + '.model.state'], 'load_transfer_stats',
                        lambda plugin: {'success_total': 123, 'today_success': 7})
    routes = {r['path']: r for r in endpoints.routes.build_api_routes(plugin)}
    def clear():
        return routes['/transfer_history_clear']['endpoint'](payload={}).data.result['removed']
    def status(**kwargs):
        return routes['/transfer_status']['endpoint'](**kwargs)
    return SimpleNamespace(data=data, queue=queue, plugin=plugin, routes=routes,
                           clear=clear, status=status, handlers=endpoints.handlers)


def record(name, phase='completed', **kwargs):
    return {'source_hash': name, 'transfer_state': phase, 'source_downloader': 'source',
            'to_download': 'target', 'to_download_id': name.upper(), 'updated_at': 1, **kwargs}


def test_clear_all_pages_preserves_physical_records_stats_and_route_auth(history_api):
    env = history_api
    env.data.update({f'source-h{i}': record(f'h{i}') for i in range(125)})
    env.data['unrelated'] = {'value': 4}
    before = copy.deepcopy(env.data)
    summary = env.status()['status']['summary']
    assert env.clear() == 125
    assert env.status()['total'] == 0
    assert env.status()['status']['summary'] == summary
    assert all(env.data[key] == value for key, value in before.items())
    assert set(env.data) - set(before) == {'transfer_history_snapshots'}
    assert env.clear() == 0
    assert env.routes['/transfer_history_clear']['auth'] == 'bear'
    assert env.routes['/transfer_history_clear']['methods'] == ['POST']
    env.plugin.del_data.assert_not_called()
    env.plugin.delete_torrents.assert_not_called()


@pytest.mark.parametrize('phase', ['adding', 'verifying', 'rollback', 'target_ready', 'source_pausing', 'unknown'])
def test_inflight_phases_remain_visible(history_api, phase):
    env = history_api
    env.data['source-a'] = record('a', phase)
    assert env.clear() == 0
    assert env.status()['total'] == 1


@pytest.mark.parametrize('fields', [
    {'hr_protected': True}, {'delete_source_requested': True},
    {'delete_source_requested': True, 'delete_source': False},
])
def test_protected_and_pending_source_not_hidden(history_api, fields):
    env = history_api
    env.data['source-a'] = record('a', **fields)
    assert env.clear() == 0
    assert env.status()['total'] == 1


def test_target_queue_identity_not_source_record_key(history_api):
    env = history_api
    env.data['source-a'] = record('a')
    env.queue['target::a'] = {'downloader': 'target', 'hash': 'A', 'phase': 'verifying'}
    assert env.clear() == 0
    assert env.status()['total'] == 1
    env.queue.clear()
    assert env.clear() == 1
    env.queue['target::a'] = {'downloader': 'target', 'hash': 'A'}
    assert env.status()['total'] == 1  # unchanged record is visible once re-enqueued


@pytest.mark.parametrize('phase', ['completed', 'failed', 'rolled_back'])
def test_ended_then_any_record_change_or_new_transaction_reappears(history_api, phase):
    env = history_api
    env.data['source-a'] = record('a', phase)
    assert env.clear() == 1
    assert env.status()['total'] == 0
    env.data['source-a']['internal_safety_marker'] = True  # not a display field
    assert env.status()['total'] == 1
    assert env.clear() == 1
    env.data['source-a'] = record('a', phase, created_at=500)
    assert env.status()['total'] == 1


def test_race_changed_between_snapshot_and_save_is_visible(history_api):
    env = history_api
    env.data['source-a'] = record('a')
    def save(key, value):
        env.data['source-a']['delete_source_requested'] = True
        env.data[key] = copy.deepcopy(value)
    env.plugin.save_data.side_effect = save
    assert env.clear() == 1  # snapshot, not a deletion acknowledgement
    assert env.status()['total'] == 1


def test_invalid_serialization_stays_visible(history_api):
    env = history_api
    env.data['source-a'] = record('a', internal=float('nan'))
    assert env.clear() == 0
    assert env.status()['total'] == 1
