"""从 MoviePilot 站点管理读取 NexusPHP 论坛 Cookie 与 UA。"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SiteAuth:
    cookie: str = ""
    ua: str = ""
    status: str = "missing"


def resolve_site_auth(domain: str) -> SiteAuth:
    try:
        from app.db.site_oper import SiteOper

        site = SiteOper().get_by_domain(domain)
        if not site:
            return SiteAuth(status="site_not_configured")
        cookie = (getattr(site, "cookie", "") or "").strip()
        ua = (getattr(site, "ua", "") or "").strip()
        if not cookie:
            return SiteAuth(ua=ua, status="cookie_missing")
        return SiteAuth(cookie=cookie, ua=ua, status="mp_site_cookie")
    except Exception:
        return SiteAuth(status="site_lookup_failed")
