"""蜂巢 PT 人生快照推送：对齐 madrays fengchaosignin 的 pt-life/snapshot 契约。

PUT /api/integrations/moviepilot/v1/pt-life/snapshot，payload（schemaVersion 2）：
instanceId / pluginVersion / moviePilotVersion / clientBatchId / collectedAt / sites。
站点数据取自 MP 本地统计（SiteOper.get_userdata 每站最新一条 + SitesHelper 索引器补齐
domain/mpSiteId），字段与 madrays 一一对应；无名称或带 error 的行跳过，上限 200。
clientBatchId 在同一轮推送（含重试）内保持不变，丢失响应不会产生第二份快照。
"""
from datetime import datetime, timezone

MAX_SITES = 200


class StatsNotReady(RuntimeError):
    """MP 站点统计尚未就绪（启动初期/无数据），应延迟补推而非报错。"""


def _nonnegative(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, number)


def _bonus(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, number)


def _default_collector():
    """MP 本地站点统计：每站取 updated_day 最新一行，仅保留索引器中存在的站点。"""
    from app.db.site_oper import SiteOper
    from app.helper.sites import SitesHelper

    managed = {str(item.get("name")): item
               for item in (SitesHelper().get_indexers() or []) if item.get("name")}
    rows = SiteOper().get_userdata() or []
    by_day = {}
    for row in rows:
        name = getattr(row, "name", None)
        if name in managed:
            day = getattr(row, "updated_day", "")
            by_day.setdefault(f"{day}_{name}", row)
    latest = sorted(by_day.values(),
                    key=lambda row: getattr(row, "updated_day", "") or "", reverse=True)
    sites, seen = [], set()
    for row in latest:
        name = row.name
        if name in seen:
            continue
        seen.add(name)
        data = row.to_dict() if hasattr(row, "to_dict") else dict(row.__dict__)
        data.pop("_sa_instance_state", None)
        sites.append(data)
    return sites, managed


def collect_site_statistics(collector=None):
    """返回归一化站点数组；无可用数据抛 StatsNotReady。collector 可注入供测试。"""
    if collector is None:
        try:
            sites, managed = _default_collector()
        except ImportError as exc:
            raise StatsNotReady("site_statistics_unavailable") from exc
        except Exception as exc:
            raise StatsNotReady(f"site_statistics_error: {type(exc).__name__}") from exc
    else:
        sites, managed = collector()

    normalized = []
    for site in sites[:MAX_SITES]:
        if not isinstance(site, dict) or not site.get("name") or site.get("error"):
            continue
        config = managed.get(str(site.get("name"))) or {}
        normalized.append({
            "name": str(site.get("name")),
            "domain": str(config.get("url") or ""),
            "mpSiteId": str(config.get("id") or ""),
            "siteUserId": str(site.get("userid") or ""),
            "username": str(site.get("username") or ""),
            "userLevel": str(site.get("user_level") or ""),
            "upload": _nonnegative(site.get("upload")),
            "download": _nonnegative(site.get("download")),
            "bonus": _bonus(site.get("bonus")),
            "seeding": _nonnegative(site.get("seeding")),
            "seedingSize": _nonnegative(site.get("seeding_size")),
            "joinAt": str(site.get("join_at") or ""),
        })
    if not normalized:
        raise StatsNotReady("site_statistics_empty")
    return normalized


def push_snapshot(request, *, instance_id, plugin_version, sites,
                  movie_pilot_version="", batch_id=None, now=None):
    """构造 payload 并 PUT 快照；batch_id 由调用方在同一轮重试间复用以保证幂等。"""
    if not sites:
        raise StatsNotReady("site_statistics_empty")
    moment = now or datetime.now(timezone.utc)
    payload = {
        "schemaVersion": 2,
        "instanceId": instance_id,
        "pluginVersion": plugin_version,
        "moviePilotVersion": movie_pilot_version,
        "clientBatchId": batch_id or f"{instance_id}-{moment.isoformat()[:19]}",
        "collectedAt": moment.isoformat(),
        "sites": sites,
    }
    return request("PUT", "/pt-life/snapshot", json=payload)
