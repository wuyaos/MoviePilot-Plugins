from datetime import datetime
from typing import TYPE_CHECKING, Dict, List, Optional

from .models import RunReport, SiteRunReport

if TYPE_CHECKING:
    from .trend import PriceTrendStore

    try:
        from ..sites.base import FarmSiteConfig
    except ImportError:
        from sites.base import FarmSiteConfig


_STATUS_EMOJIS = {
    "completed": "✅",
    "partial": "⚠️",
    "failed": "❌",
    "skipped": "⚠️",
}

_ACTION_CATEGORIES = (
    ({"harvest", "harvest_all"}, "🌾", "收获"),
    ({"plant"}, "🌱", "种植"),
    ({"breed"}, "🐣", "养殖"),
    ({"sell"}, "💰", "出售"),
    ({"steal"}, "🥷", "偷菜"),
    ({"like"}, "👍", "点赞"),
    ({"buy_slot"}, "🏗", "扩地"),
    ({"visit"}, "🚜", "参观"),
)


def _signed(value: int) -> str:
    return f"{'+' if value >= 0 else ''}{value}"


def _format_site_detail(site_report: SiteRunReport) -> str:
    # 普通跳过不通知；以下软停止需保留：互动达到每日上限（首次或重复探测）、出售时库存不足。
    meaningful_actions = []
    interaction_actions = {"steal", "like", "buy_slot", "visit"}
    daily_limit_reasons = {"daily_exhausted", "daily_already_exhausted"}
    soft_stop_reasons = daily_limit_reasons | {"insufficient_stock"}
    for action in site_report.actions:
        if action.action == "harvest_all" and action.success:
            target_str = str(action.target or "")
            # harvest_all 未拆分明细（target=all）且无魔力收获，视为无收获
            if target_str == "all" and int(action.profit or 0) == 0:
                continue
        if action.skipped and action.reason not in soft_stop_reasons:
            continue
        # 非互动失败沿用原通知策略不显示；互动失败需要明确通知。
        if not action.success and action.action not in interaction_actions and action.reason not in soft_stop_reasons:
            continue
        meaningful_actions.append(action)
    # 站点无有意义操作不显示
    if not meaningful_actions:
        return ""
    has_interaction_failure = any(
        action.action in interaction_actions and not action.success
        for action in meaningful_actions
    )
    site_emoji = "⚠️" if has_interaction_failure else _STATUS_EMOJIS.get(site_report.status, "⚠️")
    lines = [
        f"【{site_report.site_name}】{site_emoji}  "
        f"魔力 {_signed(site_report.total_profit)}"
    ]
    grouped_actions = [[] for _ in range(len(_ACTION_CATEGORIES) + 1)]
    for action in meaningful_actions:
        category_index = next(
            (
                index
                for index, (action_names, _, _) in enumerate(_ACTION_CATEGORIES)
                if action.action in action_names
            ),
            len(_ACTION_CATEGORIES),
        )
        grouped_actions[category_index].append(action)

    categories = (*_ACTION_CATEGORIES, (set(), "📋", "其他"))
    for (action_names, icon, label), actions in zip(categories, grouped_actions):
        successful_actions = [
            action for action in actions if action.success and not action.skipped
        ]
        failed_actions = [action for action in actions if not action.success]
        # 成功完成本批互动后额度归零仍是一次成功操作，不重复显示为“达到上限”。
        # 仅真正跳过的额度耗尽/重复探测才显示上限提示。
        limit_actions = [
            action for action in actions
            if action.skipped and action.reason in daily_limit_reasons
        ]
        parts = []
        if successful_actions:
            # harvest_all 的 target 已包含收获明细和数量（如「收获了小麦×2」），
            # 不再追加 ×N；其他动作按目标名聚合后追加数量。
            raw_targets = []
            target_counts = {}
            for action in successful_actions:
                target = str(action.target) if action.target else "未知"
                if action.action == "harvest_all":
                    raw_targets.append(target)
                    continue
                quantity = max(1, int(action.quantity or 1))
                target_quantity = quantity if action.action in {"harvest", "plant", "breed", "sell"} else 1
                target_counts[target] = target_counts.get(target, 0) + target_quantity
            targets = raw_targets + [f"{name}×{count}" for name, count in list(target_counts.items())[:5]]
            detail = f"（{'、'.join(targets)}）" if targets else ""
            parts.append(f"✅{len(successful_actions)}{detail}")
        # 仅四类互动动作通知失败，避免改变其他既有通知噪声策略。
        if action_names & interaction_actions and failed_actions:
            failed_quantity = sum(max(1, int(action.quantity or 1)) for action in failed_actions)
            messages = [str(action.message or action.target or "失败") for action in failed_actions[:3]]
            parts.append(f"❌{failed_quantity}（{'、'.join(messages)}）")
        if action_names & interaction_actions and limit_actions:
            messages = [str(action.message or "今日额度已用完") for action in limit_actions[:1]]
            parts.append(f"⚠️达到上限（{'、'.join(messages)}）")
        if not parts:
            continue
        harvest_value_actions = [
            action for action in successful_actions
            if action.value_unit == "收获值"
        ]
        if action_names & {"harvest", "harvest_all"} and harvest_value_actions:
            harvest_value = sum(int(action.value or 0) for action in harvest_value_actions)
            value_text = f"收获值 {_signed(harvest_value)}"
        else:
            group_profit = sum(int(action.profit or 0) for action in successful_actions)
            value_text = f"魔力 {_signed(group_profit)}"
        lines.append(f"  {icon} {label}：{' '.join(parts)} {value_text}")
    return "\n".join(lines) if len(lines) > 1 else ""


def format_notification(report: RunReport) -> str:
    completed = sum(item.status == "completed" for item in report.site_reports)
    partial = sum(item.status == "partial" for item in report.site_reports)
    failed = sum(item.status == "failed" for item in report.site_reports)
    site_details = "\n\n".join(
        detail for detail in (_format_site_detail(item) for item in report.site_reports)
        if detail
    ) or "无站点执行结果"
    finished_at = datetime.fromtimestamp(report.finished_at).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    # 站点统计只显示非 0 项
    status_parts = []
    if completed:
        status_parts.append(f"✅ {completed}")
    if partial:
        status_parts.append(f"⚠️ {partial}")
    if failed:
        status_parts.append(f"❌ {failed}")
    site_summary = f"{len(report.site_reports)}（{' '.join(status_parts)} ）" if status_parts else f"{len(report.site_reports)}"
    status_message = f" {report.message}" if report.message else ""
    return (
        "━━━━━━━━━━━━━━\n"
        "🌾 农场自动化 Pro 运行报告\n"
        "━━━━━━━━━━━━━━\n"
        f"⏰ 时间：{finished_at}\n"
        f"📊 站点：{site_summary}\n"
        f"💰 魔力变化：{_signed(report.total_profit)}\n"
        f"🔄 总操作：{report.total_trades} 次\n\n"
        f"{site_details}\n\n"
        f"状态：{report.status}{status_message}"
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
