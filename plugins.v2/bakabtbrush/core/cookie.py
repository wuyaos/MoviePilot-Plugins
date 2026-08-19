"""Cookie 获取：手动配置优先，空值时从 MoviePilot CookieCloud 补取。"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from urllib.parse import urlparse


BAKABT_HOST = "bakabt.me"


def find_cookie_for_url(cookies: Mapping[str, str] | None, site_url: str) -> str:
    """按 DNS 后缀边界匹配 CookieCloud 域名，避免 evilbakabt.me 误命中。"""
    host = (urlparse(site_url).hostname or "").lower().rstrip(".")
    if not host or not cookies:
        return ""

    for raw_domain, cookie in cookies.items():
        domain = str(raw_domain).lower().strip().lstrip(".").rstrip(".")
        if not domain or not cookie:
            continue
        if host == domain or host.endswith(f".{domain}"):
            return str(cookie).strip()
    return ""


def fetch_cookiecloud_cookie(site_url: str) -> str:
    """使用 MoviePilot CookieCloud 获取单站 Cookie；不记录 Cookie 内容。"""
    try:
        from app.helper.cookiecloud import CookieCloudHelper

        cookies, _ = CookieCloudHelper().download()
        return find_cookie_for_url(cookies or {}, site_url)
    except Exception:
        return ""


def resolve_cookie(
    configured_cookie: str,
    site_url: str,
    cookiecloud_fetcher: Callable[[str], str] = fetch_cookiecloud_cookie,
) -> tuple[str, bool]:
    """返回 (cookie, 是否需要写回插件配置)。"""
    cookie = (configured_cookie or "").strip()
    if cookie:
        return cookie, False

    fetched = (cookiecloud_fetcher(site_url) or "").strip()
    return fetched, bool(fetched)
