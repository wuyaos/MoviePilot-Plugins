"""PTerClub/TJUPT 共用 NexusPHP 论坛主题页解析器。"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

from lxml import etree

from ..models import ForumEntry, SourceSpec

_POST_ID = re.compile(r"^pid(\d+)$")
_ABSOLUTE_TIME = re.compile(r"\b(20\d{2}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\b")


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
        body = _find_body_table(header)
        content = _extract_body_text(body)
        title = _entry_title(content, post_id)
        link = _post_link(source.url, post_id)
        entries.append(ForumEntry(
            source_id=source.source_id,
            entry_id=f"{source.source_id}:{post_id}",
            title=title,
            author=author,
            content=content,
            link=link,
            published_at=published,
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
        # 缺少绝对时间时仍保留消息；按抓取时刻排序并在状态中可见。
        return datetime.now(timezone.utc)
    parsed = datetime.strptime(_ABSOLUTE_TIME.search(raw).group(1), "%Y-%m-%d %H:%M:%S")
    return parsed.replace(tzinfo=ZoneInfo(timezone_name)).astimezone(timezone.utc)


def _find_body_table(header):
    bodies = header.xpath('./ancestor::div[1]/following-sibling::table[1]')
    if bodies:
        return bodies[0]
    bodies = header.xpath('following::table[contains(concat(" ", normalize-space(@class), " "), " post ")][1]')
    return bodies[0] if bodies else None


def _extract_body_text(table) -> str:
    if table is None:
        return ""
    cells = table.xpath('.//tr[1]/td[not(contains(concat(" ",normalize-space(@class)," ")," rowfollow "))]')
    node = cells[-1] if cells else table
    # 排除引用/奖励/工具箱等非正文块。
    for unwanted in node.xpath('.//*[contains(@class,"quote") or contains(@class,"toolbox") or contains(@class,"bonus")]'):
        unwanted.getparent().remove(unwanted)
    text = " ".join(part.strip() for part in node.xpath('.//text()') if part.strip())
    return " ".join(text.split())


def _entry_title(content: str, post_id: str) -> str:
    line = next((part.strip() for part in re.split(r"[\r\n]+", content) if part.strip()), "")
    return (line[:80] if line else f"论坛回复 #{post_id}")


def _text(nodes) -> str:
    if not nodes:
        return ""
    return " ".join("".join(nodes[0].itertext()).split())


def _post_link(source_url: str, post_id: str) -> str:
    parsed = urlsplit(source_url)
    query = parse_qs(parsed.query)
    query["page"] = [f"p{post_id}"]
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query, doseq=True), f"pid{post_id}"))
