from pathlib import Path

PLUGIN = Path(__file__).parents[3] / "plugins.v3" / "downloadmanagerlocal"

def test_failclean_is_disabled_and_cannot_delete():
    service = (PLUGIN / "modules/failclean/service.py").read_text(encoding="utf-8")
    assert '"deleted": 0' in service and '"cleaned": 0' in service
    assert "delete_media_file" not in service
    assert "delete_download_history_file" not in service

def test_failclean_has_no_runtime_registration():
    assert "TransferFailed" not in (PLUGIN / "__init__.py").read_text(encoding="utf-8")
    assert "FailCleanService" not in (PLUGIN / "core/lifecycle.py").read_text(encoding="utf-8")
    assert "DownloadCenterRepeatCleanup" not in (PLUGIN / "core/scheduler.py").read_text(encoding="utf-8")


def test_legacy_enabled_service_and_event_have_no_io(monkeypatch):
    import importlib
    import sys
    import types

    package_name = "_dml_retired_failclean_test"
    package = types.ModuleType(package_name)
    package.__path__ = [str(PLUGIN / "modules/failclean")]
    monkeypatch.setitem(sys.modules, package_name, package)
    try:
        service_module = importlib.import_module(package_name + ".service")
        events = importlib.import_module(package_name + ".events")

        class NoIO:
            def __getattr__(self, name):
                raise AssertionError(f"retired cleanup attempted IO: {name}")

        service = service_module.FailCleanService(NoIO()).init_module({
            "failcleanup_enabled": True,
            "failcleanup_clean_repeat": True,
            "failcleanup_notify": True,
        })
        assert service.handle_transfer_failed(NoIO())["deleted"] == 0
        assert service.cleanup_repeat_sources()["cleaned"] == 0
        assert service.clear_history()["removed"] == 0
        assert events.handle_transfer_failed_event(NoIO(), NoIO())["disabled"]
    finally:
        for name in list(sys.modules):
            if name.startswith(package_name + "."):
                sys.modules.pop(name, None)
