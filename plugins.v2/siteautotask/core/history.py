"""运行历史存储与规范化。"""
import time
from datetime import datetime
import pytz
from app.core.config import settings
from app.log import logger
from .execution import is_terminal_success, record_execution_key

class HistoryStore:
    def __init__(self, plugin, key="history"):
        self.plugin = plugin
        self.key = key

    def append(self, records, keep_days=30):
        history = self.plugin.get_data(self.key) or []
        now = datetime.now(tz=pytz.timezone(settings.TZ)).strftime("%Y-%m-%d %H:%M:%S")
        history.append({"date": now, "records": records})
        if keep_days:
            try:
                cutoff = time.time() - int(keep_days) * 86400
                history = [item for item in history
                           if datetime.strptime(item["date"], "%Y-%m-%d %H:%M:%S").timestamp() >= cutoff]
            except Exception as e:
                logger.error(f"清理运行历史失败：{e}")
        self.plugin.save_data(self.key, history)
        return history

    def latest(self, limit=10):
        history = self.plugin.get_data(self.key) or []
        return list(reversed(history[-limit:]))

    def terminal_keys_today(self):
        """返回当天终态成功的执行键集合，供主 cron/手动补跑跳过。"""
        history = self.plugin.get_data(self.key) or []
        today = datetime.now(tz=pytz.timezone(settings.TZ)).strftime("%Y-%m-%d")
        return {
            record_execution_key(record)
            for run in history
            if str(run.get("date", "")).startswith(today)
            for record in (run.get("records") or [])
            if is_terminal_success(record)
        }
