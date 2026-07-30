"""执行历史存储。"""
from datetime import datetime, timedelta

import pytz
from app.core.config import settings


class HistoryStore:
    def __init__(self, plugin, key="history"):
        self.plugin = plugin
        self.key = key

    def append(self, records, keep_days=30):
        history = self.plugin.get_data(self.key) or []
        now = datetime.now(tz=pytz.timezone(settings.TZ))
        history.append({"date": now.strftime("%Y-%m-%d %H:%M:%S"), "records": records})
        cutoff = now - timedelta(days=max(1, int(keep_days)))
        history = [run for run in history
                   if self._parse(run.get("date"), now.tzinfo) >= cutoff]
        self.plugin.save_data(self.key, history)

    def latest(self, limit=20):
        return list(reversed((self.plugin.get_data(self.key) or [])[-limit:]))

    def terminal_keys_today(self):
        today = datetime.now(tz=pytz.timezone(settings.TZ)).strftime("%Y-%m-%d")
        return {
            record.get("execution_key")
            for run in self.plugin.get_data(self.key) or []
            if str(run.get("date", "")).startswith(today)
            for record in run.get("records") or []
            if record.get("terminal")
        }

    @staticmethod
    def _parse(value, tz):
        try:
            return tz.localize(datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S"))
        except Exception:
            return datetime.min.replace(tzinfo=tz)
