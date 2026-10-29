# -*- coding: utf-8 -*-
"""统一通知出口（阶段四 P4-1）单元测试。

运行：pytest tests/v3/downloadmanagerlocal/test_notify_module.py -q

锁定语义（docs/downloadmanagerlocal-optimization-plan.md §6）：
1. 标题统一为「下载中心 · 模块名（可选后缀）」；
2. 数量口径统一：普通「结果：成功 X，跳过 Y，失败 Z」，观察期「预览：N 个候选，未执行」；
3. notify_module_result 安全发送：post_message 抛异常只告警返回 False，不中断业务；
4. 消息类型默认 Manual，可由调用点覆盖（保持各模块原路由）。
"""
import importlib.machinery
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import Mock

import pytest

PLUGIN = Path(__file__).resolve().parents[3] / "plugins.v3" / "downloadmanagerlocal"
PREFIX = "app.plugins.downloadmanagerlocal"


@pytest.fixture
def notify(monkeypatch):
    def module(name, **attrs):
        result = types.ModuleType(name)
        result.__spec__ = importlib.machinery.ModuleSpec(name, None)
        result.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, result)
        return result

    def load(relpath, name):
        spec = importlib.util.spec_from_file_location(
            name, PLUGIN / relpath)
        result = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = result
        spec.loader.exec_module(result)
        return result

    module("app")
    module("app.sdk")
    module("app.sdk.logging", logger=Mock())
    module("app.schemas")
    module("app.schemas.types", MessageType=Mock(Manual="manual", Plugin="plugin"))
    return load("utils/notify.py", PREFIX + ".utils.notify")


def test_module_title_format(notify):
    assert notify.module_title("rename") == "下载中心 · 种子重命名"
    assert notify.module_title("autoremove", "观察模式") == "下载中心 · 自动删种（观察模式）"
    assert notify.module_title("unknown_module") == "下载中心 · unknown_module"


def test_result_text_success_metrics(notify):
    text = notify.result_text(success=8, skipped=3, failed=1, downloader="QB1", extra="触发：手动")
    assert text.splitlines() == [
        "结果：成功 8，跳过 3，失败 1",
        "下载器：QB1",
        "触发：手动",
    ]


def test_result_text_observe_preview(notify):
    text = notify.result_text(observe=True, preview_count=12)
    assert text == "预览：12 个候选，未执行"


def test_notify_module_result_sends_with_defaults(notify):
    plugin = Mock()
    assert notify.notify_module_result(plugin, "rename", text="结果：成功 1，跳过 0，失败 0") is True
    kwargs = plugin.post_message.call_args.kwargs
    assert kwargs["title"] == "下载中心 · 种子重命名"
    assert kwargs["parse_mode"] == "plain"
    assert kwargs["mtype"] == "manual"


def test_notify_module_result_swallows_post_message_error(notify):
    plugin = Mock()
    plugin.post_message.side_effect = RuntimeError("channel down")
    assert notify.notify_module_result(plugin, "transfer", text="x", suffix="任务执行完成") is False
    assert plugin.post_message.call_count == 1


def test_notify_module_result_handles_missing_plugin(notify):
    assert notify.notify_module_result(None, "hr", text="x") is False
    assert notify.notify_module_result(Mock(post_message=None), "hr", text="x") is False
