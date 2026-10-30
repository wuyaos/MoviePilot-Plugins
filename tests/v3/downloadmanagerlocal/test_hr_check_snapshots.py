"""H&R 状态检查回归：真实服务入口与快照应用，下载器和落盘边界离线替身。"""
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def hr_check(mp_stubs, monkeypatch):
    # 其他测试按需挂载过同名假包；每例重建真实子模块，并在退出时恢复。
    prefix = "app.plugins.downloadmanagerlocal."
    previous = {key: value for key, value in sys.modules.items() if key.startswith(prefix)}
    for key in previous:
        sys.modules.pop(key)
    try:
        module = mp_stubs("modules/hr/service.py", "modules.hr.service")
        service = module.HrService(Mock())
        service._config = module.HrConfig(enabled=True, downloaders=["qb"], auto_cleanup_days=0)
        service._tasks = {
            "qb:abc": module.HrTask(downloader="qb", hash="abc", title="sample"),
        }
        downloader = SimpleNamespace(type="qbittorrent", instance=Mock())
        monkeypatch.setattr(module, "downloader_services", lambda names: {"qb": downloader})
        # 只聚焦采样与任务存在性；不执行标签写入、通知、持久化和全局 guard 更新。
        monkeypatch.setattr(service, "_evaluate_all", Mock(return_value=0))
        monkeypatch.setattr(service, "_save_tasks", Mock())
        monkeypatch.setattr(service, "_refresh_guard", Mock())
        yield module, service, downloader
    finally:
        for key in list(sys.modules):
            if key.startswith(prefix):
                sys.modules.pop(key)
        sys.modules.update(previous)


def test_check_tasks_updates_snapshot_and_resets_each_cycle(hr_check):
    module, service, downloader = hr_check
    downloader.instance.get_torrents.return_value = [{
        "hash": "abc", "name": "sample", "size": 1024, "ratio": 1.5,
        "uploaded": 1536, "downloaded": 1024, "completion_on": 1234, "seeding_time": 321, "state": "uploading",
    }]

    result = service.check_tasks("回归")

    assert result["enabled"] is True
    assert result["deleted"] == 0
    assert service._tasks["qb:abc"].ratio == 1.5
    assert service._tasks["qb:abc"].completed_on == 1234
    assert service._tasks["qb:abc"].downloader_seeding_time == 321
    assert service._tasks["qb:abc"].uploaded == 1536
    service._save_tasks.assert_called_once()
    service._refresh_guard.assert_called_once()

    # 下一轮成功返回空列表，不得残留上一轮快照而误认为种子仍存在。
    downloader.instance.get_torrents.return_value = []
    result = service.check_tasks("回归")
    assert result["deleted"] == 1
    assert service._tasks["qb:abc"].deleted is True


@pytest.mark.parametrize("failed", [False, True])
def test_check_tasks_empty_or_failed_query(hr_check, failed):
    module, service, downloader = hr_check
    if failed:
        downloader.instance.get_torrents.side_effect = RuntimeError("offline")
    else:
        downloader.instance.get_torrents.return_value = []

    result = service.check_tasks("回归")

    assert result["failed_downloaders"] == (["qb"] if failed else [])
    assert result["deleted"] == (0 if failed else 1)
    assert service._tasks["qb:abc"].deleted is (not failed)



def test_transmission_snapshot_captures_completion_timestamp(hr_check):
    module, _, _ = hr_check
    torrent = SimpleNamespace(
        hashString="abc", name="sample", total_size=1024,
        done_date=SimpleNamespace(timestamp=lambda: 1234),
        upload_ratio=0.5, downloaded_ever=1024, uploaded_ever=512, secondsSeeding=5678,
        percent_done=1.0, added_date=1000, status="seeding",
    )

    snapshot = module.torrent_snapshot(torrent, "tr", "transmission", now=2000)

    assert snapshot.completed_on == 1234
    assert snapshot.downloader_seeding_time == 5678

def test_check_tasks_unavailable_downloader_preserves_task(hr_check, monkeypatch):
    module, service, downloader = hr_check
    service._config.downloaders = ["qb", "unavailable"]
    task = module.HrTask(downloader="unavailable", hash="abc", title="offline sample")
    service._tasks[task.key] = task
    downloader.instance.get_torrents.return_value = []

    result = service.check_tasks("回归")

    assert result["failed_downloaders"] == ["unavailable"]
    assert result["deleted"] == 1
    assert task.deleted is False
