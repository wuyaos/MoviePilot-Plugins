"""PT 签到中心 V3 页面 JSON 构建器。"""
from typing import Any

from .ui_components import HistoryTable, MigrationPreview, OverviewStats, SiteCard


def _empty_data_alert() -> dict[str, Any]:
    return {"component": "VAlert", "props": {"type": "info", "variant": "tonal"},
            "text": "阶段1为 UI 与 API 契约骨架，当前数据为空；阶段2接入真实签到数据。"}


def build_page(page: str, **data: Any) -> dict[str, Any]:
    """按页面标识返回宿主已注册的 Vuetify 组件。"""
    if page == "overview":
        return OverviewStats(data.get("stats"), data.get("next_schedule", "暂无调度"))
    if page == "sites":
        return SiteCard(**data)
    if page == "history":
        return HistoryTable(data.get("items", []))
    if page == "settings":
        return MigrationPreview(data.get("items", []))
    return OverviewStats()


def build_overview(**data: Any) -> list[dict[str, Any]]:
    """构造总览页，保留空数据提示而不伪造站点结果。"""
    stats = data.get("stats") or {"today_success": 0, "signed": 0, "failed": 0, "unconfirmed": 0}
    return [build_page("overview", stats=stats, next_schedule=data.get("next_schedule", "暂无调度")),
            _empty_data_alert(), HistoryTable([])]
