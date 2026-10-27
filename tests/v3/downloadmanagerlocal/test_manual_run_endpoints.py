"""新端点离线测试：POST /transfer_run 与 POST /tag_complement。

运行：micromamba run -n base python -m pytest tests/v3/downloadmanagerlocal/test_manual_run_endpoints.py -q

宿主（app / fastapi）、下载器、模型与服务层全部替身；不连接 MoviePilot 或真实下载器。
MODULE_SWITCHES 用最小字面量充当门控接缝，真源与全量键数由 test_gating.py 覆盖。
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
    """schemas.Response[T] 替身：返回带 success/message/data 的命名空间。"""

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
    """隔离加载真实 controller 并替换全部外部边界。"""
    _module(monkeypatch, 'app', schemas=types.SimpleNamespace(Response=FakeResponse))
    _module(monkeypatch, 'app.sdk')
    _module(monkeypatch, 'app.sdk.logging', logger=Mock())
    _module(monkeypatch, 'fastapi', HTTPException=FakeHTTPException)

    for package, path in (
        (PREFIX, PLUGIN),
        (PREFIX + '.adapter', PLUGIN / 'adapter'),
        (PREFIX + '.controller', PLUGIN / 'controller'),
        (PREFIX + '.model', PLUGIN / 'model'),
        (PREFIX + '.service', PLUGIN / 'service'),
        (PREFIX + '.service.hr', PLUGIN / 'service/hr'),
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
    _module(monkeypatch, PREFIX + '.service.archive', serialized_rename_state=lambda fn: fn)
    _module(monkeypatch, PREFIX + '.service.hr.guard', HrGuard=Mock())
    _module(monkeypatch, PREFIX + '.service.hr.rules', load_preset_rules=Mock(return_value={}))
    site_tag = _module(monkeypatch, PREFIX + '.service.site_tag',
                       execute_tag_cleanup=Mock(), scan_and_clean_tags=Mock(),
                       complement_history=Mock(return_value={'completed': 0, 'skipped': 0,
                                                             'downloaders': {}}))
    _module(monkeypatch, PREFIX + '.service.upload_limit_worker', stop_upload_limit_worker=Mock())
    _module(monkeypatch, PREFIX + '.service.upload_limiter',
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

    def load(relpath, name):
        spec = importlib.util.spec_from_file_location(name, PLUGIN / relpath)
        result = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, spec.name, result)
        spec.loader.exec_module(result)
        return result

    return types.SimpleNamespace(
        handlers=load('controller/handlers.py', PREFIX + '.controller.handlers'),
        routes=load('controller/api.py', PREFIX + '.controller.api'),
        site_tag=site_tag,
    )


def _fake_plugin(**attrs):
    """最小 plugin 替身：transfer 为 Mock，_transfer_active 直接给值。"""
    plugin = types.SimpleNamespace(transfer=Mock(), **attrs)
    return plugin


def test_route_contract(endpoints):
    """按当前工作树：36 条路由，两条新 POST 端点 auth=bear 且用 Response 包装。"""
    routes = endpoints.routes.build_api_routes(Mock())
    assert len(routes) == 36
    by_path = {route['path']: route for route in routes}
    for path, summary in (('/transfer_run', '手动执行一轮转移做种'),
                          ('/tag_complement', '手动执行站点标签历史补全')):
        route = by_path[path]
        assert route['methods'] == ['POST']
        assert route['auth'] == 'bear'
        assert route['summary'] == summary
        assert route['response_model'].model_type.__name__ == 'ModuleActionResult'


def test_transfer_run_rejected_when_module_disabled(endpoints):
    """模块门控：插件总开关/转移开关任一关闭 → HTTP 400，不进入 transfer。"""
    plugin = _fake_plugin(_transfer_enabled=False)
    with pytest.raises(FakeHTTPException) as excinfo:
        endpoints.handlers.api_transfer_run(plugin)
    assert excinfo.value.status_code == 400
    assert plugin.transfer.call_count == 0


def test_transfer_run_reports_incomplete_config(endpoints):
    """开关打开但下载器/种子路径未配置：返回 success=False，不启动转移。"""
    plugin = _fake_plugin(_transfer_enabled=True, _transfer_active=False)
    response = endpoints.handlers.api_transfer_run(plugin)
    assert response.success is False
    assert response.data.code == 1
    assert '未就绪' in response.data.msg
    assert plugin.transfer.call_count == 0


def test_transfer_run_invokes_transfer(endpoints):
    """模块生效时调用 plugin.transfer(trigger_source="手动") 并返回成功。"""
    plugin = _fake_plugin(_transfer_enabled=True, _transfer_active=True)
    response = endpoints.handlers.api_transfer_run(plugin)
    plugin.transfer.assert_called_once_with(trigger_source='手动')
    assert response.success is True
    assert response.data.code == 0
    assert response.data.msg == '转移做种已执行'


def test_transfer_run_reports_exception(endpoints):
    """转移抛错时返回 success=False 且带原因，不向调用方抛异常。"""
    plugin = _fake_plugin(_transfer_enabled=True, _transfer_active=True)
    plugin.transfer.side_effect = RuntimeError('boom')
    response = endpoints.handlers.api_transfer_run(plugin)
    assert response.success is False
    assert 'boom' in response.data.msg


def test_tag_complement_rejected_when_module_disabled(endpoints):
    """站点标签模块未生效 → HTTP 400，不触发补全。"""
    plugin = _fake_plugin(_tag_enabled=False)
    with pytest.raises(FakeHTTPException) as excinfo:
        endpoints.handlers.api_tag_complement(plugin)
    assert excinfo.value.status_code == 400
    assert endpoints.site_tag.complement_history.call_count == 0


def test_tag_complement_invokes_history_complement(endpoints):
    """模块生效时调用 complement_history(plugin) 并把统计放进 result。"""
    endpoints.site_tag.complement_history.return_value = {
        'completed': 3, 'skipped': 1, 'downloaders': {'QB1': 3}}
    plugin = _fake_plugin(_tag_enabled=True)
    response = endpoints.handlers.api_tag_complement(plugin)
    endpoints.site_tag.complement_history.assert_called_once_with(plugin)
    assert response.success is True
    assert response.data.result == {'completed': 3, 'skipped': 1, 'downloaders': {'QB1': 3}}
    assert response.data.msg == '站点标签历史补全完成'


def test_tag_complement_reports_exception(endpoints):
    """补全抛错时返回 success=False 且带原因。"""
    endpoints.site_tag.complement_history.side_effect = RuntimeError('site down')
    plugin = _fake_plugin(_tag_enabled=True)
    response = endpoints.handlers.api_tag_complement(plugin)
    assert response.success is False
    assert 'site down' in response.data.msg
