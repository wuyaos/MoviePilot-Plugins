"""PTNewsWatch URL 规范化与凭据边界校验。"""
from __future__ import annotations

from ipaddress import ip_address
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit


def normalize_url(value: str) -> str:
    parsed = urlsplit(str(value or "").strip())
    scheme = parsed.scheme.lower()
    hostname = (parsed.hostname or "").lower().rstrip(".")
    port = parsed.port
    netloc = hostname
    if port and not (scheme == "https" and port == 443):
        netloc = f"{hostname}:{port}"
    path = parsed.path or "/"
    query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)), doseq=True)
    return urlunsplit((scheme, netloc, path, query, ""))


def validate_source_url(value: str, site_domain: str) -> str:
    normalized = normalize_url(value)
    parsed = urlsplit(normalized)
    if parsed.scheme != "https":
        raise ValueError("仅允许 HTTPS 来源地址")
    host = parsed.hostname or ""
    if not host:
        raise ValueError("来源地址缺少域名")
    if _is_private_host(host):
        raise ValueError("来源地址不能指向本机或内网")
    domain = str(site_domain or "").lower().rstrip(".")
    if domain and host != domain and not host.endswith(f".{domain}"):
        raise ValueError(f"来源地址域名必须属于 {domain}")
    return normalized


def safe_content_link(value: str, base_url: str = "") -> str:
    target = urljoin(base_url, str(value or "").strip())
    parsed = urlsplit(target)
    return target if parsed.scheme.lower() in {"http", "https"} and parsed.netloc else ""


def same_origin(left: str, right: str) -> bool:
    a = urlsplit(normalize_url(left))
    b = urlsplit(normalize_url(right))
    return a.scheme == b.scheme and a.netloc == b.netloc


def _is_private_host(host: str) -> bool:
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".localhost"):
        return True
    try:
        address = ip_address(host)
    except ValueError:
        return False
    return any((
        address.is_private,
        address.is_loopback,
        address.is_link_local,
        address.is_reserved,
        address.is_unspecified,
    ))
