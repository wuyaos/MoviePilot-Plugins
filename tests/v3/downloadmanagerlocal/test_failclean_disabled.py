"""失败清理停用契约：旧配置不能触发任何删除。"""

from pathlib import Path


PLUGIN = Path(__file__).parents[3] / "plugins.v3" / "downloadmanagerlocal"


def test_failclean_compat_stub_never_deletes():
    source = (PLUGIN / "modules/failclean/service.py").read_text(encoding="utf-8")
    assert "旧配置和历史导入仍可解析" in source
    assert '"deleted": 0' in source
    assert '"cleaned": 0' in source
    assert "delete_media_file" not in source
    assert "delete_download_history_file" not in source


def test_no_failclean_runtime_registration():
    init_source = (PLUGIN / "__init__.py").read_text(encoding="utf-8")
    lifecycle_source = (PLUGIN / "core" / "lifecycle.py").read_text(encoding="utf-8")
    scheduler_source = (PLUGIN / "core" / "scheduler.py").read_text(encoding="utf-8")

    assert "EventType.TransferFailed" not in init_source
    assert "FailCleanService" not in lifecycle_source
    assert "DownloadCenterRepeatCleanup" not in scheduler_source
