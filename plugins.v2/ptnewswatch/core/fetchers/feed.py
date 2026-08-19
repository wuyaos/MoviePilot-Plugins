"""RSS/Atom 网络抓取器。"""
from __future__ import annotations

from datetime import datetime, timezone

import requests

from ..models import SourceFetchResult, SourceSpec
from ..parsers.feed import parse_feed


class FeedFetcher:
    def __init__(self, *, timeout: int = 30, proxy_url: str | None = None):
        self.timeout = timeout
        self.proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None

    def fetch(self, source: SourceSpec, *, cookie: str = "", ua: str = "") -> SourceFetchResult:
        headers = {
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
            "User-Agent": ua or "Mozilla/5.0 PTNewsWatch/0.1",
            "Referer": _origin(source.url),
        }
        if cookie:
            headers["Cookie"] = cookie
        fetched_at = datetime.now(timezone.utc)
        try:
            response = requests.get(
                source.url,
                headers=headers,
                proxies=self.proxies,
                timeout=(5, self.timeout),
                allow_redirects=True,
            )
            response.raise_for_status()
            entries = parse_feed(response.content, source)
            return SourceFetchResult(
                source_id=source.source_id,
                source_title=source.title,
                success=True,
                entries=entries,
                auth_status="cookie" if cookie else "public",
                fetched_at=fetched_at,
            )
        except Exception as error:
            return SourceFetchResult(
                source_id=source.source_id,
                source_title=source.title,
                success=False,
                error=str(error),
                auth_status="cookie" if cookie else "public",
                fetched_at=fetched_at,
            )


def _origin(url: str) -> str:
    from urllib.parse import urlsplit

    parsed = urlsplit(url)
    return f"{parsed.scheme}://{parsed.netloc}/"
