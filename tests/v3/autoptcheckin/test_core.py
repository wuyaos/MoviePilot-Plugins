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


def test_credentials_order_and_refresh():
    m = load("core.credentials")
    resolver = m.CredentialResolver()
    spec = m.CredentialSpec(refresh="password")
    # uid 仅展示，不做冲突判断：候选按声明顺序，local_cookie 命中即返回
    candidates = {"cookiecloud": m.Credential("cookiecloud", "old", "u2"), "local_cookie": m.Credential("local_cookie", "new", "u1")}
    result = resolver.resolve(spec, candidates, "u1", lambda c: m.CredentialCheck("valid", c.uid))
    assert result.status == "valid" and result.credential.value == "new"
    renewed = m.Credential("local_cookie", "renewed", "u1")
    checks = iter([m.CredentialCheck("invalid", "u1"), m.CredentialCheck("valid", "u1")])
    result = resolver.resolve(spec, {"cookiecloud": m.Credential("cookiecloud", "expired", "u1")}, "u1",
                              lambda c: next(checks), lambda: renewed)
    assert result.status == "valid"
    assert result.credential == renewed


def test_verification_always_reads_and_unconfirmed():
    v = load("core.verification")
    called = []
    class Verifier:
        def parse(self, page, uid, date):
            called.append(page)
            return None
    result = v.verify_after_submit(lambda: "unparseable", Verifier(), "u1", "2026-01-01")
    assert result.status.value == "unconfirmed" and called == ["unparseable"]


def test_migration_preview_is_idempotent_and_read_only():
    m = load("core.migration")
    config = {"cron": "0 9 * * *", "onlyonce": True}
    sources = {"AutoPtCheckin": {"status": "ready", "config": config}}
    first = m.build_preview(sources, {}, {"sites": []})
    second = m.build_preview(sources, {}, {"sites": []})
    assert first == second and list(first["changes"]) == ["cron"]
    assert config == {"cron": "0 9 * * *", "onlyonce": True}


