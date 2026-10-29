"""P5-c 结果出口与缺失快照回归。"""

import pytest
import sys
import types
from types import SimpleNamespace
from unittest.mock import Mock


@pytest.fixture
def p5c_modules(mp_stubs, monkeypatch):
    """通过共享 MP 桩加载本包模块，避免依赖宿主安装路径。"""
    guard = types.ModuleType("app.plugins.downloadmanagerlocal.modules.hr.guard")
    guard.SKIP_PATH_AUTO_REMOVE = "auto"
    guard.HrGuard = Mock
    monkeypatch.setitem(sys.modules, guard.__name__, guard)
    autoremove = mp_stubs("modules/autoremove/service.py", "modules.autoremove.service")
    sitetag = mp_stubs("modules/sitetag/service.py", "modules.sitetag.service")
    return autoremove, sitetag


def test_autoremove_additive_skipped_projection(p5c_modules):
    """跳过徽标是两个既有跳过分项的加法投影。"""
    autoremove, _ = p5c_modules
    service = autoremove.AutoRemoveService(Mock())
    result = service._empty_result("test")
    result["details"] = [{"skipped_protected": 2, "skipped_missing": 3}]
    service._sync_totals(result)
    assert result["skipped_protected"] == 2
    assert result["skipped_missing"] == 3
    assert result["skipped"] == 5


def test_persisted_status_missing_snapshot_is_none(p5c_modules):
    """旧数据未带新增快照键时，读取必须保持缺失而非伪造 0。"""
    _, sitetag = p5c_modules
    plugin = SimpleNamespace(get_data=Mock(return_value=None))
    assert sitetag.get_cleanup_status(plugin) is None
    assert sitetag.get_module_status(plugin)["round"] is None


def test_status_save_is_single_batch_write(p5c_modules):
    """结果出口只保存最近一次快照，避免扫描批次堆积历史。"""
    _, sitetag = p5c_modules
    plugin = SimpleNamespace(
        get_data=Mock(return_value=None),
        save_data=Mock(),
        _site_tag_status={"completed": 1, "skipped": 0, "matched": {}, "round": {
            "checked": 1, "success": 1, "no_update": 0, "failed": 0,
        }},
    )
    sitetag._module_state(plugin)["round"] = {"checked": 2, "success": 1, "no_update": 1, "failed": 0}
    plugin.save_data(sitetag.SITE_TAG_STATUS_KEY, dict(plugin._site_tag_status))
    plugin.save_data.assert_called_once()
    assert plugin.save_data.call_args.args[0] == sitetag.SITE_TAG_STATUS_KEY
