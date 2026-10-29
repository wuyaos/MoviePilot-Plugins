"""公共 H&R 联动反例：真实服务/guard/标签适配器，隔离下载器与持久化。"""
import copy
import importlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def interlock(mp_stubs, monkeypatch):
    prefix = "app.plugins.downloadmanagerlocal."
    previous = {key: value for key, value in sys.modules.items() if key.startswith(prefix)}
    for key in previous:
        sys.modules.pop(key)
    try:
        monkeypatch.setitem(sys.modules, "fastapi", SimpleNamespace(HTTPException=RuntimeError))
        module = mp_stubs("modules/hr/service.py", "modules.hr.service")
        api = importlib.import_module(prefix + "modules.hr.interlock")
        plugin = Mock()
        plugin._module_observe_only = {"hr": False, "transfer": False, "autoremove": False}
        data = {}
        plugin.save_data.side_effect = lambda key, value: data.__setitem__(key, copy.deepcopy(value))
        plugin.get_data.side_effect = lambda key: copy.deepcopy(data.get(key))
        service = module.HrService(plugin)
        service._config = module.HrConfig(enabled=True, protection_enabled=True, downloaders=["qb"])
        for name in ("qb", "other"):
            task = module.HrTask(downloader=name, hash="abc", title=name, hit_and_run=True)
            service._tasks[task.key] = task
        service._refresh_guard()
        instance = Mock()
        instance.remove_torrents_tag.return_value = None
        instance.set_torrents_tag.return_value = None
        downloader = SimpleNamespace(type="qbittorrent", instance=instance)
        services = Mock(return_value={"qb": downloader})
        monkeypatch.setattr(api, "downloader_services", services)
        monkeypatch.setattr(module, "downloader_services", services)
        yield SimpleNamespace(module=module, api=api.HrInterlock(service), service=service,
                              instance=instance, services=services, plugin=plugin, data=data)
    finally:
        for key in list(sys.modules):
            if key.startswith(prefix):
                sys.modules.pop(key)
        sys.modules.update(previous)


ARGS = dict(source="transfer_source", operation_id="transfer-1", authorized=True)


def release(env, **kwargs):
    return env.api.release("qb", "abc", **(ARGS | {"target_verified": True} | kwargs))


@pytest.mark.parametrize("source", ("auto_remove", "transfer_failure", "sync_delete", "", "unknown"))
def test_unauthorized_source_zero_downloader_writes(interlock, source):
    with pytest.raises(PermissionError):
        release(interlock, source=source)
    interlock.services.assert_not_called()
    assert interlock.instance.mock_calls == []
    assert interlock.api.query("qb", "abc")["protected"]


def test_explicit_authorization_required(interlock):
    with pytest.raises(PermissionError):
        release(interlock, authorized=False)
    assert interlock.instance.mock_calls == []


@pytest.mark.parametrize("instance", ("", None, "  "))
def test_hash_only_never_crosses_instances(interlock, instance):
    with pytest.raises(ValueError):
        interlock.api.release(instance, "abc", **ARGS, target_verified=True)
    with pytest.raises(ValueError):
        interlock.api.query(instance, "abc")
    assert interlock.instance.mock_calls == []
    release(interlock)
    assert interlock.api.query("other", "abc")["protected"]
    assert interlock.service.get_task("other", "abc").interlock_state == ""


@pytest.mark.parametrize("module,source", (("hr", "transfer_source"), ("transfer", "transfer_source"),
                                          ("hr", "error_torrent_delete"), ("autoremove", "error_torrent_delete")))
def test_observation_zero_writes(interlock, module, source):
    interlock.plugin._module_observe_only[module] = True
    with pytest.raises(PermissionError):
        release(interlock, source=source, error_confirmed=True)
    interlock.services.assert_not_called()
    assert interlock.instance.mock_calls == []


def test_skipverify_is_not_verification(interlock):
    with pytest.raises(TypeError):
        interlock.api.release("qb", "abc", **ARGS, skipverify=True)
    with pytest.raises(PermissionError):
        interlock.api.release("qb", "abc", **ARGS)
    assert interlock.instance.mock_calls == []


def test_error_delete_requires_reconfirmation(interlock):
    with pytest.raises(PermissionError):
        release(interlock, source="error_torrent_delete")
    assert interlock.instance.mock_calls == []
    assert release(interlock, source="error_torrent_delete", error_confirmed=True)["state"] == "released"


@pytest.mark.parametrize("restore_fails", (False, True))
def test_delete_failure_restores_local_protection_even_when_tag_fails(interlock, restore_fails):
    assert release(interlock)["state"] == "released"
    interlock.api.begin_delete("qb", "abc", **ARGS)
    if restore_fails:
        interlock.instance.set_torrents_tag.side_effect = RuntimeError("tag offline")
    result = interlock.api.finish_delete("qb", "abc", **ARGS, success=False)
    assert result["protected"] and result["state"] == "restored"
    assert ("tag restore failed" in result["error"]) is restore_fails
    saved = interlock.data["hr_tasks"]["qb:abc"]
    assert saved["interlock_state"] == "restored"
    interlock.service._refresh_guard()
    assert interlock.api.query("qb", "abc")["protected"]
    again = interlock.api.finish_delete("qb", "abc", **ARGS, success=False)
    assert again == result
    interlock.instance.set_torrents_tag.assert_called_once()


def test_release_is_idempotent_and_delete_requires_reservation(interlock):
    first = release(interlock)
    assert release(interlock) == first
    interlock.instance.remove_torrents_tag.assert_called_once()
    with pytest.raises(PermissionError):
        interlock.api.finish_delete("qb", "abc", **ARGS, success=True)
    interlock.api.begin_delete("qb", "abc", **ARGS)
    with pytest.raises(PermissionError):
        interlock.api.begin_delete("qb", "abc", **ARGS)
    result = interlock.api.finish_delete("qb", "abc", **ARGS, success=True)
    assert result["state"] == "deleted" and not result["protected"]
    assert interlock.api.finish_delete("qb", "abc", **ARGS, success=True) == result
    interlock.instance.delete_torrents.assert_not_called()


@pytest.mark.parametrize("disabled", (True, False))
def test_disabled_or_unconfirmed_only_blocks_dangerous_path(interlock, disabled):
    if disabled:
        interlock.service.config.enabled = False
        interlock.service._refresh_guard()
    else:
        interlock.service._guard.mark_unconfirmed()
    query = interlock.api.query("qb", "abc")
    assert query["unconfirmed"] is (not disabled)
    with pytest.raises(PermissionError):
        release(interlock)
    interlock.services.assert_not_called()
    # Queries/other module work still execute; no lifecycle or scheduler is started.
    assert len(interlock.service.get_service_infos()["tasks"]) == 2
    records = importlib.import_module("app.plugins.downloadmanagerlocal.controller.records")
    page, size, result_filter = records.record_query()
    assert records.record_page([{"hash": "rename-history"}], page, size, result_filter)["total"] == 1
    assert interlock.instance.mock_calls == []


def test_old_task_dict_and_json_roundtrip_have_no_release(interlock):
    cls = interlock.module.HrTask
    old = {"downloader": "qb", "hash": "abc", "title": "old", "hr_duration": 72, "uploaded": 123}
    for task in (cls.model_validate(old), cls.model_validate_json(json.dumps(old))):
        assert task.interlock_state == task.interlock_id == ""
        assert all(task.model_dump()[key] == value for key, value in old.items())
        assert cls.model_validate_json(task.model_dump_json()) == task


@pytest.mark.parametrize("state", ("pending", "released", "deleting", "restoring"))
def test_restart_keeps_interrupted_protection_and_inspectable_state(interlock, state):
    task = interlock.service._tasks["qb:abc"]
    task.interlock_state, task.interlock_id, task.interlock_source = state, "transfer-1", "transfer_source"
    interlock.service._save_tasks()
    interlock.service._tasks = interlock.service._load_tasks()
    interlock.service._refresh_guard()
    result = interlock.api.query("qb", "abc")
    assert result["state"] == "interrupted" and result["protected"]
    assert result["operation_id"] == "transfer-1" and result["error"]
    with pytest.raises(PermissionError):
        release(interlock)
    assert interlock.instance.mock_calls == []


def test_scan_and_reregistration_during_release_cannot_overwrite_reservation(interlock, monkeypatch):
    service = interlock.service
    task = service._tasks["qb:abc"]
    def io(**kwargs):
        assert not service._lock._is_owned()
        assert service.get_task("qb", "abc").interlock_state == "pending"
        # Concurrent thread can query service while downloader IO is running.
        with ThreadPoolExecutor(max_workers=1) as pool:
            assert pool.submit(service.get_task, "qb", "abc").result(timeout=2).interlock_state == "pending"
        assert not service.register_task("qb", "abc", torrent_data={"hit_and_run": True})
        interlock.instance.get_torrents.return_value = []
        result = service.run_scan("interlock test")
        assert result["check"]["deleted"] == 1  # only the unrelated instance
        assert service._tasks["qb:abc"] is task
        assert task.interlock_state == "pending" and not task.deleted
    interlock.instance.remove_torrents_tag.side_effect = io
    released = release(interlock)
    assert released["state"] == "released", released
    assert task.interlock_id == "transfer-1"
    service._refresh_guard()
    assert not interlock.api.query("qb", "abc")["protected"]
    assert not service.clear_task("qb", "abc")


@pytest.mark.parametrize("failure", (False, RuntimeError("remove offline")))
def test_tag_release_failure_is_not_authorized_success(interlock, failure):
    if failure is False:
        interlock.instance.remove_torrents_tag.return_value = False
    else:
        interlock.instance.remove_torrents_tag.side_effect = failure
    result = release(interlock)
    assert result["protected"] and result["state"] == "restored" and result["error"]
    with pytest.raises(PermissionError):
        interlock.api.begin_delete("qb", "abc", **ARGS)


def test_operation_identity_cannot_be_reused_by_other_source(interlock):
    release(interlock)
    with pytest.raises(PermissionError):
        release(interlock, source="error_torrent_delete", error_confirmed=True)
    interlock.instance.remove_torrents_tag.assert_called_once()


def test_persistence_failure_leaves_local_protection(interlock):
    interlock.plugin.save_data.side_effect = RuntimeError("disk full")
    with pytest.raises(RuntimeError):
        release(interlock)
    assert interlock.api.query("qb", "abc")["protected"]
    assert interlock.api.query("qb", "abc")["state"] == "interrupted"
    assert interlock.instance.mock_calls == []


def test_reload_during_tag_io_cannot_grant_stale_authorization(interlock):
    def io(**kwargs):
        interlock.service._tasks = interlock.service._load_tasks()
        interlock.service._refresh_guard()
    interlock.instance.remove_torrents_tag.side_effect = io
    result = release(interlock)
    assert result["state"] == "interrupted" and result["protected"]
    with pytest.raises(PermissionError):
        interlock.api.begin_delete("qb", "abc", **ARGS)


def test_stop_during_tag_io_cannot_resurrect_guard(interlock):
    interlock.instance.remove_torrents_tag.side_effect = lambda **kwargs: interlock.service.stop()
    result = release(interlock)
    assert result["state"] == "interrupted"
    assert not interlock.service._guard.enabled
    assert interlock.service.get_task("qb", "abc").interlock_state == "interrupted"


def test_failure_accounting_after_observe_change_has_zero_tag_writes(interlock):
    release(interlock)
    interlock.api.begin_delete("qb", "abc", **ARGS)
    interlock.plugin._module_observe_only["hr"] = True
    result = interlock.api.finish_delete("qb", "abc", **ARGS, success=False)
    assert result["protected"] and result["state"] == "restored"
    assert "tag restore failed" in result["error"]
    interlock.instance.set_torrents_tag.assert_not_called()


def test_unconfirmed_state_survives_failure_accounting(interlock):
    release(interlock)
    interlock.api.begin_delete("qb", "abc", **ARGS)
    interlock.service._guard.mark_unconfirmed()
    result = interlock.api.finish_delete("qb", "abc", **ARGS, success=False)
    assert result["unconfirmed"] and result["protected"]
    interlock.instance.set_torrents_tag.assert_not_called()


def test_rejected_persistence_reserves_no_downloader_writes(interlock):
    interlock.plugin.save_data.side_effect = None
    interlock.plugin.save_data.return_value = False
    with pytest.raises(RuntimeError):
        release(interlock)
    assert interlock.api.query("qb", "abc")["protected"]
    assert interlock.instance.mock_calls == []


def test_restore_io_is_outside_service_lock(interlock):
    release(interlock)
    interlock.api.begin_delete("qb", "abc", **ARGS)
    def restore(**kwargs):
        assert not interlock.service._lock._is_owned()
        assert interlock.api.query("qb", "abc")["protected"]
    interlock.instance.set_torrents_tag.side_effect = restore
    assert interlock.api.finish_delete("qb", "abc", **ARGS, success=False)["protected"]


def test_invalid_source_cannot_reserve_or_report_deletion(interlock):
    release(interlock)
    interlock.instance.reset_mock()
    for method, extra in ((interlock.api.begin_delete, {}), (interlock.api.finish_delete, {"success": False})):
        with pytest.raises(PermissionError):
            method("qb", "abc", **(ARGS | {"source": "sync_delete"}), **extra)
    assert interlock.instance.mock_calls == []
    assert interlock.api.query("qb", "abc")["state"] == "released"


def test_unprotected_task_is_not_given_a_new_release(interlock):
    task = interlock.service._tasks["qb:abc"]
    task.hr_status = interlock.module.HrStatus.COMPLIANT
    interlock.service._refresh_guard()
    with pytest.raises(PermissionError):
        release(interlock)
    assert interlock.instance.mock_calls == []
    assert interlock.service.get_task("qb", "abc").interlock_state == ""
