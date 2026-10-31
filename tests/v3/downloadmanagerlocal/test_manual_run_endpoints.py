"""新端点离线测试：POST /transfer_run 与 POST /tag_complement。

运行：micromamba run -n base python -m pytest tests/v3/downloadmanagerlocal/test_manual_run_endpoints.py -q

宿主（app / fastapi）、下载器、模型与服务层全部替身；不连接 MoviePilot 或真实下载器。
MODULE_SWITCHES 用最小字面量充当门控接缝，真源与全量键数由 test_gating.py 覆盖。
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
    'CleanupModuleRequest', 'CleanupModuleResult', 'DiagnosticsResult', 'EmptyRequest', 'ExecutionHistoryPageResult', 'HashActionResult', 'HrActionResult',
    'HrClearTaskRequest', 'HrPresetsResult', 'HrSkipStatsResult', 'HrTasksResult',
    'ModuleActionResult', 'ModuleConfigSummaryResult', 'ModuleStatusResult', 'OverviewResult', 'RenamePageResult',
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
            RENAME_RECORDS_KEY='rename_records', RENAME_RETRY_STATE_KEY='rename_retry_state',
            TRANSFER_SKIP_STATS_KEY='transfer_skip_stats', TRANSFER_STATS_KEY='transfer_stats',
            load_transfer_stats=Mock())
    _module(monkeypatch, PREFIX + '.modules.rename.archive', serialized_rename_state=lambda fn: fn)
    _module(monkeypatch, PREFIX + '.modules.rename.service', scan_renames=Mock(return_value={'renamed': 0}))
    _module(monkeypatch, PREFIX + '.modules.hr.guard', HrGuard=Mock())
    _module(monkeypatch, PREFIX + '.modules.hr.rules', load_preset_rules=Mock(return_value={}))
    site_tag = _module(monkeypatch, PREFIX + '.modules.sitetag.service',
                       execute_tag_cleanup=Mock(), scan_and_clean_tags=Mock(),
                       complement_history=Mock(return_value={'completed': 0, 'skipped': 0,
                                                             'downloaders': {}}))
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
    }, observe_skip=lambda *args, **kwargs: False,
            module_faults=Mock(return_value={}), module_observe_flags=Mock(return_value={}),
            observe_previews=Mock(return_value={}))

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
    """最小 plugin 替身：transfer 为 Mock，_transfer_active 直接给值。

    手动转移在真实插件里由后台线程执行，防重入口的锁与标志在 __init__ 里初始化；
    替身必须带上，否则测的是「替身缺属性」而不是「后台语义」。
    """
    plugin = types.SimpleNamespace(
        transfer=Mock(),
        _transfer_manual_running=False,
        _transfer_manual_lock=threading.Lock(),
        **attrs,
    )
    return plugin


def _wait_called(mock, timeout=2.0):
    """等后台线程真正调到 transfer（daemon 线程启动有调度延迟）。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if mock.called:
            return True
        time.sleep(0.01)
    return mock.called


def test_route_contract(endpoints):
    """按当前工作树：40 条路由（含数据清理端点），新 POST 端点 auth=bear 且用 Response 包装。"""
    routes = endpoints.routes.build_api_routes(Mock())
    assert len(routes) == 42
    by_path = {route['path']: route for route in routes}
    for path, summary in (('/transfer_run', '手动执行一轮转移做种'),
                          ('/tag_complement', '手动执行站点标签历史补全')):
        route = by_path[path]
        assert route['methods'] == ['POST']
        assert route['auth'] == 'bear'
        assert route['summary'] == summary
        assert route['response_model'].model_type.__name__ == 'ModuleActionResult'
    scan = by_path['/rename_scan']
    assert scan['methods'] == ['POST']
    summary = by_path['/module_config_summary']
    assert summary['methods'] == ['GET']
    assert summary['auth'] == 'bear'
    assert summary['summary'] == '获取模块配置摘要'
    assert summary['response_model'].__name__ == 'ModuleConfigSummaryResult'
    assert scan['auth'] == 'bear'
    assert scan['summary'] == '立即扫描并重命名未处理种子'
    assert scan['response_model'].model_type.__name__ == 'RetryRenamesResult'


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
    """模块生效时后台线程调用 plugin.transfer(trigger_source="手动")，端点立即返回。"""
    plugin = _fake_plugin(_transfer_enabled=True, _transfer_active=True)
    response = endpoints.handlers.api_transfer_run(plugin)
    assert response.success is True
    assert response.data.code == 0
    assert '已开始' in response.data.msg
    assert response.data.running is True
    assert _wait_called(plugin.transfer), '后台线程没有调用 transfer'
    plugin.transfer.assert_called_once_with(trigger_source='手动')


def test_transfer_run_returns_before_transfer_finishes(endpoints):
    """端点不等转移跑完——120 个种子的整轮实测超过 180s，同步会读超时。"""
    plugin = _fake_plugin(_transfer_enabled=True, _transfer_active=True)
    release = threading.Event()

    def _slow_transfer(**kwargs):
        release.wait(timeout=5)

    plugin.transfer.side_effect = _slow_transfer
    started = time.time()
    response = endpoints.handlers.api_transfer_run(plugin)
    elapsed = time.time() - started
    try:
        assert response.data.code == 0
        assert elapsed < 1.0, f'端点阻塞了 {elapsed:.2f}s，应当立即返回'
        assert plugin._transfer_manual_running is True, '转移未结束前防重入标志应为 True'
    finally:
        release.set()
        for _ in range(200):
            if not plugin._transfer_manual_running:
                break
            time.sleep(0.01)


def test_transfer_run_guards_reentrancy(endpoints):
    """上一轮还在跑时再点一次：拒绝并提示，不再起第二个线程。"""
    plugin = _fake_plugin(_transfer_enabled=True, _transfer_active=True)
    plugin._transfer_manual_running = True
    response = endpoints.handlers.api_transfer_run(plugin)
    assert response.success is False
    assert response.data.code == 1
    assert '已在后台运行' in response.data.msg
    plugin.transfer.assert_not_called()


def test_transfer_run_reports_exception(endpoints):
    """转移抛错：后台吞掉并记日志，不向调用方抛异常，防重入标志复位。"""
    plugin = _fake_plugin(_transfer_enabled=True, _transfer_active=True)
    plugin.transfer.side_effect = RuntimeError('boom')
    response = endpoints.handlers.api_transfer_run(plugin)
    assert response.success is True
    assert response.data.code == 0
    assert _wait_called(plugin.transfer)
    for _ in range(200):
        if not plugin._transfer_manual_running:
            break
        time.sleep(0.01)
    assert plugin._transfer_manual_running is False, '异常路径也必须复位防重入标志'

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


def test_rename_scan_starts_background_scan(endpoints):
    """POST /rename_scan：立即返回 running=True，后台线程真调用 scan_renames(plugin)。"""
    scan = sys.modules[PREFIX + '.modules.rename.service'].scan_renames
    scan.reset_mock()
    scan.return_value = {'renamed': 2}
    plugin = _fake_plugin(_rename_enabled=True)

    response = endpoints.handlers.api_rename_scan(plugin)

    assert response.success is True
    assert response.data.code == 0
    assert response.data.running is True
    deadline = time.time() + 5
    while scan.call_count == 0 and time.time() < deadline:
        time.sleep(0.02)
    assert scan.call_count == 1
    assert scan.call_args.args[0] is plugin
    while getattr(plugin, '_rename_scan_running', False) and time.time() < deadline:
        time.sleep(0.02)
    assert plugin._rename_scan_running is False


def test_rename_scan_rejected_when_already_running(endpoints):
    """扫描运行中再次触发：返回 code=1，不重复启动。"""
    scan = sys.modules[PREFIX + '.modules.rename.service'].scan_renames
    scan.reset_mock()
    plugin = _fake_plugin(_rename_enabled=True, _rename_scan_running=True)

    response = endpoints.handlers.api_rename_scan(plugin)

    assert response.success is False
    assert response.data.code == 1
    assert '已在运行' in response.data.msg
    assert scan.call_count == 0


def test_rename_scan_rejected_when_module_disabled(endpoints):
    """命名模块未生效 → HTTP 400，不启动扫描。"""
    scan = sys.modules[PREFIX + '.modules.rename.service'].scan_renames
    scan.reset_mock()
    plugin = _fake_plugin(_rename_enabled=False)
    with pytest.raises(FakeHTTPException) as excinfo:
        endpoints.handlers.api_rename_scan(plugin)
    assert excinfo.value.status_code == 400
    assert scan.call_count == 0


def test_hr_tasks_returns_empty_when_service_isolated(endpoints):
    """H&R 服务被隔离（None）时任务列表返回空而不是 500：前端会无条件轮询本端点。"""
    plugin = _fake_plugin(_hr_service=None)
    result = endpoints.handlers.api_hr_tasks(plugin)
    assert result.tasks == []
    assert result.summary == {}


def test_hr_manual_actions_reject_isolated_service(endpoints):
    """模块开关为开但服务初始化被隔离时，手动端点给出明确 400 而不是 AttributeError 文案。"""
    plugin = _fake_plugin(_hr_enabled=True, _hr_service=None)
    request = types.SimpleNamespace()
    for name, call in (
        ("hr_check", lambda: endpoints.handlers.api_hr_check(plugin)),
        ("hr_scan", lambda: endpoints.handlers.api_hr_scan(plugin)),
        ("hr_clear_compliant", lambda: endpoints.handlers.api_hr_clear_compliant(plugin)),
        ("hr_clear_missing", lambda: endpoints.handlers.api_hr_clear_missing(plugin)),
        ("hr_clear_task", lambda: endpoints.handlers.api_hr_clear_task(plugin, request)),
    ):
        try:
            result = call()
        except FakeHTTPException as e:
            assert e.status_code == 400, name
            assert "初始化失败" in e.detail, name
            continue
        raise AssertionError(f"{name} 未拒绝，返回 {result!r}")
        assert "初始化失败" in excinfo.value.detail, name


# ── 转移记录名称（P7-2c 需求④）：GET /transfer_status 带出源种子名 ────────────

def _transfer_status_stubs(monkeypatch, queue: dict):
    """替身：待办队列与任务配置读取，避免为状态投影拉起真实转移模块。"""
    _module(monkeypatch, PREFIX + '.modules.transfer', __path__=[str(PLUGIN / 'modules' / 'transfer')])
    _module(monkeypatch, PREFIX + '.modules.transfer.recheck',
            load_seed_recheck_queue=Mock(return_value=queue))
    _module(monkeypatch, PREFIX + '.modules.transfer.tasks', load_transfer_tasks=Mock(return_value=[]))


def test_transfer_status_exposes_source_name(endpoints, monkeypatch):
    """在途与最近记录都带出 source_name；旧记录缺失时为空串，不伪造名字。"""
    _transfer_status_stubs(monkeypatch, {
        'QB2::' + 'b' * 40: {
            'source_downloader': 'QB1', 'downloader': 'QB2', 'source_hash': 'a' * 40,
            'hash': 'b' * 40, 'phase': 'verifying', 'created_at': time.time(),
            'source_name': '在途.源种子.mkv',
        },
    })
    records = {
        'QB1-' + 'a' * 40: {
            'source_hash': 'a' * 40, 'transfer_state': 'completed', 'to_download': 'QB2',
            'to_download_id': 'b' * 40, 'updated_at': 2.0, 'source_name': '已完成.源种子.mkv',
        },
        'QB1-' + 'c' * 40: {
            'source_hash': 'c' * 40, 'transfer_state': 'rolled_back', 'to_download': 'QB2',
            'to_download_id': 'd' * 40, 'updated_at': 1.0,
        },
    }
    plugin = types.SimpleNamespace(
        get_data=lambda key=None: copy.deepcopy(records.get(key) if key else records))

    status = endpoints.handlers.api_transfer_status(plugin)["status"]

    assert status['pending'][0]['source_name'] == '在途.源种子.mkv'
    rows = {row['source_hash']: row for row in status['records']}
    assert rows['a' * 40]['source_name'] == '已完成.源种子.mkv'
    assert rows['c' * 40]['source_name'] == ''
    assert status['total'] == 2 and status['page_size'] == 20, '分页与总数口径不能被名称字段改动'


def test_transfer_status_source_name_supports_orm_rows(endpoints, monkeypatch):
    """get_data() 返回 ORM 行列表时同样带出名称，缺失时为空串。"""
    _transfer_status_stubs(monkeypatch, {})
    rows = [
        types.SimpleNamespace(key='QB1-' + 'e' * 40, value={
            'source_hash': 'e' * 40, 'transfer_state': 'completed', 'to_download': 'QB2',
            'to_download_id': 'f' * 40, 'updated_at': 3.0, 'source_name': 'ORM.源种子.mkv',
        }),
        types.SimpleNamespace(key='QB1-' + 'g' * 40, value={
            'source_hash': 'g' * 40, 'transfer_state': 'failed', 'to_download': 'QB2',
            'to_download_id': 'h' * 40, 'updated_at': 1.0,
        }),
    ]
    plugin = types.SimpleNamespace(
        get_data=lambda key=None: copy.deepcopy(rows) if key is None else None)

    status = endpoints.handlers.api_transfer_status(plugin)["status"]

    names = {row['source_hash']: row['source_name'] for row in status['records']}
    assert names == {'e' * 40: 'ORM.源种子.mkv', 'g' * 40: ''}


def test_diagnostics_detail_limit_through_route(endpoints, monkeypatch):
    """走真实路由 endpoint：默认快照只读，run=true 才触发新检查。"""
    seen = []

    service = importlib.import_module(PREFIX + '.modules.diagnostics.service')

    def fake_diagnostics(plugin, detail_limit=20, run=False):
        seen.append((detail_limit, run))
        if run:
            return {'detail_limit': detail_limit, 'checked': True}
        return {'checked': False, 'checks': []}

    monkeypatch.setattr(service, 'diagnostics_snapshot', fake_diagnostics)
    plugin = Mock()
    plugin.api_diagnostics = types.MethodType(endpoints.handlers.api_diagnostics, plugin)

    route = {item['path']: item for item in endpoints.routes.build_api_routes(plugin)}['/diagnostics']
    assert route['methods'] == ['GET'] and route['auth'] == 'bear', '路由契约不变'

    assert route['endpoint']().model_dump()['checked'] is False, '默认返回未检查空快照'
    assert route['endpoint'](detail_limit=200, run=True).model_dump()['detail_limit'] == 200, '显式 run 才执行'
    assert seen == [(20, False), (200, True)]

    with pytest.raises(FakeHTTPException) as error:
        route['endpoint'](detail_limit=21)
    assert error.value.status_code == 400
    assert '20/50/100/200' in error.value.detail, '拒绝时列出可接受的档位'
    assert seen == [(20, False), (200, True)], '非法值不得进入诊断构建'


def test_diagnostics_default_matches_service_whitelist(endpoints):
    """handler 默认值与诊断服务白名单同源，避免两处各写一套档位。"""
    import inspect

    service = importlib.import_module(PREFIX + '.modules.diagnostics.service')
    default = inspect.signature(endpoints.handlers.api_diagnostics).parameters['detail_limit'].default

    assert service.MODULE_DETAIL_LIMIT_CHOICES == (20, 50, 100, 200)
    assert default == service.MODULE_DETAIL_ITEM_LIMIT == 20


def test_upload_limit_reallocate_partial_failure_is_not_success(endpoints):
    """code=2（部分失败）必须映射 success=False 且 msg 明示部分失败，不得伪装完全成功。"""
    service = importlib.import_module(PREFIX + '.modules.uploadlimit.service')
    service.run_upload_limit_cycle.return_value = {'errors': ['QB1: timeout'], 'downloaders': []}

    plugin = _fake_plugin(_upload_limit_enabled=True)
    response = endpoints.handlers.api_upload_limit_reallocate(plugin)

    assert response.success is False, 'code=2 是部分失败，success 必须为 False'
    assert '部分下载器限速写入失败' in response.message
    assert response.data.code == 2 and response.data.errors == ['QB1: timeout']


def test_upload_limit_disable_restore_partial_failure_is_not_success(endpoints):
    """停用恢复 code=2 同样不得报 success=True（service 已给「部分限速恢复失败」msg）。"""
    service = importlib.import_module(PREFIX + '.modules.uploadlimit.service')
    service.restore_upload_limits.return_value = {
        'code': 2, 'msg': '部分限速恢复失败', 'downloaders': [], 'errors': ['TR1: offline'],
    }

    plugin = _fake_plugin(_upload_limit_enabled=True, get_config=lambda: {'upload_limit_enabled': True},
                          update_config=lambda config=None: True, _upload_limit_state_error=None)
    response = endpoints.handlers.api_upload_limit_disable_restore(plugin)

    assert response.success is False
    assert response.message == '部分限速恢复失败'
