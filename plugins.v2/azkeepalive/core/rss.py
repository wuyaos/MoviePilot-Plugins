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


def get_site_cookie(site_url: str) -> str:
    """从 CookieCloud 获取站点 Cookie"""
    if not site_url:
        return ""
    try:
        from urllib.parse import urlparse
        from app.helper.cookiecloud import CookieCloudHelper
        cookies, _ = CookieCloudHelper().download()
        if not cookies:
            return ""
        domain = urlparse(site_url).netloc
        for d, c in cookies.items():
            if domain.endswith(d):
                logger.debug(f"CookieCloud 匹配到 {domain} 的 Cookie")
                return c
    except Exception as e:
        logger.debug(f"CookieCloud 获取失败: {e}")
    return ""


def visit_site(
    site_url: str, cookie: str = "", timeout: int = 30, proxies: dict | None = None
) -> dict[str, Any]:
    """访问站点首页，解析用户信息。返回 {"ok": bool, ...stats}"""
    from app.utils.http import RequestUtils
    result: dict[str, Any] = {"ok": False}
    try:
        headers = {**REQUEST_HEADERS}
        if cookie:
            headers["Cookie"] = cookie
        res = RequestUtils(
            headers=headers, proxies=proxies, timeout=timeout,
        ).get_res(url=site_url)
        if not res or res.status_code != 200:
            logger.warning(f"AZ站点访问异常: {site_url} [{res.status_code if res else '无响应'}]")
            return result
        result["ok"] = True
        logger.info(f"AZ站点访问成功: {site_url}")
        if cookie:
            result.update(_parse_user_stats(res.text))
    except Exception as e:
        logger.warning(f"AZ站点访问失败: {site_url} - {e}")
    return result


def _parse_user_stats(html: str) -> dict[str, str]:
    """从页面 HTML 解析上传/下载/分享率/H&R 等用户信息"""
    stats: dict[str, str] = {}
    # 上传量
    m = re.search(r'[上UP]\w*[传load]\w*[：:]\s*([\d,.]+\s*[KMGTP]?i?B)', html, re.I)
    if m:
        stats["upload"] = m.group(1).strip()
    # 下载量
    m = re.search(r'[下Down]\w*[载load]\w*[：:]\s*([\d,.]+\s*[KMGTP]?i?B)', html, re.I)
    if m:
        stats["download"] = m.group(1).strip()
    # 分享率
    m = re.search(r'[分Share]\w*[享率atio]\w*[：:]\s*([\d,.]+|∞|Inf)', html, re.I)
    if m:
        stats["ratio"] = m.group(1).strip()
    # H&R
    m = re.search(r'H&R[：:\s]*(\d+)', html, re.I)
    if m:
        stats["hnr"] = m.group(1).strip()
    # 魔力值/Bonus
    m = re.search(r'[魔Bonus]\w*[力Points]\w*[：:]\s*([\d,.]+)', html, re.I)
    if m:
        stats["bonus"] = m.group(1).strip()
    if stats:
        logger.debug(f"AZ用户信息: {stats}")
    return stats
