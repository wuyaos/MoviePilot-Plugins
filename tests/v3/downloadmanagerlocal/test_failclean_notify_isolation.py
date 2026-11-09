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
