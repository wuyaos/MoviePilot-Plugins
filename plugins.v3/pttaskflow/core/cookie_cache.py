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


_CF_ONLY_COOKIES = {
    "cf_clearance", "__cf_bm", "__cfruid", "__cf_chl_tk",
    "cf_chl_prog", "cf_chl_seq", "cf_chl_rc_ni", "cf_chl_rc_m",
}


def cookiecloud_cookies() -> dict:
    """只读宿主 CookieCloud，返回 {domain: cookie串}；不可用返回空 dict。

    V3 无 CookieCloudHelper：按宿主 settings 与 CryptoJsUtils 自解密。
    本地/远端模式均只读，不写回、不记录凭据。
    """
    import json
    from hashlib import md5
    from pathlib import Path
    from urllib.parse import quote, urlsplit

    result: dict = {}
    try:
        from app.sdk.config import settings
        from app.sdk.utilities import CryptoJsUtils

        key = (settings.COOKIECLOUD_KEY or "").strip()
        password = (settings.COOKIECLOUD_PASSWORD or "").strip()
        if not key or not password:
            return result
        if settings.COOKIECLOUD_ENABLE_LOCAL:
            # KEY 只作为单个文件名，禁止路径穿越；本地模式不降级发远端请求。
            if key in {".", ".."} or any(char in key for char in "/\\:"):
                return result
            data = json.loads(
                (Path(settings.COOKIE_PATH) / f"{key}.json").read_text(encoding="utf-8"))
        else:
            from app.sdk.network import RequestUtils

            server = (settings.COOKIECLOUD_HOST or "").strip().rstrip("/")
            parsed = urlsplit(server)
            if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                    or parsed.query or parsed.fragment):
                return result
            response = RequestUtils(timeout=20, content_type="application/json").get_res(
                url=f"{server}/get/{quote(key, safe='')}", allow_redirects=False,
                raise_exception=True)
            if response is None:
                return result
            try:
                if response.status_code != 200:
                    return result
                data = response.json()
            finally:
                response.close()
        crypt_key = md5(f"{key}-{password}".encode()).hexdigest()[:16].encode()
        payload = json.loads(
            CryptoJsUtils.decrypt(data["encrypted"], crypt_key).decode("utf-8"))
        groups = payload.get("cookie_data", payload)
        by_domain: dict = {}
        for items in groups.values():
            for item in items:
                domain = str(item.get("domain", "")).lower()
                name, value = item.get("name"), item.get("value")
                if not isinstance(name, str) or not name or not isinstance(value, str):
                    continue
                if name in {"CookieAutoDeleteBrowsingDataCleanup",
                            "CookieAutoDeleteCleaningDiscarded"}:
                    continue
                if any(char in name + value for char in "\r\n;") or "=" in name:
                    continue
                by_domain.setdefault(domain, {})[name] = value
        for domain, cookies in by_domain.items():
            if cookies and not set(cookies) <= _CF_ONLY_COOKIES:
                result[domain] = "; ".join(f"{n}={v}" for n, v in cookies.items())
    except Exception:
        return {}
    return result
