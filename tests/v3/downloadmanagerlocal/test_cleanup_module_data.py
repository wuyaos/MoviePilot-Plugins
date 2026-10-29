# -*- coding: utf-8 -*-
"""数据页模块数据清理（阶段五 P5-1/P5-2）行为测试。

运行：pytest tests/v3/downloadmanagerlocal/test_cleanup_module_data.py -q

锁定语义（docs/downloadmanagerlocal-optimization-plan.md §7.2/§7.3 + 决策 C）：
1. rename_archive 清空只删 archived=True 条目（连归档状态），重试期计数保留；
2. rename_history/transfer_stats/autoremove_state/failclean_state 清空写空值，返回真实条数，无数据返回 0；
3. 白名单外的 module 拒绝（HTTP 400），不信任前端传入对象；
4. 不触碰下载器数据、H&R 安全状态、transfer_schedule、upload_limit_state。

桩方案沿用 test_manual_run_endpoints.py：宿主与外部边界全部替身，
rename/archive.py 加载真实模块（装饰器直通），其余服务桩为 Mock。
"""
import importlib.machinery
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import Mock

import pytest

PLUGIN = Path(__file__).resolve().parents[3] / 'plugins.v3/downloadmanagerlocal'
PREFIX = 'app.plugins.downloadmanagerlocal'

ARCHIVE_STATE = 'rename_retry_state'
ARCHIVED_KEYS = 'archived'


class FakeHTTPException(Exception):
    def __init__(self, status_code: int = 500, detail: str = ''):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class _FakeResponseFactory:
    def __init__(self, model_type):
        self.model_type = model_type

    def __call__(self, **kwargs):
        return types.SimpleNamespace(model=self.model_type, **kwargs)


class FakeResponse:
    def __class_getitem__(cls, model_type):
        return _FakeResponseFactory(model_type)


class FakeBaseModel:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    @classmethod
    def model_validate(cls, payload):
        return cls(**payload)

    def model_dump(self):
        return dict(self.__dict__)


class FakePlugin:
    """最小插件桩：save_data/get_data 走内存 dict。"""

    def __init__(self, data=None):
        self._data = dict(data or {})

    def get_data(self, key):
        return self._data.get(key)

    def save_data(self, key, value):
        self._data[key] = value


def _module(monkeypatch, name, **attrs):
    result = types.ModuleType(name)
    path = attrs.get('__path__')
    result.__spec__ = importlib.machinery.ModuleSpec(name, None, is_package=path is not None)
    result.__dict__.update(attrs)
    monkeypatch.setitem(sys.modules, name, result)
    return result


def _load(relpath, name):
    spec = importlib.util.spec_from_file_location(name, PLUGIN / relpath)
    result = importlib.util.module_from_spec(spec)
    monkeypatch_module = sys.modules
    monkeypatch_module[spec.name] = result
    spec.loader.exec_module(result)
    return result


MODEL_NAMES = (
    'CleanupModuleRequest', 'CleanupModuleResult', 'DiagnosticsResult', 'EmptyRequest',
    'HashActionResult', 'HrActionResult', 'HrClearTaskRequest', 'HrPresetsResult',
    'HrSkipStatsResult', 'HrTasksResult', 'ModuleActionResult', 'ModuleStatusResult',
    'OverviewResult', 'RenamePageResult', 'RetryRenamesResult', 'SelectionItem',
    'TagCleanupExecuteRequest', 'TagCleanupExecuteResult', 'TagCleanupScanRequest',
    'TagCleanupScanResult', 'UploadLimitDisableResult', 'UploadLimitReallocateResult',
    'UploadLimitRulesRequest', 'UploadLimitRulesResult', 'UploadLimitSiteTagsRequest',
    'UploadLimitSiteTagsResult', 'UploadLimitStatusResult',
)


@pytest.fixture
def archive(monkeypatch):
    """加载真实 rename/archive.py：装饰器直通，state 存取用真实键名。"""
    _module(monkeypatch, 'app')
    _module(monkeypatch, 'app.sdk')
    _module(monkeypatch, 'app.sdk.logging', logger=Mock())
    _module(monkeypatch, 'app.schemas')
    _module(monkeypatch, 'app.schemas.types')
    _module(monkeypatch, PREFIX)
    _module(monkeypatch, PREFIX + '.model')
    _module(monkeypatch, PREFIX + '.model.state',
            RENAME_RECORDS_KEY='rename_records', RENAME_RETRY_STATE_KEY=ARCHIVE_STATE)
    return _load(ARCHIVE_REL := 'modules/rename/archive.py', PREFIX + '.modules.rename.archive')


@pytest.fixture
def cleanup(monkeypatch, archive):
    """handlers 真实模块 + 白名单依赖桩（archive 用真实模块）。"""
    _module(monkeypatch, 'app', schemas=types.SimpleNamespace(Response=FakeResponse))
    _module(monkeypatch, 'app.sdk')
    _module(monkeypatch, 'app.sdk.logging', logger=Mock())
    _module(monkeypatch, 'fastapi', HTTPException=FakeHTTPException)

    for package, path in (
        (PREFIX, PLUGIN),
        (PREFIX + '.adapter', PLUGIN / 'adapter'),
        (PREFIX + '.controller', PLUGIN / 'controller'),
        (PREFIX + '.model', PLUGIN / 'model'),
        (PREFIX + '.modules', PLUGIN / 'modules'),
        (PREFIX + '.modules.hr', PLUGIN / 'modules/hr'),
        (PREFIX + '.utils', PLUGIN / 'utils'),
    ):
        _module(monkeypatch, package, __path__=[str(path)])

    model_api = _module(monkeypatch, PREFIX + '.model.api')
    api_base = type('ApiBusinessModel', (FakeBaseModel,), {})
    model_api.ApiBusinessModel = api_base
    for name in MODEL_NAMES:
        setattr(model_api, name, type(name, (api_base,), {}))

    _module(monkeypatch, PREFIX + '.adapter.moviepilot',
            get_downloader_service=Mock(), get_downloader_services=Mock(return_value={}),
            get_url_domain=Mock(return_value='example.org'), list_builtin_sites=Mock())
    _module(monkeypatch, PREFIX + '.model.state',
            RENAME_RECORDS_KEY='rename_records', RENAME_RETRY_STATE_KEY=ARCHIVE_STATE,
            TRANSFER_SKIP_STATS_KEY='transfer_skip_stats', TRANSFER_STATS_KEY='transfer_stats',
            load_transfer_stats=Mock())
    _module(monkeypatch, PREFIX + '.modules.autoremove.constants',
            REMOVER_STATE_DATA_KEY='remover_state')
    _module(monkeypatch, PREFIX + '.modules.failclean.constants',
            FAILCLEAN_STATUS_DATA_KEY='failclean_status')
    monkeypatch.setitem(sys.modules, PREFIX + '.modules.rename.archive', archive)
    _module(monkeypatch, PREFIX + '.modules.rename.service', scan_renames=Mock(return_value={'renamed': 0}))
    _module(monkeypatch, PREFIX + '.modules.hr.guard', HrGuard=Mock())
    _module(monkeypatch, PREFIX + '.modules.hr.rules', load_preset_rules=Mock(return_value={}))
    _module(monkeypatch, PREFIX + '.modules.sitetag.service',
            execute_tag_cleanup=Mock(), scan_and_clean_tags=Mock(),
            complement_history=Mock(return_value={'completed': 0, 'skipped': 0, 'downloaders': {}}))
    _module(monkeypatch, PREFIX + '.modules.uploadlimit.worker', stop_upload_limit_worker=Mock())
    _module(monkeypatch, PREFIX + '.modules.uploadlimit.service',
            get_upload_limit_status=Mock(), persist_upload_limit_site_rules=Mock(),
            restore_upload_limits=Mock(), run_upload_limit_cycle=Mock(),
            scan_upload_limit_site_tags=Mock())
    _module(monkeypatch, PREFIX + '.utils.config', MODULE_SWITCHES={
        'transfer': ('transfer_enabled', '_transfer_enabled'),
        'rename': ('rename_enabled', '_rename_enabled'),
        'tag': ('tag_enabled', '_tag_enabled'),
        'hr': ('hr_enabled', '_hr_enabled'),
        'autoremove': ('remover_enabled', '_remover_enabled'),
        'failclean': ('failcleanup_enabled', '_failcleanup_enabled'),
        'upload_limit': ('upload_limit_enabled', '_upload_limit_enabled'),
    }, observe_skip=lambda *args, **kwargs: False)

    return _load('controller/handlers.py', PREFIX + '.controller.handlers')


def test_clear_rename_archive_removes_only_archived(archive):
    plugin = FakePlugin({ARCHIVE_STATE: {
        'aaa': {'archived': True, 'fail_count': 3},
        'bbb': {'archived': False, 'fail_count': 1},
        'ccc': {'archived': True, 'fail_count': 9},
    }})
    result = archive.clear_rename_archive(plugin)
    assert result['code'] == 0 and result['removed'] == 2
    state = plugin.get_data(ARCHIVE_STATE)
    assert set(state) == {'bbb'}
    assert state['bbb']['fail_count'] == 1


def test_clear_rename_archive_empty_state(archive):
    result = archive.clear_rename_archive(FakePlugin({}))
    assert result['code'] == 0 and result['removed'] == 0


def test_clear_rename_archive_all_archived(archive):
    plugin = FakePlugin({ARCHIVE_STATE: {'x1': {'archived': True}, 'x2': {'archived': True}}})
    result = archive.clear_rename_archive(plugin)
    assert result['removed'] == 2 and plugin.get_data(ARCHIVE_STATE) == {}


def test_cleanup_actions_whitelist_semantics(cleanup):
    """白名单五种对象语义与真实条数；schedule/上传限速恢复状态不在名单。"""
    plugin = FakePlugin({
        ARCHIVE_STATE: {'h1': {'archived': True}, 'h2': {'archived': False}},
        'rename_records': {'r1': {'original_name': 'a'}, 'r2': {'original_name': 'b'}},
        'transfer_stats': {'total': 5},
        'transfer_skip_stats': {'skip': 2},
        'remover_state': {'last_run_at': 1710000000.0, 'deleted': 3, 'candidate_list': [{'hash': 'a'}]},
        'failclean_status': {
            'last_scan_time': 1710000000.0,
            'last_scan_trigger': '定时',
            'scan': {'scanned': 4, 'cleaned': 2, 'failed': 0, 'skipped': 1},
            'event': {'deleted': 1, 'failed': 0, 'skipped': 0},
            'total': {'cleaned': 9, 'failed': 2, 'skipped': 3},
        },
        'transfer_schedule': {'queue': ['should-stay']},
        'upload_limit_state': {'restore': 'should-stay'},
    })
    actions = cleanup._cleanup_actions(plugin)
    assert set(actions) == {
        'rename_archive', 'rename_history', 'transfer_stats',
        'autoremove_state', 'failclean_state',
    }
    assert actions['rename_archive']() == 1
    assert set(plugin.get_data(ARCHIVE_STATE)) == {'h2'}
    assert actions['rename_history']() == 2
    assert plugin.get_data('rename_records') == {}
    assert actions['rename_history']() == 0
    assert actions['transfer_stats']() == 2
    assert plugin.get_data('transfer_stats') == {}
    # 自动删种：清最近一轮执行状态（只存最近一轮，无累计段），清后按 new 口径计 0
    assert actions['autoremove_state']() == 1
    remover_state = plugin.get_data('remover_state')
    assert remover_state['last_run_at'] == 0.0 and remover_state['deleted'] == 0
    assert remover_state['candidate_list'] == []
    assert actions['autoremove_state']() == 0
    # 失败清理：只清最近巡检/即时清理结果，total 累计值保留
    assert actions['failclean_state']() == 1
    failclean_state = plugin.get_data('failclean_status')
    assert failclean_state['last_scan_time'] == 0.0 and failclean_state['last_scan_trigger'] == ''
    assert failclean_state['scan'] == {'scanned': 0, 'cleaned': 0, 'failed': 0, 'skipped': 0}
    assert failclean_state['event'] == {'deleted': 0, 'failed': 0, 'skipped': 0}
    assert failclean_state['total'] == {'cleaned': 9, 'failed': 2, 'skipped': 3}
    assert actions['failclean_state']() == 0
    assert plugin.get_data('transfer_schedule') == {'queue': ['should-stay']}
    assert plugin.get_data('upload_limit_state') == {'restore': 'should-stay'}


def test_cleanup_module_data_rejects_unknown_module(cleanup):
    """白名单外对象拒绝（HTTP 400），不执行任何清理。"""
    plugin = FakePlugin({'rename_records': {'r1': {}}})
    with pytest.raises(FakeHTTPException) as excinfo:
        cleanup.api_cleanup_module_data(plugin, {'module': 'hr_tasks'})
    assert excinfo.value.status_code == 400
    assert plugin.get_data('rename_records') == {'r1': {}}
