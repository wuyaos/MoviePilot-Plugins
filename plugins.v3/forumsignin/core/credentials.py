"""Resolve managed-site cookies and per-adapter local credentials."""
from dataclasses import dataclass, field
from urllib.parse import urlsplit

@dataclass(frozen=True)
class CredentialSpec:
    kind: str = "cookie"
    cookie_sources: tuple = ("managed_site", "local_cookie")
    refresh: str | None = None
    identity_field: str = "uid"

@dataclass(frozen=True)
class Credential:
    source: str
    value: str = field(default="", repr=False)
    ua: str = ""
    proxy: bool = False
    username: str = field(default="", repr=False)
    password: str = field(default="", repr=False)


def hostname(value):
    return (urlsplit(value if "://" in value else "https://" + value).hostname or "").lower()


def resolve(site, config, managed=()):
    spec = site["credential"]
    fields = site.get("fields", [])
    if spec.kind == "api":
        key = next((field["key"] for field in fields if field.get("type") == "password"), "")
        value = config.get(key, "").strip() if key else ""
        return Credential("local_api", value) if value else None
    binding = config.get(site["id"] + "_managed_site_id")
    matches = [row for row in managed if hostname(row.get("url", "")) == site["domain"]]
    if binding:  # 空串视为未绑定，避免写入 "" 后站点永远 UNCONFIRMED
        matches = [row for row in matches if str(row.get("id")) == str(binding)]
        if not matches:
            raise ValueError("managed_site_binding_missing")
    if len(matches) > 1:
        raise ValueError("managed_site_binding_required")
    if matches and matches[0].get("cookie"):
        row = matches[0]
        return Credential("managed_site", row["cookie"], row.get("ua") or "", bool(row.get("proxy")))
    cookie_key = next((field["key"] for field in fields if field.get("key", "").endswith("_cookie")), "")
    username_key = next((field["key"] for field in fields if "username" in field.get("key", "")), "")
    password_key = next((field["key"] for field in fields if "password" in field.get("key", "")), "")
    cookie = config.get(cookie_key, "").strip() if cookie_key else ""
    username = config.get(username_key, "").strip() if username_key else ""
    password = config.get(password_key, "") if password_key else ""
    if cookie or (username and password):
        return Credential("local_cookie", cookie, username=username, password=password)
    return None


def cookiecloud_cookie(url):
    """只读宿主 CookieCloud，返回匹配域名的 Cookie 串；不可用返回空串，不记录凭据。"""
    import json
    from hashlib import md5
    from pathlib import Path
    from urllib.parse import quote

    host = hostname(url)
    try:
        from app.sdk.config import settings
        from app.sdk.utilities import CryptoJsUtils

        key = (settings.COOKIECLOUD_KEY or "").strip()
        password = (settings.COOKIECLOUD_PASSWORD or "").strip()
        if not host or not key or not password:
            return ""
        if settings.COOKIECLOUD_ENABLE_LOCAL:
            if key in {".", ".."} or any(char in key for char in "/\\:"):
                return ""
            data = json.loads((Path(settings.COOKIE_PATH) / f"{key}.json").read_text(encoding="utf-8"))
        else:
            from app.sdk.network import RequestUtils

            server = (settings.COOKIECLOUD_HOST or "").strip().rstrip("/")
            parsed = urlsplit(server)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                return ""
            response = RequestUtils(timeout=20, content_type="application/json").get_res(
                url=f"{server}/get/{quote(key, safe='')}", allow_redirects=False, raise_exception=True)
            if response is None or response.status_code != 200:
                return ""
            data = response.json()
        crypt_key = md5(f"{key}-{password}".encode()).hexdigest()[:16].encode()
        payload = json.loads(CryptoJsUtils.decrypt(data["encrypted"], crypt_key).decode("utf-8"))
        pairs = []
        for items in payload.get("cookie_data", payload).values():
            for item in items:
                domain = (item.get("domain") or "").lower()
                if not (host == domain.lstrip(".") or (domain.startswith(".") and host.endswith(domain))):
                    continue
                name, value = item.get("name"), item.get("value")
                if isinstance(name, str) and name and isinstance(value, str):
                    pairs.append((name, value))
        return "; ".join(f"{name}={value}" for name, value in pairs)
    except Exception:
        return ""
