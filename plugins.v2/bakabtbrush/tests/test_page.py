from __future__ import annotations

from core.page import build_page
from core.state import default_state, record_run, update_qb


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


def test_page_has_four_overview_cards_and_five_log_columns():
    state = default_state()
    state["account"].update({"uploaded_mb": 100, "downloaded_mb": 50, "ratio": "2.00"})
    state["completed_hashes"] = ["a" * 40]
    update_qb(state, uploaded_mb=25, downloaded_mb=10, downloading_count=1, max_downloading=2)
    record_run(state, {"status": "success", "torrent": "Example", "push": "已推送 1 个", "detail": "ok"})

    page = build_page(state)
    cards = page[0]["content"]
    texts = list(_find_text(page))

    assert len(cards) == 4
    assert {"BakaBT 流量", "qB 刷流流量", "历史下载种子", "上次运行"}.issubset(texts)
    assert {"时间", "状态", "种子", "推送", "详情"}.issubset(texts)
    assert any("下载槽位：1/2" in text for text in texts)
