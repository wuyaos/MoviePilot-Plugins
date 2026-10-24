"""蜂巢 PT 人生快照推送（pt_life）契约：归一化、payload 幂等、挂接行为。"""
import asyncio
from types import SimpleNamespace

import pytest

from forum_under_test import ForumSignin
from forum_under_test.integrations.pt_life import (StatsNotReady, collect_site_statistics,
                                                   push_snapshot)


def row(**over):
    data = {"name": "蜂巢", "userid": "42", "username": "u", "user_level": "3",
            "upload": "1024", "download": -5, "bonus": "77.5", "seeding": 3,
            "seeding_size": None, "join_at": "2024-01-02"}
    data.update(over)
    return data


def managed():
    return {"蜂巢": {"url": "https://fengchao.chat", "id": 7}}


def test_normalize_maps_madrays_fields():
    sites = collect_site_statistics(collector=lambda: ([row()], managed()))
    assert sites == [{"name": "蜂巢", "domain": "https://fengchao.chat", "mpSiteId": "7",
                      "siteUserId": "42", "username": "u", "userLevel": "3",
                      "upload": 1024, "download": 0, "bonus": 77.5,
                      "seeding": 3, "seedingSize": 0, "joinAt": "2024-01-02"}]


@pytest.mark.parametrize("bad", [row(name=""), row(error="timeout"), "junk", None])
def test_invalid_rows_skipped(bad):
    assert collect_site_statistics(collector=lambda: ([bad, row()], managed()))[0]["name"] == "蜂巢"


def test_cap_200_and_dedupe_by_collector():
    rows = [row(name=f"s{i}") for i in range(201)]
    sites = collect_site_statistics(collector=lambda: (rows, {}))
    assert len(sites) == 200 and sites[-1]["name"] == "s199"


def test_no_usable_rows_raises_not_ready():
    with pytest.raises(StatsNotReady):
        collect_site_statistics(collector=lambda: ([row(name=""), row(error="x")], managed()))


def test_snapshot_payload_and_idempotent_batch():
    calls = []

    def request(method, path, **kwargs):
        calls.append((method, path, kwargs["json"]))
        return {"ok": True}

    sites = collect_site_statistics(collector=lambda: ([row()], managed()))
    first = push_snapshot(request, instance_id="inst-1", plugin_version="3.1.18",
                          sites=sites, movie_pilot_version="v3.5", batch_id="b-1",
                          now=SimpleNamespace(isoformat=lambda: "2026-10-24T12:00:00"))
    push_snapshot(request, instance_id="inst-1", plugin_version="3.1.18",
                  sites=sites, batch_id="b-1")
    method, path, payload = calls[0]
    assert (method, path) == ("PUT", "/pt-life/snapshot")
    assert payload["schemaVersion"] == 2 and payload["instanceId"] == "inst-1"
    assert payload["clientBatchId"] == "b-1" and payload["moviePilotVersion"] == "v3.5"
    assert payload["collectedAt"] == "2026-10-24T12:00:00" and payload["sites"] == sites
    assert calls[1][2]["clientBatchId"] == "b-1"
    assert first == {"ok": True}


def test_push_rejects_empty_sites():
    with pytest.raises(StatsNotReady):
        push_snapshot(lambda *a, **k: {}, instance_id="i", plugin_version="p", sites=[])


class FakeAdapterClient:
    def __init__(self):
        self.closed = False

    def request(self, method, path, **kwargs):
        assert kwargs["json"]["schemaVersion"] == 2
        return SimpleNamespace(json=lambda: {"code": 0, "data": {"accepted": True}})

    def close(self):
        self.closed = True


def make_plugin(config=None, stats_error=None):
    plugin = ForumSignin()
    plugin.init_plugin({"enabled": True, "enabled_sites": ["fengchao"],
                        "fengchao_api_key": "synthetic", **(config or {})})
    if stats_error is not None:
        import forum_under_test as module
        def boom(collector=None):
            raise stats_error
        module.collect_site_statistics = boom
    else:
        import forum_under_test as module
        module.collect_site_statistics = lambda collector=None: [{"name": "蜂巢"}]
    fake = FakeAdapterClient()
    plugin._client = lambda site: fake
    return plugin, fake


def test_push_success_persists_result():
    plugin, fake = make_plugin()
    ok, detail = plugin._push_pt_life(retries=0)
    assert ok and detail == ""
    record = plugin._get("last_pt_life_push")
    assert record["success"] is True and record["sites"] == 1 and fake.closed


def test_push_missing_key_fails_without_client():
    plugin = ForumSignin()
    plugin.init_plugin({"enabled": True})
    ok, detail = plugin._push_pt_life(retries=0)
    assert not ok and detail == "missing_api_key"
    assert plugin._get("last_pt_life_push") is None


def test_push_stats_not_ready_records_and_schedules_retry():
    plugin, _fake = make_plugin(stats_error=StatsNotReady("site_statistics_empty"))
    ok, detail = plugin._push_pt_life(retries=0)
    assert not ok and detail == "site_statistics_empty"
    assert plugin._get("last_pt_life_push")["success"] is False
    plugin._schedule_pt_life_retry()
    assert [s["id"] for s in plugin.get_service()] == ["ForumSigninPtLifeRetry"]
    plugin._schedule_pt_life_retry()
    assert len(plugin.get_service()) == 1  # 不重复注册


def test_run_once_pushes_only_when_fengchao_confirmed(monkeypatch):
    plugin, _fake = make_plugin()
    pushed = []
    monkeypatch.setattr(plugin, "_push_pt_life", lambda retries=0: pushed.append(retries) or (True, ""))
    plugin._execute_with_retry = lambda domain, readonly=False: {
        "site_id": domain.split(".")[0], "status": "already" if "fengchao" in domain else "skipped"}
    plugin.run_once()
    assert pushed == [0]


def test_run_once_skips_push_without_fengchao(monkeypatch):
    plugin, _fake = make_plugin({"enabled_sites": []})
    pushed = []
    monkeypatch.setattr(plugin, "_push_pt_life", lambda retries=0: pushed.append(retries) or (True, ""))
    plugin.run_once()
    assert pushed == []
