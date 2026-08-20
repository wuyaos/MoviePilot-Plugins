from datetime import datetime, timezone

from core.models import ForumEntry
from core.notifier import build_digest_text


def test_digest_groups_sources_and_adds_failures():
    entry = ForumEntry(
        "fengchao_pt", "1", "Title", "Author", "Summary",
        "https://example.com/1", datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc),
    )
    text = build_digest_text([entry], timezone_name="Asia/Shanghai", failures=["TJUPT（Cookie失效）"])
    assert "蜂巢 · PT生态" in text
    assert "08-19 20:00" in text
    assert "TJUPT（Cookie失效）" in text


def test_digest_links_title_without_standalone_original_url():
    entry = ForumEntry(
        "fengchao_pt", "2", "开放注册公告", "Author", "公告摘要",
        "https://example.com/topic/2", datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc),
    )
    text = build_digest_text([entry], timezone_name="Asia/Shanghai")
    assert "[开放注册公告](<https://example.com/topic/2>)" in text
    assert text.count(entry.link) == 1
    assert entry.link not in {line.strip() for line in text.splitlines()}
    assert "【PT 论坛资讯动态】" not in text


def test_digest_truncates_on_complete_entry_boundary():
    entries = [
        ForumEntry(
            "fengchao_pt", str(index), f"标题{index}", "Author", f"BODY_{index}_" + "字" * 80,
            f"https://example.com/{index}", datetime(2026, 8, 19, 12, index, tzinfo=timezone.utc),
        )
        for index in range(3)
    ]
    text = build_digest_text(entries, timezone_name="Asia/Shanghai", maximum_chars=320)
    assert len(text) <= 320
    assert "内容请查看插件数据页" in text
    for entry in entries:
        linked = f"[{entry.title}](<{entry.link}>)" in text
        assert (f"BODY_{entry.entry_id}_" in text) == linked
