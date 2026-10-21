"""Only host-managed and local credentials; no login or renewal."""
from dataclasses import dataclass, field
from urllib.parse import urlsplit

@dataclass(frozen=True)
class CredentialSpec:
    kind: str = "cookie"
    cookie_sources: tuple = ("managed_site", "local_cookie")
    refresh: None = None
    identity_field: str = "uid"

@dataclass(frozen=True)
class Credential:
    source: str
    value: str = field(repr=False)
    ua: str = ""
    proxy: bool = False


def hostname(value):
    return (urlsplit(value if "://" in value else "https://" + value).hostname or "").lower()


def resolve(site, config, managed=()):
    if site["credential"].kind == "api":
        value = config.get("fengchao_api_key", "").strip()
        return Credential("local_api", value) if value else None
    binding = config.get(site["id"] + "_managed_site_id")
    matches = [row for row in managed if hostname(row.get("url", "")) == site["domain"]]
    if binding is not None:
        matches = [row for row in matches if str(row.get("id")) == str(binding)]
        if not matches:
            raise ValueError("managed_site_binding_missing")
    if len(matches) > 1:
        raise ValueError("managed_site_binding_required")
    if matches and matches[0].get("cookie"):
        row = matches[0]
        return Credential("managed_site", row["cookie"], row.get("ua") or "", bool(row.get("proxy")))
    value = config.get(site["id"] + "_cookie", "").strip()
    return Credential("local_cookie", value) if value else None
