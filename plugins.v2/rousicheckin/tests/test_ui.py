import sys
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_DIR))

from ui import build_form, build_page  # noqa: E402


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def test_form_exposes_cookie_and_credentials_without_legacy_token():
    form, model = build_form()
    models = {
        (node.get("props") or {}).get("model")
        for node in walk(form)
        if (node.get("props") or {}).get("model")
    }
    assert {"username", "password", "cookie"}.issubset(models)
    assert "token" not in models
    assert "expire_threshold_days" not in models
    assert model["cookie"] == ""
    assert model["cron"] == "7 9 * * *"


def test_page_shows_session_user_and_history_cards():
    page = build_page(
        {"status": "refreshed", "username": "tester", "expires_at": "2026-09-20"},
        {"username": "tester", "uploaded": "1.00 TB", "downloaded": "2.00 GB", "level": 2, "magic": "100"},
        {"time": "2026-08-21 09:07:00", "status": "今日已签", "new_message_count": 0},
        [{"date": "2026-08-21", "time": "2026-08-21 09:07:00", "status_code": "success_already", "message": "今日已签到"}],
    )
    texts = {node.get("text") for node in walk(page) if isinstance(node.get("text"), str)}
    components = [node.get("component") for node in walk(page)]
    assert {"登录状态", "用户信息", "最近运行", "签到历史"}.issubset(texts)
    assert "Cookie 已刷新" in texts
    assert "VTable" in components
