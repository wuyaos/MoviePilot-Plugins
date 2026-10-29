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

SERVICE = Path(__file__).resolve().parents[3] / 'plugins.v3/downloadmanagerlocal/modules/transfer'
PREFIX = 'app.plugins.downloadmanagerlocal.modules.transfer'


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
                 'app.plugins.downloadmanagerlocal.model', 'app.plugins.downloadmanagerlocal.modules.hr'):
        module(name, __path__=[])
    module('app.sdk.logging', logger=Mock())
    module('app.plugins.downloadmanagerlocal.model.state', SEED_RECHECK_QUEUE_KEY='queue', record_transfer_success=Mock())
    guard = Mock()
    guard.is_protected.return_value = False
    guard.return_value.is_protected.side_effect = lambda *a, **k: guard.is_protected(*a, **k)
    guard.return_value.should_skip.side_effect = lambda path, dl, h: guard.is_protected(dl, h)
    guard.return_value.unconfirmed = False
    module('app.plugins.downloadmanagerlocal.modules.hr.guard',
           HrGuard=guard, SKIP_PATH_TRANSFER_SOURCE='transfer_source')
    module(PREFIX + '.service', post_transfer_process=Mock(return_value=True))

    # recheck 依赖真实 utils.torrent_adapter（纯 Python，只用到被替身的 app.sdk.logging），
    # 因此这里挂上真实的 utils 包与适配器，而不是再造替身。
    plugin_root = SERVICE.parent.parent
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
    pipeline = load('pipeline')
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



def _rt_cycle(r, attrs):
    """以给定 rt 属性推进一步真实持久队列。"""
    row = {'hash': 'abc', **attrs}
    r.target.get_torrents.return_value = ([row], None)
    queue = r.recheck.load_seed_recheck_queue(r.plugin)
    r.recheck.process_seed_recheck_once(r.plugin, queue)


def test_autostart_false_rt_skipverify_incomplete_never_deletes_source(runtime):
    """rt + 跳过校验 + 自动开始关：没有完整度证据时**不得**删源。

    覆盖一个真实缺口：rt 无可信校验，上面那次 seed_is_ready 会被 skipverify 旁路；
    若自动开始也关着，活动证据同样不可用——不兜住就是「零证据删源」。
    """
    r = runtime
    r.plugin._seed_autostart = False
    r.plugin._seed_skipverify = True
    r.services['target'].type = 'rtorrent'
    assert begin(r)
    # rt 报告未完成（complete=0）且不在活动状态：这是「数据未确认完整」
    for _ in range(3):
        _rt_cycle(r, {'state': 0, 'complete': 0, 'progress': 0})
    r.source.delete_torrents.assert_not_called()
    assert r.data['source-abc']['transfer_state'] != 'completed'


def test_autostart_false_rt_skipverify_complete_deletes_source(runtime):
    """同组合但 rt 报告完整：完整度成立，允许删源。"""
    r = runtime
    r.plugin._seed_autostart = False
    r.plugin._seed_skipverify = True
    r.services['target'].type = 'rtorrent'
    assert begin(r)
    for _ in range(3):
        _rt_cycle(r, {'state': 1, 'complete': 1, 'progress': 100})
        if r.source.delete_torrents.called:
            break
    r.source.delete_torrents.assert_called_once_with(delete_file=False, ids=['abc'])

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


# ── 失败次数上限（v3.9.6）：连续失败 3 次后放弃，手动触发重置 ─────────────────

@pytest.mark.parametrize('attempts, state, manual, expected', [
    (0, 'failed', False, False),        # 刚失败一次但未到上限
    (2, 'failed', False, False),        # 还差一次
    (3, 'failed', False, True),         # 达上限 → 放弃
    (5, 'failed', False, True),         # 超过上限（旧数据）→ 仍放弃
    (3, 'rolled_back', False, False),   # 有计数但非终态 → 不放弃（可能还在回滚）
    (3, 'failed', True, False),         # 手动触发 → 放行并重置
    (0, '', False, False),              # 无历史
])
def test_abandon_gate(runtime, attempts, state, manual, expected):
    """已放弃判据：需同时满足「终态 failed」与「计数达上限」，手动触发永远放行。"""
    previous = {'attempts': attempts, 'transfer_state': state}
    assert runtime.pipeline.transfer_is_abandoned(previous, manual) is expected


def test_rollback_attempts_accumulate_across_rounds_then_cap_marks_failed(runtime):
    """每次回滚完成累加一次失败；到上限置终态 failed 并跳出待办队列。"""
    r = runtime
    for round_no in (1, 2):
        assert not r.pipeline.begin_transfer(
            r.plugin, r.services['source'], r.services['target'], 'abc',
            {'state': 'uploading'}, lambda: None, lambda: False,
        )
        cycle(r)
        record = r.plugin.get_data('source-abc')
        assert record['attempts'] == round_no
        assert record['transfer_state'] == 'rolled_back'
        assert r.data['queue'] == {}, '回滚完成后不应留在待办队列'

    # 第 3 次：达上限 → 终态 failed（不是 rolled_back）
    assert not r.pipeline.begin_transfer(
        r.plugin, r.services['source'], r.services['target'], 'abc',
        {'state': 'uploading'}, lambda: None, lambda: False,
    )
    cycle(r)
    record = r.plugin.get_data('source-abc')
    assert record['attempts'] == 3
    assert record['transfer_state'] == 'failed'
    assert r.data['queue'] == {}
    assert r.pipeline.transfer_is_abandoned(record, manual=False)
    assert not r.pipeline.transfer_is_abandoned(record, manual=True), '手动触发必须能救回来'


# ── 转移记录名称（P7-2c 需求④）：随事务保存源种子名，供数据页展示 ─────────────

def begin_with(r, torrent, attempts=None):
    """以指定源种子快照登记转移（校验随事务落盘的展示字段）。"""
    return r.pipeline.begin_transfer(
        r.plugin, r.services['source'], r.services['target'], 'abc', torrent,
        lambda: 'abc', lambda: False, attempts=attempts,
    )


@pytest.mark.parametrize('torrent, expected', [
    ({'state': 'uploading', 'name': '示例.种子.mkv'}, '示例.种子.mkv'),          # qB dict
    ({'state': 'uploading', 'torrentName': 'camelName.mkv'}, 'camelName.mkv'),  # camelCase
    ({'state': 'uploading'}, ''),                                              # 无名称 → 空串
])
def test_source_name_recorded_from_torrent_snapshot(runtime, torrent, expected):
    """名称字段兼容 dict 与 camelCase，缺失时为空串且登记照常成功。

    对象形态（TR）不在 pipeline 层覆盖：`is_torrent_active` 的 qbittorrent 分支只接受
    dict，对象种子在该类型下本就不可达；`get_torrent_name` 读对象由
    test_torrent_field_shapes.py::test_get_torrent_name_accepts_dict_and_object 覆盖。
    """
    r = runtime
    assert begin_with(r, torrent)
    assert r.data['source-abc']['source_name'] == expected
    assert r.data['queue']['target::abc']['source_name'] == expected


def test_source_name_survives_reload_and_verify_complete(runtime):
    """字段随来源记录与待办队列落盘，重载后仍可读，校验完成后不丢失。"""
    r = runtime
    assert begin_with(r, {'state': 'uploading', 'name': '持久名.mkv'})
    reloaded = r.recheck.load_seed_recheck_queue(r.plugin)
    assert reloaded['target::abc']['source_name'] == '持久名.mkv'
    cycle(r)
    cycle(r, 'checkingUP')
    cycle(r)
    cycle(r, 'stalledUP')
    assert r.data['source-abc']['transfer_state'] == 'completed'
    assert r.data['source-abc']['source_name'] == '持久名.mkv'


def test_source_name_survives_rollback(runtime):
    """回滚与终态重写都复用同一 item，展示字段不能被回滚路径擦掉。"""
    r = runtime
    assert not r.pipeline.begin_transfer(
        r.plugin, r.services['source'], r.services['target'], 'abc',
        {'state': 'uploading', 'name': '回滚名.mkv'}, lambda: None, lambda: False,
    )
    assert r.data['queue']['target::abc']['phase'] == 'rollback'
    assert r.data['queue']['target::abc']['source_name'] == '回滚名.mkv'
    cycle(r)
    assert r.data['source-abc']['transfer_state'] == 'rolled_back'
    assert r.data['source-abc']['source_name'] == '回滚名.mkv'
