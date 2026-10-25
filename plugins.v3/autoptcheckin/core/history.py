"""签到历史；持久化边界仅保存结果与页面证据，不保存凭据。

持久化后端为插件独立 SQLite（PLUGIN_DATA_PATH/AutoPtCheckin/autoptcheckin.db，WAL），
不再走宿主 save_data 整行 JSON 重写；未提供 db_path 时退化为内存后端（测试用）。
"""
import json
import sqlite3
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from threading import RLock
from .models import SignResult


def open_local_db(path) -> sqlite3.Connection:
    """打开（并按需初始化）插件本地库；调用方负责关闭。"""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("CREATE TABLE IF NOT EXISTS records ("
                 "seq INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT NOT NULL, data TEXT NOT NULL)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_records_time ON records(time)")
    conn.execute("CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.commit()
    return conn


class IconCacheDB:
    """favicon 缓存（kv 表）；value 为 base64 数据或空串（解析失败的负缓存）。"""

    def __init__(self, db_path):
        self._conn = open_local_db(db_path) if db_path else None

    def all(self) -> dict:
        if not self._conn:
            return {}
        rows = self._conn.execute("SELECT key, value FROM kv WHERE key LIKE 'icon:%'").fetchall()
        return {key.removeprefix("icon:"): value for key, value in rows}

    def put_many(self, mapping: dict) -> None:
        if not self._conn or not mapping:
            return
        with self._conn:
            self._conn.executemany(
                "INSERT INTO kv (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                [(f"icon:{sid}", value) for sid, value in mapping.items()])

    def get_flag(self, key: str):
        if not self._conn:
            return None
        row = self._conn.execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def set_flag(self, key: str, value: str = "1") -> None:
        if not self._conn:
            return
        with self._conn:
            self._conn.execute(
                "INSERT INTO kv (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))

    def put_many(self, mapping: dict) -> None:
        if not self._conn or not mapping:
            return
        with self._conn:
            self._conn.executemany(
                "INSERT INTO kv (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                [(f"icon:{sid}", value) for sid, value in mapping.items()])

    def import_json(self, db_path, cache: dict) -> int:
        """迁移导入旧 icon.cache JSON；返回导入条数。"""
        if not cache:
            return 0
        if not self._conn:
            self._conn = open_local_db(db_path)
        self.put_many({str(sid): value for sid, value in cache.items()})
        return len(cache)


class HistoryStore:
    KEY = "history.records"
    RETENTION_DAYS = 14

    def __init__(self, get_data=None, save_data=None, clock=None, db_path=None):
        self._get_data = get_data
        self._save_data = save_data
        self._clock = clock or (lambda: datetime.now().astimezone())
        self._records = []
        self._lock = RLock()
        self._conn = open_local_db(db_path) if db_path else None

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

    def import_json(self, db_path, records: list) -> int:
        """迁移导入宿主 history.records JSON；返回导入条数（超出保留期的不导）。"""
        if not records:
            return 0
        cutoff = self._clock() - timedelta(days=self.RETENTION_DAYS)
        fresh = []
        for item in records:
            try:
                if self._time(item["time"]) >= cutoff:
                    fresh.append(item)
            except (KeyError, ValueError):
                continue
        if not self._conn:
            self._conn = open_local_db(db_path)
        with self._conn:
            self._conn.executemany(
                "INSERT INTO records (time, data) VALUES (?, ?)",
                [(item["time"], json.dumps(item, ensure_ascii=False)) for item in fresh])
        return len(fresh)

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    # ---- 记录组装（两后端共用） ----

    def _normalize(self, result: SignResult | dict) -> dict:
        if isinstance(result, SignResult):
            evidence = asdict(result.evidence) if result.evidence else {}
            record = {"time": self._clock().isoformat(), "site": result.site_id,
                      "trigger": result.metadata.get("trigger", "manual"),
                      "action": result.metadata.get("action", "sign"),
                      "status": result.status.value, "message": result.message,
                      "reward": result.reward.reported if result.reward else None,
                      "evidence": {**evidence, "record_status": evidence.get("status", "")}}
        else:
            record = deepcopy(result)
        record["time"] = self._time(record.get("time") or self._clock().isoformat()).isoformat()
        record["status"] = "signed" if record["status"] == "already" else record["status"]
        evidence = record.get("evidence") or {}
        return {"time": record["time"], "site": record["site"], "status": record["status"],
                "trigger": record.get("trigger", "manual"),
                "action": record.get("action", "sign"),
                "message": record.get("message", ""), "reward": record.get("reward"),
                "evidence": {key: evidence.get(key, "") for key in
                             ("button_text", "uid", "date", "record_status")}}

    def append(self, result: SignResult | dict) -> dict:
        record = self._normalize(result)
        with self._lock:
            if self._conn:
                if self._time(record["time"]) >= self._clock() - timedelta(days=self.RETENTION_DAYS):
                    with self._conn:
                        self._conn.execute("INSERT INTO records (time, data) VALUES (?, ?)",
                                           (record["time"], json.dumps(record, ensure_ascii=False)))
                # 顺手清理过期行（字符串比较与 ISO 本地时区序一致，宽松边界可接受）
                cutoff = (self._clock() - timedelta(days=self.RETENTION_DAYS)).isoformat()
                with self._conn:
                    self._conn.execute("DELETE FROM records WHERE time < ?", (cutoff,))
            else:
                records = self._load()
                if self._time(record["time"]) >= self._clock() - timedelta(days=self.RETENTION_DAYS):
                    records.append(record)
                self._save(records)
        return deepcopy(record)

    def list(self, page: int = 1, size: int = 20) -> dict:
        page, size = max(1, page), max(1, min(100, size))
        with self._lock:
            if self._conn:
                total = self._conn.execute("SELECT count(*) FROM records").fetchone()[0]
                rows = self._conn.execute(
                    "SELECT data FROM records ORDER BY time DESC LIMIT ? OFFSET ?",
                    (size, (page - 1) * size)).fetchall()
                return {"total": total, "items": [json.loads(row[0]) for row in rows]}
            records = sorted(self._load(), key=lambda item: self._time(item["time"]), reverse=True)
            start = (page - 1) * size
            return {"total": len(records), "items": deepcopy(records[start:start + size])}

    def clear_today(self) -> int:
        """删除本地时区当天的签到缓存记录并返回删除数量。"""
        now = self._clock()
        with self._lock:
            if self._conn:
                rows = self._conn.execute("SELECT seq, data FROM records").fetchall()
                doomed = [seq for seq, data in rows
                          if self._time(json.loads(data)["time"]).astimezone(now.tzinfo).date() == now.date()]
                if doomed:
                    with self._conn:
                        self._conn.executemany("DELETE FROM records WHERE seq = ?", [(s,) for s in doomed])
                return len(doomed)
            records = self._load()
            kept = [item for item in records if self._time(item["time"]).astimezone(now.tzinfo).date() != now.date()]
            self._save(kept)
            return len(records) - len(kept)

    def today_counts(self) -> dict[str, int]:
        now = self._clock()
        # Network/protocol outcomes remain in history, outside the four result cards.
        counts = dict(success=0, signed=0, failed=0, unconfirmed=0)
        with self._lock:
            if self._conn:
                rows = self._conn.execute("SELECT data FROM records").fetchall()
                items = [json.loads(data) for (data,) in rows]
            else:
                items = self._load()
            for item in items:
                if item.get("action", "sign") == "sign" and self._time(item["time"]).astimezone(now.tzinfo).date() == now.date():
                    status = "failed" if item["status"] == "auth_failed" else item["status"]
                    if status in counts:
                        counts[status] += 1
        return counts
