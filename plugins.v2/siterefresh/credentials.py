# input: SiteRefresh 配置、MoviePilot 站点名称与 URL
# output: 登录凭据，优先 KeePass WebDAV，失败时手动配置兜底
# pos: SiteRefresh 凭据来源路由层，隔离 KeePass 与手动配置策略
from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse

from app.log import logger
from app.utils.string import StringUtils

from .keepass import Credential, KeePassWebDavProvider


def resolve_credential(config: dict, site_name: str, site_url: str) -> tuple[Optional[Credential], str]:
    if config.get("keepass_enabled", True):
        provider = KeePassWebDavProvider(
            url=config.get("keepass_webdav_url") or "",
            username=config.get("keepass_webdav_username") or "",
            password=config.get("keepass_webdav_password") or "",
            master_password=config.get("keepass_master_password") or "",
            cache_minutes=_safe_int(config.get("keepass_cache_minutes"), 5),
        )
        credential, msg = provider.get_credential(site_name=site_name, site_url=site_url)
        if credential:
            return credential, ""
        logger.info(f"SiteRefresh: {msg}，尝试手动配置兜底")
    return _resolve_manual(config.get("siteconf") or "", site_url)


def _safe_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _resolve_manual(siteconf: str, site_url: str) -> tuple[Optional[Credential], str]:
    for line in siteconf.splitlines():
        parsed = _parse_config_line(line)
        if parsed and _domain_matches(parsed.domain, site_url):
            return parsed, ""
    return None, "未获取到匹配站点配置"


def _parse_config_line(line: str) -> Optional[Credential]:
    line = (line or "").strip()
    if not line or line.startswith("#"):
        return None
    parts = [item.strip() for item in line.split("|")]
    domain = _normalize_config_domain(parts[0] if parts else "")
    if len(parts) < 3 or not domain or not parts[1] or not parts[2]:
        logger.error(f"SiteRefresh: 站点配置有误，已跳过：{parts[0] if parts else '<空域名>'}|***")
        return None
    return Credential(domain=domain, username=parts[1], password=parts[2], two_step_code=parts[3] if len(parts) >= 4 else "")


def _normalize_config_domain(config_domain: str) -> str:
    parsed = urlparse(config_domain if "://" in config_domain else f"https://{config_domain}")
    if parsed.username or parsed.password or parsed.path not in ("", "/"):
        return ""
    return (parsed.hostname or "").lower().strip()


def _domain_matches(config_domain: str, site_url: str) -> bool:
    parsed = urlparse(site_url or "")
    host = (parsed.hostname or parsed.netloc or "").lower().strip()
    root = (StringUtils.get_url_domain(site_url) or "").lower().strip()
    candidates = {x for x in (host, root) if x}
    return bool(config_domain and candidates and any(x == config_domain or x.endswith(f".{config_domain}") for x in candidates))
