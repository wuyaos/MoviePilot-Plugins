import sys
from datetime import datetime
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from core.models import ActionResult, RunReport, SiteRunReport
from core.reporting import (
    build_history_rows,
    build_price_sections,
    build_stat_cards,
    format_notification,
)
from core.trend import PriceTrendStore
from sites.playlet import PlayLetConfig


def _run_report() -> RunReport:
    return RunReport(
        started_at=900.0,
        finished_at=1000.0,
        site_reports=[
            SiteRunReport(
                site_id="playlet",
                site_name="PlayLet",
                mode="smart",
                actions=[
                    ActionResult("harvest", "小麦", True),
                    ActionResult("harvest", "小麦", True),
                    ActionResult("plant", "玉米", True),
                    ActionResult("sell", "牛", False, message="出售失败"),
                    ActionResult("unknown", "其他目标", True),
                ],
                total_profit=-500,
                trades_count=4,
                status="partial",
                message="部分操作失败",
            ),
            SiteRunReport(
                site_id="siqi",
                site_name="思齐",
                mode="smart",
                actions=[ActionResult("like", "好友", True)],
                total_profit=0,
                trades_count=1,
                status="completed",
            ),
        ],
        total_profit=-500,
        total_trades=5,
        status="partial",
        message="部分站点或操作未完成",
    )


def test_format_notification_groups_actions_and_failures():
    report = _run_report()

    text = format_notification(report)

    assert text.startswith("━━━━━━━━━━━━━━\n🌾 农场自动化 Pro 运行报告")
    assert datetime.fromtimestamp(1000.0).strftime("%Y-%m-%d %H:%M:%S") in text
    assert "📊 站点：2（✅成功 1 / ⚠️部分 1 / ❌失败 0）" in text
    assert "💰 总利润：-500" in text
    assert "【PlayLet】⚠️ 4笔 利润-500" in text
    assert "🌾 收获：✅2（小麦） ❌0" in text
    assert "🌱 种植：✅1（玉米） ❌0" in text
    assert "💰 出售：✅0 ❌1（牛：出售失败）" in text
    assert "📋 其他：✅1（其他目标） ❌0" in text
    assert "【思齐】✅ 1笔 利润0" in text
    assert "👍 点赞：✅1（好友） ❌0" in text
    assert text.endswith("状态：partial 部分站点或操作未完成")


def test_format_notification_handles_empty_site_reports():
    report = RunReport(
        started_at=0,
        finished_at=0,
        site_reports=[],
        status="skipped",
        message="未选择有效站点",
    )

    text = format_notification(report)

    assert "📊 站点：0（✅成功 0 / ⚠️部分 0 / ❌失败 0）" in text
    assert "无站点执行结果" in text
    assert text.endswith("状态：skipped 未选择有效站点")


def test_build_stat_cards_uses_report_totals():
    cards = build_stat_cards(_run_report())

    assert len(cards) == 4
    values = [card["content"][0]["content"][1]["text"] for card in cards]
    assert values == ["2", "-500", "5", "partial"]
    assert all(card["component"] == "VCol" for card in cards)


def test_build_history_rows_reverses_and_formats_values():
    first_ts = 1000.0
    rows = build_history_rows([
        {"time": first_ts, "site_name": "PlayLet", "action": "收获", "profit": 50, "status": "ok"},
        {"time": "手工时间", "site": "思齐", "message": "点赞完成", "profit": "-20"},
    ])

    assert len(rows) == 2
    first_cells = [cell["text"] for cell in rows[0]["content"]]
    second_cells = [cell["text"] for cell in rows[1]["content"]]
    assert first_cells == ["手工时间", "思齐", "点赞完成", "-20", "-"]
    assert second_cells == [
        datetime.fromtimestamp(first_ts).strftime("%Y-%m-%d %H:%M:%S"),
        "PlayLet",
        "收获",
        "50",
        "ok",
    ]


def test_build_price_sections_uses_crop_names_and_trends():
    report = SiteRunReport(
        site_id="playlet",
        site_name="PlayLet",
        mode="smart",
        market_prices={"crop_1": 880, "unknown": 7},
    )
    trends = PriceTrendStore()
    trends.record("playlet", {"crop_1": 800}, ts=1)
    trends.record("playlet", {"crop_1": 880}, ts=2)

    sections = build_price_sections(
        [report],
        site_configs={"playlet": PlayLetConfig()},
        trend_store=trends,
    )

    assert len(sections) == 1
    assert sections[0]["content"][0]["text"] == "📊 PlayLet"
    price_cards = sections[0]["content"][1]["content"]
    wheat_content = price_cards[0]["content"][0]["content"]
    unknown_content = price_cards[1]["content"][0]["content"]
    assert [item["text"] for item in wheat_content] == ["小麦", "880", "价格: 800→880"]
    assert [item["text"] for item in unknown_content] == ["unknown", "7"]
