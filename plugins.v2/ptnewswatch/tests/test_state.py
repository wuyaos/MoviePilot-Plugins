from datetime import datetime, timezone

from core.models import ForumEntry, SourceFetchResult
from core.state import apply_source_result, default_state


def entry(entry_id):
    return ForumEntry("s", entry_id, entry_id, "a", "c", "https://e/" + entry_id, datetime.now(timezone.utc))


def result(entries, success=True):
    return SourceFetchResult("s", "Source", success, entries=entries, error="failed" if not success else "", fetched_at=datetime.now(timezone.utc))


def test_first_run_silent_then_only_new_entries():
    state = default_state()
    assert apply_source_result(state, result([entry("1"), entry("2")]), first_run_push_recent=False) == []
    new = apply_source_result(state, result([entry("2"), entry("3")]), first_run_push_recent=False)
    assert [item.entry_id for item in new] == ["3"]


def test_failure_does_not_advance_seen():
    state = default_state()
    apply_source_result(state, result([entry("1")]), first_run_push_recent=False)
    before = list(state["sources"]["s"]["seen_entry_ids"])
    apply_source_result(state, result([entry("2")], success=False), first_run_push_recent=False)
    assert state["sources"]["s"]["seen_entry_ids"] == before
