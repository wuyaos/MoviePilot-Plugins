"""路径修复 API 的授权、记录身份与预览/执行分离。"""
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from test_manual_run_endpoints import endpoints, _module, _fake_plugin, PREFIX, FakeHTTPException




def configure(endpoints, monkeypatch, *, active=None):
    class Blocked(ValueError):
        pass
    path = _module(monkeypatch, PREFIX + '.modules.transfer.path_repair',
                   PathRepairBlocked=Blocked,
                   diagnose=Mock(return_value={'state': 'mismatch', 'repairable': False, 'reason': '远端现场无法确认'}),
                   repair=Mock(return_value={'code': 0, 'msg': '已提交真实校验'}))
    _module(monkeypatch, PREFIX + '.modules.transfer.recheck',
            _queue_key=lambda dl, h: f'{dl}::{h}', _queue_lock=lambda p: threading.RLock(),
            load_seed_recheck_queue=lambda p: active or {})
    record = {'source': 'transfer', 'source_downloader': 'source', 'source_hash': 'a' * 40,
              'transfer_state': 'verifying', 'to_download': 'target', 'to_download_id': 'a' * 40}
    plugin = _fake_plugin(_transfer_enabled=True, get_data=Mock(return_value=record))
    request = SimpleNamespace(source_downloader='source', source_hash='a' * 40, execute=False, token='')
    return path, plugin, request


def test_preview_is_readonly_and_returns_reason(endpoints, monkeypatch):
    path, plugin, request = configure(endpoints, monkeypatch)
    response = endpoints.handlers.api_transfer_path_repair(plugin, request)
    assert response.success and response.data.diagnostic['state'] == 'mismatch'
    path.repair.assert_not_called()


def test_execute_calls_repair_only_with_stored_target_identity(endpoints, monkeypatch):
    path, plugin, request = configure(endpoints, monkeypatch)
    request.execute, request.token = True, 'preview-token'
    response = endpoints.handlers.api_transfer_path_repair(plugin, request)
    assert response.success
    item = path.repair.call_args.args[1]
    assert item['downloader'] == 'target' and item['hash'] == 'a' * 40
    assert path.repair.call_args.args[2] == 'preview-token'


def test_missing_record_and_foreign_queue_cannot_repair(endpoints, monkeypatch):
    path, plugin, request = configure(endpoints, monkeypatch)
    plugin.get_data.return_value = None
    with pytest.raises(FakeHTTPException) as exc:
        endpoints.handlers.api_transfer_path_repair(plugin, request)
    assert exc.value.status_code == 404
    active = {'target::' + 'a' * 40: {'source_downloader': 'other', 'source_hash': 'a' * 40}}
    path, plugin, request = configure(endpoints, monkeypatch, active=active)
    with pytest.raises(FakeHTTPException) as exc:
        endpoints.handlers.api_transfer_path_repair(plugin, request)
    assert exc.value.status_code == 409
    path.repair.assert_not_called()


def test_disabled_module_and_blocked_repair_report_failure(endpoints, monkeypatch):
    path, plugin, request = configure(endpoints, monkeypatch)
    plugin._transfer_enabled = False
    with pytest.raises(FakeHTTPException) as exc:
        endpoints.handlers.api_transfer_path_repair(plugin, request)
    assert exc.value.status_code == 400
    plugin._transfer_enabled = True
    request.execute = True
    path.repair.side_effect = path.PathRepairBlocked('原路径存在，拒绝修复')
    result = endpoints.handlers.api_transfer_path_repair(plugin, request)
    assert not result.success and result.data.code == 1


def test_route_is_authenticated_post(endpoints):
    route = next(r for r in endpoints.routes.build_api_routes(Mock()) if r['path'] == '/transfer_path_repair')
    assert route['auth'] == 'bear' and route['methods'] == ['POST']
