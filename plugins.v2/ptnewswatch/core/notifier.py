"""PTNewsWatch 聚合通知文本。"""
from __future__ import annotations

from collections import defaultdict
from zoneinfo import ZoneInfo

from .models import ForumEntry
from .source_registry import SOURCE_BY_ID


def build_digest_text(
    entries: list[ForumEntry], *, timezone_name: str,
    failures: list[str] | None = None, maximum_chars: int = 2000,
) -> str:
    grouped = defaultdict(list)
    for entry in entries:
        grouped[entry.source_id].append(entry)
    lines = ["【PT 论坛资讯动态】", ""]
    for source_id, source_entries in grouped.items():
        source = SOURCE_BY_ID.get(source_id)
        lines.append(f"【{source.title if source else source_id}】")
        for entry in sorted(source_entries, key=lambda item: item.published_at):
            local = entry.published_at.astimezone(ZoneInfo(timezone_name))
            author = f" · {entry.author}" if entry.author else ""
            lines.append(f"• {local:%m-%d %H:%M}{author}  {entry.title}")
            if entry.content:
                lines.append(f"  {_summary(entry.content, 300)}")
            if entry.link:
                lines.append(f"  {entry.link}")
        lines.append("")
    lines.append(f"本轮新增：{len(entries)} 条")
    if failures:
        lines.append("")
        lines.append("读取失败：" + "；".join(failures))
    text = "\n".join(lines).strip()
    return text if len(text) <= maximum_chars else text[:maximum_chars - 12] + "\n…内容已截断"


def _summary(value: str, maximum: int) -> str:
    value = " ".join((value or "").split())
    return value if len(value) <= maximum else value[:maximum - 1] + "…"
