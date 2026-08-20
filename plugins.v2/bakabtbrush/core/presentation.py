"""通知和数据页共用的本地时间与间隔格式。"""

from __future__ import annotations

from datetime import datetime, timezone

try:
    from app.core.config import settings as _mp_settings
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo(getattr(_mp_settings, "TZ", "Asia/Shanghai"))
except Exception:
    _TZ = None


def format_local_time(value: datetime | str | None, *, compact: bool = False) -> str:
    timestamp = parse_datetime(value)
    if timestamp is None:
        return "未知"
    local = timestamp.astimezone(_TZ) if _TZ else timestamp.astimezone()
    return local.strftime("%m月%d日 %H:%M" if compact else "%Y-%m-%d %H:%M:%S")


def format_elapsed(start: datetime | str | None, end: datetime | None = None) -> str:
    started = parse_datetime(start)
    if started is None:
        return "未知"
    ended = _utc(end or datetime.now(timezone.utc))
    seconds = max(0, int((ended - started).total_seconds()))
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}分钟"
    hours, remainder = divmod(minutes, 60)
    if hours < 24:
        return f"{hours}小时{remainder}分钟" if remainder else f"{hours}小时"
    days, remainder_hours = divmod(hours, 24)
    return f"{days}天{remainder_hours}小时" if remainder_hours else f"{days}天"


def parse_datetime(value: datetime | str | None) -> datetime | None:
    if isinstance(value, datetime):
        return _utc(value)
    if not value:
        return None
    try:
        return _utc(datetime.fromisoformat(str(value).replace("Z", "+00:00")))
    except (TypeError, ValueError):
        return None


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
