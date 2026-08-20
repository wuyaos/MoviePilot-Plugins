"""PTerClub/TJUPT 共用 NexusPHP 论坛主题页解析器。"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

from lxml import etree

from ..models import ForumEntry, SourceSpec
from .content import html_to_text, normalize_text

_POST_ID = re.compile(r"^pid(\d+)$")
_ABSOLUTE_TIME = re.compile(r"\b(20\d{2}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\b")
_URL_ONLY = re.compile(r"^https?://\S+$", re.I)
_PROFILE_LINE = re.compile(r"^(帖子|上传|下载|分享率|做种积分)\s*[：:]", re.I)


def parse_nexus_topic(html_text: str, source: SourceSpec) -> list[ForumEntry]:
    root = etree.HTML(html_text or "")
    if root is None:
        raise ValueError("论坛页面无法解析")
    entries = []
    for header in root.xpath('//table[starts-with(@id,"pid")]'):
        match = _POST_ID.match(header.get("id") or "")
        if not match:
            continue
        post_id = match.group(1)
        author = _text(header.xpath('.//a[contains(@href,"userdetails.php")][1]'))
        published = _parse_header_time(header, source.timezone_name)
        body = _find_body_node(header, post_id)
        raw_content = _extract_body_text(body)
        title, content = _split_title_content(raw_content, post_id)
        entries.append(ForumEntry(
            source_id=source.source_id,
            entry_id=f"{source.source_id}:{post_id}",
            title=title,
            author=author,
            content=content,
            link=_post_link(source.url, post_id),
            published_at=published,
            source_title=source.title,
            base_source_id=source.base_id,
        ))
    return entries


def extract_previous_page_url(html_text: str, page_url: str) -> str:
    root = etree.HTML(html_text or "")
    if root is None:
        return ""
    href = root.xpath('//a[contains(normalize-space(string(.)),"上一页")][1]/@href')
    return urljoin(page_url, href[0]) if href else ""


def is_login_page(final_url: str, html_text: str) -> bool:
    lower = (html_text or "").lower()
    return (
        "login.php" in (final_url or "").lower()
        or ('type="password"' in lower and "login.php" in lower)
        or ("name=\"password\"" in lower and "登录" in html_text)
    )


def _parse_header_time(header, timezone_name: str) -> datetime:
    titles = header.xpath('.//span[@title]/@title')
    raw = next((value for value in titles if _ABSOLUTE_TIME.search(value)), "")
    if not raw:
        match = _ABSOLUTE_TIME.search(" ".join(header.xpath('.//text()')))
        raw = match.group(1) if match else ""
    if not raw:
        return datetime.now(timezone.utc)
    parsed = datetime.strptime(_ABSOLUTE_TIME.search(raw).group(1), "%Y-%m-%d %H:%M:%S")
    return parsed.replace(tzinfo=ZoneInfo(timezone_name)).astimezone(timezone.utc)


def _find_body_node(header, post_id: str):
    exact = header.xpath(f'following::*[@id="pid{post_id}body"][1]')
    if exact:
        return exact[0]
    tables = header.xpath('following::table[contains(concat(" ",normalize-space(@class)," ")," post ")][1]')
    if not tables:
        tables = header.xpath('following::table[1]')
    if not tables:
        return None
    table = tables[0]
    # 不允许宽泛回退跨到下一帖 header，宁可跳过无法确认的正文。
    if (table.get("id") or "").startswith("pid"):
        return None
    cells = table.xpath('.//tr[1]/td')
    return cells[-1] if cells else table


def _extract_body_text(node) -> str:
    if node is None:
        return ""
    clone = etree.fromstring(etree.tostring(node))
    for unwanted in clone.xpath(
        './/script | .//style | .//form | .//button | '
        './/*[contains(concat(" ",normalize-space(@class)," ")," toolbox ")] | '
        './/*[contains(concat(" ",normalize-space(@class)," ")," magic ")] | '
        './/*[contains(concat(" ",normalize-space(@class)," ")," bonus ")]'
    ):
        parent = unwanted.getparent()
        if parent is not None:
            parent.remove(unwanted)
    return html_to_text(etree.tostring(clone, encoding="unicode", method="html"))


def _split_title_content(content: str, post_id: str) -> tuple[str, str]:
    lines = content.splitlines()
    title_index = None
    for index, line in enumerate(lines):
        candidate = line.strip().lstrip("- ").strip()
        if not candidate or _URL_ONLY.match(candidate) or _PROFILE_LINE.match(candidate):
            continue
        title_index = index
        break
    if title_index is None:
        return f"论坛回复 #{post_id}", content
    title = lines[title_index].strip().lstrip("- ").strip()[:120]
    remaining = lines[:title_index] + lines[title_index + 1:]
    while remaining and not remaining[0].strip():
        remaining.pop(0)
    while remaining and not remaining[-1].strip():
        remaining.pop()
    return title, normalize_text("\n".join(remaining))


def _text(nodes) -> str:
    if not nodes:
        return ""
    return " ".join("".join(nodes[0].itertext()).split())


def _post_link(source_url: str, post_id: str) -> str:
    parsed = urlsplit(source_url)
    query = parse_qs(parsed.query)
    query["page"] = [f"p{post_id}"]
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query, doseq=True), f"pid{post_id}"))
