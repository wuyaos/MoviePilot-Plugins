"""任务执行引擎。

只负责编排：站点发现、任务开关、结果收集、反馈关联与通知数据。
站点业务逻辑留在 sites/，UI 留在 ui/，调度留在 scheduler.py。
"""
from datetime import datetime, timedelta
import threading
import pytz
from app.core.config import settings
from app.log import logger
from ..base.result import TaskResult
from ..base.decorator import TaskType
from .task_keys import site_task_key, claim_task_key
from ..sites import get_site_handler
from ..utils.display import display_record_lines, display_task
from ..utils.feedback import NotificationIcons, detect_reward_type


class TaskEngine:
    def __init__(self, plugin):
        self.plugin = plugin
        self.history = plugin.history
        self._lock = threading.Lock()

    def run_scheduled(self):
        """主 cron：执行除织梦喊话外的全部任务，跳过今天已成功任务。"""
        return self.run(skip_successful=True)

    def run(self, retry_only=False, manual_only=False, skip_successful=False):
        """执行主任务组；织梦喊话始终由独立调度处理。"""
        if not self._lock.acquire(blocking=False):
            logger.warning("已有站点任务正在执行，跳过本次调度")
            return []
        try:
            return self._run_locked(
                retry_only=retry_only,
                manual_only=manual_only,
                skip_successful=skip_successful,
            )
        finally:
            self._lock.release()

    def _run_locked(self, retry_only=False, manual_only=False, skip_successful=False):
        cfg = self.plugin.config
        retry_keys = {item.get("task_id") for item in getattr(self.plugin, "retry_records", [])} if retry_only else None
        should_skip_successful = manual_only or skip_successful or retry_only
        successful_today = self.history.successful_task_ids_today() if should_skip_successful else set()
        if not cfg.chat_sites:
            logger.info("未配置需要执行的站点")
            return []
        records = []
        skipped_successful = 0
        run_label = "失败重试" if retry_only else ("手动补跑" if manual_only else "主定时")
        for site, handler, task, claim_id in self._collect_configured_tasks("main"):
            task_key = task["config_key"]
            if retry_keys is not None and task.get("id") not in retry_keys and task_key not in retry_keys:
                continue

            if should_skip_successful and task.get("id") in successful_today:
                skipped_successful += 1
                task_name = display_task(
                    handler.site_name,
                    task.get("label") or task.get("id"),
                    task.get("task_type"),
                )
                logger.info(f"{run_label} - {handler.site_name} - {task_name} - 今天已经成功，跳过")
                continue
            record = self._run_task(handler, task, claim_task_id=claim_id, skip_if_no_claim=True)
            records.append(record)
        if records:
            self.history.append(records, cfg.history_days)
            self._schedule_failed(records, is_retry=retry_only)
            from .notify import send_summary
            send_summary(self.plugin, records, is_retry=retry_only)
        if should_skip_successful:
            logger.info(
                f"{run_label}完成：执行 {len(records)} 个任务，"
                f"跳过 {skipped_successful} 个今天已成功任务"
            )
        return records

    def _build_handler(self, site):
        info = dict(site)
        info["use_proxy"] = self.plugin.config.use_proxy
        info["feedback_timeout"] = self.plugin.config.feedback_timeout
        info["interval_cnt"] = self.plugin.config.interval_cnt
        try:
            return get_site_handler(info, self.plugin.handler_classes)
        except Exception as e:
            logger.error(f"构造站点处理器失败：{site.get('name')}，错误：{e}")
            return None

    def _configure_task(self, site, task):
        """按配置页控件解析任务：下拉非空即启用，其余由开关控制。"""
        task = dict(task)
        task_key = site_task_key(site, task)
        task["config_key"] = task_key
        if not task.get("claim_options"):
            return task, None, self.plugin.task_enabled(task_key)

        task["claim_key"] = claim_task_key(site, task)
        claim_id = self.plugin.claim_task_id(task["claim_key"])
        if task.get("task_type") == TaskType.CLAIM and claim_id:
            selected_id = str(claim_id)
            selected_option = next(
                (option for option in task["claim_options"] if str(option.get("id")) == selected_id),
                None,
            )
            if selected_option:
                task["selected_option_label"] = selected_option.get("label") or task.get("label")
        return task, claim_id, bool(claim_id)

    def _collect_configured_tasks(self, scope, site_handlers=None):
        """按配置收集任务组：main 排除织梦喊话，medal 仅勋章，zm 仅织梦喊话。"""
        if site_handlers is None:
            site_handlers = (
                (site, self._build_handler(site))
                for site in self.plugin.selected_sites()
            )
        for site, handler in site_handlers:
            if not handler:
                continue
            is_zm = hasattr(handler, "get_latest_message_time")
            for raw_task in self.plugin.tasks_for(handler):
                task_type = raw_task.get("task_type")
                if scope == "main" and is_zm and task_type == TaskType.CHAT:
                    continue
                if scope == "medal" and task_type != TaskType.MEDAL:
                    continue
                if scope == "zm" and (not is_zm or task_type != TaskType.CHAT):
                    continue
                task, claim_id, enabled = self._configure_task(site, raw_task)
                if enabled:
                    yield site, handler, task, claim_id

    def _run_task(self, handler, task, claim_task_id=None, skip_if_no_claim=False):
        """执行单个任务，并统一记录任务进度、喊话内容与反馈。"""
        now = datetime.now(tz=pytz.timezone(settings.TZ)).strftime("%Y-%m-%d %H:%M:%S")
        task_label = task.get("selected_option_label") or task.get("label") or task.get("id")
        task_name = display_task(handler.site_name, task_label, task.get("task_type"))
        sent_messages = []
        original_send = getattr(handler, "send_messagebox", None)
        if task.get("task_type") == TaskType.CHAT and callable(original_send):
            def tracked_send(message=None, *args, **kwargs):
                message = str(message or "")
                message_name = f"[喊话] “{message}”"
                if message:
                    sent_messages.append(message)
                    logger.info(f"{handler.site_name} - {message_name} -> 开始发送")
                outcome = original_send(message, *args, **kwargs)
                if message:
                    success = bool(outcome and outcome[0]) if isinstance(outcome, tuple) else bool(outcome)
                    detail = str(outcome[1] or "") if isinstance(outcome, tuple) and len(outcome) > 1 else ""
                    phase = "发送成功" if success else "发送失败"
                    if detail in {"发送成功", "消息发送成功", ""}:
                        detail = ""
                    logger.info(f"{handler.site_name} - {message_name} -> {phase}{f' -> {detail}' if detail else ''}")
                return outcome
            handler.send_messagebox = tracked_send
            original_collect = getattr(handler, "collect_message_feedback", None)
            if callable(original_collect):
                def tracked_collect(message, *args, **kwargs):
                    feedback = original_collect(message, *args, **kwargs)
                    message_name = f"[喊话] “{message}”"
                    if feedback:
                        icon = NotificationIcons.get(detect_reward_type(str(feedback)))
                        logger.info(f"{handler.site_name} - {message_name} -> {icon} {feedback}")
                    else:
                        logger.info(f"{handler.site_name} - {message_name} -> 无反馈")
                    return feedback
                handler.collect_message_feedback = tracked_collect
        else:
            original_collect = None
        if task.get("task_type") != TaskType.CHAT:
            logger.info(f"{handler.site_name} - {task_name} - 开始执行")
        try:
            needs_claim_id = task.get("task_type") == TaskType.CLAIM or task.get("claim_options")
            if needs_claim_id:
                if skip_if_no_claim and not claim_task_id:
                    return {
                        "date": now, "site": handler.site_name, "domain": handler.domain,
                        "task_id": task.get("id"), "task_label": task.get("label"),
                        "task_type": task.get("task_type", TaskType.GENERIC),
                        "success": True, "status": "未配置，跳过",
                    }
                raw = task["func"](claim_task_id) if claim_task_id is not None else task["func"]()
            else:
                raw = task["func"]()
            result = self.normalize_result(raw)
            feedback = None
            if task.get("task_type") == TaskType.CHAT and self.plugin.config.get_feedback:
                feedback = handler.get_feedback()
            status = result.message
            if task.get("task_type") == TaskType.CHAT and result.success and sent_messages:
                status = f"已发送“{'；'.join(sent_messages)}”"
            record = {
                "date": now, "site": handler.site_name, "domain": handler.domain,
                "task_id": task["id"], "task_label": task_label,
                "task_type": task.get("task_type", TaskType.GENERIC),
                "success": result.success, "status": status,
            }
            if sent_messages:
                record["messages"] = sent_messages
            if feedback:
                record["feedback"] = feedback
            if result.rewards:
                record["rewards"] = result.rewards
            if task.get("task_type") == TaskType.CHAT and not callable(original_collect):
                for line in display_record_lines(record):
                    reward_text = "；".join(
                        f"{NotificationIcons.get(item.get('type', ''))} {item.get('description', '')}".strip()
                        for item in line["rewards"]
                        if item.get("description")
                    ) or "无反馈"
                    logger.info(f"{handler.site_name} - {line['task']} -> {reward_text}")
            else:
                outcome = "成功" if result.success else "失败"
                logger.info(f"{handler.site_name} - {task_name} - 执行{outcome} -> {status}")
            return record
        except Exception as e:
            logger.error(f"{handler.site_name} - {task_name} - 执行失败 - {e}", exc_info=True)
            return {
                "date": now, "site": handler.site_name, "domain": handler.domain,
                "task_id": task.get("id"), "task_label": task.get("label"),
                "task_type": task.get("task_type", TaskType.GENERIC),
                "success": False, "status": f"执行失败：{e}",
            }
        finally:
            if task.get("task_type") == TaskType.CHAT and callable(original_send):
                handler.send_messagebox = original_send
            if task.get("task_type") == TaskType.CHAT and callable(original_collect):
                handler.collect_message_feedback = original_collect

    def _schedule_failed(self, records, is_retry=False):
        """记录仍失败的任务；新失败批次从 0 次开始，实际重试后次数加一。"""
        failed = [record for record in records if not record.get("success")]
        if not failed or self.plugin.config.retry_count <= 0:
            if is_retry:
                self.plugin.retry_records = []
                self.plugin.retry_attempt = 0
            return
        self.plugin.retry_records = failed
        self.plugin.retry_attempt = (
            getattr(self.plugin, "retry_attempt", 0) + 1 if is_retry else 0
        )

    def run_debug(self, site_filter=None, task_filter=None):
        """调试执行：绕过配置开关与 chat_sites 限制，按过滤器直接执行指定任务。

        用于本地真实调试。写历史但不调度重试、不发通知，避免污染正常运行状态。
        site_filter: 站点 id（字符串）或域名；为空则执行全部站点。
        task_filter: 任务 id/name/label 子串（不区分大小写）；为空则执行该站点全部任务。
        """
        if not self._lock.acquire(blocking=False):
            logger.warning("调试执行被跳过：已有站点任务正在执行")
            return []
        try:
            return self._run_debug_locked(site_filter, task_filter)
        finally:
            self._lock.release()

    def _run_debug_locked(self, site_filter, task_filter):
        cfg = self.plugin.config
        sites = self.plugin.all_sites()
        if site_filter:
            sites = [s for s in sites
                     if str(s.get("id")) == str(site_filter)
                     or (s.get("domain") or "") == site_filter]
        if not sites:
            logger.info(f"调试执行：未匹配到站点 {site_filter!r}")
            return []
        records = []
        for site in sites:
            handler = self._build_handler(site)
            if not handler:
                continue
            tasks = self.plugin.tasks_for(handler)
            if task_filter:
                kw = task_filter.lower()
                tasks = [t for t in tasks
                         if kw in t.get("id", "").lower()
                         or kw in t.get("name", "").lower()
                         or kw in t.get("label", "").lower()]
            for task in tasks:
                task = dict(task)
                task["config_key"] = site_task_key(site, task)
                # CLAIM 任务：读配置，空则跳过（与正式运行一致）
                claim_id = None
                if task.get("task_type") == TaskType.CLAIM:
                    task["claim_key"] = claim_task_key(site, task)
                    claim_id = self.plugin.claim_task_id(task["claim_key"]) or None
                record = self._run_task(handler, task, claim_task_id=claim_id, skip_if_no_claim=True)
                records.append(record)
        self.history.append(records, cfg.history_days)
        return records

    def run_medal(self):
        """独立勋章 cron：只执行今天尚未成功的已配置勋章任务。"""
        if not self._lock.acquire(blocking=False):
            logger.warning("已有站点任务正在执行，跳过本次勋章检查")
            return []
        try:
            return self._run_medal_locked()
        finally:
            self._lock.release()

    def _run_medal_locked(self):
        cfg = self.plugin.config
        if not cfg.chat_sites:
            logger.info("未配置需要执行的站点")
            return []
        successful_today = self.history.successful_task_ids_today()
        records = []
        skipped_successful = 0
        for _, handler, task, claim_id in self._collect_configured_tasks("medal"):
            if task.get("id") in successful_today:
                skipped_successful += 1
                task_name = display_task(
                    handler.site_name,
                    task.get("label") or task.get("id"),
                    task.get("task_type"),
                )
                logger.info(f"勋章定时 - {handler.site_name} - {task_name} - 今天已经成功，跳过")
                continue
            record = self._run_task(handler, task, claim_task_id=claim_id, skip_if_no_claim=False)
            records.append(record)
        if records:
            self.history.append(records, cfg.history_days)
            self._schedule_failed(records)
            from .notify import send_summary
            send_summary(self.plugin, records, is_retry=False)
        logger.info(
            f"勋章定时完成：执行 {len(records)} 个任务，"
            f"跳过 {skipped_successful} 个今天已成功任务"
        )
        return records

    # ===== 织梦 24h 电力冷却调度 =====

    def run_zm(self):
        """织梦 24h 电力冷却调度执行。

        仅由 scheduler 的 siteautotask_zm date trigger 触发。
        检查冷却 → 执行已启用的织梦任务 → 读邮件时间 → 更新状态 → 重新注册下次 date trigger。
        """
        if not self._lock.acquire(blocking=False):
            logger.warning("已有站点任务正在执行，跳过本次织梦喊话")
            return []
        try:
            return self._run_zm_locked()
        finally:
            self._lock.release()

    def _run_zm_locked(self):
        cfg = self.plugin.config
        tz = pytz.timezone(settings.TZ)
        now = datetime.now(tz=tz)

        # 冷却检查
        if cfg.last_zm_execution_time:
            try:
                last = datetime.fromisoformat(cfg.last_zm_execution_time)
                if last.tzinfo is None:
                    last = tz.localize(last)
                elapsed = (now - last).total_seconds()
                if elapsed < cfg.zm_cooldown:
                    remaining = cfg.zm_cooldown - elapsed
                    logger.info(f"织梦执行冷却中，距下次可执行还有 {remaining:.0f} 秒")
                    return []
            except Exception:
                pass

        if not cfg.chat_sites:
            logger.info("未配置需要执行的站点")
            return []

        zm_handler, zm_site = self._find_zm_handler()
        if not zm_handler:
            logger.info("未选中织梦站点，跳过 24h 调度")
            return []

        records = []
        for _, handler, task, claim_id in self._collect_configured_tasks(
            "zm", [(zm_site, zm_handler)]
        ):
            record = self._run_task(
                handler,
                task,
                claim_task_id=claim_id,
                skip_if_no_claim=True,
            )
            records.append(record)

        # 更新执行时间
        cfg.last_zm_execution_time = now.isoformat()
        # 读邮件时间并重新调度
        self._refresh_zm_schedule(zm_handler)

        self.history.append(records, cfg.history_days)
        from .notify import send_summary
        send_summary(self.plugin, records, is_retry=False)
        return records

    def _find_zm_handler(self):
        """从已选站点中找到织梦处理器（具备 get_latest_message_time 的）。"""
        for site in self.plugin.selected_sites():
            handler = self._build_handler(site)
            if handler and hasattr(handler, "get_latest_message_time"):
                return handler, site
        return None, None

    def _refresh_zm_schedule(self, handler=None):
        """读邮件时间，更新 zm_mail_time，重新注册下次 date trigger。"""
        cfg = self.plugin.config
        tz = pytz.timezone(settings.TZ)
        now = datetime.now(tz=tz)

        if handler is None:
            handler, _ = self._find_zm_handler()
        if handler and hasattr(handler, "get_latest_message_time"):
            try:
                mail_time_str = handler.get_latest_message_time()
                if mail_time_str:
                    cfg.zm_mail_time = str(mail_time_str)
            except Exception as e:
                logger.error(f"读取织梦邮件时间失败：{e}")

        # 计算 next_time = mail_time + 24h
        next_time = None
        if cfg.zm_mail_time:
            try:
                mail_time = datetime.strptime(cfg.zm_mail_time, "%Y-%m-%d %H:%M:%S")
                if mail_time.tzinfo is None:
                    mail_time = tz.localize(mail_time)
                next_time = mail_time + timedelta(hours=24)
                if next_time <= now:
                    logger.info("距上次织梦邮件已超 24 小时，立即执行")
                    next_time = now + timedelta(seconds=3)
                else:
                    diff = int((next_time - now).total_seconds())
                    logger.info(f"距下次织梦执行还有 {diff // 3600} 小时 {(diff % 3600) // 60} 分钟")
            except Exception as e:
                logger.error(f"解析织梦邮件时间失败：{e}")
                next_time = now + timedelta(seconds=3)
        else:
            logger.info("未获取到织梦邮件时间，3 秒后重试")
            next_time = now + timedelta(seconds=3)

        self.plugin.save_config()
        self.plugin.reschedule_zm(next_time)

    def retry_failed(self):
        """重试仍启用且今天尚未成功的失败任务，织梦喊话不进入主任务组。"""
        pending = list(getattr(self.plugin, "retry_records", None) or [])
        if not pending:
            return []

        successful_today = self.history.successful_task_ids_today()
        configured_ids = {
            task.get("id")
            for _, _, task, _ in self._collect_configured_tasks("main")
        }
        pending = [
            record for record in pending
            if record.get("task_id") in configured_ids
            and record.get("task_id") not in successful_today
        ]
        self.plugin.retry_records = pending
        if not pending:
            self.plugin.retry_attempt = 0
            logger.info("失败重试：待重试任务今天均已成功，无需执行")
            return []
        if getattr(self.plugin, "retry_attempt", 0) >= self.plugin.config.retry_count:
            self.plugin.retry_records = []
            self.plugin.retry_attempt = 0
            logger.info("失败重试：已达到最大重试次数，停止重试")
            return []

        records = self.run(retry_only=True)
        # 锁冲突时 run 返回空列表，保留失败状态；正常执行后仅保留仍失败项。
        if records:
            self.plugin.retry_records = [record for record in records if not record.get("success")]
            if not self.plugin.retry_records:
                self.plugin.retry_attempt = 0
        return records

    @staticmethod
    def normalize_result(raw):
        # TaskResult（鸭子类型：MoviePilot 跨路径加载时 isinstance 可能失败）
        if hasattr(raw, "success") and hasattr(raw, "message") and not isinstance(raw, (tuple, dict)):
            return TaskResult(
                bool(raw.success),
                str(raw.message) if raw.message is not None else "",
                getattr(raw, "feedback", None),
                getattr(raw, "rewards", None) or [],
            )
        if isinstance(raw, TaskResult):
            return raw
        if isinstance(raw, tuple) and len(raw) >= 2:
            return TaskResult.ok(str(raw[1])) if raw[0] else TaskResult.fail(str(raw[1]))
        if isinstance(raw, dict):
            return TaskResult(
                bool(raw.get("success", True)),
                str(raw.get("message") or raw.get("msg") or raw.get("status") or "执行完成"),
                raw.get("feedback"), raw.get("rewards") or [],
            )
        text = "执行完成" if raw is None else str(raw)
        failed = any(word in text.lower() for word in ("失败", "异常", "error"))
        return TaskResult(not failed, text)
