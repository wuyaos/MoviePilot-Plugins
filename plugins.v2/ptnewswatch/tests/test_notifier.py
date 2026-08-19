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
