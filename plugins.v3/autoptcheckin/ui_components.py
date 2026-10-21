"""命名组件工厂输出宿主已注册的 Vuetify 节点，不依赖自定义前端组件。"""
from typing import Any


def StatusBadge(status: str = "unconfirmed", message: str = "") -> dict:
    labels = {"success": ("成功", "success"), "already": ("已签", "primary"),
              "failed": ("失败", "error"), "unconfirmed": ("未确认", "orange")}
    label, color = labels.get(status, (status, "warning"))
    return {"component": "VChip", "props": {"color": color, "title": message}, "text": label}


def RewardSummary(summary: str = "暂无奖励记录") -> dict:
    return {"component": "VCardText", "text": summary}


def CredentialSource(source: str = "") -> dict:
    labels = {"cookiecloud": "CookieCloud", "site_manager": "站点管理",
              "local_cache": "本地缓存", "credentials": "账密", "api_key": "API Key"}
    return {"component": "VChip", "props": {"variant": "outlined"},
            "text": labels.get(source, "未配置凭证")}


def OverviewStats(stats: dict[str, int] | None = None, next_schedule: str = "暂无调度") -> dict:
    stats = stats or {}
    cards = []
    for key, title, color in [("today_success", "今日成功", "success"), ("signed", "已签", "primary"),
                              ("failed", "失败", "error"), ("unconfirmed", "未确认", "orange")]:
        cards.append({"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [
            {"component": "VCard", "props": {"color": color, "variant": "tonal"}, "content": [
                {"component": "VCardTitle", "text": title},
                {"component": "VCardText", "text": str(stats.get(key, 0))}]}]})
    return {"component": "VCard", "props": {"variant": "outlined", "stats": stats,
            "next-schedule": next_schedule, "status-endpoint": "plugin/AutoPtCheckin/status",
            "manual-action": "manual-signin"}, "content": [
        {"component": "VCardTitle", "text": "总览"},
        {"component": "VRow", "content": cards},
        {"component": "VCardText", "text": f"下次调度：{next_schedule}"},
        {"component": "VBtn", "props": {"color": "primary"}, "text": "手动签到（查看阶段1状态）",
         "events": {"click": {"api": "plugin/AutoPtCheckin/status", "method": "get"}}},
    ]}

def SiteCard(site_name: str = "", uid: str = "", credential_source: str = "",
             status: str = "unconfirmed", message: str = "", reward_summary: str = "暂无奖励记录",
             domain: str = "") -> dict:
    return {"component": "VCard", "props": {"variant": "outlined", "site-name": site_name,
            "uid": uid, "credential-source": credential_source, "result": status,
            "reward": reward_summary, "actions": ["signin", "verify", "history"]}, "content": [
        {"component": "VCardText", "text": f"UID：{uid or '未读取'}"},
        CredentialSource(credential_source), StatusBadge(status, message), RewardSummary(reward_summary),
        {"component": "VBtn", "props": {"disabled": not bool(domain)}, "text": "单站签到（阶段1未接管）",
         "events": {"click": {"api": "plugin/AutoPtCheckin/signin_by_domain", "method": "post",
                              "params": {"domain": domain}}}},
    ]}


def HistoryTable(items: list[dict[str, Any]] | None = None) -> dict:
    return {"component": "VDataTable", "props": {
        "evidence-field": "evidence",
        "items": items or [], "headers": [
            {"title": title, "key": key} for title, key in [
                ("时间", "time"), ("站点", "site"), ("状态", "status"),
                ("消息", "message"), ("奖励", "reward"), ("证据", "evidence")]],
        "item-value": "id", "show-expand": True, "items-per-page": 10,
        "no-data-text": "阶段1暂无签到历史，阶段2接入真实数据"},
        "slots": {"expanded-row": [{"component": "tr", "content": [
            {"component": "td", "props": {"colspan": 7}, "content": [
                {"component": "VAlert", "props": {"type": "info", "text": "阶段2接入按钮文本、UID、日期及本人记录行证据"}}]}]}]}}


def MigrationPreview(items: list[dict[str, Any]] | None = None) -> dict:
    return {"component": "VDataTable", "props": {
        "read-only": True,
        "items": items or [], "headers": [{"title": title, "key": key} for title, key in [
            ("来源", "source"), ("新字段", "target"), ("冲突", "conflict"), ("不迁移项", "skipped")]],
        "item-value": "source", "items-per-page": 10,
        "no-data-text": "暂无迁移预览，阶段2接入 V2 配置；当前不会迁移或写入数据"}}
