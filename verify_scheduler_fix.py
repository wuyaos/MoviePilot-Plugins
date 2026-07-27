#!/usr/bin/env python3
"""验证本轮插件定时任务修复的版本、静态契约与本地 MoviePilot 注册状态。"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PLUGINS = {
    "TangRedPacketClaim": "tangredpacketclaim",
    "TangLottery": "tanglottery",
    "GGPTMedalBuyer": "ggptmedalbuyer",
    "CoverGen": "covergen",
    "AzKeepAlive": "azkeepalive",
    "YzyySignin": "yzyysignin",
    "SunnyPTSignin": "sunnyptsignin",
    "ForumSignin": "forumsignin",
    "TorrentTransfer": "torrenttransfer",
    "PtHitAndRun": "pthitandrun",
    "SiteAutoTask": "siteautotask",
    "PterMedalBuyer": "ptermedalbuyer",
    "MyPTMedalBuyer": "myptmedalbuyer",
    "AutoPtCheckin": "autoptcheckin",
    "FarmAuto": "farmauto",
    "RousiCheckin": "rousicheckin",
}


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def api_json(base_url: str, path: str, api_token: str):
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        headers={"X-API-KEY": api_token},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def static_verify() -> None:
    run(sys.executable, "-m", "compileall", "-q", "plugins.v2")
    run(sys.executable, "-m", "pytest", "plugins.v2/farmauto/tests", "-q")
    run(sys.executable, "-m", "pytest", "plugins.v2/siteautotask/tests", "-q")
    run("git", "diff", "--check")

    metadata = json.loads((ROOT / "package.v2.json").read_text(encoding="utf-8"))
    for plugin_id, directory in PLUGINS.items():
        source = (ROOT / "plugins.v2" / directory / "__init__.py").read_text(encoding="utf-8")
        match = re.search(r'plugin_version\s*=\s*"([0-9.]+)"', source)
        assert match, f"{plugin_id}: 未找到 plugin_version"
        version = match.group(1)
        assert metadata[plugin_id]["version"] == version, f"{plugin_id}: 版本不一致"
        assert f"v{version}" in metadata[plugin_id]["history"], f"{plugin_id}: 缺少 history"
    print(f"[OK] 静态、测试、版本元数据：{len(PLUGINS)} 个插件")


def runtime_verify(base_url: str, api_token: str) -> None:
    installed = set(api_json(base_url, "/api/v1/plugin/installed", api_token))
    schedules = api_json(base_url, f"/api/v1/dashboard/schedule2?token={api_token}", api_token)
    schedule_ids = [str(item.get("id") or "") for item in schedules]

    failures: list[str] = []
    for plugin_id in PLUGINS:
        if plugin_id not in installed:
            print(f"[SKIP] {plugin_id}: 本地 MP 未安装")
            continue
        config = api_json(base_url, f"/api/v1/plugin/{plugin_id}", api_token)
        enabled = bool(config.get("enabled", False))
        jobs = [job_id for job_id in schedule_ids if job_id.startswith(f"{plugin_id}_")]
        if enabled and not jobs:
            reason = []
            if config.get("cron") == "":
                reason.append("cron 为空")
            if plugin_id == "PtHitAndRun" and not config.get("downloader"):
                reason.append("未配置下载器")
            if reason:
                print(f"[SKIP] {plugin_id}: enabled 但无任务（{'、'.join(reason)}）")
            else:
                failures.append(f"{plugin_id}: enabled 但未注册任务")
        else:
            print(f"[OK] {plugin_id}: enabled={enabled}, jobs={jobs}")

    duplicates = sorted({job_id for job_id in schedule_ids if schedule_ids.count(job_id) > 1})
    if duplicates:
        failures.append(f"调度 ID 重复: {duplicates}")
    if failures:
        raise AssertionError("；".join(failures))
    print("[OK] 本地 MoviePilot 冷启动调度注册")


def main() -> None:
    static_verify()
    env_file = Path(os.environ.get("MOVIEPILOT_ENV_FILE", "/home/wuya/.config/moviepilot/app.env"))
    env = load_env(env_file)
    api_token = os.environ.get("API_TOKEN") or env.get("API_TOKEN", "")
    base_url = os.environ.get("MOVIEPILOT_BASE_URL", "http://127.0.0.1:7300")
    if not api_token:
        raise SystemExit(f"缺少 API_TOKEN；请设置环境变量或配置 {env_file}")
    try:
        runtime_verify(base_url, api_token)
    except urllib.error.URLError as error:
        raise SystemExit(f"无法访问本地 MoviePilot {base_url}: {error}") from error


if __name__ == "__main__":
    main()
