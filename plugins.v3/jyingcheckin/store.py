"""插件数据存储：session（token 会话）/ latest（最近结果）/ history（历史）。

凭据边界：token 只存插件数据（不回写配置、不进日志/历史/通知）；history 落盘前
剥离敏感字段，仅保留状态、站点原文文案与奖励证据。历史保留 90 天、上限 200 条。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Callable

HISTORY_KEY = "jyingcheckin_history"
LATEST_KEY = "jyingcheckin_latest"
SESSION_KEY = "jyingcheckin_session"

HISTORY_RETENTION_DAYS = 90
HISTORY_MAX_ENTRIES = 200

# 落盘白名单：终态记录只保留这些键
HISTORY_FIELDS = (
    "date", "time", "status", "mode", "message", "days", "points",
    "lucky", "retry_used", "token_refreshed",
)


class Store:
    """适配宿主 get_data/save_data 的插件数据层（离线测试可注入内存实现）。"""

    def __init__(self, getter: Callable[[str], Any], setter: Callable[[str, Any], None]):
        self._get = getter
        self._set = setter

    # ---- session（token 会话，含续登回写） --------------------------------

    def get_session(self) -> dict:
        data = self._get(SESSION_KEY)
        return data if isinstance(data, dict) else {}

    def save_session(self, token: str, user_id: Any, expires_at: float) -> None:
        self._set(SESSION_KEY, {"token": token, "user_id": user_id, "expires_at": expires_at})

    def clear_session(self) -> None:
        self._set(SESSION_KEY, None)

    def session_expired(self) -> bool:
        """本地预判：超过 token TTL 视为疑似过期（真正判据仍是站点 401）。"""
        session = self.get_session()
        expires_at = session.get("expires_at") or 0
        if not session.get("token"):
            return True
        return expires_at <= 0 or expires_at <= datetime.now().timestamp()

    # ---- latest / history（终态记录） -------------------------------------

    def get_latest(self) -> dict:
        data = self._get(LATEST_KEY)
        return data if isinstance(data, dict) else {}

    def get_history(self) -> list:
        data = self._get(HISTORY_KEY)
        return data if isinstance(data, list) else []

    def record(self, result: dict) -> dict:
        """落一条终态：剥离敏感字段 → 更新 latest → 追加 history（去 Trim）。"""
        clean = {key: result.get(key) for key in HISTORY_FIELDS if result.get(key) is not None}
        clean["time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._set(LATEST_KEY, clean)
        history = [entry for entry in self.get_history() if isinstance(entry, dict)]
        history.insert(0, clean)
        history = [entry for entry in history if self._within_retention(entry)][:HISTORY_MAX_ENTRIES]
        self._set(HISTORY_KEY, history)
        return clean

    @staticmethod
    def _within_retention(entry: dict) -> bool:
        date = str(entry.get("date") or "")
        try:
            entry_day = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            return True  # 无法解析的旧条目按保留处理，交给条数上限裁剪
        return entry_day >= datetime.now() - timedelta(days=HISTORY_RETENTION_DAYS)
