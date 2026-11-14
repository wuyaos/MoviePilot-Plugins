"""真实转移入口的标签筛选回归；所有下载器 IO 均为替身。"""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from test_transfer_tasks_engine import tr  # noqa: F401


@pytest.mark.parametrize("source_type", ["transmission", "qbittorrent"])
@pytest.mark.parametrize("empty_label_ok", [True, False, None])
@pytest.mark.parametrize("include,exclude,labels,category,expected", [
    ("已转移", "", [], "", False),
    ("已转移", "", None, "", False),
    ("已转移", "", [""], "", False),
    ("已转移", "", ["其他"], "", False),
    ("已转移", "", ["已转移"], "", True),
    ("已转移,保种", "", ["已转移"], "", False),
    ("已转移,保种", "", ["已转移", "保种"], "", True),
    (" 已转移 , , 保种 ", "", ["已转移", "保种"], "", True),
    ("已转移", "禁止", ["已转移", "禁止"], "", False),
    ("", "", [], "", True),
    ("", "", None, "", True),
    ("", "", [""], "", True),
    ("", "", ["其他"], "", True),
    (" , ", "", [], "", True),
    ("", "禁止", ["禁止"], "", False),
    ("", "禁止", [], "", True),
    ("已转移", "", ["已转移"], "seed", False),
])
def test_run_task_label_filter(tr, monkeypatch, source_type, empty_label_ok,
                               include, exclude, labels, category, expected):
    source, target = Mock(), Mock()
    source.get_completed_torrents.return_value = [{"hash": "abc", "state": "pausedUP"}]
    target.get_torrents.return_value = ([], None)
    services = {
        "source": SimpleNamespace(name="source", type=source_type, instance=source),
        "target": SimpleNamespace(name="target", type="qbittorrent", instance=target),
    }
    plugin = SimpleNamespace(
        service_info=services.get, _scan_limit=500,
        get_hash=lambda *a: "abc", get_save_path=lambda *a: "/data",
        get_label=lambda *a: labels, get_category=lambda *a: "",
        get_data=lambda *a: {}, save_data=Mock(), convert_save_path=lambda *a: "/data",
    )
    task = dict(name="标签筛选", from_downloader="source", to_downloader="target",
                no_paths="", include_category=category, include_labels=include,
                exclude_labels=exclude, empty_label_ok=empty_label_ok,
                from_path="", to_path="", delete_source=False, delete_duplicate=False)
    if empty_label_ok is None:
        task.pop("empty_label_ok")
    monkeypatch.setattr(tr, "_transfer_stopped", lambda *a: False)
    monkeypatch.setattr(tr, "_transfer_delay_status", lambda *a: (False, 0, 0))
    monkeypatch.setattr(tr, "get_torrent_payloads", Mock(return_value={"abc": b"payload"}))
    monkeypatch.setattr(tr, "begin_transfer", Mock(return_value=True))
    totals = dict(success=0, fail=0, skip=0, del_dup=0)

    tr._run_task(plugin, task, "手动", 0, totals)

    assert totals["success"] == int(expected)
    assert tr.begin_transfer.call_count == int(expected)
    assert tr.get_torrent_payloads.call_count == int(expected)
    assert target.get_torrents.call_count == int(expected)
    source.delete_torrents.assert_not_called()
    target.delete_torrents.assert_not_called()
    if expected:
        assert tr.begin_transfer.call_args.kwargs["delete_source"] is False
        assert tr.get_torrent_payloads.call_args.args[-1] == ["abc"]
