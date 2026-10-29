"""P5A read projections: no write and no change to P4 classification."""
import copy

from test_records_contract import records_api  # noqa: F401
from test_manual_run_endpoints import endpoints  # noqa: F401


def query(env, result_filter='all'):
    return env.client.get('/transfer_status', params={
        'page_size': 100, 'result_filter': result_filter}).json()


def test_optional_fields_are_read_only_and_default_safely(records_api):
    env = records_api
    env.data.clear()
    env.data['qb-a'] = {'source_hash': 'a', 'transfer_state': 'failed',
                        'error': 'target offline', 'attempts': 3, 'created_at': 123}
    env.data['qb-b'] = {'source_hash': 'b', 'transfer_state': 'completed'}
    before = copy.deepcopy(env.data)
    rows = {row['source_hash']: row for row in query(env)['items']}
    assert (rows['a']['error'], rows['a']['attempts'], rows['a']['created_at']) == ('target offline', 3, 123)
    assert (rows['b']['error'], rows['b']['attempts'], rows['b']['created_at']) == ('', 0, 0)
    assert env.data == before


def test_hidden_history_keeps_physical_index_safety_and_summary(records_api):
    env = records_api
    env.data.clear()
    env.data['qb-a'] = {'source_hash': 'a', 'transfer_state': 'completed',
                        'to_download': 'target', 'to_download_id': 'target-a',
                        'attempts': 3, 'hr_protected': True, 'history_hidden': True}
    before = copy.deepcopy(env.data)
    body = query(env)
    assert body['total'] == 0 and body['items'] == []
    assert body['status']['summary']['completed'] == 1
    assert env.data == before
    assert env.data['qb-a']['to_download_id'] == 'target-a'


def test_missing_and_equal_times_sort_stably_after_reload(records_api):
    env = records_api
    env.data.clear()
    for key, timestamp in [('z', None), ('b', 5), ('a', 5), ('y', None)]:
        env.data['qb-' + key] = {'source_hash': key, 'transfer_state': 'failed'}
        if timestamp is not None:
            env.data['qb-' + key]['updated_at'] = timestamp
    assert [row['source_hash'] for row in query(env)['items']] == ['a', 'b', 'y', 'z']
    snapshot = copy.deepcopy(env.data)
    env.data.clear()
    env.data.update(reversed(list(snapshot.items())))
    assert [row['source_hash'] for row in query(env)['items']] == ['a', 'b', 'y', 'z']


def test_special_categories_and_other_inflight_partition_all(records_api):
    env = records_api
    env.data.clear()
    for phase in ('completed', 'failed', 'target_ready', 'rollback', 'rolled_back', 'verifying', 'adding', 'source_pausing'):
        env.data['qb-' + phase] = {'source_hash': phase, 'transfer_state': phase,
                                   'delete_source_requested': phase == 'target_ready'}
    groups = [{row['source_hash'] for row in query(env, value)['items']}
              for value in ('success', 'failed', 'source_pending', 'rollback')]
    for i, group in enumerate(groups):
        assert all(group.isdisjoint(other) for other in groups[i + 1:])
    all_rows = {row['source_hash'] for row in query(env)['items']}
    classified = set.union(*groups)
    assert all_rows - classified == {'verifying', 'adding', 'source_pausing'}
    assert classified | {'verifying', 'adding', 'source_pausing'} == all_rows
    assert groups[0] == {'completed'} and groups[1] == {'failed'}
    assert groups[3] == {'rollback', 'rolled_back'}
