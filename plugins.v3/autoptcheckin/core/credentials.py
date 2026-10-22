"""凭据只在内存中流转；持久化仅保存明确失效候选的指纹。"""
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Callable, Literal

# 仅由 Cloudflare 挑战 Cookie 构成的候选不能证明站点登录态
_CF_ONLY_COOKIES = {"cf_clearance", "__cf_bm", "__cfruid", "__cf_chl_tk", "cf_chl_prog", "cf_chl_seq", "cf_chl_rc_ni", "cf_chl_rc_m"}

@dataclass(frozen=True)
class CredentialSpec:
    kind: Literal["cookie", "api_key"] = "cookie"
    cookie_sources: tuple[str, ...] = ("cookiecloud", "managed_site", "local_cookie")
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

class CredentialResolver:
    def __init__(self, invalid_fingerprints: set[str] | None = None):
        self.invalid_fingerprints = invalid_fingerprints if invalid_fingerprints is not None else set()

    def select_cookie(self, candidates: dict[str, Credential], bound_uid: str = '') -> CredentialResolution:
        """试点先选择 Cookie；身份校验在 runner 的新页面前读中执行。"""
        for source in CredentialSpec().cookie_sources:
            candidate = candidates.get(source)
            if candidate is None or not candidate.value:
                continue
            if candidate.fingerprint not in self.invalid_fingerprints:
                return CredentialResolution(candidate, 'valid')
        return CredentialResolution(None, 'auth_failed', '站点管理中缺少可用 Cookie')

    def resolve(self, spec: CredentialSpec, candidates: dict[str, Credential], bound_uid: str,
                validate: Callable[[Credential], CredentialCheck],
                refresh: Callable[[], Credential] | None = None) -> CredentialResolution:
        explicitly_invalid = False
        for source in spec.cookie_sources:
            candidate = candidates.get(source)
            if candidate is None or not candidate.value:
                continue
            if candidate.fingerprint in self.invalid_fingerprints:
                explicitly_invalid = True
                continue
            try:
                check = validate(candidate)
            except Exception:
                return CredentialResolution(None, "network_error", "凭证校验不可达，未触发续期")
            if check.status == "valid":
                return CredentialResolution(Credential(source, candidate.value, check.uid), "valid")
            if check.status != "invalid":
                return CredentialResolution(None, check.status, "未明确失效，不续期或切换凭证")
            explicitly_invalid = True
            self.invalid_fingerprints.add(candidate.fingerprint)
        # 无候选不等同于明确认证失效；阶段1不做静默首次登录。
        if explicitly_invalid and spec.refresh == "password" and refresh:
            try:
                candidate = refresh()
                check = validate(candidate)
            except Exception:
                return CredentialResolution(None, "network_error", "续期校验不可达")
            if check.status == "valid":
                return CredentialResolution(Credential(candidate.source, candidate.value, check.uid), "valid")
            return CredentialResolution(None, "unconfirmed", "续期未通过身份校验")
        return CredentialResolution(None, "auth_failed", "没有已验证凭证")


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
