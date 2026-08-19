"""药丸 Atom Cookie：手工配置优先，空值时 CookieCloud 精确补取。"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from urllib.parse import urlparse


def find_cookie_for_url(cookies: Mapping[str, str] | None, site_url: str) -> str:
    host = (urlparse(site_url).hostname or "").lower().rstrip(".")
    if not host or not cookies:
        return ""
    for raw_domain, value in cookies.items():
        domain = str(raw_domain).lower().strip().lstrip(".").rstrip(".")
        if value and (host == domain or host.endswith(f".{domain}")):
            return str(value).strip()
    return ""


def fetch_cookiecloud_cookie(site_url: str) -> str:
    try:
        from app.helper.cookiecloud import CookieCloudHelper

        cookies, _ = CookieCloudHelper().download()
        return find_cookie_for_url(cookies or {}, site_url)
    except Exception:
        return ""


def resolve_invites_cookie(
    configured_cookie: str,
    *,
    site_url: str = "https://invites.fun/",
    fetcher: Callable[[str], str] = fetch_cookiecloud_cookie,
) -> tuple[str, bool]:
    """返回 (cookie, 是否需要完整回写插件配置)。"""
    configured = (configured_cookie or "").strip()
    if configured:
        return configured, False
    fetched = (fetcher(site_url) or "").strip()
    return fetched, bool(fetched)
