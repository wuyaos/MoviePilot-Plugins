from datetime import datetime
from typing import TYPE_CHECKING, Dict, List, Optional

from .models import RunReport, SiteRunReport

if TYPE_CHECKING:
    from .trend import PriceTrendStore

    try:
        from ..sites.base import FarmSiteConfig
    except ImportError:
        from sites.base import FarmSiteConfig


def format_notification(report: RunReport) -> str:
    completed = sum(item.status == "completed" for item in report.site_reports)
    partial = sum(item.status == "partial" for item in report.site_reports)
    failed = sum(item.status == "failed" for item in report.site_reports)
    currency_hint = "各站点币种"
    return (
        "农场自动化 Pro 运行完成\n"
        f"站点：{len(report.site_reports)}（成功 {completed} / 部分 {partial} / 失败 {failed}）\n"
        f"总利润：{report.total_profit} {currency_hint}\n"
        f"成功操作：{report.total_trades} 次\n"
        f"状态：{report.status}{('；' + report.message) if report.message else ''}"
    )


def _stat_card(icon: str, label: str, value: str, color: str) -> dict:
    return {
        "component": "VCol",
        "props": {"cols": 6, "md": 3},
        "content": [{
            "component": "VCard",
            "props": {"color": color, "variant": "tonal", "class": "pa-3"},
            "content": [
                {"component": "div", "props": {"class": "text-caption"}, "text": f"{icon} {label}"},
                {"component": "div", "props": {"class": "text-h6 font-weight-bold"}, "text": value},
            ],
        }],
    }


def build_stat_cards(report: RunReport) -> List[dict]:
    return [
        _stat_card("🌐", "站点", str(len(report.site_reports)), "info"),
        _stat_card("💰", "本次利润", f"{report.total_profit:,}", "success"),
        _stat_card("🔄", "成功操作", str(report.total_trades), "warning"),
        _stat_card("📋", "运行状态", report.status, "primary"),
    ]


def build_history_rows(history: list) -> List[dict]:
    rows: List[dict] = []
    for record in reversed(history):
        raw_time = record.get("time", record.get("ts", ""))
        if isinstance(raw_time, (int, float)):
            raw_time = datetime.fromtimestamp(raw_time).strftime("%Y-%m-%d %H:%M:%S")
        status = record.get("status", "-")
        rows.append({
            "component": "tr",
            "content": [
                {"component": "td", "text": str(raw_time)},
                {"component": "td", "text": str(record.get("site", record.get("site_name", "-")))},
                {"component": "td", "text": str(record.get("action", record.get("message", "-")))},
                {"component": "td", "text": f"{int(record.get('profit', 0)):,}"},
                {"component": "td", "text": str(status)},
            ],
        })
    return rows


def build_price_sections(
    site_reports: List[SiteRunReport],
    site_configs: Optional[Dict[str, "FarmSiteConfig"]] = None,
    trend_store: Optional["PriceTrendStore"] = None,
) -> List[dict]:
    sections: List[dict] = []
    for report in site_reports:
        site_config = (site_configs or {}).get(report.site_id)
        price_items = []
        for crop_key, price in report.market_prices.items():
            crop = site_config.crops.get(crop_key, {}) if site_config else {}
            crop_name = crop.get("name", crop_key)
            card_content = [
                {"component": "div", "props": {"class": "text-caption"}, "text": crop_name},
                {"component": "div", "props": {"class": "text-h6"}, "text": str(price)},
            ]
            samples = trend_store.get(report.site_id, crop_key)[-5:] if trend_store else []
            if samples:
                card_content.append({
                    "component": "div",
                    "props": {"class": "text-caption text-medium-emphasis mt-1"},
                    "text": "价格: " + "→".join(str(sample_price) for _, sample_price in samples),
                })
            price_items.append({
                "component": "VCol",
                "props": {"cols": 6, "md": 3},
                "content": [{
                    "component": "VCard",
                    "props": {"variant": "tonal", "class": "pa-2"},
                    "content": card_content,
                }],
            })
        sections.append({
            "component": "div",
            "content": [
                {"component": "div", "props": {"class": "text-subtitle-1 mt-3"}, "text": f"📊 {report.site_name}"},
                {"component": "VRow", "content": price_items},
            ],
        })
    return sections
