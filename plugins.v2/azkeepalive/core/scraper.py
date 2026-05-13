# input: site_url, cookie, 种子页 HTML
# output: 种子列表解析, 站点访问, CookieCloud 获取
# pos: 页面解析层，替代原 RSS 解析

from __future__ import annotations

import re
from typing import Any

from app.log import logger

from .models import FeedItem, parse_size_bytes

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
BASE_HEADERS = {"User-Agent": USER_AGENT}


def fetch_torrents(
    site_url: str, cookie: str = "", timeout: int = 30,
    proxies: dict | None = None, freeleech: bool = True, page: int = 1,
) -> list[FeedItem]:
    """从种子列表页解析种子信息（支持分页）"""
    from app.utils.http import RequestUtils
    base = f"{site_url.rstrip('/')}/torrents?q=&adult=&anime_id=&uploader="
    if freeleech:
        base += "&freeleech=1"
    url = f"{base}&page={page}"
    headers = {**BASE_HEADERS}
    if cookie:
        headers["Cookie"] = cookie
    res = RequestUtils(
        headers=headers, proxies=proxies, timeout=timeout,
    ).get_res(url=url)
    if not res or res.status_code != 200:
        code = res.status_code if res else "无响应"
        raise RuntimeError(f"种子页请求失败: [{code}] {url}")
    res.encoding = res.encoding or "utf-8"
    items = _parse_torrent_rows(res.text, site_url)
    logger.debug(f"第{page}页解析: {len(items)} 条种子")
    return items


def _parse_torrent_rows(html: str, site_url: str) -> list[FeedItem]:
    """从 HTML 解析种子行"""
    items: list[FeedItem] = []
    # 匹配 torrent-link: <a class="torrent-link" href="...">TITLE</a>
    row_pattern = re.compile(
        r'<a\s+class="torrent-link"\s+href="([^"]+)"[^>]*>\s*(.*?)\s*</a>',
        re.DOTALL,
    )
    # 匹配同行 td: size / seeders（td[2] 和 td[3]）
    td_pattern = re.compile(r'<td[^>]*>\s*(.*?)\s*</td>', re.DOTALL)

    # 按 <tr> 分割
    tr_blocks = re.split(r'<tr[^>]*>', html)
    for block in tr_blocks:
        link_m = row_pattern.search(block)
        if not link_m:
            continue
        href = link_m.group(1).strip()
        title = re.sub(r'<[^>]+>', '', link_m.group(2)).strip()
        title = re.sub(r'\s+', ' ', title)

        tds = td_pattern.findall(block)
        # td[0]=标题列, td[1]=书签, td[2]=体积, td[3]=做种, td[4]=下载中, td[5]=完成
        size_text = re.sub(r'<[^>]+>', '', tds[2]).strip() if len(tds) > 2 else ""
        seeders_text = re.sub(r'<[^>]+>', '', tds[3]).strip() if len(tds) > 3 else ""

        size_bytes = parse_size_bytes(size_text)
        seeders = int(seeders_text) if seeders_text.isdigit() else None
        dl_url = f"{href}/download" if href else ""
        is_free = 'Free Download' in block or 'freeleech' in block.lower()

        items.append(FeedItem(
            title=title, url=dl_url,
            seeders=seeders, size_bytes=size_bytes, size_text=size_text,
            is_free=is_free,
        ))
    logger.debug(f"页面解析: {len(items)} 条种子")
    return items


def filter_eligible(
    items: list[FeedItem], min_seeders: int, max_size_gb: float = 10.0,
    require_free: bool = True,
) -> list[FeedItem]:
    """筛选并排序候选种子（体积小优先）"""
    max_bytes = int(max_size_gb * 1024**3)
    eligible = [
        it for it in items
        if it.seeders is not None and it.seeders >= min_seeders
        and it.size_bytes is not None and it.size_bytes <= max_bytes
        and (not require_free or it.is_free)
    ]
    eligible.sort(key=lambda it: (it.size_bytes or 0, -(it.seeders or 0)))
    return eligible


def get_site_cookie(site_url: str) -> str:
    """从 CookieCloud 获取站点 Cookie"""
    if not site_url:
        return ""
    try:
        from urllib.parse import urlparse
        from app.helper.cookiecloud import CookieCloudHelper
        cookies, msg = CookieCloudHelper().download()
        if not cookies:
            logger.warning(f"CookieCloud 未返回 cookies: {msg}")
            return ""
        domain = urlparse(site_url).netloc
        # 双向匹配
        for d, c in cookies.items():
            if domain.endswith(d) or d.endswith(domain):
                logger.info(f"CookieCloud 匹配: site={domain} → cookie_key={d}")
                return c
        logger.warning(f"CookieCloud 中无 {domain} 的 Cookie；可用域名: {list(cookies.keys())[:10]}")
    except Exception as e:
        logger.warning(f"CookieCloud 获取失败: {e}")
    return ""


def visit_site(
    site_url: str, cookie: str = "", timeout: int = 30, proxies: dict | None = None
) -> dict[str, Any]:
    """访问站点首页，解析用户信息"""
    from app.utils.http import RequestUtils
    result: dict[str, Any] = {"ok": False}
    try:
        headers = {**BASE_HEADERS}
        if cookie:
            headers["Cookie"] = cookie
        res = RequestUtils(
            headers=headers, proxies=proxies, timeout=timeout,
        ).get_res(url=site_url)
        if not res or res.status_code != 200:
            logger.warning(f"站点访问异常: [{res.status_code if res else '无响应'}]")
            return result
        result["ok"] = True
        logger.info(f"AZ站点访问成功: {site_url} (HTML {len(res.text)} bytes)")
        # 始终尝试解析（cookie 已由调用方传递，无需再次判断）
        stats = _parse_user_stats(res.text)
        if stats:
            result.update(stats)
        else:
            has_bar = "ratio-bar" in res.text
            has_login = "Sign in" in res.text or "LOGIN" in res.text[:3000].upper()
            logger.warning(f"用户信息解析为空 ratio-bar={has_bar} login页={has_login} "
                           f"cookie长度={len(cookie)}")
    except Exception as e:
        logger.warning(f"站点访问失败: {e}")
    return result


def _parse_user_stats(html: str) -> dict[str, str]:
    """从 ratio-bar 解析用户信息，兼容 HTML entity / 多行 SVG / a/span"""
    import html as html_lib
    stats: dict[str, str] = {}
    # 用位置窗口代替懒惰闭合标签匹配，避免 li 内嵌 div 导致提前截断
    bar_m = re.search(r'<div[^>]+class="[^"]*ratio-bar[^"]*"', html)
    source = html[bar_m.start():bar_m.start() + 6000] if bar_m else html
    li_blocks = re.findall(r'<li\b[\s\S]*?</li>', source)
    key_map = {
        "Uploaded": "upload", "Downloaded": "download", "Ratio": "ratio",
        "Buffer (Upload - Download)": "buffer", "Active Seeds": "seeds",
        "Active Leeches": "leeches", "Bonus Points": "bonus",
        "Hit & Run": "hnr", "Reseed Requests": "reseed",
    }
    for block in li_blocks:
        title_m = re.search(r'(?:data-bs-original-title|data-original-title|aria-label|title)="([^"]+)"', block)
        if not title_m:
            continue
        key = html_lib.unescape(title_m.group(1).strip())
        mapped = key_map.get(key)
        if not mapped:
            continue
        text = re.sub(r'<svg[\s\S]*?</svg>', ' ', block)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = html_lib.unescape(re.sub(r'\s+', ' ', text)).strip()
        for prefix in ("BP:", "H&R:", "Reseed:"):
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
                break
        if text:
            stats[mapped] = text
    if stats:
        logger.info(f"AZ用户信息解析成功: {stats}")
    return stats
