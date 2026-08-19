from ptnewswatch.core.config import PluginConfig
from ptnewswatch.ui.form import build_form
from ptnewswatch.ui.page import build_page


def walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from walk(item)


def test_form_contains_flat_source_models_and_cookie():
    form, model = build_form(PluginConfig())
    models = {(node.get("props") or {}).get("model") for node in walk(form)}
    assert "source_pter_digest_enabled" in models
    assert "source_invites_pt_fy_enabled" in models
    assert "invites_cookie" in models
    assert model["cron"] == "30 */12 * * *"


def test_page_renders_timeline_in_configured_timezone():
    state = {
        "last_run": {"time": "2026-08-19T12:00:00Z", "new_count": 1},
        "sources": {"fengchao_pt": {"last_success_at": "2026-08-19T12:00:00Z", "seen_entry_ids": ["1"]}},
        "recent_entries": [{
            "source_id": "fengchao_pt", "entry_id": "1", "title": "T", "author": "A",
            "content": "C", "link": "https://e/1", "published_at": "2026-08-19T12:00:00Z",
        }],
        "history": [],
    }
    page = build_page(state, "Asia/Shanghai")
    texts = [node.get("text") for node in walk(page) if node.get("text")]
    assert any("08-19 20:00" in text for text in texts)
    assert "T" in texts
