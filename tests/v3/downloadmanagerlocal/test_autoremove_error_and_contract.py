"""旧错误关键词是 AND 子项；空值禁用是既有语义，本轮不新增删除行为。"""
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def autoremove_error(mp_stubs, monkeypatch):
    prefix = "app.plugins.downloadmanagerlocal."
    previous = {key: value for key, value in sys.modules.items() if key.startswith(prefix)}
    for key in previous:
        sys.modules.pop(key)
    try:
        module = mp_stubs("modules/autoremove/service.py", "modules.autoremove.service")
        # H&R 不属于本测试范围；只隔离查询，不替换条件、扫描、执行路径。
        monkeypatch.setattr(module, "HrGuard", Mock(return_value=SimpleNamespace(
            should_skip=Mock(return_value=False))))
        yield module
    finally:
        for key in list(sys.modules):
            if key.startswith(prefix):
                sys.modules.pop(key)
        sys.modules.update(previous)


def run_cycle(module, *, error="disk full", **conditions):
    torrent = dict(hashString="abc", name="fixture", totalSize=2 * 1024 ** 3,
                   uploadRatio=3, doneDate=1, uploadedEver=1024,
                   downloadDir="/data/keep", status="stopped", labels=["keep"],
                   errorString=error, trackers=[dict(announce="https://tracker.test/a", tier=0)])
    instance = Mock()
    instance.get_torrents.return_value = ([torrent], None)
    plugin = Mock()
    plugin.get_data.return_value = None
    plugin.service_info.return_value = SimpleNamespace(type="transmission", instance=instance)
    service = module.AutoRemoveService(plugin)
    service.init_module(dict(enabled=True, remover_enabled=True, remover_observe_only=False,
                             remover_action="delete", remover_downloaders=["tr"],
                             remover_errorkeywords="disk full") | conditions)
    result = service.run_cycle("regression")
    return service, result, instance


@pytest.mark.parametrize("error", ["disk full", "", "ordinary paused"])
def test_empty_error_keywords_disable_only_error_subcondition(autoremove_error, error):
    # 既有语义：空关键词不参与过滤；不是「空关键词禁止删除」。
    service, result, instance = run_cycle(
        autoremove_error, error=error, remover_errorkeywords="", remover_ratio="2")
    assert service._conditions.error_pattern is None
    assert result["candidates"] == result["deleted"] == 1
    instance.delete_torrents.assert_called_once_with(delete_file=False, ids=["abc"])


def test_all_empty_conditions_keep_existing_unfiltered_behavior(autoremove_error):
    # 属既有行为，本次不改；显式记录风险，不能借空关键词引入新全局闸门。
    service, result, instance = run_cycle(autoremove_error, remover_errorkeywords="")
    assert service._conditions.error_pattern is None
    assert result["candidate_list"][0]["reason"] == "无筛选条件"
    assert result["deleted"] == 1
    instance.delete_torrents.assert_called_once_with(delete_file=False, ids=["abc"])


@pytest.mark.parametrize("other", [
    {"remover_ratio": "3"},
    {"remover_time": "1000000000"},
    {"remover_size": "3-4"},
    {"remover_upspeed": "0"},
    {"remover_pathkeywords": "not-this-path"},
    {"remover_trackerkeywords": "not-this-tracker"},
    {"remover_labels": "missing"},
])
def test_matching_error_cannot_bypass_any_other_and_condition(autoremove_error, other):
    _, result, instance = run_cycle(autoremove_error, **other)
    # 错误命中但任一其他条件失败：若改成独立 OR 删除，此断言会失败。
    assert result["candidates"] == result["deleted"] == 0
    instance.delete_torrents.assert_not_called()
    instance.stop_torrents.assert_not_called()


def test_other_condition_cannot_bypass_nonmatching_error(autoremove_error):
    _, result, instance = run_cycle(autoremove_error, error="ordinary paused", remover_ratio="2")
    assert result["candidates"] == result["deleted"] == 0
    instance.delete_torrents.assert_not_called()


@pytest.mark.parametrize("error,deleted", [
    ("DISK is FULL", 1), ("permission was denied", 1),
    ("disk denied", 0), ("permission full", 0), ("disk", 0), ("", 0),
])
def test_error_regex_alternatives_preserve_group_pairing(autoremove_error, error, deleted):
    # 多值是一个 re.I 正则，不是逗号 chips；组内顺序配对，组间 OR，仍与 ratio AND。
    _, result, instance = run_cycle(
        autoremove_error, error=error, remover_ratio="2",
        remover_errorkeywords=r"disk.*full|permission.*denied")
    assert result["deleted"] == deleted
    assert instance.delete_torrents.call_count == deleted


def test_regex_alternatives_cannot_become_independent_or_delete(autoremove_error):
    _, result, instance = run_cycle(
        autoremove_error, error="permission denied", remover_ratio="3",
        remover_errorkeywords=r"disk.*full|permission.*denied")
    assert result["candidates"] == result["deleted"] == 0
    instance.delete_torrents.assert_not_called()


@pytest.mark.parametrize("key", ["remover_ratio", "remover_time", "remover_upspeed"])
def test_numeric_conditions_do_not_accept_unrelated_multivalue_or(autoremove_error, key):
    _, result, instance = run_cycle(autoremove_error, **{key: "1,2"})
    assert result["config_error"]
    assert result["candidates"] == result["deleted"] == 0
    instance.delete_torrents.assert_not_called()
