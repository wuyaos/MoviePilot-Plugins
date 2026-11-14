"""转移规则 tracker 域名筛选；真实入口，下载器 IO 全部为替身。"""
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from test_transfer_tasks_engine import tr, tt  # noqa: F401


@pytest.mark.parametrize("source_type", ["qbittorrent", "transmission"])
@pytest.mark.parametrize("include,exclude,urls,expected", [
    ("shadowthein.net", "", ["https://shadowthein.net/key/announce"], True),
    ("SHADOWTHEIN.NET.", "", ["https://SHADOWTHEIN.NET.:443/key/announce"], True),
    ("other.net,shadowthein.net", "", ["udp://shadowthein.net:80/announce"], True),
    ("shadowthein.net", "shadowthein.net", ["https://shadowthein.net/key"], False),
    ("shadowthein.net", "blocked.net", ["https://shadowthein.net/a", "https://blocked.net/b"], False),
    ("shadowthein.net", "", ["https://sub.shadowthein.net/a"], False),
    ("shadowthein.net", "", ["https://shadowthein.net.evil.net/a"], False),
    ("shadowthein.net", "", ["https://shadowthein.net@evil.net/a"], False),
    ("", "blocked.net", ["https://shadowthein.net/a"], True),
    ("", "shadowthein.net", ["https://shadowthein.net/a"], False),
    ("shadowthein.net", "", [], False),
    ("", "blocked.net", [], False),
    ("shadowthein.net", "", ["http://[invalid/a"], False),
    ("shadowthein.net", "", ["https://shadowthein.net/a", "invalid"], False),
    ("", "", [], True),
    ("", "", ["http://[invalid/a"], True),
    ("https://shadowthein.net/private-key/announce", "", ["https://shadowthein.net/a"], False),
])
def test_run_tracker_filter(tr, monkeypatch, source_type, include, exclude, urls, expected):
    source, target = Mock(), Mock()
    # 两个源类型分别走真实 URL 提取逻辑，不依赖站点识别。
    field = "url" if source_type == "qbittorrent" else "announce"
    torrent = dict(hash="accepted", state="pausedUP", trackers=[{field: url, "tier": 0} for url in urls])
    source.get_completed_torrents.return_value = [torrent]
    target.get_torrents.return_value = ([], None)
    services = {
        "source": SimpleNamespace(name="source", type=source_type, instance=source),
        "target": SimpleNamespace(name="target", type="qbittorrent", instance=target),
    }
    plugin = SimpleNamespace(
        service_info=services.get, _scan_limit=1, get_hash=lambda t, _: t["hash"],
        get_save_path=lambda *a: "/data", get_label=lambda *a: ["已转移"],
        get_category=lambda *a: "seed", get_data=lambda *a: {}, save_data=Mock(),
        convert_save_path=lambda *a: "/data",
    )
    task = dict(name="Tracker", from_downloader="source", to_downloader="target",
                no_paths="", include_category="seed", include_labels="已转移", exclude_labels="",
                include_trackers=include, exclude_trackers=exclude, from_path="", to_path="",
                delete_source=False, delete_duplicate=False)
    monkeypatch.setattr(tr, "_transfer_stopped", lambda *a: False)
    monkeypatch.setattr(tr, "_transfer_delay_status", lambda *a: (False, 0, 0))
    monkeypatch.setattr(tr, "get_torrent_payloads", Mock(return_value={"accepted": b"torrent"}))
    monkeypatch.setattr(tr, "begin_transfer", Mock(return_value=True))
    if not include and not exclude:
        monkeypatch.setattr(tr, "get_tracker_urls", Mock(side_effect=AssertionError("留空不应读取 tracker")))
    totals = dict(success=0, fail=0, skip=0, del_dup=0)

    tr._run_task(plugin, task, "兜底扫描", 0, totals)

    assert totals["success"] == int(expected)
    assert tr.get_torrent_payloads.call_count == int(expected)
    assert target.get_torrents.call_count == int(expected)
    source.delete_torrents.assert_not_called()
    target.delete_torrents.assert_not_called()
    assert "private-key" not in str(tr.logger.mock_calls)


@pytest.mark.parametrize("value,expected", [
    ("", ""), ("ShadowTheIn.Net., other.net\nshadowthein.net", "other.net,shadowthein.net"),
    ("https://shadowthein.net/key/announce", None), ("*.shadowthein.net", None),
    ("shadowthein.net/path", None), ("bad..net", None), (["shadowthein.net"], None),
])
def test_tracker_filter_round_trip(tt, value, expected):
    raw = dict(name="保存", from_downloader="TR", to_downloader="QB",
               include_trackers=value, exclude_trackers="")
    normalized = tt._normalize_task(raw, 0)
    if expected is None:
        assert normalized is None
    else:
        assert normalized["include_trackers"] == expected
        tasks = tt.load_transfer_tasks(SimpleNamespace(_transfer_tasks=json.dumps([normalized])))
        assert tasks[0]["include_trackers"] == expected
        assert tasks[0]["exclude_trackers"] == ""


def test_legacy_task_does_not_enable_tracker_filter(tt):
    task = tt._normalize_task(dict(name="旧规则", from_downloader="TR", to_downloader="QB"), 0)
    assert task["include_trackers"] == task["exclude_trackers"] == ""


@pytest.mark.parametrize("tag_result,expected", [(None, "unknown_site"), (False, "failed"), (True, "ok")])
def test_post_transfer_keeps_tag_outcome_without_unknown_site_warning(tr, monkeypatch, tag_result, expected):
    target = Mock()
    target.get_torrents.return_value = ([dict(hash="abc", name="data.mkv", tags="", save_path="/data", trackers=[])], None)
    plugin = SimpleNamespace(_tag_enabled=True, _tag_torrent=Mock(return_value=tag_result))
    monkeypatch.setattr(tr, "_transfer_stopped", lambda *a: False)
    outcome = {}
    assert tr.post_transfer_process(plugin, SimpleNamespace(instance=target, type="qbittorrent"), "abc", 0, outcome)
    assert outcome["site_tag_result"] == expected
    assert not any("站点未识别" in str(call) for call in tr.logger.warning.call_args_list)
    if tag_result is False:
        assert any("站点标签写入失败" in str(call) for call in tr.logger.error.call_args_list)
    target.delete_torrents.assert_not_called()
