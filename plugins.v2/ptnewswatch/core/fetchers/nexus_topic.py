"""NexusPHP 主题最后两页抓取器。"""
from __future__ import annotations

from datetime import datetime, timezone

import requests

from ..auth.mp_site_cookie import SiteAuth
from ..models import SourceFetchResult, SourceSpec
from ..parsers.nexus_topic import extract_previous_page_url, is_login_page, parse_nexus_topic


class NexusTopicFetcher:
    def __init__(self, *, timeout: int = 30, proxy_url: str | None = None, pages: int = 2):
        self.timeout = timeout
        self.pages = min(5, max(1, pages))
        self.proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None

    def fetch(self, source: SourceSpec, auth: SiteAuth) -> SourceFetchResult:
        fetched_at = datetime.now(timezone.utc)
        if not auth.cookie:
            return SourceFetchResult(
                source.source_id, source.title, False,
                error="未找到 MoviePilot 站点 Cookie",
                auth_status=auth.status,
                fetched_at=fetched_at,
            )
        headers = {
            "Cookie": auth.cookie,
            "User-Agent": auth.ua or "Mozilla/5.0 PTNewsWatch/0.1",
            "Referer": source.url.split("#", 1)[0],
        }
        entries_by_id = {}
        url = source.url
        try:
            for _ in range(self.pages):
                if not url:
                    break
                response = requests.get(
                    url,
                    headers=headers,
                    proxies=self.proxies,
                    timeout=(5, self.timeout),
                    allow_redirects=True,
                )
                response.raise_for_status()
                if is_login_page(response.url, response.text):
                    raise PermissionError("论坛 Cookie 已失效")
                entries = parse_nexus_topic(response.text, source)
                if not entries:
                    raise ValueError("论坛最后一页未解析到帖子")
                for entry in entries:
                    entries_by_id[entry.entry_id] = entry
                url = extract_previous_page_url(response.text, response.url)
            return SourceFetchResult(
                source.source_id,
                source.title,
                True,
                entries=list(entries_by_id.values()),
                auth_status="mp_site_cookie",
                fetched_at=fetched_at,
            )
        except Exception as error:
            return SourceFetchResult(
                source.source_id,
                source.title,
                False,
                error=str(error),
                auth_status="cookie_invalid" if isinstance(error, PermissionError) else auth.status,
                fetched_at=fetched_at,
            )
