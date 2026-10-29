# -*- coding: utf-8 -*-
"""清理记录的服务级契约（报告步骤9/10/11）。

运行：pytest tests/v3/downloadmanagerlocal/test_cleanup_runtime_status.py -q

锁定语义：
1. 自动删种 ``clear_history`` 同时清持久化与内存，清后 API 状态不再显示旧结果；
2. 失败清理 ``clear_history`` 只清最近巡检/即时清理结果，``total`` 累计计数保留；
3. 模块正在运行（run_lock 被占）返回 busy，不做任何清理，handler 转 409；
4. 持久化失败不得改内存、不得返回成功；
5. 没有最近结果时返回 removed=0 —— 不因「状态对象非空」误报；
6. 状态锁可重入：``_record_scan_result`` 内联 ``_record_result`` 不死锁。

桩方案沿用 test_observe_isolation_autoremove.py（真实服务 + 真实 history.py，
扫描器/守卫/通知替身），handler 侧复用 test_cleanup_module_data.py 的夹具。
"""
import importlib.machinery
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import Mock

import pytest

from test_cleanup_module_data import (  # noqa: F401 — 复用 handler 夹具与插件桩
    FakeHTTPException,
    FakePlugin,
    archive,
    cleanup,
)

PLUGIN = Path(__file__).resolve().parents[3] / 'plugins.v3/downloadmanagerlocal'
PREFIX = 'app.plugins.downloadmanagerlocal'
REMOVER_STATE_KEY = 'remover_state'
FAILCLEAN_STATUS_KEY = 'failclean_status'

RECENT_RUN_AT = 1710000000.0


def _module(monkeypatch, name, path=None, **attrs):
    result = types.ModuleType(name)
    result.__spec__ = importlib.machinery.ModuleSpec(name, None, is_package=path is not None)
    if path is not None:
        result.__path__ = [str(path)]
    result.__dict__.update(attrs)
    monkeypatch.setitem(sys.modules, name, result)
    return result


def _load(relpath, name):
    spec = importlib.util.spec_from_file_location(name, PLUGIN / relpath)
    result = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = result
    spec.loader.exec_module(result)
    return result


@pytest.fixture
def autoremove(monkeypatch):
    """加载真实 AutoRemoveService 与真实 history.py；规则/扫描器/守卫用替身。"""
    _module(monkeypatch, 'app')
    _module(monkeypatch, 'app.sdk')
    _module(monkeypatch, 'app.sdk.logging', logger=Mock())
    _module(monkeypatch, 'app.sdk.config', settings=Mock())
    _module(monkeypatch, 'app.schemas')
    _module(monkeypatch, 'app.schemas.types', MessageType=Mock())
    _module(monkeypatch, 'app.modules')
    _module(monkeypatch, 'app.modules.qbittorrent', Qbittorrent=type('Qbittorrent', (), {}))
    _module(monkeypatch, 'app.modules.transmission', Transmission=type('Transmission', (), {}))
    _module(monkeypatch, 'app.plugins')
    _module(monkeypatch, PREFIX, path=PLUGIN)
    _module(monkeypatch, PREFIX + '.modules', path=PLUGIN / 'modules')
    _module(monkeypatch, PREFIX + '.modules.hr', path=PLUGIN / 'modules/hr')
    _module(monkeypatch, PREFIX + '.modules.hr.constants',
            build_hr_config_defaults=Mock(return_value={}))
    _module(monkeypatch, PREFIX + '.modules.hr.guard',
            HrGuard=Mock, SKIP_PATH_AUTO_REMOVE='auto_remove')
    _module(monkeypatch, PREFIX + '.modules.failclean.constants',
            build_failclean_config_defaults=Mock(return_value={}))
    _module(monkeypatch, PREFIX + '.modules.rename.service',
            build_rename_flat_defaults=Mock(return_value={}))
    _module(monkeypatch, PREFIX + '.modules.sitetag.service', DEFAULT_TAG_CONFIG={
        'interval_cron': '0 3 * * *', 'enable_media_tag': False,
        'enable_tag': True, 'enable_category': False, 'enable_del_tags': False,
        'downloaders': [], 'all_cat': [], 'all_cat_rename': [],
        'rename_type': 'movie', 'path_rename': False, 'catprefix': '',
    })
    _module(monkeypatch, PREFIX + '.adapter', path=PLUGIN / 'adapter')
    _module(monkeypatch, PREFIX + '.utils', path=PLUGIN / 'utils')
    _module(monkeypatch, PREFIX + '.utils.torrent_adapter', delete_torrent_with_files=Mock())
    _load('utils/config.py', PREFIX + '.utils.config')

    package = PREFIX + '.modules.autoremove'
    _module(monkeypatch, package, path=PLUGIN / 'modules/autoremove')
    _module(monkeypatch, package + '.rules', parse_remover_config=Mock())
    _module(monkeypatch, package + '.scanner',
            build_snapshot=Mock(), downloader_type=Mock(), read_torrents=Mock(), torrent_hash=Mock())
    _load('modules/autoremove/constants.py', package + '.constants')
    models = _load('modules/autoremove/models.py', package + '.models')
    _load('modules/autoremove/criteria.py', package + '.criteria')
    _load('modules/autoremove/history.py', package + '.history')
    service = _load('modules/autoremove/service.py', package + '.service')
    return types.SimpleNamespace(service=service, models=models)


@pytest.fixture
def failclean(monkeypatch):
    """加载真实 FailCleanService 与真实 history.py；宿主/通知/守卫用替身。"""
    _module(monkeypatch, 'app')
    _module(monkeypatch, 'app.sdk')
    _module(monkeypatch, 'app.sdk.logging', logger=Mock())
    _module(monkeypatch, 'app.schemas')
    _module(monkeypatch, 'app.schemas.types', MessageType=Mock())
    _module(monkeypatch, 'app.plugins')
    _module(monkeypatch, PREFIX, path=PLUGIN)
    _module(monkeypatch, PREFIX + '.modules', path=PLUGIN / 'modules')
    _module(monkeypatch, PREFIX + '.modules.hr', path=PLUGIN / 'modules/hr')
    _module(monkeypatch, PREFIX + '.modules.hr.guard',
            HrGuard=Mock, SKIP_PATH_TRANSFER_FAILURE='transfer_failure')
    _module(monkeypatch, PREFIX + '.utils', path=PLUGIN / 'utils')
    _module(monkeypatch, PREFIX + '.utils.config',
            module_active=Mock(return_value=True), observe_skip=Mock(return_value=False))

    package = PREFIX + '.modules.failclean'
    _module(monkeypatch, package, path=PLUGIN / 'modules/failclean')
    _module(monkeypatch, package + '.notify',
            notify_delete_failure=Mock(), notify_delete_success=Mock(), notify_scan_result=Mock())
    _module(monkeypatch, package + '.hostapi',
            media_extensions=Mock(return_value=set()), local_download_paths=Mock(return_value=[]))
    _load('modules/failclean/constants.py', package + '.constants')
    config = _load('modules/failclean/config.py', package + '.config')
    _load('modules/failclean/history.py', package + '.history')
    service = _load('modules/failclean/service.py', package + '.service')
    return types.SimpleNamespace(service=service, config=config)


def _autoremove_service(autoremove, plugin):
    """构造状态已从持久化恢复的自动删种服务（不触发 init_module 的规则解析）。"""
    service = autoremove.service.AutoRemoveService(plugin)
    service._config = autoremove.models.RemoverConfig()
    service._stopped = False
    service._status = service._load_status()
    return service


def _failclean_service(failclean, plugin):
    """构造状态已从持久化恢复的失败清理服务。"""
    service = failclean.service.FailCleanService(plugin)
    service._config = failclean.config.FailCleanConfig()
    service._stopped = False
    service._status = service._load_status()
    return service


class FailingPlugin(FakePlugin):
    """save_data 直接失败的插件桩，用于验证「保存失败不得改内存」。"""

    def save_data(self, key, value):
        raise RuntimeError('保存失败')


REMOVER_HISTORY = {
    'last_run_at': RECENT_RUN_AT,
    'last_trigger': '定时',
    'deleted': 4,
    'details': [{'downloader': 'QB1', 'deleted': 4}],
    'candidate_list': [{'hash': 'a', 'name': 'seed'}],
}

FAILCLEAN_HISTORY = {
    'last_scan_time': RECENT_RUN_AT,
    'last_scan_trigger': '定时',
    'scan': {'scanned': 4, 'cleaned': 2, 'failed': 0, 'skipped': 1},
    'event': {'deleted': 1, 'failed': 0, 'skipped': 0},
    'total': {'cleaned': 9, 'failed': 2, 'skipped': 3},
}


def test_autoremove_clear_history_syncs_memory_and_disk(autoremove):
    """清记录后：持久化与内存同时归零，API 状态不再显示旧结果。"""
    plugin = FakePlugin({REMOVER_STATE_KEY: dict(REMOVER_HISTORY)})
    service = _autoremove_service(autoremove, plugin)

    assert service.clear_history() == {'removed': 1, 'busy': False}

    assert service.get_module_status()['last_run_at'] == 0.0
    assert service.get_module_status()['deleted'] == 0
    stored = plugin.get_data(REMOVER_STATE_KEY)
    assert stored['last_run_at'] == 0.0 and stored['deleted'] == 0
    assert stored['candidate_list'] == [] and stored['details'] == []


def test_autoremove_clear_history_without_history(autoremove):
    """没有最近结果时返回 0，且不写持久化。"""
    plugin = FakePlugin({})
    service = _autoremove_service(autoremove, plugin)

    assert service.clear_history() == {'removed': 0, 'busy': False}
    assert plugin.get_data(REMOVER_STATE_KEY) is None


def test_autoremove_clear_history_busy_when_running(autoremove):
    """正在执行时返回 busy，不做任何清理（由 handler 转 409）。"""
    plugin = FakePlugin({REMOVER_STATE_KEY: dict(REMOVER_HISTORY)})
    service = _autoremove_service(autoremove, plugin)

    assert service._run_lock.acquire(blocking=False) is True
    try:
        assert service.clear_history() == {'removed': 0, 'busy': True}
    finally:
        service._run_lock.release()
    assert plugin.get_data(REMOVER_STATE_KEY)['last_run_at'] == RECENT_RUN_AT


def test_autoremove_clear_history_save_failure_keeps_memory(autoremove):
    """持久化失败：抛错且内存状态不变，不出现「清完仍显示旧结果」或假成功。"""
    plugin = FailingPlugin({REMOVER_STATE_KEY: dict(REMOVER_HISTORY)})
    service = _autoremove_service(autoremove, plugin)

    with pytest.raises(RuntimeError):
        service.clear_history()
    assert service.get_module_status()['last_run_at'] == RECENT_RUN_AT
    assert service._status['candidate_list'] == [{'hash': 'a', 'name': 'seed'}]


def test_failclean_clear_history_keeps_total(failclean):
    """清最近巡检/即时清理结果，total 累计计数与 H&R 跳过统计保留。"""
    plugin = FakePlugin({FAILCLEAN_STATUS_KEY: dict(FAILCLEAN_HISTORY)})
    service = _failclean_service(failclean, plugin)
    service._recent_deletes['a|/tmp/x'] = RECENT_RUN_AT

    assert service.clear_history() == {'removed': 1, 'busy': False}

    status = service.get_module_status()
    assert status['last_scan_time'] == 0.0 and status['last_scan_trigger'] == ''
    assert status['scan'] == {'scanned': 0, 'cleaned': 0, 'failed': 0, 'skipped': 0}
    assert status['event'] == {'deleted': 0, 'failed': 0, 'skipped': 0}
    assert status['total'] == {'cleaned': 9, 'failed': 2, 'skipped': 3}
    assert plugin.get_data(FAILCLEAN_STATUS_KEY)['total'] == {'cleaned': 9, 'failed': 2, 'skipped': 3}
    assert service._recent_deletes == {'a|/tmp/x': RECENT_RUN_AT}


def test_failclean_clear_history_with_only_total(failclean):
    """只有累计计数、没有最近结果时返回 0（不因状态对象非空误报）。"""
    plugin = FakePlugin({FAILCLEAN_STATUS_KEY: {'total': {'cleaned': 5, 'failed': 1, 'skipped': 0}}})
    service = _failclean_service(failclean, plugin)

    assert service.clear_history() == {'removed': 0, 'busy': False}
    assert plugin.get_data(FAILCLEAN_STATUS_KEY) == {'total': {'cleaned': 5, 'failed': 1, 'skipped': 0}}


def test_failclean_clear_history_busy_and_save_failure(failclean):
    """巡检运行中返回 busy；保存失败抛错且累计计数不变。"""
    plugin = FakePlugin({FAILCLEAN_STATUS_KEY: dict(FAILCLEAN_HISTORY)})
    service = _failclean_service(failclean, plugin)

    assert service._run_lock.acquire(blocking=False) is True
    try:
        assert service.clear_history() == {'removed': 0, 'busy': True}
    finally:
        service._run_lock.release()

    failing = _failclean_service(failclean, FailingPlugin({FAILCLEAN_STATUS_KEY: dict(FAILCLEAN_HISTORY)}))
    with pytest.raises(RuntimeError):
        failing.clear_history()
    assert failing.get_module_status()['last_scan_time'] == RECENT_RUN_AT
    assert failing.get_module_status()['total'] == {'cleaned': 9, 'failed': 2, 'skipped': 3}


def test_failclean_status_lock_is_reentrant(failclean):
    """状态锁可重入：_record_scan_result 内联 _record_result 不死锁且计数落盘。"""
    plugin = FakePlugin({})
    service = _failclean_service(failclean, plugin)

    service._record_scan_result('定时', {'scanned': 2, 'cleaned': 1, 'failed': 0, 'skipped': 1})

    assert service.get_module_status()['last_scan_trigger'] == '定时'
    assert plugin.get_data(FAILCLEAN_STATUS_KEY)['total']['cleaned'] == 1
    assert service.clear_history() == {'removed': 1, 'busy': False}


def test_history_count_ignores_empty_template_and_cumulative_only(autoremove, failclean):
    """数据页计数口径：空模板与「只有累计」都算 0 条可清理记录。"""
    assert autoremove.service.history_removed_count({'last_run_at': 0.0}) == 0
    assert autoremove.service.history_removed_count(autoremove.service._empty_status()) == 0
    assert autoremove.service.history_removed_count({'last_run_at': RECENT_RUN_AT}) == 1
    assert failclean.service.history_removed_count({'total': {'cleaned': 5, 'failed': 0, 'skipped': 0}}) == 0
    assert failclean.service.history_removed_count({'scan': {'cleaned': 1}}) == 1
    assert failclean.service.history_removed_count({'last_scan_time': RECENT_RUN_AT}) == 1


class _BusyService:
    """clear_history 返回固定结果的替身服务。"""

    def __init__(self, outcome):
        self.outcome = outcome
        self.calls = 0

    def clear_history(self):
        self.calls += 1
        return self.outcome


def test_cleanup_handler_reports_busy_as_409(cleanup):
    """服务忙时 handler 转 409，且不写持久化。"""
    plugin = FakePlugin({REMOVER_STATE_KEY: {'last_run_at': RECENT_RUN_AT}})
    plugin._autoremove_service = _BusyService({'removed': 0, 'busy': True})
    plugin._failclean_service = _BusyService({'removed': 0, 'busy': True})
    actions = cleanup._cleanup_actions(plugin)

    for module in ('autoremove_state', 'failclean_state'):
        with pytest.raises(FakeHTTPException) as excinfo:
            actions[module]()
        assert excinfo.value.status_code == 409
    assert plugin.get_data(REMOVER_STATE_KEY) == {'last_run_at': RECENT_RUN_AT}


def test_cleanup_handler_prefers_service_result(cleanup):
    """服务在用时以服务返回为准，不再由 handler 直接读写持久化。"""
    plugin = FakePlugin({REMOVER_STATE_KEY: {'last_run_at': RECENT_RUN_AT}})
    service = _BusyService({'removed': 3, 'busy': False})
    plugin._autoremove_service = service
    actions = cleanup._cleanup_actions(plugin)

    assert actions['autoremove_state']() == 3
    assert service.calls == 1
    assert plugin.get_data(REMOVER_STATE_KEY) == {'last_run_at': RECENT_RUN_AT}
