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


@pytest.mark.parametrize("source_type", ["transmission", "qbittorrent"])
@pytest.mark.parametrize("filtered_by", ["include", "exclude", "category", "path", "delay", "tracker", "none"])
@pytest.mark.parametrize("scan_limit", [2, 0])
def test_run_task_limits_candidates_after_filters(tr, monkeypatch, source_type,
                                                 filtered_by, scan_limit):
    source, target = Mock(), Mock()
    rejected = [dict(hash=f"rejected-{i}", labels=[], category="seed", path="/data")
                for i in range(500)] if filtered_by != "none" else []
    accepted = [dict(hash=f"accepted-{i}", labels=["已转移"], category="seed", path="/data")
                for i in range(3)]
    for torrent in rejected:
        if filtered_by == "exclude":
            torrent["labels"] = ["已转移", "禁止"]
        elif filtered_by == "category":
            torrent.update(labels=["已转移"], category="other")
        elif filtered_by == "path":
            torrent.update(labels=["已转移"], path="/excluded")
        elif filtered_by in ("delay", "tracker"):
            torrent["labels"] = ["已转移"]
    source.get_completed_torrents.return_value = rejected + accepted
    target.get_torrents.return_value = ([], None)
    services = {
        "source": SimpleNamespace(name="source", type=source_type, instance=source),
        "target": SimpleNamespace(name="target", type="qbittorrent", instance=target),
    }
    plugin = SimpleNamespace(
        service_info=services.get, _scan_limit=scan_limit,
        get_hash=Mock(side_effect=lambda t, _: t["hash"]),
        get_save_path=lambda t, _: t["path"], get_label=lambda t, _: t["labels"],
        get_category=lambda t, _: t["category"],
        get_data=lambda *a: {}, save_data=Mock(), convert_save_path=lambda *a: "/data",
    )
    task = dict(name="扫描上限", from_downloader="source", to_downloader="target",
                no_paths="/excluded", include_category="seed",
                include_labels="" if filtered_by == "none" else "已转移",
                exclude_labels="禁止", from_path="", to_path="",
                include_trackers="shadowthein.net" if filtered_by == "tracker" else "",
                delete_source=False, delete_duplicate=False)
    monkeypatch.setattr(tr, "_transfer_stopped", lambda *a: False)
    monkeypatch.setattr(tr, "_transfer_delay_status", lambda p, t, *a:
                        (filtered_by == "delay" and t["hash"].startswith("rejected-"), 0, 0))
    monkeypatch.setattr(tr, "get_torrent_payloads", Mock(return_value={
        t["hash"]: b"payload" for t in accepted}))
    monkeypatch.setattr(tr, "begin_transfer", Mock(return_value=True))
    if filtered_by == "tracker":
        monkeypatch.setattr(tr, "get_tracker_urls", lambda t, _: [
            "https://other.net/announce" if t["hash"].startswith("rejected-")
            else "https://shadowthein.net/announce"])
    totals = dict(success=0, fail=0, skip=0, del_dup=0)

    tr._run_task(plugin, task, "兜底扫描", 0, totals)

    expected = max(1, scan_limit)
    assert totals == dict(success=expected, fail=0, skip=0, del_dup=0, notify=True)
    assert tr.get_torrent_payloads.call_args.args[-1] == [
        t["hash"] for t in accepted[:expected]]
    assert tr.begin_transfer.call_count == expected
    assert plugin.get_hash.call_count == len(rejected) + expected
    assert target.get_torrents.call_count == expected
    source.delete_torrents.assert_not_called()
    target.delete_torrents.assert_not_called()
    assert all(call.kwargs["delete_source"] is False for call in tr.begin_transfer.call_args_list)
