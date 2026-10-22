"""Build the offline NexusPHP declaration table from the QNAP exports."""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).parents[1]
SITES = Path("D:/tmp/qnap-sites-full.json")
CONFIG = Path("D:/tmp/qnap-exp/ac_export.json")
COOKIE_LOG = Path("C:/Users/wff19/AppData/Local/Temp/pi-bash-d36f972573bcf8a5.log")
OUTPUT = ROOT / "plugins.v3/autoptcheckin/sites/native/generic_sites.json"
NATIVE_ALIASES = {"pterclub.net": "pterclub", "kp.m-team.cc": "mteam"}
EXCLUDED_SPECIAL = {"darkland", "digitalcore", "mteam"}


def host(value: str) -> str:
    return (urlsplit(value).hostname or value).lower().removeprefix("www.")


def generic_id(value: str, used: set[str]) -> str:
    parts = host(value).split(".")
    if len(parts) > 1:
        parts.pop()
    result = re.sub(r"[.-]+", "_", "_".join(parts)).strip("_") or "site"
    while result in used:
        result += "_g"
    return result


def main() -> None:
    site_rows = json.loads(SITES.read_text(encoding="utf-8"))["data"]
    config = json.loads(CONFIG.read_text(encoding="utf-8"))["data"]
    if isinstance(config, str):
        config = ast.literal_eval(config)
    selected = {str(item) for item in config["sign_sites"] + config["login_sites"]}
    rows = [row for row in site_rows + config.get("custom_sites_data", []) if str(row.get("id")) in selected]
    native_dir = ROOT / "plugins.v3/autoptcheckin/sites/native"
    native_ids, native_hosts = set(), set()
    for path in native_dir.glob("*.py"):
        if path.name == "__init__.py":
            continue
        text = path.read_text(encoding="utf-8")
        id_match = re.search(r'^\s*id\s*=\s*["\']([^"\']+)', text, re.M)
        url_match = re.search(r'^\s*url\s*=\s*["\']([^"\']+)', text, re.M)
        if id_match:
            native_ids.add(id_match.group(1))
        if url_match:
            native_hosts.add(host(url_match.group(1)))
    cookie_hosts = set()
    for line in COOKIE_LOG.read_text(encoding="utf-8").splitlines():
        if "c_secure_pass" in line:
            cookie_hosts.add(host(line.split()[0].lstrip(".")))
    declarations, excluded = [], []
    used = set(native_ids)
    seen_hosts = set()
    for row in rows:
        url, row_host = row.get("url", ""), host(row.get("url", ""))
        row_id = NATIVE_ALIASES.get(row_host, str(row.get("id")))
        if row_host in seen_hosts:
            continue
        seen_hosts.add(row_host)
        if row_id in EXCLUDED_SPECIAL or str(row.get("name", "")).lower() in EXCLUDED_SPECIAL:
            reason = "special-case"
        elif row_id in native_ids or row_host in native_hosts:
            reason = "native-covered"
        elif row_host not in cookie_hosts:
            reason = "no-c_secure_pass-evidence"
        else:
            site_id = generic_id(url, used)
            used.add(site_id)
            declarations.append({"id": site_id, "name": row.get("name") or site_id,
                                 "url": url, "attendance_path": "/attendance.php"})
            continue
        excluded.append({"id": row.get("id"), "name": row.get("name"), "url": url, "reason": reason})
    declarations.sort(key=lambda item: item["id"])
    OUTPUT.write_text(json.dumps(declarations, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"declarations": len(declarations), "excluded": len(excluded),
                      "excluded_rows": excluded}, ensure_ascii=False))


if __name__ == "__main__":
    main()
