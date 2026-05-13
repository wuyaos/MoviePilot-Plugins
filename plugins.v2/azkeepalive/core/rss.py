# input: rss_url, feedparser, requests
# output: fetch_rss(), parse_feed() → List[FeedItem]
# pos: RSS 拉取与解析层，供 keepalive runner 调用

from __future__ import annotations

import re
from typing import Any

from app.log import logger

from .models import FeedItem, parse_size_bytes

USER_AGENT = "AZ_KeepAlive/1.0"
REQUEST_HEADERS = {"User-Agent": USER_AGENT, "Referer": "https://animez.to/"}


def fetch_rss(rss_url: str, timeout: int = 30, proxies: dict | None = None) -> str:
    """拉取 RSS XML 文本"""
    from app.utils.http import RequestUtils
    res = RequestUtils(
        headers=REQUEST_HEADERS, proxies=proxies, timeout=timeout
    ).get_res(url=rss_url)
    if not res:
        raise RuntimeError(f"RSS 请求失败: {rss_url}")
    if res.status_code != 200:
        raise RuntimeError(f"RSS 返回 {res.status_code}: {rss_url}")
    res.encoding = res.encoding or "utf-8"
    return res.text


def parse_feed(xml_text: str, max_items: int = 50) -> list[FeedItem]:
    """解析 RSS XML 为 FeedItem 列表"""
    try:
        import feedparser
    except ImportError:
        raise RuntimeError("缺少依赖: feedparser，请在插件目录放置 requirements.txt")

    feed = feedparser.parse(xml_text)
    entries = list(feed.entries or [])[:max_items]
    items: list[FeedItem] = []
    for entry in entries:
        url = _torrent_url(entry)
        if not url:
            continue
        title = re.sub(r"\s+", " ", str(entry.get("title") or "untitled")).strip()
        size_bytes, size_text = _parse_size(entry)
        items.append(FeedItem(
            title=title, url=url,
            seeders=_parse_seeders(entry),
            size_bytes=size_bytes, size_text=size_text,
        ))
    logger.debug(f"RSS 解析完成: {len(items)} 条有效条目")
    return items


def filter_eligible(items: list[FeedItem], min_seeders: int) -> list[FeedItem]:
    """筛选并排序候选种子（体积小优先）"""
    eligible = [
        it for it in items
        if it.seeders is not None and it.seeders >= min_seeders
        and it.size_bytes is not None
    ]
    eligible.sort(key=lambda it: (it.size_bytes or 0, -(it.seeders or 0)))
    return eligible


def _torrent_url(entry: Any) -> str:
    for enc in entry.get("enclosures", []) or []:
        href = str(enc.get("href") or enc.get("url") or "").strip()
        if href:
            return href
    for link in entry.get("links", []) or []:
        href = str(link.get("href") or "").strip()
        ltype = str(link.get("type") or "").lower()
        if href and ("bittorrent" in ltype or _is_dl_url(href)):
            return href
    return str(entry.get("link") or "").strip()


def _is_dl_url(url: str) -> bool:
    low = url.lower()
    return ".torrent" in low or "download" in low or "dl.php" in low


def _parse_seeders(entry: Any) -> int | None:
    val = _val_from_entry(entry, {"seed", "seeds", "seeder", "seeders"})
    if val is None:
        return None
    m = re.search(r"\d+", str(val).replace(",", ""))
    return int(m.group(0)) if m else None


def _parse_size(entry: Any) -> tuple[int | None, str]:
    val = _val_from_entry(entry, {"size", "length", "contentlength"})
    if val is None:
        for enc in entry.get("enclosures", []) or []:
            val = enc.get("length") or enc.get("size")
            if val is not None:
                break
    if val is None:
        return None, ""
    text = str(val).strip()
    return parse_size_bytes(text), text


def _val_from_entry(entry: Any, names: set[str]) -> Any:
    targets = {re.sub(r"[^a-z0-9]+", "_", n.lower()).strip("_") for n in names}
    for key, value in entry.items():
        norm = re.sub(r"[^a-z0-9]+", "_", str(key).lower()).strip("_")
        if norm in targets or any(norm.endswith(f"_{t}") for t in targets):
            return value
    return None


def visit_site(site_url: str, timeout: int = 30, proxies: dict | None = None) -> bool:
    """访问站点首页，模拟用户活跃。返回是否成功。"""
    from app.utils.http import RequestUtils
    try:
        res = RequestUtils(
            headers=REQUEST_HEADERS, proxies=proxies, timeout=timeout,
        ).get_res(url=site_url)
        if res and res.status_code == 200:
            logger.info(f"AZ站点访问成功: {site_url}")
            return True
        code = res.status_code if res else "无响应"
        logger.warning(f"AZ站点访问异常: {site_url} [{code}]")
    except Exception as e:
        logger.warning(f"AZ站点访问失败: {site_url} - {e}")
    return False
