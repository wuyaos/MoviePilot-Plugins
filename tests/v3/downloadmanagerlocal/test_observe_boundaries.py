"""观察模式（阶段三）写边界测试：失败清理删文件、H&R 打标 / 移除标签。

运行：micromamba run -n base python -X utf8 -m pytest tests/v3/downloadmanagerlocal/test_observe_boundaries.py -q

宿主（app / 下载器 / H&R guard / 通知）全部替身；加载真实的 `utils/config.py`、
`modules/failclean/service.py` 与 `modules/hr/service.py`，锁定三条语义：

1. 观察模式下失败清理不删源文件、不删下载历史，返回 skipped 结果（不计入成功数）；
2. 观察模式下 H&R 不打标、不移除标签，但纳管与跟踪状态照常维护；
3. 未开启观察时守卫不误拦（原有写路径照常执行）。
"""

import importlib.machinery
import importlib.util
import sys
import types
from pathlib import Path
from threading import Lock, RLock
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

PLUGIN = Path(__file__).resolve().parents[3] / 'plugins.v3/downloadmanagerlocal'
PREFIX = 'app.plugins.downloadmanagerlocal'


def _module(monkeypatch, name, **attrs):
    """注册带 __spec__ 的模块替身（pytest 断言重写要求 spec 非 None）。"""
    path = attrs.pop('__path__', None)
    module = types.ModuleType(name)
    module.__spec__ = importlib.machinery.ModuleSpec(name, None, is_package=path is not None)
    if path is not None:
        module.__path__ = path
    module.__dict__.update(attrs)
    monkeypatch.setitem(sys.modules, name, module)
    return module


class _FakeHrTaskType:
    """H&R 任务类型替身：只需支持中文标签。"""

    def __init__(self, label):
        self.label = label

    def to_chinese(self):
        return self.label


class _FakeHrTask:
    """H&R 任务替身：只保留纳管流程用到的字段与标识。"""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.hash = str(kwargs.get('hash') or '')
        self.downloader = str(kwargs.get('downloader') or '')
        self.site_name = str(kwargs.get('site_name') or '')
        self.hr_deadline_days = int(kwargs.get('hr_deadline_days') or 0)

    @property
    def key(self):
        return f'{self.downloader}:{self.hash}'

    @property
    def identifier(self):
        return self.key

    def required_hours(self):
        return 0.0


@pytest.fixture
def boundaries(monkeypatch):
    """加载真实 failclean / hr 服务与真实观察模式解析器，返回替身与模块句柄。"""
    _module(monkeypatch, 'app')
    _module(monkeypatch, 'app.sdk')
    _module(monkeypatch, 'app.sdk.logging', logger=Mock())
    _module(monkeypatch, PREFIX, __path__=[str(PLUGIN)])
    _module(monkeypatch, PREFIX + '.utils', __path__=[str(PLUGIN / 'utils')])
    _module(monkeypatch, PREFIX + '.model', __path__=[str(PLUGIN / 'model')])
    _module(monkeypatch, PREFIX + '.model.state', RENAME_RECORDS_KEY='rename_records')
    _module(monkeypatch, PREFIX + '.modules', __path__=[str(PLUGIN / 'modules')])

    # utils/config.py 的默认值来源：本测试不加载各模块实现
    _module(
        monkeypatch,
        PREFIX + '.modules.autoremove.constants',
        MIGRATION_OBSERVE_ONLY_KEY='migration_observe_only',
        build_remover_config_defaults=Mock(return_value={}),
    )
    _module(
        monkeypatch,
        PREFIX + '.modules.rename.service',
        build_rename_flat_defaults=Mock(return_value={}),
    )
    _module(
        monkeypatch,
        PREFIX + '.modules.sitetag.service',
        DEFAULT_TAG_CONFIG={
            'interval_cron': '0 3 * * *',
            'enable_media_tag': False,
            'enable_tag': True,
            'enable_category': False,
            'enable_del_tags': False,
            'downloaders': [],
            'all_cat': [],
            'all_cat_rename': [],
            'rename_type': 'movie',
            'path_rename': False,
            'catprefix': '',
        },
    )

    # ---- failclean 依赖替身 ----
    failclean_constants = _module(
        monkeypatch,
        PREFIX + '.modules.failclean.constants',
        FAILCLEAN_LOG_PREFIX='【PT下载中心:整理失败清理】',
        FAILCLEAN_NOTIFY_PREVIEW_LIMIT=5,
        FAILCLEAN_RECENT_WINDOW_SECONDS=30,
        FAILCLEAN_SCAN_TRIGGER='重复下载残留巡检',
        FAILCLEAN_STATUS_DATA_KEY='failclean_status',
        FAILCLEAN_TRANSFER_FAILED_TRIGGER='整理失败',
        build_failclean_config_defaults=Mock(return_value={}),
    )
    failclean_host = _module(
        monkeypatch,
        PREFIX + '.modules.failclean.hostapi',
        media_extensions=Mock(return_value={'.mkv'}),
        local_download_paths=Mock(return_value=[]),
        delete_media_file=Mock(return_value=True),
        delete_download_history_file=Mock(),
        send_download_file_deleted=Mock(),
    )
    _module(
        monkeypatch,
        PREFIX + '.modules.failclean.config',
        FailCleanConfig=type('FailCleanConfig', (), {}),
        parse_failclean_config=Mock(return_value=SimpleNamespace()),
    )
    _module(
        monkeypatch,
        PREFIX + '.modules.failclean.notify',
        notify_delete_failure=Mock(),
        notify_delete_success=Mock(),
        notify_scan_result=Mock(),
    )
    _module(monkeypatch, PREFIX + '.modules.failclean', __path__=[str(PLUGIN / 'modules/failclean')])

    # ---- hr 依赖替身 ----
    hr_constants = _module(
        monkeypatch,
        PREFIX + '.modules.hr.constants',
        HR_LOG_PREFIX='【PT下载中心:H&R】',
        HR_TASKS_DATA_KEY='hr_tasks',
        build_hr_config_defaults=Mock(return_value={}),
    )
    hr_status = SimpleNamespace(
        PENDING='pending',
        IN_PROGRESS='in_progress',
        COMPLIANT='compliant',
        NEEDS_SEEDING='needs_seeding',
        OVERDUE='overdue',
    )
    hr_task_type = SimpleNamespace(NORMAL=_FakeHrTaskType('普通'), DISCOVERY=_FakeHrTaskType('自动发现'))
    hr_guard = _module(
        monkeypatch,
        PREFIX + '.modules.hr.guard',
        SKIP_PATH_TRANSFER_FAILURE='transfer_failure',
        SKIP_PATH_AUTO_REMOVE='auto_remove',
        HrGuard=lambda: Mock(should_skip=Mock(return_value=False), get_skip_stats=Mock(return_value={})),
        get_guard=Mock(),
    )
    hr_scanner = _module(
        monkeypatch,
        PREFIX + '.modules.hr.scanner',
        HrTorrentSnapshot=type('HrTorrentSnapshot', (), {}),
        apply_snapshot=Mock(),
        downloader_services=Mock(return_value={}),
        downloader_type=Mock(return_value='qbittorrent'),
        is_excluded=Mock(return_value=(False, '')),
        read_torrents=Mock(return_value=([], None)),
        remove_hr_tag=Mock(),
        resolve_site=Mock(return_value=('site1', 'Site1')),
        set_hr_tag=Mock(),
        torrent_snapshot=Mock(),
    )
    _module(
        monkeypatch,
        PREFIX + '.modules.hr.models',
        HrConfig=type('HrConfig', (), {}),
        HrStatus=hr_status,
        HrTask=_FakeHrTask,
        HrTaskType=hr_task_type,
        hr_task_key=lambda downloader, torrent_hash: f'{downloader}:{torrent_hash}',
    )
    _module(
        monkeypatch,
        PREFIX + '.modules.hr.evaluator',
        evaluate_task=Mock(),
        initialize_requirements=Mock(),
        seeding_progress=Mock(),
    )
    _module(
        monkeypatch,
        PREFIX + '.modules.hr.cleanup',
        auto_cleanup=Mock(),
    )
    _module(
        monkeypatch,
        PREFIX + '.modules.hr.notify',
        record_task_event=Mock(),
        send_summary=Mock(),
    )
    _module(
        monkeypatch,
        PREFIX + '.modules.hr.rules',
        parse_hr_config=Mock(return_value=SimpleNamespace()),
    )
    _module(monkeypatch, PREFIX + '.modules.hr', __path__=[str(PLUGIN / 'modules/hr')])

    def load(relpath, name, package):
        spec = importlib.util.spec_from_file_location(package + name, PLUGIN / relpath)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    config_module = load('utils/config.py', '.config', PREFIX + '.utils')
    failclean_module = load('modules/failclean/service.py', '.service', PREFIX + '.modules.failclean')
    hr_module = load('modules/hr/service.py', '.service', PREFIX + '.modules.hr')
    return SimpleNamespace(
        utils=config_module,
        failclean=failclean_module.FailCleanService,
        hr=hr_module.HrService,
        failclean_host=failclean_host,
        hr_scanner=hr_scanner,
        hr_guard=hr_guard,
        failclean_constants=failclean_constants,
        hr_constants=hr_constants,
    )


def _plugin(observe: bool):
    """构造带观察模式快照的插件替身。"""
    return SimpleNamespace(
        _module_observe_only={
            'transfer': False,
            'rename': False,
            'tag': False,
            'hr': observe,
            'autoremove': False,
            'failclean': observe,
            'upload_limit': False,
        },
    )


def _failclean_service(boundaries, observe: bool):
    service = boundaries.failclean.__new__(boundaries.failclean)
    service._plugin = _plugin(observe)
    service._config = SimpleNamespace(enabled=True, notify=False, retain_hours=6)
    service._guard = Mock(should_skip=Mock(return_value=False))
    service._recent_deletes = {}
    service._lock = Lock()
    service._run_lock = RLock()
    service._stopped = False
    return service


def _hr_service(boundaries, observe: bool):
    service = boundaries.hr.__new__(boundaries.hr)
    service._plugin = _plugin(observe)
    service._config = SimpleNamespace(
        enabled=True,
        downloaders=[],
        hit_and_run_tag='HR',
        exclude_tags=[],
        exclude_categories=[],
        site_in_scope=lambda name: True,
        get_site_rule=lambda name: SimpleNamespace(hr_active=True),
        site_rules={},
    )
    service._tasks = {}
    service._lock = RLock()
    service._save_tasks = lambda: None
    service._refresh_guard = lambda: None
    service._tracker_mappings = lambda: {}
    return service


def _hr_snapshot(boundaries):
    """让纳管流程拿到一个命中 H&R 的种子快照。"""
    boundaries.hr_scanner.downloader_services.return_value = {'QB1': Mock()}
    boundaries.hr_scanner.read_torrents.return_value = ([Mock()], None)
    boundaries.hr_scanner.torrent_snapshot.return_value = SimpleNamespace(
        torrent_hash='hash1',
        trackers=[],
        tags=[],
        title='测试种子',
        size=1.0,
        added_on=1.0,
    )
    boundaries.hr_scanner.set_hr_tag.reset_mock()
    boundaries.hr_scanner.remove_hr_tag.reset_mock()


def test_observe_blocks_failclean_delete(boundaries):
    """观察模式下失败清理不删文件、不删历史，返回 skipped（不计成功数、不消耗失败重试）。"""
    service = _failclean_service(boundaries, observe=True)

    result = service._delete_source_file(
        fileitem=Mock(),
        path='/downloads/影视/剧集/未整理.mkv',
        downloader_id='QB1',
        download_hash='hash1',
        reason='整理失败',
        send_notify=False,
    )

    assert result['deleted'] == 0
    assert result['history_deleted'] is False
    assert result['skipped'] is True
    assert boundaries.failclean_host.delete_media_file.call_count == 0
    assert boundaries.failclean_host.delete_download_history_file.call_count == 0
    assert boundaries.failclean_host.send_download_file_deleted.call_count == 0
    previews = boundaries.utils.observe_previews(service._plugin)
    assert previews['failclean']['count'] == 1
    assert '未整理.mkv' in previews['failclean']['samples'][0]


def test_failclean_delete_runs_when_observe_disabled(boundaries):
    """未开启观察时守卫不误拦：源文件与下载历史照常删除。"""
    service = _failclean_service(boundaries, observe=False)

    result = service._delete_source_file(
        fileitem=Mock(),
        path='/downloads/影视/剧集/未整理.mkv',
        downloader_id='QB1',
        download_hash='hash2',
        reason='整理失败',
        send_notify=False,
    )

    assert result['deleted'] == 1
    assert result['skipped'] is False
    assert boundaries.failclean_host.delete_media_file.call_count == 1
    assert boundaries.failclean_host.delete_download_history_file.call_count == 1
    assert boundaries.utils.observe_previews(service._plugin) == {}


def test_observe_blocks_hr_tag_writes(boundaries):
    """观察模式下 H&R 不打标、不移除标签，但纳管与任务跟踪照常维护。"""
    _hr_snapshot(boundaries)
    service = _hr_service(boundaries, observe=True)

    assert service.register_task('QB1', 'hash1') is True
    assert boundaries.hr_scanner.set_hr_tag.call_count == 0
    assert 'QB1:hash1' in service._tasks

    task = service._tasks['QB1:hash1']
    service._remove_tag(task, {'QB1': Mock()})
    assert boundaries.hr_scanner.remove_hr_tag.call_count == 0

    previews = boundaries.utils.observe_previews(service._plugin)
    assert previews['hr']['count'] == 2
    assert '打 H&R 标签' in previews['hr']['samples'][0]
    assert '移除 H&R 标签' in previews['hr']['samples'][1]


def test_hr_tag_writes_run_when_observe_disabled(boundaries):
    """未开启观察时 H&R 打标与移除标签照常执行。"""
    _hr_snapshot(boundaries)
    service = _hr_service(boundaries, observe=False)

    assert service.register_task('QB1', 'hash1') is True
    assert boundaries.hr_scanner.set_hr_tag.call_count == 1

    task = service._tasks['QB1:hash1']
    service._remove_tag(task, {'QB1': Mock()})
    assert boundaries.hr_scanner.remove_hr_tag.call_count == 1
    assert boundaries.utils.observe_previews(service._plugin) == {}
