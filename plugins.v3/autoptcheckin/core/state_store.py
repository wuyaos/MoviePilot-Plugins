"""轨道状态表：每站×动作的规范化当前状态；历史只做流水，状态表供收集与展示。"""
import json
from copy import deepcopy
from datetime import datetime
from threading import Lock
from typing import Callable

VERSION = 1
SUCCESS = "success"
FAILED = "failed"
PENDING = "pending"
DISABLED = "disabled"
TRACKS = ("sign", "login")

# 成功族只有 success/signed：运行时 already 在 _record_result 入口统一归一为 signed（见插件侧），
# 状态表不再出现 already。
SIGN_SUCCESS = frozenset({"success", "signed"})
LOGIN_SUCCESS = frozenset({"login_ok"})
# 门控类 skipped：结构性禁用（不进队列、不重试），reason 即判定依据。
GATE_SKIPS = frozenset({
    "signin_not_selected", "site_disabled", "signin_not_supported", "signin_not_applicable",
    "native_unverified", "hook_not_implemented", "pilot_not_enabled", "site_removed",
    "login_not_supported", "login_not_selected",
})
# 纯空转结果：只写历史，不改状态表（锁忙/取消不得降级已有结论）。
TRANSIENT_SKIPS = frozenset({"skipped", "cancelled"})
NON_FAILURE = frozenset({"maintenance", "network_error", "protocol_pending"})
KNOWN_FAILURES = frozenset({"failed", "auth_failed", "unconfirmed"})
KNOWN_FAILURES = frozenset({"failed", "auth_failed", "unconfirmed"})

_METADATA_BUDGET = 2048


def _clip_metadata(meta: dict) -> dict:
    """metadata 落表前压缩：steps 截尾、超预算丢 steps 只留摘要，防止状态表膨胀。"""
    clipped = dict(meta)
    steps = clipped.get("steps")
    if isinstance(steps, list) and len(steps) > 5:
        clipped["steps"] = steps[:5] + [{"step": "...", "dropped": len(steps) - 5}]
    try:
        raw = json.dumps(clipped, ensure_ascii=False)
    except (TypeError, ValueError):
        return {"error": "metadata not serializable"}
    if len(raw) <= _METADATA_BUDGET:
        return clipped
    keep = {k: v for k, v in clipped.items() if k != "steps"}
    keep["steps_clipped"] = True
    if len(json.dumps(keep, ensure_ascii=False, default=str)) > _METADATA_BUDGET:
        return {"error": "metadata oversized"}
    return keep

def normalize(track: str, status: str, reason: str | None = None) -> str:
    """唯一映射点：运行/历史结果值 → 轨道四值状态（success/failed/pending/disabled）。"""
    status = (status or "").strip()
    if status in GATE_SKIPS or (reason or "") in GATE_SKIPS:
        return DISABLED
    if track == "sign" and status in SIGN_SUCCESS:
        return SUCCESS
    if track == "login" and status in LOGIN_SUCCESS:
        return SUCCESS
    if status in TRANSIENT_SKIPS or status in NON_FAILURE or not status:
        return PENDING
    return FAILED if status in KNOWN_FAILURES else PENDING


class TrackStateStore:
    """内存副本 + save_data 整键持久化；进程内锁防调度与 API 线程并发读改写。"""

    def __init__(self, load=None, save=None, clock: Callable = datetime.now) -> None:
        self._load_fn = load or (lambda key=None: None)
        self._save_fn = save or (lambda key, value: None)
        self._clock = clock
        self._lock = Lock()
        self._data: dict = {"version": VERSION, "day": "", "updated": "", "sites": {}}
        self._loaded = False

    # -- 基础 ---------------------------------------------------------------
    def ensure(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            raw = self._load_fn("track.state") if callable(self._load_fn) else None
            if isinstance(raw, dict) and raw.get("version") == VERSION and isinstance(raw.get("sites"), dict):
                self._data = deepcopy(raw)
            self._data.setdefault("version", VERSION)
            self._data.setdefault("day", "")
            self._data.setdefault("updated", "")
            self._data.setdefault("sites", {})
            self._loaded = True

    def _flush(self) -> None:
        self._data["updated"] = self._clock().isoformat()
        self._save_fn("track.state", deepcopy(self._data))

    def _entry(self, site: str, track: str) -> dict:
        return self._data["sites"].setdefault(str(site), {}).setdefault(track, {})

    def rollover(self) -> None:
        """日切：跨天后 success 失效为 pending（签到/登录均为每日任务）。"""
        self.ensure()
        today = self._clock().date().isoformat()
        with self._lock:
            if self._data.get("day") == today:
                return
            for tracks in self._data["sites"].values():
                for entry in tracks.values():
                    if entry.get("state") == SUCCESS:
                        entry.clear()
                        entry["state"] = PENDING
            self._data["day"] = today
            self._flush()

    # -- 写入 ---------------------------------------------------------------
    def apply_result(self, site: str, track: str, status: str, *, message: str = "",
                     reason: str | None = None, time: str | None = None,
                     metadata: dict | None = None) -> str:
        """执行结果 UPSERT；锁忙/取消只写历史不改表（调用方约定），此处再兜底跳过。"""
        self.ensure()
        if status in TRANSIENT_SKIPS and not (reason or "") in GATE_SKIPS:
            return self.state_of(site, track)
        state = normalize(track, status, reason)
        with self._lock:
            entry = self._entry(site, track)
            entry["state"] = state
            entry["status"] = status or ""
            entry["message"] = message or ""
            entry["time"] = time or self._clock().isoformat()
            # 诊断元数据（steps/page_action）随结果落表；空值清除残留避免陈旧误导。
            if metadata:
                entry["metadata"] = _clip_metadata(metadata)
            else:
                entry.pop("metadata", None)
            if reason:
                entry["reason"] = reason
            else:
                entry.pop("reason", None)
            self._flush()
        return state

    def set_state(self, site: str, track: str, state: str, *, reason: str | None = None) -> None:
        self.ensure()
        with self._lock:
            entry = self._entry(site, track)
            if entry.get("state") == state and entry.get("reason") == reason:
                return
            entry["state"] = state
            if reason:
                entry["reason"] = reason
            else:
                entry.pop("reason", None)
            self._flush()

    def reconfigure(self, decisions: dict[str, dict[str, tuple[str, str | None]]]) -> None:
        """配置变更后全量重算：decisions[site][track] = (state, reason)；success/failed 结论保留。"""
        self.ensure()
        with self._lock:
            for site, tracks in decisions.items():
                for track, (state, reason) in tracks.items():
                    entry = self._entry(site, track)
                    if entry.get("state") in (SUCCESS, FAILED):
                        continue
                    if entry.get("state") == state and entry.get("reason") == reason:
                        continue
                    entry.clear()
                    entry["state"] = state
                    if reason:
                        entry["reason"] = reason
            self._flush()

    def clear_transient(self) -> None:
        """清理缓存：非禁用轨道全部回到 pending，等待重新执行。"""
        self.ensure()
        with self._lock:
            for tracks in self._data["sites"].values():
                for entry in tracks.values():
                    if entry.get("state") == DISABLED:
                        continue
                    entry.clear()
                    entry["state"] = PENDING
            self._flush()

    # -- 读取 ---------------------------------------------------------------
    def state_of(self, site: str, track: str) -> str:
        self.ensure()
        with self._lock:
            entry = deepcopy(self._data["sites"].get(str(site), {}).get(track, {}))
        return entry.get("state", PENDING)

    def entry_of(self, site: str, track: str) -> dict:
        self.ensure()
        with self._lock:
            return deepcopy(self._data["sites"].get(str(site), {}).get(track, {}))

    def due_sites(self, track: str) -> list[str]:
        self.ensure()
        with self._lock:
            sites = deepcopy(self._data["sites"])
        return [site for site, tracks in sites.items()
                if tracks.get(track, {}).get("state") in (FAILED, PENDING)]

    def snapshot(self) -> dict:
        self.ensure()
        with self._lock:
            return deepcopy(self._data)

    def counts(self) -> dict:
        """今日三卡口径：success/failed（原始值非 unconfirmed）/unconfirmed。"""
        self.ensure()
        today = self._clock().date().isoformat()
        out = {track: {"success": 0, "failed": 0, "unconfirmed": 0} for track in TRACKS}
        with self._lock:
            sites = deepcopy(self._data["sites"])
        for tracks in sites.values():
            for track, entry in tracks.items():
                if track not in out or entry.get("time", "")[:10] != today:
                    continue
                if entry.get("state") == SUCCESS:
                    out[track]["success"] += 1
                elif entry.get("state") == FAILED:
                    key = "unconfirmed" if entry.get("status") == "unconfirmed" else "failed"
                    out[track][key] += 1
        return out

    def rebuild_from_history(self, records: list[dict]) -> None:
        """损坏/首次初始化：按最近历史（时间倒序）派生初始表，保留逐站最新结论。"""
        self.ensure()
        with self._lock:
            for item in records:
                track = item.get("action", "sign")
                if track not in TRACKS:
                    continue
                site = str(item.get("site"))
                entry = self._data["sites"].setdefault(site, {}).setdefault(track, {})
                if entry.get("state") in (SUCCESS, FAILED):
                    continue
                entry["state"] = normalize(track, item.get("status", ""), item.get("reason"))
                entry["status"] = item.get("status", "")
                entry["message"] = item.get("message", "")
                entry["time"] = item.get("time", "")
            self._flush()


