"""聚影签到 V3（jying.top 账密模式，仅 B 路径）。

流程（docs/jyingcheckin-plan.md 修订 2）：
- 凭据 = username/password；token 存插件数据（7 天绝对过期，多端登录互不踢线）。
- 状态机五态：success / already / auth_failed / pending / unknown。
- 单轮最多重登 1 次；POST 后网络错误按 pending 重试（站点每日幂等，重发安全）。
- 重试链只在终态落一次历史与通知；成功/已签/认证失败不重试。
"""
from __future__ import annotations

import logging
import threading
from copy import deepcopy
from typing import Any

from .client import JyingClient
from .store import Store

try:
    from app.sdk.plugin import _PluginBase
except ImportError:  # 离线契约测试无宿主
    class _PluginBase:  # type: ignore[no-redef]
        pass

logger = logging.getLogger("JyingCheckin")

STATUS_SUCCESS = "success"
STATUS_ALREADY = "already"
STATUS_AUTH_FAILED = "auth_failed"
STATUS_PENDING = "pending"
STATUS_UNKNOWN = "unknown"



class JyingCheckin(_PluginBase):
    plugin_id = "JyingCheckin"
    plugin_name = "聚影签到"
    plugin_desc = "聚影 jying.top 每日签到保活：账密自动登录、token 续期，支持普通/幸运签到"
    plugin_version = "1.0.0"
    plugin_author = "jtcym"
    plugin_icon = "jyingcheckin.png"
    plugin_config_prefix = "jyingcheckin_"
    plugin_order = 26
    auth_level = 1

    def __init__(self):
        self._config: dict = {}
        self._stopped = False
        self._services: list[dict] = []
        self._schedule_error: str | None = None
        self._round_lock = threading.Lock()
        self._client = JyingClient()
        self._store = Store(self._data_get, self._data_set)

    # ---- 宿主数据读写（离线无宿主时退化为内存） ---------------------------

    def _data_get(self, key: str) -> Any:
        try:
            return self.get_data(key)
        except Exception:
            return None

    def _data_set(self, key: str, value: Any) -> None:
        try:
            self.save_data(key, value)
        except Exception:
            pass

    # ---- 生命周期 ---------------------------------------------------------

    def init_plugin(self, config: dict | None = None) -> None:
        self.stop_service()
        self._config = {**self.get_form()[1], **deepcopy(config or {})}
        self._stopped = False
        self._schedule_error = None
        enabled = bool(self._config.get("enabled"))
        if enabled and self._config.get("onlyonce"):
            from apscheduler.triggers.date import DateTrigger

            self._services = [{"id": "JyingCheckinRunOnce", "name": "聚影签到单次运行",
                               "trigger": DateTrigger(), "func": self.run_once, "kwargs": {}}]
        elif enabled and self._config.get("cron"):
            try:
                from apscheduler.triggers.cron import CronTrigger
                from app.sdk.config import settings

                trigger = CronTrigger.from_crontab(self._config["cron"], timezone=settings.TZ)
                self._services = [{"id": "JyingCheckinScheduled", "name": "聚影定时签到",
                                   "trigger": trigger, "func": self.run_once, "kwargs": {}}]
            except (ValueError, TypeError, ImportError):
                self._schedule_error = "invalid_cron"

    def get_state(self) -> bool:
        return bool(self._config.get("enabled")) and not self._stopped

    def get_service(self) -> list[dict]:
        return list(self._services)

    def stop_service(self) -> None:
        self._stopped = True
        self._services = []
        try:
            from app.sdk.scheduler import remove_plugin_job

            remove_plugin_job(self.plugin_id)
        except ImportError:
            pass

    # ---- V3 页面契约 -------------------------------------------------------

    def get_form(self) -> tuple[list, dict]:
        from .config_form import build_form
        return build_form()

    def get_page(self) -> list:
        """数据页：登录状态 KPI + 最近签到记录表（声明式 Vuetify JSON）。"""
        session = self._store.get_session()
        latest = self._store.get_latest()
        history = [h for h in self._store.get_history() if isinstance(h, dict)]
        expires_at = session.get("expires_at") or 0

        from datetime import datetime
        if session.get("token"):
            login_text = f"有效（token 至 {datetime.fromtimestamp(expires_at).strftime('%m-%d %H:%M')}）" if expires_at else "有效"
            login_color = "success"
        else:
            login_text, login_color = "未登录", "error"

        status_labels = {
            STATUS_SUCCESS: ("签到成功", "success"),
            STATUS_ALREADY: ("今日已签", "info"),
            STATUS_AUTH_FAILED: ("认证失败", "error"),
            STATUS_PENDING: ("待确认", "warning"),
            STATUS_UNKNOWN: ("未确认", "warning"),
        }
        latest_text, latest_color = ("暂无记录", "grey") if not latest else status_labels.get(
            latest.get("status"), (latest.get("status"), "grey"))
        lucky_text = "已开启" if self._config.get("lucky_mode") else "关闭"
        ok_days = len({h.get("date") for h in history if h.get("status") in (STATUS_SUCCESS, STATUS_ALREADY)})

        def kpi(icon: str, label: str, value: str, color: str = "") -> dict:
            value_cls = f"text-h6 font-weight-bold text-{color}" if color else "text-h6 font-weight-bold"
            return {
                "component": "VCard",
                "props": {"variant": "tonal", "class": "h-100"},
                "content": [
                    {"component": "VCardText", "props": {"class": "text-center pa-3"}, "content": [
                        {"component": "div", "props": {"class": "text-h5 mb-1"}, "text": icon},
                        {"component": "span", "props": {"class": value_cls}, "text": value},
                        {"component": "span", "props": {"class": "text-caption text-medium-emphasis d-block mt-1"}, "text": label},
                    ]},
                ],
            }

        page: list = [{
            "component": "VRow",
            "props": {"dense": True},
            "content": [
                {"component": "VCol", "props": {"cols": 6, "md": 3}, "content": [kpi("🔐", "登录状态", login_text, login_color)]},
                {"component": "VCol", "props": {"cols": 6, "md": 3}, "content": [kpi("📊", "最近签到", latest_text, latest_color)]},
                {"component": "VCol", "props": {"cols": 6, "md": 3}, "content": [kpi("🍀", "幸运模式", lucky_text, "success" if self._config.get("lucky_mode") else "")]},
                {"component": "VCol", "props": {"cols": 6, "md": 3}, "content": [kpi("📅", "累计成功", f"{ok_days} 天", "info")]},
            ],
        }]

        rows = []
        for idx, h in enumerate(history[:30], start=1):
            label, color = status_labels.get(h.get("status"), (h.get("status"), "medium-emphasis"))
            mode = "幸运签" if h.get("lucky") else "普通签"
            days = h.get("days")
            points = h.get("points")
            award = " / ".join(part for part in [
                f"{days} 天" if days is not None else "",
                f"{points} 分" if points is not None else "",
            ] if part)
            rows.append([
                (str(idx), "text-body-2 text-medium-emphasis"),
                (str(h.get("time") or h.get("date") or "—"), "text-body-2"),
                (mode, "text-body-2 text-center"),
                (award or "—", "text-body-2 text-center"),
                (str(h.get("message") or ""), "text-body-2 text-medium-emphasis"),
                (label, f"text-body-2 text-center text-{color}"),
            ])

        header_cells = [("#", ""), ("时间", ""), ("模式", "text-center"), ("奖励", "text-center"),
                        ("消息", ""), ("状态", "text-center")]
        table = {
            "component": "VTable",
            "props": {"density": "comfortable"},
            "content": [
                {"component": "thead", "content": [
                    {"component": "tr", "content": [
                        {"component": "th", "props": {"class": c or "text-caption text-medium-emphasis"}, "text": t}
                        for t, c in header_cells
                    ]},
                ]},
                {"component": "tbody", "content": [
                    {"component": "tr", "content": [
                        {"component": "td", "props": {"class": c}, "text": t} for t, c in row
                    ]} for row in rows
                ]},
            ],
        }
        page.append({
            "component": "VRow",
            "content": [
                {"component": "VCol", "props": {"cols": 12}, "content": [
                    {"component": "VCard", "props": {"variant": "tonal"}, "content": [
                        {"component": "VCardTitle", "text": "📋 签到记录（最近 30 条）"},
                        {"component": "VCardText", "props": {"class": "pa-2"}, "content": [
                            table if rows else {"component": "VAlert", "props": {"type": "info", "variant": "tonal", "text": "暂无签到记录，等待首次签到后生成"}},
                        ]},
                    ]},
                ]},
            ],
        })
        return page

    def get_api(self) -> list[dict]:
        specs = [("/checkin", self.api_checkin, "POST"),
                 ("/status", self.api_status, "GET"),
                 ("/history", self.api_history, "GET")]
        return [{"path": path, "endpoint": endpoint, "methods": [method], "auth": "bear"}
                for path, endpoint, method in specs]

    # ---- 核心编排：单轮签到 -------------------------------------------------

    def run_once(self, trigger: str = "scheduled") -> dict:
        """一轮签到，返回终态 dict（含 status/message）。"""
        if not self._round_lock.acquire(blocking=False):
            return {"status": "busy", "message": "上一轮仍在执行"}
        try:
            result = self._execute(trigger)
        except Exception as exc:  # 编排兜底：未预期异常按 pending 处理
            logger.error("聚影签到执行异常：%s", exc, exc_info=True)
            result = {"status": STATUS_PENDING, "message": f"执行异常: {exc.__class__.__name__}"}
        finally:
            self._round_lock.release()
        return self._finalize(result, trigger)

    def _execute(self, trigger: str) -> dict:
        cfg = self._config
        username = str(cfg.get("username") or "")
        password = str(cfg.get("password") or "")
        if not username or not password:
            return {"status": STATUS_AUTH_FAILED, "message": "未配置账号或密码"}

        relogin_budget = 1  # 单轮最多整段重登一次
        refreshed = False
        session = self._store.get_session()
        token = session.get("token") or ""

        # 1) 有 token 先探测（顺带拿 checked_today）
        if token and not self._store.session_expired():
            probe = self._client.stats(token)
            if probe.ok:
                data = probe.data
                if data.get("checked_today"):
                    return {**self._terminal(STATUS_ALREADY, message="今日已签到", probe=data),
                            "token_refreshed": refreshed}
                # 未签 → 直接签到（进入第 3 步）
            elif probe.auth_expired:
                token = ""
            else:
                # 网络错误 / 非 JSON：探测失败不等于未签，按 pending 重试
                return {"status": STATUS_PENDING,
                        "message": probe.error or probe.message or "状态探测失败",
                        "token_refreshed": refreshed}

        # 2) 无 token → 登录
        if not token:
            login = self._client.login(username, password)
            if not login.ok:
                if login.error.startswith("network:"):
                    return {"status": STATUS_PENDING, "message": login.error,
                            "token_refreshed": refreshed}
                return {"status": STATUS_AUTH_FAILED, "message": login.message or "登录失败",
                        "token_refreshed": refreshed}
            token = login.token
            self._store.save_session(login.token, login.user_id, login.expires_at)
            relogin_budget -= 1
            refreshed = True

        # 3) 签到（幸运签需 user_id，未知则降级普通签并在文案注明）
        lucky = bool(cfg.get("lucky_mode"))
        user_id = self._store.get_session().get("user_id")
        if lucky and user_id is None:
            lucky = False
            degraded_note = "（幸运签缺少 user_id，已降级普通签）"
        else:
            degraded_note = ""
        submit = self._client.luck_draw(token, user_id) if lucky else self._client.do_checkin(token)

        # 4) 提交期 auth 失效：重登一次再试
        if submit.auth_expired and relogin_budget > 0:
            relogin_budget -= 1
            refreshed = True
            login = self._client.login(username, password)
            if login.ok:
                self._store.save_session(login.token, login.user_id, login.expires_at)
                token = login.token
                user_id = self._store.get_session().get("user_id")
                if lucky and user_id is not None:
                    submit = self._client.luck_draw(token, user_id)
                else:
                    lucky = False
                    submit = self._client.do_checkin(token)
            # 重登失败时沿用 submit 的 auth_expired 结果走下方分支

        # 5) 提交结果归类
        if submit.ok:
            data = submit.data
            return {
                "status": STATUS_SUCCESS,
                "message": (submit.message or "签到成功") + degraded_note,
                "mode": "lucky" if lucky else "normal",
                "days": data.get("my_total_days") or data.get("total_days"),
                "points": data.get("reward_points") or data.get("points"),
                "lucky": lucky,
                "token_refreshed": refreshed,
            }
        if submit.auth_expired:
            return {"status": STATUS_AUTH_FAILED,
                    "message": submit.message or "会话失效且重新登录未成功",
                    "token_refreshed": refreshed}
        if submit.error.startswith("network:"):
            # POST 可能已落地；站点每日幂等，重试安全
            return {"status": STATUS_PENDING, "message": submit.error,
                    "token_refreshed": refreshed}
        message = submit.message or submit.error or f"HTTP {submit.http_status}"
        if "已签" in message:
            return {**self._terminal(STATUS_ALREADY, message=message), "token_refreshed": refreshed}
        return {"status": STATUS_UNKNOWN, "message": message, "token_refreshed": refreshed}

    @staticmethod
    def _terminal(status: str, message: str, probe: dict | None = None) -> dict:
        result = {"status": status, "message": message}
        if isinstance(probe, dict):
            result["days"] = probe.get("my_total_days")
            result["points"] = probe.get("reward_points")
        return result

    # ---- 终态落盘 / 重试链 / 通知 -------------------------------------------

    def _finalize(self, result: dict, trigger: str) -> dict:
        status = result.get("status") or STATUS_UNKNOWN
        today = self._today()

        if status == STATUS_PENDING:
            retry_used = int(result.get("retry_used") or 0)
            max_retry = int(self._config.get("retry_count") or 0)
            if retry_used < max_retry:
                self._schedule_retry(retry_used + 1)
                return {**result, "date": today, "retrying": True}
            # 额度耗尽 → pending 终态
            result["retry_used"] = retry_used

        record = self._store.record({**result, "date": today})
        self._notify(status, record)
        logger.info("聚影签到终态：%s（%s / %s）", status, trigger, record.get("message"))
        return record

    def _schedule_retry(self, retry_used: int) -> None:
        """pending 中间态：retry_interval 分钟后重跑一次（不落历史不通知）。"""
        try:
            from apscheduler.triggers.date import DateTrigger
            from datetime import datetime, timedelta

            minutes = int(self._config.get("retry_interval") or 5)
            self._services = [{
                "id": f"JyingCheckinRetry-{retry_used}",
                "name": f"聚影签到重试({retry_used})",
                "trigger": DateTrigger(run_date=datetime.now() + timedelta(minutes=minutes)),
                "func": self.run_once,
                "kwargs": {"trigger": f"retry-{retry_used}"},
            }]
        except Exception:
            logger.warning("聚影签到重试调度注册失败", exc_info=True)

    def _notify(self, status: str, record: dict) -> None:
        if not self._config.get("notify"):
            return
        text = record.get("message") or status
        if record.get("days"):
            text += f"\n累计签到 {record['days']} 天"
        if record.get("points") is not None:
            text += f"\n获得积分 {record['points']}"
        try:
            self.post_message(title="【聚影签到】", text=text)
        except Exception:
            logger.warning("聚影签到通知发送失败", exc_info=True)

    @staticmethod
    def _today() -> str:
        from datetime import datetime

        return datetime.now().strftime("%Y-%m-%d")

    # ---- API ----------------------------------------------------------------

    def api_checkin(self, body: dict | None = None) -> dict:
        """手动签到：同步执行一轮并返回终态。"""
        if not self._config.get("enabled"):
            return {"success": False, "message": "插件未启用", "data": None}
        result = self.run_once(trigger="manual")
        if result.get("status") == "busy":
            return {"success": False, "message": result["message"], "data": None}
        ok = result.get("status") in (STATUS_SUCCESS, STATUS_ALREADY)
        return {"success": ok, "message": result.get("message") or result.get("status"), "data": result}

    def api_status(self) -> dict:
        session = self._store.get_session()
        from datetime import datetime

        expires_at = session.get("expires_at") or 0
        return {
            "success": True,
            "message": "",
            "data": {
                "enabled": bool(self._config.get("enabled")),
                "lucky_mode": bool(self._config.get("lucky_mode")),
                "logged_in": bool(session.get("token")),
                "token_expires_at": datetime.fromtimestamp(expires_at).strftime("%Y-%m-%d %H:%M:%S") if expires_at else None,
                "latest": self._store.get_latest(),
                "schedule_error": self._schedule_error,
            },
        }

    def api_history(self, body: dict | None = None) -> dict:
        return {"success": True, "message": "", "data": {"items": self._store.get_history()}}
