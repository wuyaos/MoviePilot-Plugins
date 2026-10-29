"""转移观察写边界：真实 config/service/pipeline，下载器及持久化为隔离替身。"""
import copy
import importlib
import sys
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from test_hr_interlock import interlock  # noqa: F401

PREFIX = "app.plugins.downloadmanagerlocal."


@pytest.fixture
def observed(interlock, monkeypatch):
    env = interlock
    monkeypatch.setattr(sys.modules["app.schemas"], "ServiceInfo", SimpleNamespace, raising=False)
    env.transfer = importlib.import_module(PREFIX + "modules.transfer.service")
    env.pipeline = importlib.import_module(PREFIX + "modules.transfer.pipeline")
    env.recheck = importlib.import_module(PREFIX + "modules.transfer.recheck")
    env.rename = importlib.import_module(PREFIX + "modules.rename.service")
    env.config = importlib.import_module(PREFIX + "utils.config")
    plugin = env.plugin
    plugin._module_observe_only = {"transfer": True, "rename": False}
    plugin._observe_previews = {}
    plugin._transfer_stop_generation = 0
    plugin._event = threading.Event()
    plugin._seed_recheck_lock = threading.RLock()
    plugin._seed_recheck_queue_lock = plugin._seed_recheck_lock
    plugin._seed_recheck_stop_event = None
    plugin._scan_limit = 500
    plugin._seed_max_wait_minutes = 120
    plugin._seed_autostart = False
    plugin._seed_skipverify = False
    plugin._pause_source = False
    plugin._deletesource = True
    plugin._transfer_rename_enabled = True
    plugin._rename_enabled = True
    plugin._tag_enabled = True
    plugin._hr_service = None
    plugin._hr_enabled = False
    plugin._torrent_tags = []
    plugin._remainoldtag = True
    plugin._remainoldcat = True
    plugin._fromdownloader = "source"
    env.source = Mock()
    env.target = Mock()
    for instance in (env.source, env.target):
        instance.delete_torrents.return_value = True
        instance.start_torrents.return_value = True
        instance.stop_torrents.return_value = True
        instance.recheck_torrents.return_value = True
    env.services = {
        "source": SimpleNamespace(name="source", type="qbittorrent", instance=env.source),
        "target": SimpleNamespace(name="target", type="qbittorrent", instance=env.target),
    }
    plugin.service_info.side_effect = env.services.get
    plugin.get_hash.side_effect = lambda row, kind: row["hash"]
    plugin.get_save_path.return_value = "/data"
    plugin.get_label.return_value = []
    plugin.get_category.return_value = "TV"
    env.source.get_completed_torrents.return_value = [{"hash": "abc", "state": "pausedUP"}]
    env.target.get_torrents.return_value = ([], None)
    env.task = dict(name="preview", from_downloader="source", to_downloader="target",
                    no_paths="", include_category="", empty_label_ok=True,
                    exclude_labels="", include_labels="", from_path="", to_path="")
    assert env.config.observe_only(plugin, "transfer") is True
    return env


@pytest.mark.parametrize("kind", ["qbittorrent", "transmission", "rtorrent"])
def test_observe_download_never_adds_or_touches_temporary_tags(observed, monkeypatch, kind):
    env = observed
    for name in ("create_temporary_tag", "release_temporary_tag", "forget_temporary_tag"):
        monkeypatch.setattr(env.transfer, name, Mock())
    env.services["target"].type = kind
    assert env.transfer.download_torrent(env.plugin, env.services["target"], b"torrent", "/data", {}) is None
    assert env.target.mock_calls == []
    env.transfer.create_temporary_tag.assert_not_called()
    env.transfer.release_temporary_tag.assert_not_called()
    env.transfer.forget_temporary_tag.assert_not_called()
    assert env.plugin._observe_previews["transfer"]["count"] == 1


def test_observe_candidate_scan_counts_skips_before_export_or_transaction(observed, monkeypatch):
    env = observed
    monkeypatch.setattr(env.transfer, "get_torrent_payloads", Mock())
    totals = dict(success=0, fail=0, skip=0, del_dup=0)
    env.transfer._run_task(env.plugin, env.task, "手动", 0, totals)
    assert totals == dict(success=0, fail=0, skip=1, del_dup=0)
    env.transfer.get_torrent_payloads.assert_not_called()
    env.plugin.save_data.assert_not_called()
    assert env.target.mock_calls == []
    assert env.source.mock_calls == [(("get_completed_torrents"), (), {})]
    assert any("观察模式，仅预览不写入" in str(c) for c in env.transfer.logger.info.call_args_list)


def test_observe_begin_source_delete_and_postprocess_have_no_writes_or_executed_state(observed):
    env = observed
    add = Mock(return_value="abc")
    assert not env.pipeline.begin_transfer(env.plugin, env.services["source"], env.services["target"],
                                           "abc", {"state": "pausedUP"}, add, lambda: False)
    assert env.pipeline.delete_source(env.plugin, "source", "abc") == "protected"
    assert env.transfer.post_transfer_process(env.plugin, env.services["target"], "abc") is False
    add.assert_not_called()
    assert env.source.mock_calls == env.target.mock_calls == []
    env.plugin._rename_torrent.assert_not_called()
    env.plugin._tag_torrent.assert_not_called()
    env.plugin.save_data.assert_not_called()


@pytest.mark.parametrize("phase", ["target_added", "verifying", "target_ready", "rollback"])
def test_observed_pending_transaction_waits_intact_then_resumes_once(observed, monkeypatch, phase):
    env = observed
    item = dict(source="transfer", source_downloader="source", source_hash="abc",
                downloader="target", hash="abc", phase=phase, created_at=1,
                target_confirmed=True, target_added=True, pause_source=True,
                source_was_active=True, attempts=0, skipverify=False, autostart=False,
                delete_source_requested=False)
    queue = {"target::abc": copy.deepcopy(item)}
    env.recheck.save_seed_recheck_queue(env.plugin, queue)
    env.target.get_torrents.return_value = ([{"hash": "abc", "state": "pausedUP"}], None)
    env.plugin.save_data.reset_mock()
    env.recheck.process_seed_recheck_once(env.plugin, queue)
    assert queue["target::abc"] == item | {"updated_at": queue["target::abc"]["updated_at"]}
    assert not [call for call in env.target.mock_calls if call[0] != "get_torrents"]
    assert env.source.mock_calls == []
    assert not any(call.args[0] == "source-abc" for call in env.plugin.save_data.call_args_list)
    env.plugin._module_observe_only["transfer"] = False
    monkeypatch.setattr(env.transfer, "post_transfer_process", Mock(return_value=True))
    if phase == "rollback":
        env.target.get_torrents.return_value = ([], None)
        env.target.delete_torrents.side_effect = lambda **kw: True
    env.recheck.process_seed_recheck_once(env.plugin, queue)
    if phase == "target_added":
        env.target.recheck_torrents.assert_called_once()
        assert queue["target::abc"]["phase"] == "verifying"
        env.recheck.process_seed_recheck_once(env.plugin, queue)
        assert not queue
        env.target.recheck_torrents.assert_called_once()
    elif phase == "rollback":
        env.target.delete_torrents.assert_called_once()
        env.source.start_torrents.assert_called_once()
        assert not queue
    else:
        assert not queue
    before = list(env.target.mock_calls)
    if not queue:
        env.recheck.process_seed_recheck_once(env.plugin, queue)
        assert env.target.mock_calls == before


def test_direct_observed_rollback_keeps_progress(observed):
    env = observed
    item = dict(phase="rollback", target_added=True, source_hash="abc", attempts=2)
    before = copy.deepcopy(item)
    assert env.pipeline.rollback_transfer(env.plugin, item, env.services["target"], lambda: False) is False
    assert item == before
    assert env.source.mock_calls == env.target.mock_calls == []
    env.plugin.save_data.assert_not_called()


def test_transfer_observe_fallback_does_not_enter_manual_rename(observed, monkeypatch):
    env = observed
    monkeypatch.setattr(env.transfer, "retry_pending_renames", Mock())
    monkeypatch.setattr(env.transfer, "load_transfer_tasks", Mock(return_value=[env.task]))
    monkeypatch.setattr(env.transfer, "ensure_seed_recheck_worker", Mock())
    monkeypatch.setattr(env.transfer, "notify_fromtorrentpath_deprecated", Mock())
    env.transfer.fallback_transfer(env.plugin)
    env.transfer.retry_pending_renames.assert_not_called()
    env.target.add_torrent.assert_not_called()
    assert env.plugin._observe_previews["transfer"]["count"] == 2


@pytest.mark.parametrize("rename_observe", [True, False])
def test_manual_dirty_rename_uses_only_rename_observation(observed, monkeypatch, rename_observe):
    env = observed
    env.plugin._module_observe_only["rename"] = rename_observe
    env.target.get_torrents.return_value = ([{"hash": "abc", "name": "dirty", "save_path": "/data"}], None)
    monkeypatch.setattr(env.transfer, "is_dirty_renamed_torrent_name", lambda name: True)
    monkeypatch.setattr(env.transfer, "resolve_retry_original_name", Mock(return_value="Original"))
    env.plugin.is_rename_archived.return_value = False
    env.plugin._rename_torrent.return_value = True
    result = env.transfer.retry_dirty_torrent_names(env.plugin, env.services["target"])
    if rename_observe:
        assert result == dict(attempted=0, success=0, failed=0, skipped=1, errors=[])
        env.plugin._rename_torrent.assert_not_called()
        env.transfer.resolve_retry_original_name.assert_not_called()
        assert env.plugin._observe_previews["rename"]["count"] == 1
    else:
        assert result["success"] == result["attempted"] == 1
        env.plugin._rename_torrent.assert_called_once()
    env.plugin.record_rename_failure.assert_not_called()
    env.plugin.save_data.assert_not_called()


def test_observed_direct_rename_returns_none_and_writes_no_state_or_tags(observed):
    env = observed
    env.plugin._module_observe_only["rename"] = True
    assert env.rename.rename_torrent(env.plugin, env.target, "qbittorrent", "abc", "Name", "/data") is None
    assert env.target.mock_calls == []
    env.plugin.save_data.assert_not_called()
    env.plugin.record_rename_failure.assert_not_called()
    env.plugin.clear_rename_retry_state.assert_not_called()
    assert env.plugin._observe_previews["rename"]["count"] == 1


def test_nonobserved_real_rename_failure_still_records_failure(observed, monkeypatch):
    env = observed
    env.plugin._module_observe_only["rename"] = False
    env.plugin._rename_exclude_dirs = "/data"
    save = Mock()
    monkeypatch.setattr(env.rename, "save_rename_record", save)
    assert env.rename.rename_torrent(env.plugin, env.target, "qbittorrent", "abc", "Name", "/data") is False
    save.assert_called_once()
    assert save.call_args.args[4] is False


def test_legacy_transfer_without_created_at_still_reaches_delete(observed, monkeypatch):
    env = observed
    env.plugin._module_observe_only["transfer"] = False
    monkeypatch.setattr(env.transfer, "post_transfer_process", Mock(return_value=True))
    delete = Mock(return_value="deleted")
    monkeypatch.setattr(env.pipeline, "delete_source", delete)
    item = dict(phase="target_ready", target_confirmed=True, source_downloader="source",
                source_hash="abc", downloader="target", hash="abc", autostart=False,
                skipverify=False, delete_source_requested=True)
    assert env.pipeline.advance_transfer(env.plugin, item, env.services["target"],
                                         {"state": "pausedUP"}, lambda: False)
    assert delete.call_args.kwargs["operation_id"] == "transfer:target:abc:0"


@pytest.mark.parametrize("kind", ["qbittorrent", "transmission", "rtorrent"])
def test_nonobserved_download_preserves_add_and_tag_behavior(observed, monkeypatch, kind):
    env = observed
    env.plugin._module_observe_only["transfer"] = False
    env.services["target"].type = kind
    monkeypatch.setattr(env.transfer, "is_downloader_type", lambda requested, **kw: requested == kind)
    monkeypatch.setattr(env.transfer, "create_temporary_tag", Mock(return_value="temporary"))
    monkeypatch.setattr(env.transfer, "release_temporary_tag", Mock())
    env.target.add_torrent.return_value = SimpleNamespace(hashString="abc") if kind == "transmission" else True
    env.target.get_torrent_id_by_tag.return_value = "abc"
    assert env.transfer.download_torrent(env.plugin, env.services["target"], b"torrent", "/data", {}) == "abc"
    env.target.add_torrent.assert_called_once()
    kwargs = env.target.add_torrent.call_args.kwargs
    assert kwargs["content"] == b"torrent" and kwargs["is_paused"] is True
    if kind == "qbittorrent":
        assert kwargs["category"] == "TV" and "temporary" in kwargs["tag"]
    elif kind == "rtorrent":
        assert "temporary" in kwargs["tags"]
    else:
        assert kwargs["labels"] == []
    assert env.transfer.create_temporary_tag.call_count == int(kind != "transmission")
    assert env.transfer.release_temporary_tag.call_count == int(kind != "transmission")


@pytest.mark.parametrize("rename_observe", [True, False])
def test_manual_retry_entry_is_independent_of_transfer_observation(observed, monkeypatch, rename_observe):
    env = observed
    env.plugin._module_observe_only["rename"] = rename_observe
    monkeypatch.setattr(env.transfer, "_rename_retry_downloaders", lambda plugin: ["target"])
    monkeypatch.setattr(env.transfer, "is_dirty_renamed_torrent_name", lambda name: True)
    monkeypatch.setattr(env.transfer, "resolve_retry_original_name", Mock(return_value="Original"))
    env.plugin._retry_failed_renames.side_effect = lambda service: env.rename.retry_failed_renames(env.plugin, service)
    env.plugin.is_rename_archived.return_value = False
    env.plugin._rename_torrent.return_value = True
    env.target.get_torrents.return_value = ([{"hash": "abc", "name": "dirty", "save_path": "/data"}], None)
    result = env.transfer.retry_pending_renames(env.plugin)
    assert result["total"] == int(not rename_observe)
    assert env.plugin._rename_torrent.call_count == int(not rename_observe)
    env.plugin.record_rename_failure.assert_not_called()
    env.plugin.save_data.assert_not_called()


@pytest.mark.parametrize("caller", ["candidate", "history_retry", "single_retry", "dirty_retry"])
def test_rename_none_result_is_skipped_without_failure_or_tags(observed, monkeypatch, caller):
    env = observed
    env.plugin._module_observe_only["rename"] = False
    row = {"hash": "abc", "name": "Original", "save_path": "/data"}
    env.target.get_torrents.return_value = ([row], None)
    env.plugin.is_rename_archived.return_value = False
    env.plugin._rename_torrent.return_value = None
    monkeypatch.setattr(env.rename, "rename_torrent", Mock(return_value=None))
    monkeypatch.setattr(env.rename, "resolve_retry_original_name", Mock(return_value="Original"))
    monkeypatch.setattr(env.rename, "add_rename_tag", Mock())
    tag = importlib.import_module(PREFIX + "modules.sitetag.service")
    monkeypatch.setattr(tag, "tag_torrent", Mock())
    if caller == "candidate":
        monkeypatch.setattr(env.rename, "passes_rename_filters", lambda *args: (True, ""))
        assert env.rename.rename_candidate(env.plugin, env.services["target"], {}, row) == "skipped"
    elif caller == "history_retry":
        monkeypatch.setattr(env.rename, "get_failed_rename_hashes", lambda plugin: {"abc"})
        result = env.rename.retry_failed_renames(env.plugin, env.services["target"])
        assert result["attempted"] == result["failed"] == 0 and result["skipped"] == 1
    elif caller == "single_retry":
        result = env.rename.retry_rename_by_hash(env.plugin, env.services["target"], "abc")
        assert result["observed"] is True
    else:
        monkeypatch.setattr(env.transfer, "is_dirty_renamed_torrent_name", lambda name: True)
        monkeypatch.setattr(env.transfer, "resolve_retry_original_name", lambda *args: "Original")
        result = env.transfer.retry_dirty_torrent_names(env.plugin, env.services["target"])
        assert result["attempted"] == result["failed"] == 0 and result["skipped"] == 1
    env.rename.add_rename_tag.assert_not_called()
    tag.tag_torrent.assert_not_called()
    env.plugin._tag_torrent.assert_not_called()
    env.plugin.record_rename_failure.assert_not_called()
    env.plugin.clear_rename_retry_state.assert_not_called()
    env.plugin.save_data.assert_not_called()
