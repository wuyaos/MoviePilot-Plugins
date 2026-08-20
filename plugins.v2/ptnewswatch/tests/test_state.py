from datetime import datetime, timezone

from core.models import ForumEntry, SourceFetchResult
from core.state import add_recent_entries, apply_source_result, default_state, normalize_state


def entry(entry_id, source_id="s", content="c"):
    return ForumEntry(
        source_id, entry_id, entry_id, "a", content,
        "https://e/" + entry_id, datetime.now(timezone.utc),
        source_title="Source", base_source_id=source_id.split("#", 1)[0],
    )


def result(entries, success=True, source_id="s"):
    return SourceFetchResult(
        source_id, "Source", success, entries=entries,
        error="failed" if not success else "",
        fetched_at=datetime.now(timezone.utc),
    )


def test_first_run_returns_recent_then_only_unseen_entries():
    state = default_state()
    first = apply_source_result(state, result([entry("1"), entry("2")]))
    assert [item.entry_id for item in first] == ["1", "2"]
    second = apply_source_result(state, result([entry("2"), entry("3")]))
    assert [item.entry_id for item in second] == ["3"]
    assert state["sources"]["s"]["initialized"] is True


def test_failure_does_not_advance_seen():
    state = default_state()
    apply_source_result(state, result([entry("1")]))
    before = list(state["sources"]["s"]["seen_entry_ids"])
    apply_source_result(state, result([entry("2")], success=False))
    assert state["sources"]["s"]["seen_entry_ids"] == before


def test_source_instances_keep_seen_state_isolated():
    state = default_state()
    extra = "pter_digest#stable"
    apply_source_result(state, result([entry("1", "pter_digest")], source_id="pter_digest"))
    apply_source_result(state, result([entry("1", extra)], source_id=extra))
    new = apply_source_result(
        state,
        result([entry("1", "pter_digest"), entry("2", "pter_digest")], source_id="pter_digest"),
    )
    assert [item.entry_id for item in new] == ["2"]
    assert state["sources"][extra]["seen_entry_ids"] == ["1"]


def test_first_run_populates_recent_entries_and_returns_notifications():
    state = default_state()
    fetched = result([entry("1", "pter_digest", "initial")], source_id="pter_digest")
    notifications = apply_source_result(state, fetched)
    add_recent_entries(state, fetched.entries, history_days=30)
    assert [item.entry_id for item in notifications] == ["1"]
    assert state["recent_entries"][0]["content"] == "initial"


def test_legacy_seen_state_is_initialized_without_reset():
    state = normalize_state({"sources": {"pter_digest": {
        "seen_entry_ids": ["pter_digest:1"], "last_success_at": "2026-08-19T00:00:00Z",
    }}})
    assert state["sources"]["pter_digest"]["initialized"] is True


def test_seen_entry_refreshes_recent_content_without_notification():
    state = default_state()
    initial = result([entry("1", "pter_digest", "old")], source_id="pter_digest")
    apply_source_result(state, initial)
    add_recent_entries(state, initial.entries, history_days=30)
    refreshed = result([entry("1", "pter_digest", "updated")], source_id="pter_digest")
    notifications = apply_source_result(state, refreshed)
    add_recent_entries(state, refreshed.entries, history_days=30)
    assert notifications == []
    assert len(state["recent_entries"]) == 1
    assert state["recent_entries"][0]["content"] == "updated"
