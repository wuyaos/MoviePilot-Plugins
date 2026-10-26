"""轨道状态表：每站×动作的规范化当前状态；历史只做流水，状态表供收集与展示。"""
import json
from copy import deepcopy
from datetime import datetime
from threading import Lock
from typing import Callable

from .models import UNIFIED_REASON_ALREADY, UNIFIED_REASON_UNKNOWN, unify_result

VERSION = 2
SUCCESS = "success"
FAILED = "failed"
PENDING = "pending"
DISABLED = "disabled"
TRACKS = ("sign", "login")

# 门控类 skipped：结构性禁用（不进队列、不重试），reason 即判定依据。
GATE_SKIPS = frozenset({
    "signin_not_selected", "site_disabled", "signin_not_supported", "signin_not_applicable",
    "native_unverified", "hook_not_implemented", "pilot_not_enabled", "site_removed",
    "login_not_supported", "login_not_selected",
})
# 纯空转结果：只写历史，不改状态表（锁忙/取消不得降级已有结论）。
TRANSIENT_SKIPS = frozenset({"skipped", "cancelled"})
# 已知原始结果值全集（适配器协议值 + 统一值）；未知值归 pending 且保留 metadata.raw_status。
RAW_RESULT_STATUSES = frozenset({
    "success", "already", "signed", "login_ok", "failed", "auth_failed", "unconfirmed",
    "network_error", "maintenance", "protocol_pending", "skipped", "cancelled"})

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
    """唯一映射点：运行/历史结果值（原始或统一）→ 轨道四值状态（success/failed/pending/disabled）。

    原始值先经 unify_result 归一：signed/login_ok → success；failed/auth_failed → failed；
    pending 族与未知值 → pending（未知不算 failed，pending 不即时重试）。
    """
    status = (getattr(status, "value", None) or (status or "")).strip()
    unified, reason = unify_result(status, reason)
    if unified in GATE_SKIPS or (reason or "") in GATE_SKIPS:
        return DISABLED
    if unified in TRANSIENT_SKIPS or not unified:
        return PENDING
    if track == "sign" and unified == "signed":
        return SUCCESS
    if track == "login" and unified == "login_ok":
        return SUCCESS
    return FAILED if unified == "failed" else PENDING


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
            if isinstance(raw, dict) and raw.get("version") in (1, VERSION) and isinstance(raw.get("sites"), dict):
                self._data = deepcopy(raw)
            self._data.setdefault("version", VERSION)
            self._data.setdefault("day", "")
            self._data.setdefault("updated", "")
            self._data.setdefault("sites", {})
            self._loaded = True
            # 旧读边界：仅 version==1 的旧表做一次性兼容归一（旧 signed 即旧 already）；
            # version>=2 新表 status=signed 无 reason 即本次成功，不再重解释。
            if self._data.get("version") == 1:
                self._compat_legacy_entries()
            self._data["version"] = VERSION

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

    def _compat_legacy_entries(self) -> None:
        """旧 track.state 条目兼容读取（读取时归一，不批量重写历史）：

        - failed+unconfirmed → pending+result_unknown（未知不算 failed）；
        - failed+auth_failed 补 reason=auth_failed（真正 failed 仍 failed）；
        - success+旧 signed 补 reason=already_signed（旧 signed 即旧 already）；
        - pending+network_error/maintenance/protocol_pending 补同名 reason 并统一 status=pending。
        """
        changed = False
        for tracks in self._data["sites"].values():
            for entry in tracks.values():
                state, status = entry.get("state"), entry.get("status", "")
                reason = entry.get("reason")
                if state == FAILED and status == "unconfirmed":
                    entry.update(state=PENDING, status="pending", reason=UNIFIED_REASON_UNKNOWN)
                    changed = True
                elif status and not reason:
                    # v1 旧表解释：signed 即旧 already；failed 族补精确 reason。
                    derived = None
                    if status == "signed":
                        derived = UNIFIED_REASON_ALREADY
                    elif status == "auth_failed":
                        derived = "auth_failed"
                    elif status in ("network_error", "maintenance", "protocol_pending"):
                        derived = status
                    if derived:
                        entry["reason"] = derived
                    if status in ("network_error", "maintenance", "protocol_pending"):
                        entry["status"] = "pending"
                    changed = True
        self._data["version"] = VERSION
        if changed:
            self._flush()

    # -- 写入 ---------------------------------------------------------------
    def apply_result(self, site: str, track: str, status: str, *, message: str = "",
                     reason: str | None = None, time: str | None = None,
                     metadata: dict | None = None) -> str:
        """执行结果 UPSERT；锁忙/取消只写历史不改表（调用方约定），此处再兜底跳过。

        status/reason 接受原始或统一值；落表前经 unify_result 归一（status 统一值、
        reason 精确值），未知 reason 由映射派生，不落空。
        """
        self.ensure()
        unified, derived = unify_result(status, reason)
        if unified in TRANSIENT_SKIPS and not (reason or "") in GATE_SKIPS:
            return self.state_of(site, track)
        state = normalize(track, status, reason)
        with self._lock:
            entry = self._entry(site, track)
            entry["state"] = state
            entry["status"] = unified
            entry["message"] = message or ""
            entry["time"] = time or self._clock().isoformat()
            # 诊断元数据（steps/page_action）随结果落表；空值清除残留避免陈旧误导。
            if metadata:
                entry["metadata"] = _clip_metadata(metadata)
            else:
                entry.pop("metadata", None)
            if derived:
                entry["reason"] = derived
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
                    # 有效队列重算不覆盖已有待处理结论；禁用/重新启用仍按决策更新。
                    if entry.get("state") == PENDING and state == PENDING and reason is None:
                        continue
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
        """今日三卡口径：success/failed 为今日结论，pending 含未执行。"""
        self.ensure()
        today = self._clock().date().isoformat()
        out = {track: {"success": 0, "failed": 0, "pending": 0} for track in TRACKS}
        with self._lock:
            sites = deepcopy(self._data["sites"])
        for tracks in sites.values():
            for track, entry in tracks.items():
                if track not in out:
                    continue
                if entry.get("state") == PENDING:
                    out[track]["pending"] += 1
                elif entry.get("time", "")[:10] == today:
                    if entry.get("state") == SUCCESS:
                        out[track]["success"] += 1
                    elif entry.get("state") == FAILED:
                        out[track]["failed"] += 1
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
                raw_status = item.get("status", "")
                # 旧读边界：旧 history 记录无 reason 字段，旧 signed 即旧 already；
                # 新记录（含 reason 键）的 signed 语义由其 reason 决定，不重解释。
                if "reason" in item:
                    raw_reason = item.get("reason")
                else:
                    raw_reason = "already_signed" if raw_status == "signed" else None
                entry["state"] = normalize(track, raw_status, raw_reason)
                entry["status"] = raw_status  # 旧原始值保留，派生 reason 供展示
                _, derived = unify_result(raw_status, raw_reason)
                if derived:
                    entry["reason"] = derived
                entry["message"] = item.get("message", "")
                entry["time"] = item.get("time", "")
            self._flush()


