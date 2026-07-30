"""CookieCloud 进程内缓存；不持久化、不记录 Cookie 内容。"""
from urllib.parse import urlparse


class CookieCache:
    def __init__(self):
        self._values = {}

    def get(self, site_url, loader, refresh=False):
        hostname = (urlparse(site_url).hostname or "").lower()
        if not hostname:
            return ""
        if not refresh and hostname in self._values:
            return self._values[hostname]
        cookies = loader() or {}
        for domain, cookie in cookies.items():
            normalized = str(domain).lstrip(".").lower()
            if cookie and (hostname == normalized or hostname.endswith("." + normalized)):
                self._values[hostname] = str(cookie)
                return str(cookie)
        self._values.pop(hostname, None)
        return ""

    def clear(self, site_url):
        hostname = (urlparse(site_url).hostname or "").lower()
        self._values.pop(hostname, None)
