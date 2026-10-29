"""H&R 保护闸门模块隔离回归：关闭不拦截、无法确认时保守阻止并计数。

阶段二 D 联动规则的真实入口：模块关闭时撤销进程内保护快照，关闭的模块不得继续拦截
其它模块的危险删除；模块启用但服务未能产出快照时按「无法确认」保守跳过并计数。
"""
import sys

import pytest


@pytest.fixture
def guard_module(mp_stubs):
    # 每例重建真实 guard 模块（含真实 hr_task_key），保证共享状态互不串扰，退出时恢复。
    prefix = "app.plugins.downloadmanagerlocal."
    previous = {key: value for key, value in sys.modules.items() if key.startswith(prefix)}
    for key in previous:
        sys.modules.pop(key)
    try:
        module = mp_stubs("modules/hr/guard.py", "modules.hr.guard")
        module.get_guard().update(enabled=False, protected=[])
        yield module
    finally:
        for key in list(sys.modules):
            if key.startswith(prefix):
                sys.modules.pop(key)
        sys.modules.update(previous)


def test_disabled_module_does_not_block_deletions(guard_module):
    """模块关闭后，历史保护快照不得继续拦截其他模块的删除动作。"""
    hr_guard = guard_module.get_guard()
    hr_guard.update(enabled=True, protected=[("qb", "abc")])
    assert hr_guard.should_skip(guard_module.SKIP_PATH_AUTO_REMOVE, "qb", "abc") is True

    hr_guard.expect(enabled=False)

    assert hr_guard.unconfirmed is False
    assert hr_guard.is_protected("qb", "abc") is False
    assert hr_guard.should_skip(guard_module.SKIP_PATH_AUTO_REMOVE, "qb", "abc") is False


def test_unconfirmed_protection_blocks_delete_conservatively(guard_module):
    """模块启用但服务不可用：无法确认保护状态，保守阻止该次删除并计数。"""
    hr_guard = guard_module.get_guard()
    hr_guard.expect(enabled=True)

    assert hr_guard.unconfirmed is True
    assert hr_guard.should_skip(guard_module.SKIP_PATH_TRANSFER_SOURCE, "qb", "unknown") is True
    assert hr_guard.get_skip_stats()[guard_module.SKIP_PATH_TRANSFER_SOURCE] == 1

    # 快照可用后恢复常规判定：未纳管任务放行，纳管未达标任务继续拦截。
    hr_guard.update(enabled=True, protected=[("qb", "abc")])

    assert hr_guard.unconfirmed is False
    assert hr_guard.should_skip(guard_module.SKIP_PATH_TRANSFER_SOURCE, "qb", "unknown") is False
    assert hr_guard.should_skip(guard_module.SKIP_PATH_TRANSFER_SOURCE, "qb", "abc") is True


def test_failed_round_marks_snapshot_unconfirmed_and_keeps_snapshot(guard_module):
    """本轮检查中断：保留已有快照判定，同时把状态标记为无法确认。"""
    hr_guard = guard_module.get_guard()
    hr_guard.update(enabled=True, protected=[("qb", "abc")])

    hr_guard.mark_unconfirmed()

    assert hr_guard.unconfirmed is True
    assert hr_guard.is_protected("qb", "abc") is True
    assert hr_guard.should_skip(guard_module.SKIP_PATH_SYNC_DELETE, "qb", "other") is True
    assert hr_guard.get_skip_stats()[guard_module.SKIP_PATH_SYNC_DELETE] == 1
