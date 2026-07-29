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
    assert "📊 站点：2（✅ 1 ⚠️ 1 ）" in text
    assert "💰 魔力变化：-500" in text
    assert "【PlayLet】⚠️  魔力 -500" in text
    assert "🌾 收获：✅2（小麦×2） 魔力" in text
    assert "🌱 种植：✅1（玉米×1） 魔力" in text
    # 失败操作不计入通知，出售组无成功不显示
    assert "💰 出售" not in text
    assert "📋 其他：✅1（其他目标×1） 魔力" in text
    assert "【思齐】✅  魔力 +0" in text
    assert "👍 点赞：✅1（好友×1） 魔力" in text
    assert text.endswith("状态：partial 部分站点或操作未完成")


def test_notification_reports_interaction_outcomes_and_filters_normal_skips():
    report = RunReport(
        started_at=1,
        finished_at=2,
        site_reports=[SiteRunReport(
            site_id="siqi",
            site_name="思齐",
            actions=[
                ActionResult("steal", "好友A", True, profit=5),
                ActionResult("like", "好友B", False, message="接口失败"),
                ActionResult(
                    "buy_slot", "地块1", True, skipped=True,
                    reason="insufficient_bonus", message="魔力不足",
                ),
                ActionResult(
                    "visit", "随机农场", True, skipped=True,
                    reason="daily_exhausted", message="今日访问额度已用完",
                ),
            ],
            total_profit=5,
            trades_count=1,
            status="partial",
        )],
        total_profit=5,
        total_trades=1,
        status="partial",
    )

    text = format_notification(report)

    assert "🥷 偷菜：✅1（好友A×1） 魔力 +5" in text
    assert "👍 点赞：❌1（接口失败） 魔力 +0" in text
    assert "🏗 扩地" not in text
    assert "🚜 参观：⚠️达到上限（今日访问额度已用完） 魔力 +0" in text


def test_format_notification_handles_empty_site_reports():
    report = RunReport(
        started_at=0,
        finished_at=0,
        site_reports=[],
        status="skipped",
        message="未选择有效站点",
    )

    text = format_notification(report)

    assert "📊 站点：0" in text
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


def test_harvest_all_target_not_duplicated_with_quantity_suffix():
    report = RunReport(
        started_at=1,
        finished_at=2,
        site_reports=[SiteRunReport(
            site_id="novahd",
            site_name="NovaHD",
            actions=[
                ActionResult("harvest_all", "收获了小麦×1", True, profit=0, quantity=1),
                ActionResult("plant", "小麦", True, profit=-500, quantity=1),
            ],
            total_profit=-500,
            trades_count=2,
            status="completed",
        )],
        total_profit=-500,
        total_trades=2,
        status="completed",
    )

    text = format_notification(report)

    assert "收获了小麦×1×1" not in text
    assert "🌾 收获：✅1（收获了小麦×1） 魔力 +0" in text


def test_harvest_all_with_multiple_crops_keeps_detail():
    report = RunReport(
        started_at=1,
        finished_at=2,
        site_reports=[SiteRunReport(
            site_id="skit",
            site_name="拾刻",
            actions=[
                ActionResult("harvest_all", "收获了花生×1、小麦×1", True, profit=0, quantity=1),
                ActionResult("plant", "小麦", True, profit=-1000, quantity=1),
                ActionResult("plant", "花生", True, profit=-1000, quantity=1),
            ],
            total_profit=-2000,
            trades_count=3,
            status="completed",
        )],
        total_profit=-2000,
        total_trades=3,
        status="completed",
    )

    text = format_notification(report)

    assert "🌾 收获：✅1（收获了花生×1、小麦×1） 魔力 +0" in text


def test_notification_uses_plant_quantity_and_reports_one_successful_like_batch():
    report = RunReport(
        started_at=1,
        finished_at=2,
        site_reports=[SiteRunReport(
            site_id="siqi",
            site_name="思齐",
            actions=[
                ActionResult("plant", "玉米", True, profit=-7200, quantity=6),
                # 一个 like_farm_batch 请求可以点赞多个农场，通知仍应是一次点赞操作。
                ActionResult("like", "wmqdyjyzx、白貓、hlink", True, quantity=3),
            ],
            total_profit=-7200,
            trades_count=2,
            status="completed",
        )],
        total_profit=-7200,
        total_trades=2,
        status="completed",
    )

    text = format_notification(report)

    assert "🌱 种植：✅1（玉米×6） 魔力 -7200" in text
    assert "👍 点赞：✅1（wmqdyjyzx、白貓、hlink×1） 魔力 +0" in text
    assert "达到上限" not in text


def test_notification_shows_siqi_daily_already_exhausted_and_sell_soft_stop():
    """思齐点赞重复探测达上限（daily_already_exhausted）和出售库存不足软停止都需显示。"""
    report = RunReport(
        started_at=1,
        finished_at=2,
        site_reports=[SiteRunReport(
            site_id="siqi",
            site_name="思齐",
            actions=[
                ActionResult("sell", "玉米", True, profit=1380, message="出售成功 价格1380×1"),
                ActionResult("sell", "玉米", True, profit=1380, message="出售成功 价格1380×1"),
                ActionResult(
                    "sell", "玉米", False, skipped=True,
                    reason="insufficient_stock", message="背包中该作物数量不足",
                ),
                ActionResult(
                    "like", "随机农场", True, skipped=True,
                    reason="daily_already_exhausted", message="今日点赞额度已用完",
                ),
            ],
            total_profit=2760,
            trades_count=2,
            status="completed",
        )],
        total_profit=2760,
        total_trades=2,
        status="completed",
    )

    text = format_notification(report)

    # 思齐站点详情必须显示，不能因软停止被过滤
    assert "【思齐】✅  魔力 +2760" in text
    # 出售成功明细按实际成功数量显示
    assert "💰 出售：✅2（玉米×2）" in text
    # 点赞达上限（重复探测标记）也显示
    assert "👍 点赞：⚠️达到上限（今日点赞额度已用完）" in text
    # 软停止不计失败，站点状态为 completed
    assert text.endswith("状态：completed")
