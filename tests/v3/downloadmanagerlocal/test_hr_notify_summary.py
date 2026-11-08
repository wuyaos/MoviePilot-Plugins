# -*- coding: utf-8 -*-
"""H&R 汇总通知隔离测试：安全发送，失败保留队列。

与既有替身 `modules.hr.notify` 的测试（test_observe_boundaries.py）互补：
本文件加载真实 `modules/hr/notify.py` 与真实 `utils/notify.py`（统一出口
notify_module_result），验证 send_summary 的队列语义：

- post_message 抛异常：send_summary 返回 False，事件队列原样保留（不清空、
  不写回去重结果），下次调度重发；异常不冒泡。
- 发送成功：返回 True，队列清空；标题/消息类型/parse_mode 与原实现一致。
- notify="none"：不发送，队列保留。
- 队列为空：直接 False。

替身边界（均为模块自己声明的隔离点）：
- `modules/hr/models.py`：HrTask 依赖 pytz/pydantic/settings，汇总路径只读
  事件字典，替身为最小 HrStatus 枚举值。
- `modules/hr/constants.py` 真实加载（纯常量）。
- 事件存储用内存 dict 模拟 plugin.get_data/save_data。
"""
from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import Mock

import pytest

PREFIX = "app.plugins.downloadmanagerlocal"


class _StorePlugin:
    """带内存事件队列的宿主替身；breaking=True 时 post_message 必抛异常。"""

    def __init__(self, breaking: bool = False) -> None:
        self.store: dict = {}
        self.messages: list[dict] = []
        self.titles_attempted: list[str] = []
        self._breaking = breaking

    def get_data(self, key):
        return self.store.get(key)

    def save_data(self, key, value):
        self.store[key] = value

    def post_message(self, **kwargs):
        self.titles_attempted.append(str(kwargs.get("title", "")))
        if self._breaking:
            raise RuntimeError("通知渠道不可用")
        self.messages.append(kwargs)


@pytest.fixture
def hr_notify(mp_stubs, monkeypatch):
    import importlib.machinery

    def stub(name: str, **attrs):
        module = types.ModuleType(name)
        module.__spec__ = importlib.machinery.ModuleSpec(name, None)
        module.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, module)
        return module

    # 中间包占位（带真实 __path__），支撑 hr/notify.py 的相对导入
    plugin_root = Path(__file__).resolve().parents[3] / "plugins.v3" / "downloadmanagerlocal"
    for package, relpath in (
        (f"{PREFIX}.modules", "modules"),
        (f"{PREFIX}.modules.hr", "modules/hr"),
        (f"{PREFIX}.utils", "utils"),
    ):
        placeholder = types.ModuleType(package)
        placeholder.__spec__ = importlib.machinery.ModuleSpec(package, None, is_package=True)
        placeholder.__path__ = [str(plugin_root / relpath)]
        monkeypatch.setitem(sys.modules, package, placeholder)

    # 真实统一出口（hr/notify 依赖 utils.notify）与真实常量先落位
    mp_stubs("utils/notify.py", "utils.notify")
    mp_stubs("modules/hr/constants.py", "modules.hr.constants")

    stub(
        f"{PREFIX}.modules.hr.models",
        HrStatus=types.SimpleNamespace(
            COMPLIANT=types.SimpleNamespace(value="compliant"),
            OVERDUE=types.SimpleNamespace(value="overdue"),
            NEEDS_SEEDING=types.SimpleNamespace(value="needs_seeding"),
        ),
        HrTask=Mock(),
    )
    return mp_stubs("modules/hr/notify.py", "modules.hr.notify")


def _event(downloader: str, torrent_hash: str, status: str = "compliant") -> dict:
    return {
        "downloader": downloader,
        "torrent_hash": torrent_hash,
        "site_name": "HDSky",
        "identifier": "Test.Show.S01",
        "status": status,
        "seeding_h": "1.0",
        "required_h": "24",
        "ratio": "1.00",
        "hr_ratio": 1.0,
        "remain": "23.0h",
        "deadline": "2026-11-30",
    }


def test_send_failure_keeps_queue(hr_notify):
    plugin = _StorePlugin(breaking=True)
    events = [
        _event("qb1", "abc", "compliant"),
        _event("qb1", "abc", "overdue"),  # 同 (downloader, hash)，发送前会去重
    ]
    plugin.store["hr_notify_events"] = events

    sent = hr_notify.send_summary(plugin, "always")

    assert sent is False
    # 队列原样保留：不清空、也不把去重结果写回
    assert plugin.store["hr_notify_events"] == events
    assert plugin.titles_attempted == ["下载中心 · H&R 管理"]


def test_send_success_clears_queue(hr_notify):
    plugin = _StorePlugin()
    plugin.store["hr_notify_events"] = [
        _event("qb1", "abc", "compliant"),
        _event("qb1", "abc", "overdue"),
    ]

    sent = hr_notify.send_summary(plugin, "always")

    assert sent is True
    assert plugin.store["hr_notify_events"] == []
    assert len(plugin.messages) == 1
    message = plugin.messages[0]
    assert message["title"] == "下载中心 · H&R 管理"
    from app.schemas.types import MessageType

    assert message["mtype"] is MessageType.SiteMessage
    # 去重后只剩 1 条（同一 (downloader, hash) 保留最后写入）
    # 去重后只剩 1 条（同一 (downloader, hash) 保留最后写入的事件：overdue）
    assert "【已过期】 1 条" in message["text"]
    assert "【已完成】" not in message["text"]


def test_none_mode_skips_and_keeps_queue(hr_notify):
    plugin = _StorePlugin()
    events = [_event("qb1", "abc")]
    plugin.store["hr_notify_events"] = events

    assert hr_notify.send_summary(plugin, "none") is False
    assert plugin.store["hr_notify_events"] == events
    assert plugin.messages == []


def test_empty_queue_returns_false(hr_notify):
    plugin = _StorePlugin()

    assert hr_notify.send_summary(plugin, "always") is False
    assert plugin.messages == []
