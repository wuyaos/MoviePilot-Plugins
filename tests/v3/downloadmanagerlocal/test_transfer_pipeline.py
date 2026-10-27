"""离线运行：micromamba run -n base python -m pytest tests/v3/downloadmanagerlocal/test_transfer_pipeline.py -q

宿主、H&R 与下载器全部替身；不连接 MoviePilot 或真实下载器。
"""

import copy
import importlib.machinery
import importlib.util
import sys
import threading
import time
import types
from pathlib import Path
from unittest.mock import Mock

import pytest

SERVICE = Path(__file__).resolve().parents[3] / 'plugins.v3/downloadmanagerlocal/service'
PREFIX = 'app.plugins.downloadmanagerlocal.service'


@pytest.fixture
def runtime(monkeypatch):
    """隔离加载真实事务及校验模块，仅替换外部边界。"""
    def module(name, **attrs):
        result = types.ModuleType(name)
        # 替身必须带 __spec__：否则测试失败时 pytest 渲染回溯会去
        # importlib.resources.files() 解析父包并抛 INTERNALERROR，真实失败被掩盖。
        result.__spec__ = importlib.machinery.ModuleSpec(
            name, None, is_package="__path__" in attrs
        )
        result.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, result)
        return result

    for name in ('app', 'app.sdk', 'app.plugins', 'app.plugins.downloadmanagerlocal', PREFIX,
                 'app.plugins.downloadmanagerlocal.model', PREFIX + '.hr'):
        module(name, __path__=[])
    module('app.sdk.logging', logger=Mock())
    module('app.plugins.downloadmanagerlocal.model.state', SEED_RECHECK_QUEUE_KEY='queue', record_transfer_success=Mock())
    guard = Mock()
    guard.is_protected.return_value = False
    guard.return_value.is_protected.side_effect = lambda *a, **k: guard.is_protected(*a, **k)
    module(PREFIX + '.hr.guard', HrGuard=guard)
    module(PREFIX + '.transfer', post_transfer_process=Mock(return_value=True))

    # recheck 依赖真实 utils.torrent_adapter（纯 Python，只用到被替身的 app.sdk.logging），
    # 因此这里挂上真实的 utils 包与适配器，而不是再造替身。
    plugin_root = SERVICE.parent
    module(
        'app.plugins.downloadmanagerlocal.utils',
        __path__=[str(plugin_root / 'utils')],
    )
    adapter_spec = importlib.util.spec_from_file_location(
        'app.plugins.downloadmanagerlocal.utils.torrent_adapter',
        plugin_root / 'utils' / 'torrent_adapter.py',
    )
    adapter = importlib.util.module_from_spec(adapter_spec)
    monkeypatch.setitem(sys.modules, adapter_spec.name, adapter)
    adapter_spec.loader.exec_module(adapter)

    def load(name):
        spec = importlib.util.spec_from_file_location(PREFIX + '.' + name, SERVICE / (name + '.py'))
        result = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, spec.name, result)
        spec.loader.exec_module(result)
        return result

    recheck = load('recheck')
    pipeline = load('transfer_pipeline')
    monkeypatch.setattr(pipeline, 'ensure_seed_recheck_worker', Mock())
    source = Mock()
    target = Mock()
    for downloader in (source, target):
        downloader.delete_torrents.return_value = True
        downloader.stop_torrents.return_value = True
        downloader.start_torrents.return_value = True
        downloader.recheck_torrents.return_value = True
    source.get_torrents.return_value = ([{'hash': 'abc', 'state': 'pausedUP'}], None)
    target.get_torrents.return_value = ([{'hash': 'abc', 'state': 'pausedUP'}], None)
    def delete_target(**kwargs):
        target.get_torrents.return_value = ([], None)
        return target.delete_torrents.return_value
    target.delete_torrents.side_effect = delete_target
    services = {
        'source': types.SimpleNamespace(name='source', type='qbittorrent', instance=source),
        'target': types.SimpleNamespace(name='target', type='qbittorrent', instance=target),
    }
    data = {}
    plugin = types.SimpleNamespace(
        _seed_recheck_lock=threading.RLock(), _seed_max_wait_minutes=120,
        _pause_source=True, _deletesource=True, _seed_autostart=True, _seed_skipverify=False,
        _event=threading.Event(), service_info=services.get,
        get_hash=lambda task, kind: task['hash'] if isinstance(task, dict) else task.hashString,
        get_data=lambda key: copy.deepcopy(data.get(key)),
        save_data=lambda key, value: data.__setitem__(key, copy.deepcopy(value)),
    )
    return types.SimpleNamespace(plugin=plugin, pipeline=pipeline, recheck=recheck,
                                 source=source, target=target, services=services, data=data, guard=guard)


def begin(r):
    """登记一个原先正在做种的源任务。"""
    return r.pipeline.begin_transfer(r.plugin, r.services['source'], r.services['target'],
                                     'abc', {'state': 'uploading'}, lambda: 'abc', lambda: False)


def cycle(r, state='pausedUP'):
    """通过真实持久队列推进一步。"""
    r.target.get_torrents.return_value = ([{'hash': 'abc', 'state': state}], None)
    queue = r.recheck.load_seed_recheck_queue(r.plugin)
    r.recheck.process_seed_recheck_once(r.plugin, queue)


def test_registration_never_deletes_source_and_waits_for_active_confirmation(runtime):
    r = runtime
    assert begin(r)
    r.source.delete_torrents.assert_not_called()
    cycle(r)  # 请求校验前的状态不可用于完成判定
    r.target.recheck_torrents.assert_called_once_with(ids=['abc'])
    r.source.delete_torrents.assert_not_called()
    cycle(r, 'checkingUP')
    cycle(r)  # 完整且暂停：发起开始，但不能删源
    r.source.delete_torrents.assert_not_called()
    cycle(r, 'stalledUP')
    r.source.delete_torrents.assert_called_once_with(delete_file=False, ids=['abc'])
    assert r.data['source-abc']['transfer_state'] == 'completed'
    assert r.data['queue'] == {}


@pytest.mark.parametrize('pause_source', [True, False])
def test_pause_source_configuration(runtime, pause_source):
    r = runtime
    r.plugin._pause_source = pause_source
    assert begin(r)
    assert r.source.stop_torrents.call_count == int(pause_source)
    assert r.data['queue']['target::abc']['pause_source'] is pause_source


@pytest.mark.parametrize('active', [True, False])
def test_add_failure_rolls_back_target_before_restoring_original_source(runtime, active):
    r = runtime
    calls = []
    def delete_target(**kwargs):
        calls.append('delete_target')
        r.target.get_torrents.return_value = ([], None)
        return True
    r.target.delete_torrents.side_effect = delete_target
    r.source.start_torrents.side_effect = lambda **kwargs: calls.append('restore_source') or True
    assert not r.pipeline.begin_transfer(
        r.plugin, r.services['source'], r.services['target'], 'abc',
        {'state': 'uploading' if active else 'pausedUP'}, lambda: None, lambda: False,
    )
    cycle(r)
    assert calls == (['delete_target', 'restore_source'] if active else ['delete_target'])
    r.source.delete_torrents.assert_not_called()
    assert r.data['queue'] == {}


def test_failed_target_delete_does_not_resume_source(runtime):
    r = runtime
    begin(r)
    r.target.delete_torrents.return_value = False
    cycle(r, 'error')
    r.source.start_torrents.assert_not_called()
    assert r.data['queue']['target::abc']['phase'] == 'rollback'


def test_timeout_rolls_back_without_deleting_source(runtime):
    r = runtime
    begin(r)
    r.data['queue']['target::abc']['created_at'] = time.time() - 7300
    cycle(r, 'checkingUP')
    r.target.delete_torrents.assert_called_once()
    r.source.start_torrents.assert_called_once()
    r.source.delete_torrents.assert_not_called()


def test_query_failure_is_not_target_missing(runtime):
    r = runtime
    begin(r)
    r.target.get_torrents.return_value = (None, 'offline')
    r.recheck.process_seed_recheck_once(r.plugin, r.recheck.load_seed_recheck_queue(r.plugin))
    r.target.delete_torrents.assert_not_called()
    r.source.start_torrents.assert_not_called()
    assert r.data['queue']


def test_missing_target_restores_source(runtime):
    r = runtime
    begin(r)
    r.target.get_torrents.return_value = ([], None)
    r.recheck.process_seed_recheck_once(r.plugin, r.recheck.load_seed_recheck_queue(r.plugin))
    r.source.start_torrents.assert_called_once()
    r.source.delete_torrents.assert_not_called()
    assert not r.data['queue']


def test_hr_protection_skips_source_delete_and_counts(runtime):
    r = runtime
    r.guard.is_protected.return_value = True
    r.plugin._seed_autostart = False
    begin(r)
    cycle(r)
    cycle(r)
    r.guard.is_protected.assert_called_once_with('source', 'abc')
    r.source.delete_torrents.assert_not_called()
    assert r.data['transfer_skip_stats']['hr_protected'] == 1
    assert r.data['source-abc']['hr_protected']


def test_autostart_false_finishes_after_verified_complete(runtime):
    r = runtime
    r.plugin._seed_autostart = False
    begin(r)
    cycle(r)
    cycle(r)
    r.target.start_torrents.assert_not_called()
    r.source.delete_torrents.assert_called_once()


def test_source_delete_failure_retries_without_rolling_back_target(runtime):
    r = runtime
    r.plugin._seed_autostart = False
    r.source.delete_torrents.return_value = False
    begin(r)
    cycle(r)
    cycle(r)
    assert r.data['queue']['target::abc']['phase'] == 'target_ready'
    r.source.delete_torrents.return_value = True
    cycle(r)
    assert not r.data['queue']
    r.target.delete_torrents.assert_not_called()


def test_reload_uses_persisted_transaction_and_never_readds(runtime):
    r = runtime
    begin(r)
    r.plugin._pause_source = False  # 更改配置不能改变在途事务原状态
    cycle(r)
    cycle(r)
    cycle(r, 'uploading')
    r.target.add_torrent.assert_not_called()
    assert not r.data['queue']


def test_stop_prevents_all_pipeline_writes(runtime):
    r = runtime
    begin(r)
    r.plugin._event.set()
    cycle(r)
    r.target.recheck_torrents.assert_not_called()
    r.source.delete_torrents.assert_not_called()


def test_transmission_requires_complete_and_verifies_even_when_skipverify(runtime):
    r = runtime
    r.services['target'].type = 'transmission'
    r.plugin._seed_skipverify = True
    r.plugin._seed_autostart = False
    begin(r)
    for complete in (0, 0, 1):
        r.target.get_torrents.return_value = ([types.SimpleNamespace(
            hashString='abc', status='stopped', percent_done=complete, error=0)], None)
        r.recheck.process_seed_recheck_once(r.plugin, r.recheck.load_seed_recheck_queue(r.plugin))
        if not complete:
            r.source.delete_torrents.assert_not_called()
    r.target.recheck_torrents.assert_called_once()
    r.source.delete_torrents.assert_called_once()


def test_legacy_unowned_queue_is_not_started(runtime):
    r = runtime
    r.data['queue'] = {'old': {'hash': 'abc', 'downloader': 'target', 'source': 'legacy'}}
    assert not r.recheck.load_seed_recheck_queue(r.plugin)
    r.target.start_torrents.assert_not_called()

def rt_task(complete=1, active=1):
    """构造宿主 rtorrent 模块形态的任务字典（get_torrents 返回 dict）。"""
    return [{'hash': 'abc', 'state': 1 if active else 0, 'is_active': active,
             'complete': complete, 'progress': 100 if complete else 0}]


def rt_cycle(r):
    """按 rt 任务形态推进一步；cycle() 会把目标任务覆盖为 qB 形态字典。"""
    queue = r.recheck.load_seed_recheck_queue(r.plugin)
    r.recheck.process_seed_recheck_once(r.plugin, queue)


def test_rtorrent_target_start_triggers_verification(runtime):
    """rt 目的端无校验 API：启动即触发 rtorrent 自动哈希校验，未完成前不删源。"""
    r = runtime
    r.services['target'].type = 'rtorrent'
    begin(r)
    r.target.get_torrents.return_value = (rt_task(complete=0, active=0), None)
    rt_cycle(r)  # 启动触发校验
    r.target.start_torrents.assert_called_once_with(ids=['abc'])
    r.target.recheck_torrents.assert_not_called()
    r.source.delete_torrents.assert_not_called()
    assert r.data['queue']['target::abc']['phase'] == 'verifying'

    rt_cycle(r)  # 数据未校验完成，一直不确认做种
    r.source.delete_torrents.assert_not_called()


def test_rtorrent_target_completes_after_verification(runtime):
    r = runtime
    r.services['target'].type = 'rtorrent'
    begin(r)
    r.target.get_torrents.return_value = (rt_task(), None)
    rt_cycle(r)
    rt_cycle(r)  # 校验完成且活动：确认做种
    r.source.delete_torrents.assert_called_once_with(delete_file=False, ids=['abc'])
    assert not r.data['queue']


def test_rtorrent_skipverify_starts_without_waiting_for_completion(runtime):
    """跳过校验时 rt 目的端不等校验完成：启动后以活动状态作为做种证据。"""
    r = runtime
    r.services['target'].type = 'rtorrent'
    r.plugin._seed_skipverify = True
    begin(r)
    r.target.get_torrents.return_value = (rt_task(complete=0, active=1), None)
    rt_cycle(r)  # 不触发校验，进入 verifying
    r.target.start_torrents.assert_not_called()
    r.source.delete_torrents.assert_not_called()
    rt_cycle(r)  # 未完成也放行：启动 + 活动状态即确认做种
    r.target.start_torrents.assert_called_once_with(ids=['abc'])
    r.source.delete_torrents.assert_called_once_with(delete_file=False, ids=['abc'])
    assert not r.data['queue']


def test_qbittorrent_skipverify_still_requires_ready_state(runtime):
    """qB 跳过校验靠 skip_checking 自身完成，不会绕过就绪门禁。"""
    r = runtime
    r.plugin._seed_skipverify = True
    begin(r)
    cycle(r)  # pausedUP 仍视为就绪，但不删除源
    r.target.recheck_torrents.assert_not_called()
    r.source.delete_torrents.assert_not_called()
    cycle(r, 'stalledUP')
    r.source.delete_torrents.assert_called_once_with(delete_file=False, ids=['abc'])


def test_rollback_waits_for_target_removal_confirmation(runtime):
    r = runtime
    begin(r)
    r.target.delete_torrents.side_effect = None
    cycle(r, 'error')
    r.target.delete_torrents.assert_called_once()
    r.source.start_torrents.assert_not_called()
    assert r.data['queue']['target::abc']['phase'] == 'rollback'
