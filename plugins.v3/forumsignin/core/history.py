"""签到历史；持久化边界仅保存结果与页面证据，不保存凭据。"""
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timedelta
from threading import RLock
from .models import SignResult


class HistoryStore:
    KEY = "history.records"
    RETENTION_DAYS = 90

    def __init__(self, get_data=None, save_data=None, clock=None):
        self._get_data = get_data
        self._save_data = save_data
        self._clock = clock or (lambda: datetime.now().astimezone())
        self._records = []
        self._lock = RLock()

    @staticmethod
    def _time(value):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone()  # naive times use the host's local timezone

    def _load(self):
        records = deepcopy(self._get_data(self.KEY) or []) if self._get_data else self._records
        cutoff = self._clock() - timedelta(days=self.RETENTION_DAYS)
        kept = [item for item in records if self._time(item["time"]) >= cutoff]
        if len(kept) != len(records):
            self._save(kept)
        return kept

    def _save(self, records):
        self._records = deepcopy(records)
        if self._save_data:
            self._save_data(self.KEY, deepcopy(records))

    def append(self, result: SignResult | dict) -> dict:
        if isinstance(result, SignResult):
            evidence = asdict(result.evidence) if result.evidence else {}
            record = {"time": self._clock().isoformat(), "site": result.site_id,
                      "trigger": result.metadata.get("trigger", "manual"),
                      "status": result.status.value, "message": result.message,
                      "reward": asdict(result.reward) if result.reward else None,
                      "evidence": {**evidence, "record_status": evidence.get("status", "")}}
        else:
            record = deepcopy(result)
        record["time"] = self._time(record.get("time") or self._clock().isoformat()).isoformat()
        record["status"] = "signed" if record["status"] == "already" else record["status"]
        evidence = record.get("evidence") or {}
        record = {"time": record["time"], "site": record["site"], "status": record["status"],
                  "trigger": record.get("trigger", "manual"),
                  "message": record.get("message", ""), "reward": record.get("reward"),
                  "evidence": {key: evidence.get(key, "") for key in
                               ("button_text", "uid", "date", "record_status", "source")}}
        with self._lock:
            records = self._load()
            if self._time(record["time"]) >= self._clock() - timedelta(days=self.RETENTION_DAYS):
                records.append(record)
            self._save(records)
        return deepcopy(record)

    def list(self, page: int = 1, size: int = 20) -> dict:
        page, size = max(1, page), max(1, min(100, size))
        with self._lock:
            records = sorted(self._load(), key=lambda item: self._time(item["time"]), reverse=True)
            start = (page - 1) * size
            return {"total": len(records), "items": deepcopy(records[start:start + size])}

    def today_counts(self) -> dict[str, int]:
        now = self._clock()
        counts = dict(success=0, signed=0, failed=0, unconfirmed=0)
        with self._lock:
            for item in self._load():
                if self._time(item["time"]).astimezone(now.tzinfo).date() == now.date():
                    status = "failed" if item["status"] == "auth_failed" else item["status"]
                    if status in counts:
                        counts[status] += 1
        return counts
