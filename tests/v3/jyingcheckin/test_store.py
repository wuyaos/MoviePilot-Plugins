"""store.py 存储边界离线测试。"""
from datetime import datetime, timedelta

from jying_under_test.store import HISTORY_MAX_ENTRIES, HISTORY_RETENTION_DAYS, Store


def make_store():
    memory: dict = {}
    return Store(memory.get, lambda k, v: memory.__setitem__(k, v)), memory


def test_record_strips_non_whitelist_fields():
    store, _ = make_store()
    saved = store.record({"date": "2026-11-08", "status": "success", "message": "ok",
                          "token": "SECRET", "raw": {"token": "SECRET"}, "days": 3})
    assert saved["status"] == "success"
    assert "token" not in saved and "raw" not in saved  # 凭据不落盘
    assert saved["days"] == 3


def test_latest_and_history_updated():
    store, memory = make_store()
    store.record({"date": "2026-11-08", "status": "success", "message": "a"})
    store.record({"date": "2026-11-09", "status": "already", "message": "b"})
    assert store.get_latest()["status"] == "already"  # latest = 最近一条
    items = store.get_history()
    assert len(items) == 2 and items[0]["message"] == "b"  # 历史倒序


def test_history_retention_and_cap():
    store, _ = make_store()
    old = (datetime.now() - timedelta(days=HISTORY_RETENTION_DAYS + 1)).strftime("%Y-%m-%d")
    store.record({"date": old, "status": "success", "message": "expired"})
    assert all(item["message"] != "expired" for item in store.get_history())  # 超期剔除
    for i in range(HISTORY_MAX_ENTRIES + 10):
        store.record({"date": "2026-11-08", "status": "pending", "message": f"m{i}"})
    assert len(store.get_history()) == HISTORY_MAX_ENTRIES


def test_session_roundtrip_and_expiry():
    store, _ = make_store()
    assert store.session_expired()  # 空 session 视为过期
    store.save_session("T", 5, datetime.now().timestamp() + 3600)
    assert not store.session_expired()
    assert store.get_session()["token"] == "T"
    store.save_session("T2", None, datetime.now().timestamp() - 10)
    assert store.session_expired()  # 本地 TTL 预判


def test_clear_session():
    store, _ = make_store()
    store.save_session("T", 1, 9)
    store.clear_session()
    assert store.get_session() == {}
    assert store.session_expired()
