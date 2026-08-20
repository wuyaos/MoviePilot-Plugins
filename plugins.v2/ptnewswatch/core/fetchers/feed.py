"""RSS/Atom 网络抓取器。"""
from __future__ import annotations

from datetime import datetime, timezone

from ..models import SourceSpec
from ..parsers.feed import parse_feed
from .common import fetch_result, get_same_origin


class FeedFetcher:
    def __init__(self, *, timeout: int = 30, proxy_url: str | None = None):
        self.timeout = timeout
        self.proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None

    def fetch(self, source: SourceSpec, *, cookie: str = "", ua: str = ""):
        headers = {
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
            "User-Agent": ua or "Mozilla/5.0 PTNewsWatch/0.2",
            "Referer": _origin(source.url),
        }
        if cookie:
            headers["Cookie"] = cookie
        fetched_at = datetime.now(timezone.utc)
        try:
            response = get_same_origin(
                source.url, origin_url=source.url, headers=headers,
                proxies=self.proxies, timeout=self.timeout, context="来源",
            )
            response.raise_for_status()
            return fetch_result(
                source, True, entries=parse_feed(response.content, source),
                fetched_at=fetched_at,
            )
        except Exception as error:
            return fetch_result(source, False, error=str(error), fetched_at=fetched_at)


def _origin(url: str) -> str:
    from urllib.parse import urlsplit

    parsed = urlsplit(url)
    return f"{parsed.scheme}://{parsed.netloc}/"
