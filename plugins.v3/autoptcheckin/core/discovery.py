"""未适配/改版站点的首页签到入口发现。"""
import re
from collections.abc import Callable

def discover_signin_target(fetch: Callable[[str], tuple[int, str]], home_url: str) -> str | None:
    status, page = fetch(home_url)
    if status == 404: return None
    for href, label in re.findall(r'href=["\']([^"\']+)["\'][^>]*>([^<]*)', page or "", re.I):
        if re.search(r"签到|attendance|check.?in|sign.?in", label + " " + href, re.I):
            return href
    return None
