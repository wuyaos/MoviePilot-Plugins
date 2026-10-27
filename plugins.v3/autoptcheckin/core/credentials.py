"""凭据候选解析；已确认 Cookie 的持久化由 native 执行边界负责。"""
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Callable, Literal

# 仅由 Cloudflare 挑战 Cookie 构成的候选不能证明站点登录态
_CF_ONLY_COOKIES = {"cf_clearance", "__cf_bm", "__cfruid", "__cf_chl_tk", "cf_chl_prog", "cf_chl_seq", "cf_chl_rc_ni", "cf_chl_rc_m"}

@dataclass(frozen=True)
class CredentialSpec:
    kind: Literal["cookie", "api_key", "password"] = "cookie"
    cookie_sources: tuple[str, ...] = ("stored_cookie", "managed_site", "local_cookie", "cookiecloud")
    refresh: Literal["password"] | None = None
    identity_field: str = "uid"

@dataclass(frozen=True)
class Credential:
    source: str
    value: str = field(repr=False)
    uid: str = ""

    @property
    def fingerprint(self) -> str:
        return sha256(self.value.encode()).hexdigest()

@dataclass(frozen=True)
class CredentialCheck:
    status: Literal["valid", "invalid", "maintenance", "rate_limited", "timeout", "network_error"]
    uid: str = ""

@dataclass
class CredentialResolution:
    credential: Credential | None
    status: str
    reason: str = ""



def cookiecloud_candidate(url: str) -> CredentialResolution:
    """只读宿主 CookieCloud；不可用不等于站点认证失败，不记录异常或凭据。"""
    import json
    from hashlib import md5
    from pathlib import Path
    from urllib.parse import quote, urlsplit

    unavailable = CredentialResolution(None, "cookiecloud_unavailable")
    try:
        from app.sdk.config import settings
        from app.sdk.utilities import CryptoJsUtils

        host = (urlsplit(url).hostname or "").lower()
        key = (settings.COOKIECLOUD_KEY or "").strip()
        password = (settings.COOKIECLOUD_PASSWORD or "").strip()
        if not host or not key or not password:
            return unavailable
        if settings.COOKIECLOUD_ENABLE_LOCAL:
            # KEY 只作为单个文件名，禁止路径穿越；本地模式不降级发远端请求。
            if key in {".", ".."} or any(char in key for char in '/\\:'):
                return unavailable
            data = json.loads((Path(settings.COOKIE_PATH) / f"{key}.json").read_text(encoding="utf-8"))
        else:
            from app.sdk.network import RequestUtils

            server = (settings.COOKIECLOUD_HOST or "").strip().rstrip("/")
            parsed = urlsplit(server)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.query or parsed.fragment:
                return unavailable
            response = RequestUtils(timeout=20, content_type="application/json").get_res(
                url=f"{server}/get/{quote(key, safe='')}", allow_redirects=False,
                raise_exception=True)
            if response is None:
                return unavailable
            try:
                if response.status_code != 200:
                    return unavailable
                data = response.json()
            finally:
                response.close()
        crypt_key = md5(f"{key}-{password}".encode()).hexdigest()[:16].encode()
        payload = json.loads(CryptoJsUtils.decrypt(data["encrypted"], crypt_key).decode("utf-8"))
        groups = payload.get("cookie_data", payload)
        cookies = {}
        for items in groups.values():
            for item in items:
                domain = item.get("domain", "").lower()
                # 不按公共后缀/站点名猜测；只接受同 host 或显式父域 Cookie。
                matches = (host == domain.lstrip(".") or
                           (domain.startswith(".") and host.endswith(domain)))
                if not matches:
                    continue
                name, value = item.get("name"), item.get("value")
                if name in {"CookieAutoDeleteBrowsingDataCleanup", "CookieAutoDeleteCleaningDiscarded"}:
                    continue
                if not isinstance(name, str) or not name or not isinstance(value, str):
                    continue
                if any(char in name + value for char in "\r\n;") or "=" in name:
                    continue
                cookies[name] = value
        if not cookies or set(cookies) <= _CF_ONLY_COOKIES:
            return unavailable
        return CredentialResolution(Credential("cookiecloud", ";".join(
            f"{name}={value}" for name, value in cookies.items())), "valid")
    except Exception:
        return unavailable
