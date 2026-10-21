#!/bin/bash
# Local ForumSignin regression: offline tests + authorized local install only.
set -euo pipefail
cd "$(dirname "$0")/../.."
micromamba run -n base python -X utf8 -m pytest tests/v3/forumsignin -q
micromamba run -n base python -m json.tool package.v3.json >/dev/null
test -f plugins.v3/forumsignin/dist/assets/remoteEntry.js
echo "json-dist-ok"
micromamba run -n base python -X utf8 - <<'PY'
import json
import os
from pathlib import Path
import urllib.request

key = os.environ.get("MP_LOCAL_API_KEY", "").strip()
if not key:
    key_file = Path("D:/tmp/.mp_local_key")
    if key_file.exists():
        key = key_file.read_text(encoding="utf-8").strip()
if not key:
    raise SystemExit("MP_LOCAL_API_KEY or local key file required for runtime verification")
base = "http://127.0.0.1:17430"
log = Path("D:/test/MoviePilot-v3/config/logs/moviepilot.log")
start = log.stat().st_size
request = urllib.request.Request(
    base + "/api/v1/plugin/install/ForumSignin?repo_url=local%3A%2F%2FForumSignin&force=true",
    headers={"X-API-KEY": key})
with urllib.request.urlopen(request, timeout=60) as response:
    result = json.load(response)
if result.get("success") is not True:
    raise SystemExit("install-failed")
expected = json.loads(Path("package.v3.json").read_text(encoding="utf-8"))["ForumSignin"]["version"]
with log.open("rb") as stream:
    stream.seek(start)
    fresh = stream.read().decode("utf-8", errors="replace")
if "Error adding plugin route" in fresh:
    raise SystemExit("route-error")
if f"ForumSignin 版本：{expected}" not in fresh and f"ForumSignin 版本: {expected}" not in fresh:
    raise SystemExit("installed-version-log-not-confirmed")
print(f"ForumSignin {expected} installed; route-ok")
print("forumsignin-final-verify-ok")
PY
