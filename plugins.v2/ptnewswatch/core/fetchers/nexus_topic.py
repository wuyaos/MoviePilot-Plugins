"""NexusPHP 主题最后两页抓取器。"""
from __future__ import annotations

from datetime import datetime, timezone

from ..auth.mp_site_cookie import SiteAuth
from ..models import SourceSpec
from ..parsers.nexus_topic import extract_previous_page_url, is_login_page, parse_nexus_topic
from ..url_utils import same_origin
from .common import fetch_result, get_same_origin


class NexusTopicFetcher:
    def __init__(self, *, timeout: int = 30, proxy_url: str | None = None, pages: int = 2):
        self.timeout = timeout
        self.pages = min(5, max(1, pages))
        self.proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None

    def fetch(self, source: SourceSpec, auth: SiteAuth):
        fetched_at = datetime.now(timezone.utc)
        if not auth.cookie:
            return fetch_result(
                source, False, error="未找到 MoviePilot 站点 Cookie",
                fetched_at=fetched_at,
            )
        headers = {
            "Cookie": auth.cookie,
            "User-Agent": auth.ua or "Mozilla/5.0 PTNewsWatch/0.2",
            "Referer": source.url.split("#", 1)[0],
        }
        entries_by_id = {}
        url = source.url
        try:
            for _ in range(self.pages):
                if not url:
                    break
                response = get_same_origin(
                    url, origin_url=source.url, headers=headers,
                    proxies=self.proxies, timeout=self.timeout, context="论坛",
                )
                response.raise_for_status()
                if is_login_page(response.url, response.text):
                    raise PermissionError("论坛 Cookie 已失效")
                entries = parse_nexus_topic(response.text, source)
                if not entries:
                    if not entries_by_id:
                        raise ValueError("论坛最后一页未解析到帖子")
                    break
                for entry in entries:
                    entries_by_id[entry.entry_id] = entry
                previous = extract_previous_page_url(response.text, response.url)
                if previous and not same_origin(source.url, previous):
                    raise PermissionError("论坛上一页链接指向非同源地址")
                url = previous
            return fetch_result(
                source, True, entries=list(entries_by_id.values()),
                fetched_at=fetched_at,
            )
        except Exception as error:
            return fetch_result(source, False, error=str(error), fetched_at=fetched_at)
