# input: KDBX WebDAV 配置、MoviePilot 站点名称与 URL
# output: KeePass 中匹配 URL 域名的用户名、密码、TOTP 当前验证码
# pos: SiteRefresh 凭据源，负责只读下载 KDBX、解密并按 URL 域名匹配条目
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from time import monotonic
from typing import Optional
from urllib.parse import urlparse
import ipaddress

from app.log import logger
from app.utils.http import RequestUtils
from app.utils.string import StringUtils


@dataclass
class Credential:
    domain: str
    username: str
    password: str
    two_step_code: str = ""


class KeePassWebDavProvider:
    _cache_key: str = ""
    _cache_at: float = 0.0
    _cache_bytes: bytes = b""

    def __init__(self, url: str, username: str, password: str, master_password: str, cache_minutes: int = 5):
        self.url = (url or "").strip()
        self.username = username or ""
        self.password = password or ""
        self.master_password = master_password or ""
        self.cache_seconds = max(0, int(cache_minutes or 0)) * 60

    def get_credential(self, site_name: str, site_url: str) -> tuple[Optional[Credential], str]:
        if not self.url or not self.master_password:
            return None, "KeePass WebDAV URL 或主密码未配置"
        if not _safe_webdav_url(self.url):
            return None, "KeePass WebDAV URL 必须使用 HTTPS（localhost/私网除外）"
        try:
            kp = self._open_keepass()
        except Exception as exc:
            return None, f"KeePass 打开失败：{exc}"
        return _find_entry_credential(kp.entries, site_name, site_url)

    def _open_keepass(self):
        from pykeepass import PyKeePass
        return PyKeePass(BytesIO(self._download_bytes()), password=self.master_password)

    def _download_bytes(self) -> bytes:
        key = f"{self.url}|{self.username}|{self.password}"
        if self.cache_seconds and self._cache_key == key and self._cache_bytes:
            if monotonic() - self._cache_at <= self.cache_seconds:
                return self._cache_bytes
        headers = {}
        auth = None
        if self.username or self.password:
            auth = (self.username, self.password)
        res = RequestUtils(headers=headers, timeout=60).get_res(url=self.url, auth=auth)
        if not res or res.status_code != 200 or not res.content:
            raise RuntimeError(f"WebDAV 下载失败：{res.status_code if res else '无响应'}")
        self.__class__._cache_key = key
        self.__class__._cache_at = monotonic()
        self.__class__._cache_bytes = res.content
        return res.content


def _find_entry_credential(entries, site_name: str, site_url: str) -> tuple[Optional[Credential], str]:
    site_host = _host(site_url)
    exact = []
    root_candidates = []
    for entry in entries:
        entry_domain = _entry_domain(getattr(entry, "url", ""))
        if not entry_domain:
            continue
        if entry_domain == site_host:
            exact.append((entry, entry_domain))
        elif _same_root(entry_domain, site_host):
            root_candidates.append((entry, entry_domain))
    candidates = exact or (root_candidates if len(root_candidates) == 1 else [])
    if len(root_candidates) > 1 and not exact:
        return None, f"KeePass 找到多个同根域名条目匹配 {site_name}，请把条目 URL 精确到站点 host"
    if not candidates:
        return None, f"KeePass 未找到匹配站点 {site_name} 的 URL 域名条目"
    credential = _entry_to_credential(*candidates[0])
    if credential.username and credential.password:
        return credential, ""
    return None, f"KeePass 条目 {credential.domain} 缺少用户名或密码"


def _entry_to_credential(entry, domain: str) -> Credential:
    return Credential(
        domain=domain,
        username=getattr(entry, "username", "") or "",
        password=getattr(entry, "password", "") or "",
        two_step_code=_entry_totp(entry),
    )


def _entry_totp(entry) -> str:
    otp = getattr(entry, "otp", None)
    if otp:
        return _normalize_totp_material(str(otp))
    props = getattr(entry, "custom_properties", {}) or {}
    for key in ("otp", "totp", "TOTP", "TOTP Seed", "otp_secret"):
        value = props.get(key)
        if value:
            return _normalize_totp_material(str(value))
    return ""


def _normalize_totp_material(value: str) -> str:
    value = (value or "").strip()
    if value.isdigit() and 4 <= len(value) <= 8:
        return value
    if value.startswith("otpauth://"):
        try:
            import pyotp
            return pyotp.parse_uri(value).secret
        except Exception as exc:
            logger.warning(f"SiteRefresh: KeePass TOTP URI 解析失败：{exc}")
            return ""
    return value.replace(" ", "")


def _same_root(a: str, b: str) -> bool:
    return bool(a and b and (StringUtils.get_url_domain(a) or a) == (StringUtils.get_url_domain(b) or b))


def _safe_webdav_url(url: str) -> bool:
    parsed = urlparse(url or "")
    if parsed.scheme == "https":
        return True
    if parsed.scheme != "http":
        return False
    host = parsed.hostname or ""
    if host in ("localhost", "127.0.0.1", "::1"):
        return True
    try:
        return ipaddress.ip_address(host).is_private
    except ValueError:
        return False


def _entry_domain(url: str) -> str:
    host = _host(url)
    return host or (StringUtils.get_url_domain(url) or "").lower().strip()


def _host(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url if "://" in url else f"https://{url}")
    return (parsed.hostname or "").lower().strip()
