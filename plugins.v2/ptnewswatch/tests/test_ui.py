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


def texts(node):
    return [item.get("text") for item in walk(node) if isinstance(item.get("text"), str)]


def test_form_contains_disabled_flat_source_switches_and_url_textareas():
    form, model = build_form(PluginConfig())
    models = {(node.get("props") or {}).get("model") for node in walk(form)}
    components = {node.get("component") for node in walk(form)}
    labels = {(node.get("props") or {}).get("label") for node in walk(form)}
    assert "source_pter_digest_enabled" in models
    assert "source_pter_digest_urls" in models
    assert "source_invites_pt_fy_enabled" in models
    assert "invites_cookie" in models
    assert "first_run_push_recent" not in models
    assert "first_run_push_recent" not in model
    assert "VTextarea" in components
    assert model["source_pter_digest_enabled"] is False
    assert model["source_invites_pt_fy_enabled"] is False
    assert model["cron"] == "30 */12 * * *"
    assert "资讯保留天数" in labels


def test_page_uses_large_linked_titles_compact_scrollable_list_without_history():
    config = PluginConfig.from_dict({"source_fengchao_pt_enabled": True})
    state = {
        "last_run": {
            "time": "2026-08-19T12:00:00Z", "new_count": 1,
            "notification_sent": True,
        },
        "sources": {"fengchao_pt": {
            "last_success_at": "2026-08-19T12:00:00Z", "seen_entry_ids": ["1"],
            "last_new_count": 1, "last_error": "",
        }},
        "recent_entries": [{
            "source_id": "fengchao_pt", "base_source_id": "fengchao_pt",
            "source_title": "蜂巢 · PT生态", "entry_id": "1", "title": "可点击标题", "author": "A",
            "content": "第一段\n\n> 引用内容\n- 列表项\n第二段",
            "link": "https://e/1", "published_at": "2026-08-19T12:00:00Z",
        }],
        # 旧历史即使仍在持久化状态中，页面也不应再渲染。
        "history": [{"time": "2026-08-19T11:00:00Z"}],
    }
    page = build_page(state, "Asia/Shanghai", config=config)
    nodes = list(walk(page))
    components = {node.get("component") for node in nodes}
    assert "VTimeline" not in components
    assert "VTimelineItem" not in components
    assert "VList" in components
    assert "VTable" not in components
    assert "VDataTable" not in components
    scroll_styles = [str((node.get("props") or {}).get("style") or "") for node in nodes]
    assert any("max-height: 640px" in style and "overflow-y: auto" in style for style in scroll_styles)
    assert not any("max-height: 420px" in style for style in scroll_styles)

    linked = next(node for node in nodes if node.get("text") == "可点击标题")
    assert linked["props"]["href"] == "https://e/1"
    assert linked["props"]["rel"] == "noopener noreferrer"
    assert "text-subtitle-1" in linked["props"]["class"]
    assert "white-space: normal" in linked["props"]["style"]

    page_text = texts(page)
    assert "运行历史" not in page_text
    assert "已发送" in page_text
    assert "08-19 20:00" in page_text
    assert "第一段" in page_text
    assert "引用内容" in page_text
    assert "• 列表项" in page_text
    assert "> 引用内容" not in page_text
    assert any("border-s" in str((node.get("props") or {}).get("class") or "") for node in nodes)
    assert "第二段" in page_text


def test_page_distinguishes_disabled_pending_healthy_and_failed_sources():
    config = PluginConfig.from_dict({
        "source_tjupt_digest_enabled": True,
        "source_fengchao_pt_enabled": True,
        "source_fengchao_invites_enabled": True,
    })
    state = {"sources": {
        "fengchao_pt": {"last_success_at": "2026-08-19T11:00:00Z", "last_error": ""},
        "fengchao_invites": {"last_success_at": "", "last_error": "连接超时"},
    }}
    page_text = texts(build_page(state, "Asia/Shanghai", config=config))
    assert "已禁用" in page_text
    assert "待检查" in page_text
    assert "正常" in page_text
    assert "异常" in page_text
    assert "连接超时" in page_text
