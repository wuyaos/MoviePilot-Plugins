"""真实转移消费方 + H&R 服务/标签适配器；所有下载器 IO 为 mock。"""
import importlib
import sys
from types import ModuleType
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from test_hr_interlock import interlock  # noqa: F401 - reuse real service fixture


@pytest.fixture
def wiring(interlock, monkeypatch):
    env = interlock
    pipeline = importlib.import_module("app.plugins.downloadmanagerlocal.modules.transfer.pipeline")
    env.plugin._hr_service = env.service
    env.plugin._hr_enabled = True
    env.plugin.service_info.return_value = SimpleNamespace(instance=env.instance)
    env.instance.delete_torrents.return_value = True
    env.pipeline = pipeline
    return env


def delete(env, **kwargs):
    return env.pipeline.delete_source(env.plugin, "qb", "abc", **(
        dict(authorized=True, target_verified=True, operation_id="transfer-1") | kwargs
    ))


def test_transfer_release_delete_and_success_accounting(wiring):
    env = wiring
    assert delete(env) == "deleted"
    assert [call[0] for call in env.instance.mock_calls] == [
        "remove_torrents_tag", "delete_torrents",
    ]
    env.instance.delete_torrents.assert_called_once_with(delete_file=False, ids=["abc"])
    assert env.data["hr_tasks"]["qb:abc"]["interlock_state"] == "deleted"
    assert env.api.query("other", "abc")["protected"]


def test_transfer_protected_without_authorization_logs_reason_and_zero_writes(wiring):
    env = wiring
    assert env.pipeline.delete_source(env.plugin, "qb", "abc") == "protected"
    assert env.instance.mock_calls == []
    assert env.api.query("qb", "abc")["state"] == ""
    assert env.api.query("qb", "abc")["protected"]
    assert env.data["transfer_skip_stats"]["hr_protected"] == 1
    assert any("H&R 保护" in str(call) for call in env.pipeline.logger.info.call_args_list)


def test_transfer_unverified_cannot_release_or_begin_delete(wiring):
    env = wiring
    assert delete(env, target_verified=False) == "protected"
    assert env.instance.mock_calls == []
    assert env.api.query("qb", "abc")["state"] == ""


@pytest.mark.parametrize("failure", [False, RuntimeError("delete offline")])
def test_transfer_delete_failure_restores_protection_and_accounts(wiring, failure):
    env = wiring
    if failure is False:
        env.instance.delete_torrents.return_value = False
        assert delete(env) == "retry"
    else:
        env.instance.delete_torrents.side_effect = failure
        with pytest.raises(RuntimeError, match="delete offline"):
            delete(env)
    result = env.api.query("qb", "abc")
    assert result["protected"] and result["state"] == "restored"
    assert result["error"] == "delete failed"
    assert env.data["hr_tasks"]["qb:abc"]["interlock_state"] == "restored"
    env.instance.set_torrents_tag.assert_called_once()


@pytest.mark.parametrize("module", ["transfer", "hr"])
def test_transfer_observation_has_zero_downloader_writes(wiring, module):
    wiring.plugin._module_observe_only[module] = True
    assert delete(wiring) == "protected"
    assert wiring.instance.mock_calls == []


@pytest.mark.parametrize("skipverify,started,authorized,expected", [
    (False, True, True, True),
    (True, True, True, False),
    (False, False, True, False),
    (False, True, False, True),
])
def test_advance_transfer_passes_only_config_authorization_and_real_verification(
    wiring, monkeypatch, skipverify, started, authorized, expected,
):
    env = wiring
    pipeline = env.pipeline
    transfer = ModuleType("app.plugins.downloadmanagerlocal.modules.transfer.service")
    transfer.post_transfer_process = Mock(return_value=True)
    monkeypatch.setitem(sys.modules, transfer.__name__, transfer)
    consumer = Mock(return_value="protected")
    monkeypatch.setattr(pipeline, "delete_source", consumer)
    monkeypatch.setattr(pipeline, "save_source_record", Mock())
    monkeypatch.setattr(pipeline, "record_transfer_success", Mock())
    env.plugin._hr_enabled = authorized
    env.plugin._seed_max_wait_minutes = 120
    item = dict(phase="target_ready", target_confirmed=True, source_downloader="qb",
                source_hash="abc", downloader="target", hash="abc", created_at=1,
                skipverify=skipverify, autostart=False, delete_source_requested=True,
                target_verification_started=started)
    assert pipeline.advance_transfer(env.plugin, item, SimpleNamespace(type="qbittorrent"),
                                     {"state": "pausedUP"}, lambda: False)
    assert consumer.call_args.kwargs == dict(authorized=authorized, target_verified=expected,
                                            operation_id="transfer:target:abc:1")


@pytest.mark.parametrize("authorized", [False, True])
def test_released_reservation_cannot_bypass_begin_delete_on_next_call(wiring, authorized):
    env = wiring
    env.api.release("qb", "abc", source="transfer_source", operation_id="transfer-1",
                    authorized=True, target_verified=True)
    env.instance.reset_mock()
    env.plugin._module_observe_only["hr"] = True
    assert delete(env, authorized=authorized) == "protected"
    assert env.instance.mock_calls == []
    assert env.api.query("qb", "abc")["state"] == "released"


@pytest.mark.parametrize("kind", ["qbittorrent", "transmission", "rtorrent"])
@pytest.mark.parametrize("skipverify", [False, True])
def test_real_verification_progression_controls_protected_source_release(wiring, monkeypatch, kind, skipverify):
    env = wiring
    pipeline = env.pipeline
    transfer = ModuleType("app.plugins.downloadmanagerlocal.modules.transfer.service")
    transfer.post_transfer_process = Mock(return_value=True)
    monkeypatch.setitem(sys.modules, transfer.__name__, transfer)
    monkeypatch.setattr(pipeline, "save_transaction", Mock())
    monkeypatch.setattr(pipeline, "record_transfer_success", Mock())
    env.plugin._seed_max_wait_minutes = 120
    target = SimpleNamespace(type=kind, instance=Mock())
    target.instance.recheck_torrents.return_value = True
    target.instance.start_torrents.return_value = True
    task = ({"state": "pausedUP"} if kind == "qbittorrent" else
            {"state": 1, "complete": 1} if kind == "rtorrent" else
            SimpleNamespace(status="stopped", percent_done=1, error=0))
    item = dict(phase="target_added", target_confirmed=True, source_downloader="qb",
                source_hash="abc", downloader="target", hash="abc", created_at=1,
                skipverify=skipverify, autostart=False, delete_source_requested=True)
    assert not pipeline.advance_transfer(env.plugin, item, target, task, lambda: False)
    assert env.instance.mock_calls == []
    assert pipeline.advance_transfer(env.plugin, item, target, task, lambda: False)
    assert item["source_deleted"] is (not skipverify)
    assert item["hr_protected"] is skipverify
    assert env.api.query("qb", "abc")["state"] == ("" if skipverify else "deleted")
