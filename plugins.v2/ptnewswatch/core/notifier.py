"""PTNewsWatch 聚合通知文本。"""
from __future__ import annotations

import re
from collections import defaultdict
from zoneinfo import ZoneInfo

from .models import ForumEntry
from .source_registry import SOURCE_BY_ID
from .url_utils import safe_content_link


def build_digest_text(
    entries: list[ForumEntry], *, timezone_name: str,
    failures: list[str] | None = None, maximum_chars: int = 2000,
) -> str:
    grouped = defaultdict(list)
    for entry in entries:
        grouped[entry.base_source_id or entry.source_id].append(entry)

    heading = f"📬 本轮新增 {len(entries)} 条"
    segments: list[str] = []
    omitted = 0
    for base_source_id, source_entries in grouped.items():
        source = SOURCE_BY_ID.get(base_source_id)
        title = source_entries[0].source_title or (source.title if source else base_source_id)
        group_started = False
        for entry in sorted(source_entries, key=lambda item: item.published_at):
            segment = ("" if group_started else f"\n\n【{title}】") + _entry_block(entry, timezone_name)
            if len(heading + "".join(segments) + segment) > maximum_chars:
                omitted += 1
                continue
            segments.append(segment)
            group_started = True

    text = heading + "".join(segments)
    if failures:
        block = "\n\n读取失败：" + "；".join(failures)
        if len(text + block) <= maximum_chars:
            text += block
    if omitted:
        suffix = f"\n\n…另有 {omitted} 条内容请查看插件数据页"
        while segments and len(text + suffix) > maximum_chars:
            segments.pop()
            omitted += 1
            text = heading + "".join(segments)
            suffix = f"\n\n…另有 {omitted} 条内容请查看插件数据页"
        if len(text + suffix) <= maximum_chars:
            text += suffix
    return text[:maximum_chars]


def _entry_block(entry: ForumEntry, timezone_name: str) -> str:
    local = entry.published_at.astimezone(ZoneInfo(timezone_name))
    author = f" · {entry.author}" if entry.author else ""
    title = _markdown_title(entry.title, entry.link)
    lines = [f"\n\n• {title}", f"  {local:%m-%d %H:%M}{author}"]
    if entry.content:
        for line in _summary(entry.content, 350).splitlines():
            lines.append(f"  {line}" if line else "")
    return "\n".join(lines)


def _markdown_title(title: str, link: str) -> str:
    escaped = re.sub(r"([\\\[\]])", r"\\\1", str(title or "无标题"))
    safe_link = safe_content_link(link)
    return f"[{escaped}](<{safe_link}>)" if safe_link else escaped


def _summary(value: str, maximum: int) -> str:
    value = str(value or "").strip()
    return value if len(value) <= maximum else value[:maximum - 1].rstrip() + "…"
