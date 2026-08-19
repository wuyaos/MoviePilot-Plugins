"""RSS 2.0 与 Atom 统一解析为 ForumEntry。"""
from __future__ import annotations

import hashlib
import html as html_lib
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin

from ..models import ForumEntry, SourceSpec


def parse_feed(payload: str | bytes, source: SourceSpec) -> list[ForumEntry]:
    root = ET.fromstring(payload)
    if _local(root.tag) == "rss":
        return _parse_rss(root, source)
    if _local(root.tag) == "feed":
        return _parse_atom(root, source)
    raise ValueError("不支持的 Feed 格式")


def _parse_rss(root: ET.Element, source: SourceSpec) -> list[ForumEntry]:
    entries = []
    channel = next((node for node in root if _local(node.tag) == "channel"), None)
    if channel is None:
        return entries
    for item in channel:
        if _local(item.tag) != "item":
            continue
        title = _child_text(item, "title")
        link = _child_text(item, "link")
        guid = _child_text(item, "guid")
        content = _child_text(item, "encoded") or _child_text(item, "description")
        author = _child_text(item, "creator") or _child_text(item, "author")
        published = _parse_time(_child_text(item, "pubDate"))
        entries.append(_entry(source, guid or link, title, author, content, link, published))
    return entries


def _parse_atom(root: ET.Element, source: SourceSpec) -> list[ForumEntry]:
    entries = []
    for item in root:
        if _local(item.tag) != "entry":
            continue
        title = _child_text(item, "title")
        entry_id = _child_text(item, "id")
        link = ""
        for child in item:
            if _local(child.tag) == "link" and child.attrib.get("href"):
                if child.attrib.get("rel", "alternate") in ("alternate", ""):
                    link = child.attrib["href"]
                    break
        content = _child_text(item, "content") or _child_text(item, "summary")
        author = ""
        author_node = next((child for child in item if _local(child.tag) == "author"), None)
        if author_node is not None:
            author = _child_text(author_node, "name")
        published = _parse_time(_child_text(item, "updated") or _child_text(item, "published"))
        entries.append(_entry(source, entry_id or link, title, author, content, link, published))
    return entries


def _entry(source, raw_id, title, author, content, link, published):
    link = urljoin(source.url, link or "")
    clean_content = _clean_content(content)
    entry_id = raw_id.strip() if raw_id else ""
    if not entry_id:
        raw = f"{source.source_id}\0{title}\0{published.isoformat()}\0{clean_content}"
        entry_id = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return ForumEntry(
        source_id=source.source_id,
        entry_id=entry_id,
        title=html_lib.unescape(title or "").strip(),
        author=html_lib.unescape(author or "").strip(),
        content=clean_content,
        link=link,
        published_at=published,
    )


def _parse_time(value: str) -> datetime:
    value = (value or "").strip()
    if not value:
        return datetime.now(timezone.utc)
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _child_text(node: ET.Element, local_name: str) -> str:
    child = next((item for item in node if _local(item.tag) == local_name), None)
    return "" if child is None else " ".join("".join(child.itertext()).split())


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].split(":")[-1]


def _clean_content(value: str) -> str:
    value = re.sub(r"<(script|style)\b[^>]*>[\s\S]*?</\1>", " ", value or "", flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    return " ".join(html_lib.unescape(value).split())
