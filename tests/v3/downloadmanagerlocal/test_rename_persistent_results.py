"""P5-b：真实逐条结果、清展示与重试安全状态的行为回归。"""

import copy
import sys
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from test_rename_idempotent import mods, PREFIX
from test_manual_run_endpoints import endpoints


class Plugin:
    def __init__(self, data=None):
        self.data = copy.deepcopy(data or {})
        self.writes = []

    def get_data(self, key):
        return copy.deepcopy(self.data.get(key))

    def save_data(self, key, value):
        self.data[key] = copy.deepcopy(value)
        self.writes.append(key)


@pytest.fixture
def env(mods):
    archive = sys.modules[PREFIX + '.modules.rename.archive']
    plugin = Plugin()
    plugin.is_rename_archived = lambda h: archive.is_rename_archived(plugin, h)
    plugin.record_rename_failure = lambda *a, **kw: archive.record_rename_failure(plugin, *a, **kw)
    plugin.clear_rename_retry_state = lambda h: archive.clear_rename_retry_state(plugin, h)
    return SimpleNamespace(rename=mods.rename, archive=archive, plugin=plugin)


def test_today_results_persist_reload_and_roll_over_without_history_inference(env, monkeypatch):
    a, r, p = env.archive, env.rename, env.plugin
    class Day(date):
        value = date(2026, 1, 1)
        @classmethod
        def today(cls):
            return cls.value
    monkeypatch.setattr(a, 'date', Day)
    r.save_rename_record(p, 'ok', 'Original', 'New', True)
    r.save_rename_record(p, 'fail', 'Original', 'Original', False, '媒体识别失败')
    # 汇总不重复记逐条结果；历史更新时间也不改变今日值。
    r.record_rename_module_result(p, 'cron', 30, 40, 0)
    reloaded = Plugin(p.data)
    assert r.get_module_status(reloaded)['today_success'] == 1
    assert r.get_module_status(reloaded)['today_failed'] == 1
    assert reloaded.writes == []
    Day.value = date(2026, 1, 2)
    assert r.get_module_status(reloaded)['today_success'] == 0
    assert r.get_module_status(reloaded)['today_failed'] == 0
    a.record_daily_result(reloaded, False)
    assert a.today_stats(Plugin(reloaded.data)) == {'date': '2026-01-02', 'today_success': 0, 'today_failed': 1}


def test_old_history_is_not_a_daily_counter(env):
    p = Plugin({'rename_records': {'x': {'success': True, 'time': date.today().isoformat()}}})
    assert env.rename.get_module_status(p)['today_success'] == 0
    assert p.writes == []


@pytest.mark.parametrize('count', [1000, 1001])
def test_archive_capacity_reload_keeps_excluded_objects(env, count):
    a = env.archive
    state = {f'h{i:04}': {'archived': True, 'fail_count': 3, 'archived_at': f'2026-01-01 {i:05}'} for i in range(count)}
    p = Plugin({a.RETRY_STATE_KEY: state})
    page = a.list_rename_archive(p, 1, 1001)
    assert page['total'] == 1000
    assert page['items'][0]['hash'] == f'h{count-1:04}'
    reloaded = Plugin(p.data)
    assert a.list_rename_archive(reloaded, 1, 1001) == page
    assert len(reloaded.data[a.RETRY_STATE_KEY]) == count
    assert a.is_rename_archived(reloaded, 'h0000') is True
    if count == 1001:
        assert reloaded.data[a.RETRY_STATE_KEY]['h0000']['display_hidden'] is True


def test_missing_and_equal_times_stable_independent_of_insertion_order(env):
    a = env.archive
    items = [('z', {'archived': True}), ('b', {'archived': True, 'archived_at': '2026-01-01'}),
             ('a', {'archived': True, 'archived_at': '2026-01-01'}), ('y', {'archived': True})]
    for pairs in (items, list(reversed(items))):
        p = Plugin({a.RETRY_STATE_KEY: dict(pairs)})
        assert [i['hash'] for i in a.list_rename_archive(p)['items']] == ['a', 'b', 'y', 'z']


@pytest.mark.parametrize('clear', [False, True])
def test_archive_delete_and_clear_never_requeue_until_restore(env, clear):
    a, r, p = env.archive, env.rename, env.plugin
    r.save_rename_record(p, 'failed', 'Original', 'Original', False, '媒体识别失败')
    a.record_rename_failure(p, 'failed', 'Original', threshold=1)
    assert r.get_failed_rename_hashes(p) == set()
    result = a.clear_rename_archive(p) if clear else a.delete_rename_archive(p, 'failed')
    assert result['code'] == 0
    assert a.list_rename_archive(p)['total'] == 0
    reloaded = Plugin(p.data)
    reloaded.is_rename_archived = lambda h: a.is_rename_archived(reloaded, h)
    assert r.get_failed_rename_hashes(reloaded) == set()
    assert a.restore_rename_archive(reloaded, 'failed')['code'] == 0
    assert r.get_failed_rename_hashes(reloaded) == {'failed'}
    assert reloaded.data['rename_records']['failed']['original_name'] == 'Original'


def test_history_hide_keeps_retry_and_original_name(env):
    a, r, p = env.archive, env.rename, env.plugin
    r.save_rename_record(p, 'failed', 'Original', 'Original', False, '媒体识别失败')
    r.save_rename_record(p, 'ok', 'Original OK', 'New', True)
    retry_before = copy.deepcopy(p.data[a.RETRY_STATE_KEY])
    assert a.hide_rename_history(p) == 2
    assert a.hide_rename_history(p) == 0
    assert r.get_failed_rename_hashes(p) == {'failed'}
    assert p.data[a.RETRY_STATE_KEY] == retry_before
    assert p.data['rename_records']['ok']['original_name'] == 'Original OK'


def test_batch_saves_each_state_once_and_preserves_real_results_on_error(env):
    a, r, p = env.archive, env.rename, env.plugin
    @a.rename_write_batch
    def run(plugin):
        for i in range(10):
            r.save_rename_record(plugin, str(i), 'Original', 'New', i % 2 == 0, 'API失败')
        raise RuntimeError('stop')
    with pytest.raises(RuntimeError, match='stop'):
        run(p)
    assert len(p.data['rename_records']) == 10
    assert a.today_stats(p)['today_success'] == 5
    assert a.today_stats(p)['today_failed'] == 5
    assert len(p.writes) == len(set(p.writes)) == 3


def test_deleted_history_can_still_restore_name_through_handler(endpoints, monkeypatch):
    h = endpoints.handlers
    p = Plugin({'rename_records': {'ok': {'success': True, 'original_name': 'Original',
                                         'after_name': 'New', 'downloader': 'QB'}}})
    p._todownloader = 'QB'
    monkeypatch.setattr(h, '_require_module', lambda *args: None)
    monkeypatch.setattr(h, 'observe_skip', lambda *args: False)
    dl = Mock()
    monkeypatch.setattr(h, 'resolve_record_downloader', lambda *args: {
        'ambiguous': False, 'service': SimpleNamespace(instance=dl, type='qbittorrent', name='QB')})
    h.api_delete_rename_history(p, hash='ok')
    assert h.api_rename_history(p)['total'] == 0
    result = h.api_recovery_torrent(p, hash='ok')
    assert result.success is True
    dl.qbc.torrents_rename.assert_called_once_with(torrent_hash='ok', new_torrent_name='Original')
    assert p.data['rename_records']['ok']['original_name'] == 'Original'


def test_real_scan_batches_results_and_repeated_callback_does_not_count_success(env, monkeypatch):
    a, r, p = env.archive, env.rename, env.plugin
    config = SimpleNamespace(observe_skip=lambda *args: False)
    monkeypatch.setitem(sys.modules, PREFIX + '.utils.config', config)
    monkeypatch.setattr(r, 'MetaInfo', lambda title: SimpleNamespace(title=title))
    monkeypatch.setattr(r, 'format_torrent_name', lambda template, meta, media: 'New ' + meta.title)
    monkeypatch.setattr(r, 'notify_rename_result', lambda *args: False)
    p._rename_config = {'enabled': True, 'downloader': ['QB']}
    p._rename_exclude_dirs = ''
    p._rename_movie_format = p._rename_tv_format = 'template'
    p.chain = SimpleNamespace(recognize_media=lambda **kwargs: SimpleNamespace(type=r.MediaType.MOVIE))
    dl = Mock()
    dl.get_torrents.return_value = ([{'hash': 'one', 'name': 'Original', 'save_path': '/data'},
                                    {'hash': 'two', 'name': 'Other', 'save_path': '/data'}], None)
    service = SimpleNamespace(name='QB', type='qbittorrent', instance=dl)
    p.service_info = lambda name: service
    first = r.scan_renames(p)
    assert first['renamed'] == 2 and first['failed'] == 0
    assert dl.qbc.torrents_rename.call_count == 2
    assert p.writes.count('rename_records') == 1
    assert p.writes.count(a.DAILY_STATS_KEY) == 1
    # 重复事件读取下载器当前新名，幂等守卫必须不再调用下载器或累加。
    repeated = r.rename_candidate(p, service, r.build_rename_config(p._rename_config),
                                  {'hash': 'one', 'name': 'New Original', 'save_path': '/data'})
    assert repeated == 'skipped'
    assert dl.qbc.torrents_rename.call_count == 2
    assert a.today_stats(Plugin(p.data))['today_success'] == 2
    second = r.scan_renames(p)
    assert second['renamed'] == 0 and second['skipped'] == 2
    assert a.today_stats(p)['today_success'] == 2


def test_archive_new_failure_trims_only_old_display_and_ties_are_stable(env, monkeypatch):
    a, p = env.archive, env.plugin
    state = {f'h{i:04}': {'archived': True, 'fail_count': 3} for i in reversed(range(1000))}
    p.data[a.RETRY_STATE_KEY] = state
    monkeypatch.setattr(a, 'now_text', lambda: '2026-01-01 00:00:00')
    a.record_rename_failure(p, 'new', 'Original', threshold=1)
    assert a.list_rename_archive(p, 1, 1001)['total'] == 1000
    visible = a.list_rename_archive(Plugin(p.data), 1, 1001)['items']
    assert visible[0]['hash'] == 'new'
    assert visible[-1]['hash'] == 'h0998'
    assert p.data[a.RETRY_STATE_KEY]['h0999']['display_hidden'] is True
    assert a.is_rename_archived(p, 'h0999') is True
    assert p.data[a.RETRY_STATE_KEY]['h0999']['fail_count'] == 3


def test_existing_status_handler_projects_persisted_daily_counts_read_only(env, endpoints, monkeypatch):
    monkeypatch.setitem(sys.modules, PREFIX + '.modules.rename.service', env.rename)
    p, a = env.plugin, env.archive
    a.record_daily_result(p, True)
    a.record_daily_result(p, False)
    reloaded = Plugin(p.data)
    result = endpoints.handlers.api_rename_status(reloaded)
    assert result.status['today_success'] == result.status['today_failed'] == 1
    assert reloaded.writes == []


def test_history_cleanup_waits_for_batch_and_preserves_results(env):
    import threading
    a, r, p = env.archive, env.rename, env.plugin
    started, release, cleanup_started, cleaned = [threading.Event() for _ in range(4)]
    errors = []
    @a.rename_write_batch
    def batch(plugin):
        r.save_rename_record(plugin, 'ok', 'Original', 'New', True)
        started.set()
        assert release.wait(3)
    def run_batch():
        try:
            batch(p)
        except Exception as err:
            errors.append(err)
    def cleanup():
        cleanup_started.set()
        try:
            assert a.hide_rename_history(p) == 1
        except Exception as err:
            errors.append(err)
        finally:
            cleaned.set()
    worker = threading.Thread(target=run_batch)
    cleaner = threading.Thread(target=cleanup)
    worker.start()
    try:
        assert started.wait(3)
        cleaner.start()
        assert cleanup_started.wait(3)
        assert not cleaned.wait(0.05)
    finally:
        release.set()
        worker.join(3)
        if cleaner.ident is not None:
            cleaner.join(3)
    assert not worker.is_alive() and not cleaner.is_alive()
    assert not errors
    assert p.data['rename_records']['ok']['history_hidden'] is True
    assert p.data['rename_records']['ok']['original_name'] == 'Original'
    assert a.today_stats(Plugin(p.data))['today_success'] == 1
