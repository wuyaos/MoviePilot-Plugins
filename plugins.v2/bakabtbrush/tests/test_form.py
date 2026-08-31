from __future__ import annotations

from core.form import build_form


def _models(node):
    if isinstance(node, dict):
        model = (node.get("props") or {}).get("model")
        if model:
            yield model
        for child in node.get("content", []) or []:
            yield from _models(child)
    elif isinstance(node, list):
        for child in node:
            yield from _models(child)


def _texts(node):
    if isinstance(node, dict):
        if node.get("text"):
            yield str(node["text"])
        for child in node.get("content", []) or []:
            yield from _texts(child)
    elif isinstance(node, list):
        for child in node:
            yield from _texts(child)


def _props_for_model(node, expected_model):
    if isinstance(node, dict):
        props = node.get("props") or {}
        if props.get("model") == expected_model:
            return props
        for child in node.get("content", []) or []:
            found = _props_for_model(child, expected_model)
            if found:
                return found
    elif isinstance(node, list):
        for child in node:
            found = _props_for_model(child, expected_model)
            if found:
                return found
    return None


def test_form_uses_new_range_and_cleanup_fields_without_legacy_min_max():
    form, model = build_form([{"title": "qb", "value": "qb"}])
    models = set(_models(form))
    texts = set(_texts(form))

    assert {"rss_url", "cookie", "size_range_mb", "publish_age_range_minutes"}.issubset(models)
    assert {"auto_delete", "delete_files", "delete_seed_hours", "delete_exclude_tags"}.issubset(models)
    assert {"page_max_height", "page_visible_items"}.isdisjoint(models)
    assert "候选过滤" in texts
    assert "自动删种" in texts
    assert "数据页" not in texts
    assert model["rss_url"] == ""
    assert _props_for_model(form, "rss_url")["type"] == "password"
    assert model["auto_delete"] is False
    assert model["delete_files"] is False
