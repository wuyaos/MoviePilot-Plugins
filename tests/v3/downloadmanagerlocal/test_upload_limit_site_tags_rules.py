"""上传限速站点扫描的规则基底契约。

运行：micromamba run -n base python -X utf8 -m pytest tests/v3/downloadmanagerlocal/test_upload_limit_site_tags_rules.py -q

宿主（app / fastapi）与 service 层全部替身，不连接 MoviePilot 或真实下载器。
锁定两条语义：

1. 请求体 rules 缺失或为空 → 以已持久化 upload_limit_site_rules 为基底，只补充扫描到的站点名，不清空既有上限；
2. 显式传入非空 rules → 以传入值为基底（Config 站点策略保存路径行为不变）。
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


class FakeHTTPException(Exception):
    """fastapi.HTTPException 替身，保留 status_code/detail 语义。"""

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
    """schemas.Response[T] 替身：返回带 model 的命名空间。"""

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


MODEL_NAMES = (
    'DiagnosticsResult', 'EmptyRequest', 'HashActionResult', 'HrActionResult',
    'HrClearTaskRequest', 'HrPresetsResult', 'HrSkipStatsResult', 'HrTasksResult',
    'ModuleActionResult', 'ModuleStatusResult', 'OverviewResult', 'RenamePageResult',
    'RetryRenamesResult', 'SelectionItem', 'TagCleanupExecuteRequest',
    'TagCleanupExecuteResult', 'TagCleanupScanRequest', 'TagCleanupScanResult',
    'UploadLimitDisableResult', 'UploadLimitReallocateResult', 'UploadLimitRulesRequest',
    'UploadLimitRulesResult', 'UploadLimitSiteTagsRequest', 'UploadLimitSiteTagsResult',
    'UploadLimitStatusResult',
)


def _module(monkeypatch, name, **attrs):
    result = types.ModuleType(name)
    path = attrs.get('__path__')
    result.__spec__ = importlib.machinery.ModuleSpec(name, None, is_package=path is not None)
    result.__dict__.update(attrs)
    monkeypatch.setitem(sys.modules, name, result)
    return result


@pytest.fixture
def endpoints(monkeypatch):
    """隔离加载真实 controller.handlers 并替换全部外部边界。"""
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
            get_downloader_service=Mock(), get_url_domain=Mock(return_value='example.org'),
            list_builtin_sites=Mock())
    _module(monkeypatch, PREFIX + '.model.state',
            RENAME_RECORDS_KEY='rename_records', RENAME_RETRY_STATE_KEY='rename_retry_state',
            TRANSFER_SKIP_STATS_KEY='transfer_skip_stats', load_transfer_stats=Mock())
    _module(monkeypatch, PREFIX + '.modules.rename.archive', serialized_rename_state=lambda fn: fn)
    _module(monkeypatch, PREFIX + '.modules.hr.guard', HrGuard=Mock())
    _module(monkeypatch, PREFIX + '.modules.hr.rules', load_preset_rules=Mock(return_value={}))
    _module(monkeypatch, PREFIX + '.modules.sitetag.service',
            execute_tag_cleanup=Mock(), scan_and_clean_tags=Mock(), complement_history=Mock())
    _module(monkeypatch, PREFIX + '.modules.uploadlimit.worker', stop_upload_limit_worker=Mock())
    upload_limiter = _module(
        monkeypatch, PREFIX + '.modules.uploadlimit.service',
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
    })

    spec = importlib.util.spec_from_file_location(
        PREFIX + '.controller.handlers', PLUGIN / 'controller/handlers.py')
    handlers = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, handlers)
    spec.loader.exec_module(handlers)

    return types.SimpleNamespace(handlers=handlers, upload_limiter=upload_limiter)


PERSISTED = {'site-a': {'limit_kib': 100}}


def _scan_result():
    return {'code': 0, 'msg': '站点标签扫描完成',
            'items': [{'name': 'site-b', 'label': '🏠site-b', 'task_count': 1}], 'errors': []}


def _persisted_rules(endpoints):
    """返回 handler 交给 persist_upload_limit_site_rules 的规则基底。"""
    assert endpoints.upload_limiter.persist_upload_limit_site_rules.call_count == 1
    return endpoints.upload_limiter.persist_upload_limit_site_rules.call_args.args[1]


@pytest.fixture
def scan_ready(endpoints):
    endpoints.upload_limiter.scan_upload_limit_site_tags.return_value = _scan_result()
    endpoints.upload_limiter.persist_upload_limit_site_rules.return_value = {
        'site-a': {'limit_kib': 100}, 'site-b': {'limit_kib': 0}}
    return endpoints


def test_scan_with_empty_rules_keeps_persisted_rules(scan_ready):
    """rules 显式传空对象（真实 pydantic 模型补默认值后的形态）不得清空已持久化策略。"""
    plugin = types.SimpleNamespace(_upload_limit_site_rules=dict(PERSISTED))

    response = scan_ready.handlers.api_upload_limit_site_tags(
        plugin, {'downloaders': ['QB1'], 'rules': {}})

    assert _persisted_rules(scan_ready) == {
        'site-a': {'limit_kib': 100}, 'site-b': {'limit_kib': 0}}
    assert response.data.code == 0


def test_scan_without_rules_key_keeps_persisted_rules(scan_ready):
    """请求体没有 rules 键时同样沿用已持久化策略。"""
    plugin = types.SimpleNamespace(_upload_limit_site_rules=dict(PERSISTED))

    scan_ready.handlers.api_upload_limit_site_tags(plugin, {'downloaders': ['QB1']})

    assert _persisted_rules(scan_ready) == {
        'site-a': {'limit_kib': 100}, 'site-b': {'limit_kib': 0}}


def test_scan_with_explicit_rules_uses_request_rules(scan_ready):
    """显式传入非空 rules 仍以传入值为基底，不合并已持久化策略（Config 保存路径行为不变）。"""
    plugin = types.SimpleNamespace(_upload_limit_site_rules=dict(PERSISTED))

    scan_ready.handlers.api_upload_limit_site_tags(
        plugin, {'downloaders': ['QB1'], 'rules': {'site-c': {'limit_kib': 50}}})

    assert _persisted_rules(scan_ready) == {
        'site-c': {'limit_kib': 50}, 'site-b': {'limit_kib': 0}}


def test_scan_without_persisted_rules_stays_empty_base(scan_ready):
    """插件尚无持久化策略（属性缺失或为空）时以空字典为基底，只落扫描到的站点名。"""
    plugin = types.SimpleNamespace()

    scan_ready.handlers.api_upload_limit_site_tags(plugin, {'downloaders': ['QB1'], 'rules': {}})

    assert _persisted_rules(scan_ready) == {'site-b': {'limit_kib': 0}}
