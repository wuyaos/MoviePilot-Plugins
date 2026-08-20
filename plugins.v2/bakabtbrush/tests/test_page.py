from __future__ import annotations

from core.models import QBTorrentSnapshot
from core.page import build_page
from core.state import default_state, record_deletions, record_run, update_qb


def _find_text(node):
    if isinstance(node, dict):
        value = node.get("text")
        if value:
            yield str(value)
        for child in node.get("content", []) or []:
            yield from _find_text(child)
    elif isinstance(node, list):
        for child in node:
            yield from _find_text(child)


def _find_components(node, component):
    if isinstance(node, dict):
        if node.get("component") == component:
            yield node
        for child in node.get("content", []) or []:
            yield from _find_components(child, component)
    elif isinstance(node, list):
        for child in node:
            yield from _find_components(child, component)


def _find_href(node):
    if isinstance(node, dict):
        href = (node.get("props") or {}).get("href")
        if href:
            yield href
        for child in node.get("content", []) or []:
            yield from _find_href(child)
    elif isinstance(node, list):
        for child in node:
            yield from _find_href(child)


def test_page_has_overview_current_tasks_linked_history_and_deletions():
    state = default_state()
    state["account"].update({"uploaded_mb": 100, "downloaded_mb": 50, "ratio": "2.00"})
    state["completed_hashes"] = ["a" * 40]
    state["added"]["1"] = {
        "infohash": "b" * 40,
        "detail_url": "https://bakabt.me/torrent/1/example",
        "published_at": "2026-08-20T00:00:00Z",
    }
    update_qb(
        state,
        uploaded_mb=25,
        downloaded_mb=10,
        downloading_count=1,
        max_downloading=2,
        torrents=[QBTorrentSnapshot(
            infohash="b" * 40,
            name="Current Example",
            category="刷流",
            tags=("bakabt", "刷流"),
            state="downloading",
            progress=0.5,
            uploaded=5 * 1024**2,
            downloaded=10 * 1024**2,
        )],
    )
    record_run(state, {
        "time": "2026-08-20T00:10:00Z",
        "status": "success",
        "torrent": "History Example",
        "torrent_links": [{
            "title": "History Example",
            "url": "https://bakabt.me/torrent/2/example",
            "published_at": "2026-08-20T00:00:00Z",
            "size_mb": 500,
        }],
        "push": "已推送 1 个",
        "detail": "ok",
    })
    record_deletions(state, [{
        "time": "2026-08-20T00:20:00Z",
        "title": "Deleted Example",
        "detail_url": "https://bakabt.me/torrent/3/example",
        "reason": "做种达到 24 小时",
        "delete_files": False,
        "uploaded_gb": 2,
        "ratio": 3,
    }])

    page = build_page(state, max_height=320, visible_items=2)
    cards = page[0]["content"]
    texts = list(_find_text(page))
    hrefs = list(_find_href(page))

    assert len(cards) == 4
    assert {"BakaBT 流量", "qB 刷流流量", "历史下载种子", "上次运行"}.issubset(texts)
    assert {"当前 BakaBT 下载流程", "运行历史", "自动删除历史"}.issubset(texts)
    assert {"时间", "状态", "本轮候选 / 推送", "推送", "详情"}.issubset(texts)
    assert any("下载槽位：1/2" in text for text in texts)
    assert "Current Example" in texts
    assert "History Example" in texts
    assert "Deleted Example" in texts
    assert "https://bakabt.me/torrent/1/example" in hrefs
    assert "https://bakabt.me/torrent/2/example" in hrefs
    assert "https://bakabt.me/torrent/3/example" in hrefs
    tables = list(_find_components(page, "VTable"))
    assert tables
    assert all(table["props"]["fixed-header"] is True for table in tables)
    assert all(table["props"]["height"] <= 320 for table in tables)
