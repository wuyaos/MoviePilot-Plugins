"""源/目的共存现场协调；真实 service/persistence，下载器仅内存 fake。"""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from test_transfer_tasks_engine import tr, _load_real  # noqa: F401


@pytest.fixture
def scene(tr, monkeypatch):
    recheck = _load_real(monkeypatch, "recheck")
    monkeypatch.setattr(tr, "seed_is_ready", recheck.seed_is_ready)
    monkeypatch.setattr(tr, "seed_is_error", recheck.seed_is_error)
    target = dict(hashString="abc", name="example", labels=["🏠PTS", "收藏"],
                  download_dir="/data", status="seeding", percent_done=1, error=0)
    dl = Mock()
    dl.get_torrents.side_effect = lambda **kw: ([target], None)
    def set_tags(**kw):
        target["labels"] = kw["tags"]
        return True
    dl.set_torrent_tag.side_effect = set_tags
    source = dict(hash="abc", name="example", save_path="/data", state="uploading", tags="")
    src = SimpleNamespace(name="A", type="qbittorrent", instance=Mock())
    dst = SimpleNamespace(name="B", type="transmission", instance=dl)
    data = {}
    plugin = SimpleNamespace(
        get_data=lambda k: data.get(k), save_data=lambda k, v: data.update({k: dict(v)}),
        service_info={"A": src, "B": dst}.get,
        convert_save_path=lambda path, *a: path, get_hash=tr.get_label.__globals__["get_hash"],
        _seed_autostart=True, _transfer_stop_generation=0, _event=None,
        _transfer_rename_enabled=False, _tag_enabled=True,
        _tag_torrent=Mock(return_value=True),
    )
    task = dict(name="test", from_path="", to_path="", transfer_tag="已转移")
    item = dict(hash="abc", save_path="/data", torrent=source)
    delete = Mock(return_value="deleted")
    monkeypatch.setattr(tr, "delete_source", delete)
    def run(delete_requested=True, previous=None):
        return tr._reconcile_existing(plugin, task, src, dst, item, [target], previous or {}, delete_requested, 0)
    return SimpleNamespace(**locals())


def test_old_three_get_business_tag_without_readding(scene):
    s = scene
    assert s.run() == "deleted"
    assert set(s.target["labels"]) == {"🏠PTS", "收藏", "已转移"}
    s.dl.add_torrent.assert_not_called()
    s.dl.delete_torrents.assert_not_called()
    s.delete.assert_called_once_with(s.plugin, "A", "abc")  # never borrows historical release evidence
    assert s.data["A-abc"]["source_deleted"] is True
    assert s.data["A-abc"]["tag_result"] == "ok"


def test_disabled_retains_source_and_repeated_run_is_idempotent(scene):
    s = scene
    assert s.run(False) == "retained"
    assert s.run(False, s.data["A-abc"]) == "retained"
    s.delete.assert_not_called()
    assert s.dl.set_torrent_tag.call_count == 1
    assert s.data["A-abc"]["source_result"] == "disabled"


@pytest.mark.parametrize("change, reason", [
    ({"download_dir": "/wrong"}, "identity_unconfirmed"),
    ({"hashString": "other"}, "identity_unconfirmed"),
    ({"status": "checking"}, "target_not_ready"),
    ({"percent_done": 0.5}, "target_not_ready"),
    ({"error": 2}, "target_not_ready"),
])
def test_unsafe_target_preserves_both(scene, change, reason):
    s = scene
    s.target.update(change)
    assert s.run() == "protected"
    s.delete.assert_not_called()
    s.dl.set_torrent_tag.assert_not_called()
    assert s.data["A-abc"]["source_result"] == reason


def test_hr_block_is_not_a_release_authorization(scene):
    s = scene
    s.delete.return_value = "protected"
    assert s.run(previous={"target_verification_started": True, "skipverify": False}) == "protected"
    assert s.delete.call_args.kwargs == {}
    assert s.data["A-abc"]["hr_protected"] is True


def test_false_tag_write_is_visible_but_not_delete_evidence(scene):
    s = scene
    s.dl.set_torrent_tag.side_effect = None
    s.dl.set_torrent_tag.return_value = False
    assert s.run() == "deleted"
    assert s.data["A-abc"]["tag_result"] == "failed"


def test_latest_query_failure_preserves_source(scene):
    s = scene
    s.dl.get_torrents.side_effect = [([s.target], None), (None, True)]
    assert s.run() == "retry"
    s.delete.assert_not_called()
    assert s.data["A-abc"]["source_result"] == "query_failed"


def test_stopped_target_requests_start_but_does_not_claim_seeding(scene):
    s = scene
    s.target["status"] = "stopped"
    assert s.run() == "retained"
    s.delete.assert_not_called()
    s.dl.start_torrents.assert_called_once_with(ids=["abc"])
    assert s.data["A-abc"]["source_result"] == "start_requested"


def test_stop_during_tag_io_prevents_delete(scene):
    s = scene
    def stop(**kw):
        s.plugin._transfer_stop_generation += 1
        return True
    s.dl.set_torrent_tag.side_effect = stop
    assert s.run() == "protected"
    s.delete.assert_not_called()


def test_observe_reconcile_never_writes_or_advances(scene, monkeypatch):
    s = scene
    s.plugin._transfer_observe_only = True
    s.plugin._module_observe_only = {"transfer": True}
    import sys
    cfg = sys.modules["app.plugins.downloadmanagerlocal.utils.config"]
    monkeypatch.setattr(cfg, "observe_only", lambda plugin, module: module == "transfer")
    monkeypatch.setattr(cfg, "record_observe_preview", Mock(), raising=False)
    assert s.run() == "observed"
    assert s.data == {}
    s.dl.set_torrent_tag.assert_not_called()
    s.plugin._tag_torrent.assert_not_called()
    s.dl.start_torrents.assert_not_called()
    s.delete.assert_not_called()
