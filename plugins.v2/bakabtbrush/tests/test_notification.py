from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from core.config import BrushConfig
from core.models import BakaBTTorrent
from core.notification import build_notification
from core.runner import RunResult


def test_success_notification_uses_detail_link_and_local_time_without_utc(monkeypatch):
    monkeypatch.setattr("core.presentation._TZ", ZoneInfo("Asia/Shanghai"))
    item = BakaBTTorrent(
        torrent_id="1",
        title="Example",
        detail_url="https://bakabt.me/torrent/1/example",
        size_mb=548,
        published_at=datetime(2026, 8, 19, 21, 10, 49, tzinfo=timezone.utc),
        is_freeleech=True,
    )
    result = RunResult("success", (item,), (), "ok", 1, 2)

    title, text = build_notification(BrushConfig.from_mapping({}), result)

    assert title == "【BakaBT 刷流已加入 qB】"
    assert "[Example](https://bakabt.me/torrent/1/example)" in text
    assert "2026-08-20 05:10:49" in text
    assert "Z" not in text
    assert "UTC" not in text
    assert "详情：https://" not in text
