import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).parents[3]
PKG = ROOT / "plugins.v3" / "autoptcheckin"
sys.path.insert(0, str(PKG.parent))


def load(name):
    return importlib.import_module(f"autoptcheckin.{name}")

import importlib

def test_statuses_and_reward():
    m = load("core.models")
    assert {s.value for s in m.SignStatus} >= {"success", "already", "unconfirmed", "auth_failed"}
    assert m.extract_reward_sentence("签到奖励：12 魔力") == "12 魔力"


def test_statuses_use_unified_six_values():
    m = load("core.models")
    assert {s.value for s in m.SignStatus} >= {"success", "already", "unconfirmed", "auth_failed", "cancelled"}
    assert m.unify_result("unconfirmed")[0] == "pending"


def test_migration_preview_is_idempotent_and_read_only():
    m = load("core.migration")
    config = {"cron": "0 9 * * *", "onlyonce": True}
    sources = {"AutoPtCheckin": {"status": "ready", "config": config}}
    first = m.build_preview(sources, {}, {"sites": []})
    second = m.build_preview(sources, {}, {"sites": []})
    assert first == second and list(first["changes"]) == ["cron"]
    assert config == {"cron": "0 9 * * *", "onlyonce": True}


