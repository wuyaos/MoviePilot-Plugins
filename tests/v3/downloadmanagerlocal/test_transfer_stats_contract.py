"""P5A: real transaction persistence/statistics, with downloader boundaries replaced."""
import copy
import sys

from test_transfer_pipeline import runtime, begin, cycle  # noqa: F401


def stats(r):
    return sys.modules['app.plugins.downloadmanagerlocal.model.state'].load_transfer_stats(r.plugin)


def test_confirmed_success_is_idempotent_across_delete_retry_and_reload(runtime):
    r = runtime
    r.plugin._seed_autostart = False
    r.source.delete_torrents.return_value = False
    assert begin(r)
    cycle(r)
    cycle(r)
    assert stats(r)['success_total'] == stats(r)['today_success'] == 1
    assert r.data['source-abc']['transfer_state'] == 'target_ready'
    assert r.data['source-abc']['delete_source_pending']
    cycle(r)
    assert stats(r)['success_total'] == 1
    reloaded = copy.deepcopy(r.data['queue']['target::abc'])
    stale = copy.deepcopy(reloaded)
    stale.pop('success_counted')
    r.source.delete_torrents.return_value = True
    task = {'state': 'pausedUP'}
    assert r.pipeline.advance_transfer(r.plugin, reloaded, r.services['target'], task, lambda: False)
    assert r.pipeline.advance_transfer(r.plugin, reloaded, r.services['target'], task, lambda: False)
    assert r.pipeline.advance_transfer(r.plugin, stale, r.services['target'], task, lambda: False)
    assert stats(r)['success_total'] == 1
    assert r.plugin.get_data('source-abc')['success_counted']


def test_unconfirmed_target_never_counts_success(runtime):
    r = runtime
    assert begin(r)
    cycle(r)
    cycle(r, 'checkingUP')
    assert stats(r)['success_total'] == 0


def fail(r, attempts=0):
    assert not r.pipeline.begin_transfer(
        r.plugin, r.services['source'], r.services['target'], 'abc',
        {'state': 'uploading'}, lambda: None, lambda: False, attempts=attempts)
    cycle(r)


def test_failure_counts_only_terminal_entry_and_survives_reload_and_new_transaction(runtime, monkeypatch):
    r = runtime
    state = sys.modules['app.plugins.downloadmanagerlocal.model.state']
    monkeypatch.setattr(state, 'today_stamp', lambda: '2026-01-01')
    fail(r)
    fail(r, 1)
    assert stats(r)['failure_today_count'] == 0
    fail(r, 2)
    failed = r.plugin.get_data('source-abc')
    failed_at = failed['failed_at']
    assert stats(r)['failure_today_count'] == 1
    assert r.pipeline.rollback_transfer(r.plugin, failed, r.services['target'], lambda: False)
    assert r.plugin.get_data('source-abc')['failed_at'] == failed_at
    assert stats(r)['failure_today_count'] == 1
    # Rebuild all in-memory records from the persisted snapshot.
    r.data.update(copy.deepcopy(r.data))
    assert stats(r)['failure_today_count'] == 1
    fail(r, 0)  # independent transaction overwrites source index, not event counter
    assert 'failed_at' not in r.plugin.get_data('source-abc')
    assert stats(r)['failure_today_count'] == 1
    monkeypatch.setattr(state, 'today_stamp', lambda: '2026-01-02')
    assert stats(r)['failure_today_count'] == 0
    fail(r, 2)
    assert stats(r)['failure_today_count'] == 1
    assert r.data['transfer_stats']['failure_today_date'] == '2026-01-02'


def test_rollback_retries_are_inflight_not_terminal_failures(runtime):
    r = runtime
    r.target.delete_torrents.return_value = False
    assert begin(r)
    for _ in range(3):
        cycle(r, 'error')
    assert r.plugin.get_data('source-abc')['transfer_state'] == 'rollback'
    assert r.plugin.get_data('source-abc')['attempts'] == 0
    assert 'failed_at' not in r.plugin.get_data('source-abc')
    assert stats(r)['failure_today_count'] == 0


def test_hidden_marker_survives_save_and_new_transaction_is_not_hidden(runtime):
    r = runtime
    assert begin(r)
    r.data['source-abc'].update(history_hidden=True, hr_protected=True)
    snapshot = copy.deepcopy(r.data['source-abc'])
    item = r.recheck.load_seed_recheck_queue(r.plugin)['target::abc']
    r.pipeline.save_transaction(r.plugin, item)
    record = r.plugin.get_data('source-abc')
    assert record['history_hidden']
    assert record['attempts'] == snapshot['attempts']
    assert (record['to_download'], record['to_download_id']) == ('target', 'abc')
    assert record['source_hash'] == snapshot['source_hash']
    assert stats(r)['success_total'] == 0
    assert begin(r)
    assert not r.plugin.get_data('source-abc').get('history_hidden')


def test_protected_source_retains_existing_phase_and_adds_pending_marker(runtime):
    r = runtime
    r.guard.is_protected.return_value = True
    r.plugin._seed_autostart = False
    assert begin(r)
    cycle(r)
    cycle(r)
    record = r.plugin.get_data('source-abc')
    assert record['transfer_state'] == 'completed'
    assert record['delete_source_pending'] and record['hr_protected']
    assert stats(r)['success_total'] == 1


def test_disk_reload_rebuild_preserves_success_and_failure_counters(runtime, tmp_path):
    import json
    from types import SimpleNamespace

    r = runtime
    path = tmp_path / 'plugin-state.json'
    path.write_text('{}', encoding='utf-8')

    def read(key):
        return json.loads(path.read_text(encoding='utf-8')).get(key)

    def save(key, value):
        data = json.loads(path.read_text(encoding='utf-8'))
        data[key] = value
        path.write_text(json.dumps(data), encoding='utf-8')

    r.plugin.get_data = read
    r.plugin.save_data = save
    fail(r, 2)
    before_failure = stats(r)['failure_today_count']
    r.plugin._seed_autostart = False
    r.source.delete_torrents.return_value = False
    assert begin(r)
    cycle(r)
    cycle(r)
    before = stats(r)
    # Recreate runtime object and locks; only the JSON disk survives.
    r.plugin = SimpleNamespace(**vars(r.plugin))
    import threading
    r.plugin._seed_recheck_lock = threading.RLock()
    r.plugin._seed_recheck_queue_lock = r.plugin._seed_recheck_lock
    reloaded = r.recheck.load_seed_recheck_queue(r.plugin)['target::abc']
    r.source.delete_torrents.return_value = True
    assert r.pipeline.advance_transfer(r.plugin, reloaded, r.services['target'],
                                       {'state': 'pausedUP'}, lambda: False)
    assert stats(r) == before
    assert stats(r)['success_total'] == 1
    assert stats(r)['failure_today_count'] == before_failure == 1


def test_hidden_source_index_is_still_consumed_by_real_sync_delete(runtime):
    import ast
    from pathlib import Path
    from types import SimpleNamespace
    from unittest.mock import Mock

    r = runtime
    assert begin(r)
    r.data['source-abc']['history_hidden'] = True
    path = Path(__file__).resolve().parents[3] / 'plugins.v3/downloadmanagerlocal/modules/cleanup/service.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name == '_cleanup_transfer_target')
    guard = Mock()
    guard.return_value.should_skip.return_value = False
    instance = Mock()
    instance.is_inactive.return_value = False
    instance.delete_torrents.return_value = True
    namespace = dict(HrGuard=guard, SKIP_PATH_SYNC_DELETE='sync_delete', logger=Mock(),
                     _clean_text=lambda value: str(value or '').strip(),
                     get_downloader_services=lambda **kw: {'target': SimpleNamespace(instance=instance)})
    # Execute the unchanged production consumer, isolating its host-only imports.
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), 'exec'), namespace)
    assert namespace['_cleanup_transfer_target'](r.plugin, 'abc', 'source') == 1
    instance.delete_torrents.assert_called_once_with(delete_file=True, ids=['abc'])
    assert r.plugin.get_data('source-abc')['history_hidden']
