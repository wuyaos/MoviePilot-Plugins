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
    if binding is not None:
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
