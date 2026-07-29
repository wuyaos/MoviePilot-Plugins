"""任务执行引擎。

只负责编排：站点发现、任务开关、结果收集、反馈关联与通知数据。
站点业务逻辑留在 sites/，UI 留在 ui/，调度留在 scheduler.py。
"""
from datetime import datetime, timedelta
import threading
import time
import pytz
from app.core.config import settings
from app.log import logger
from ..base.result import TaskResult
from ..base.decorator import TaskType
from .task_keys import site_task_key, claim_task_key
from .execution import execution_key, is_retryable_failure, record_execution_key
from ..sites import get_site_handler
from ..utils.display import display_record_lines, display_task
from ..utils.feedback import NotificationIcons


class TaskEngine:
    def __init__(self, plugin):
        self.plugin = plugin
        self.history = plugin.history
        self._lock = threading.Lock()
        self._cookiecloud_cache = {}

    def run_scheduled(self):
        """主 cron：执行除织梦喊话外的全部任务，跳过今天已成功任务。

        随后自动重试当天技术失败的执行单元，最多 retry_count 次。
        """
        records = self.run(skip_successful=True)
        # 主 cron 执行后，自动重试本次失败单元（配置为 0 则跳过）。
        if getattr(self.plugin.config, "retry_count", 0) and getattr(self.plugin.config, "retry_count", 0) > 0:
            self.retry_failed()
        return records

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
        retry_keys = {record_execution_key(item) for item in getattr(self.plugin, "retry_records", [])} if retry_only else None
        should_skip_successful = manual_only or skip_successful or retry_only
        if not cfg.chat_sites:
            logger.info("未配置需要执行的站点")
            return []
        records = []
        skipped_successful = 0
        run_label = "失败重试" if retry_only else ("手动补跑" if manual_only else "主定时")
        terminal_keys = self.history.terminal_keys_today()
        last_domain_type = None
        for site, handler, task, claim_id in self._collect_configured_tasks("main"):
            ekey = execution_key(
                handler.domain, task["id"],
                str(claim_id) if claim_id else (task.get("unit_id") if task.get("task_type") == TaskType.CHAT else None)
            )
            if retry_keys is not None and ekey not in retry_keys:
                continue

            if task.get("task_type") == TaskType.MEDAL:
                if ekey in terminal_keys:
                    skipped_successful += 1
                    medal_label = task.get("selected_option_label") or task.get("label") or task.get("id")
                    task_name = display_task(handler.site_name, medal_label, task.get("task_type"))
                    logger.info(f"{run_label} - {handler.site_name} - {task_name} -> 当天已购买成功，跳过")
                    continue
            elif should_skip_successful and ekey in terminal_keys:
                skipped_successful += 1
                task_type = task.get("task_type")
                label = task.get("selected_option_label") or task.get("label") or task.get("id")
                task_name = display_task(
                    handler.site_name,
                    label,
                    task_type,
                    type_only=task_type == TaskType.CHAT,
                )
                logger.info(f"{run_label} - {handler.site_name} - {task_name} -> 今天已经成功，跳过")
                continue
            # 同站点同类型连续执行单元之间插入间隔（仅在真实执行时）。
            current_domain_type = (handler.domain, task.get("task_type"))
            if last_domain_type == current_domain_type and current_domain_type[1] in (
                TaskType.CHAT, TaskType.CLAIM, TaskType.MEDAL, TaskType.GENERIC,
            ):
                time.sleep(getattr(handler, "message_interval", cfg.interval_cnt))
            last_domain_type = current_domain_type
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
        if info.get("cookiecloud") and not info.get("cookie"):
            domain = info.get("domain") or info.get("url", "")
            if domain not in self._cookiecloud_cache:
                self._cookiecloud_cache[domain] = self.plugin._fetch_cookiecloud_cookie(info.get("url", ""))
            info["cookie"] = self._cookiecloud_cache[domain]
            if not info["cookie"]:
                logger.warning(f"{info.get('name')} - CookieCloud 未匹配到 Cookie，跳过站点")
                return None
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
        if claim_id and task.get("task_type") in (TaskType.CLAIM, TaskType.CHAT):
            selected_id = str(claim_id)
            selected_option = next(
                (option for option in task["claim_options"] if str(option.get("id")) == selected_id),
                None,
            )
            if selected_option:
                task["selected_option_label"] = selected_option.get("label") or task.get("label")
        return task, claim_id, bool(claim_id)

    def _expand_medal_units(self, site, handler, task, claim_id):
        """将 myPT 多选勋章展开为单枚执行单元；GGPT 固定勋章返回单个。"""
        if not isinstance(claim_id, (list, tuple)):
            return [(task, claim_id)]
        units = []
        for medal_id in claim_id:
            if not medal_id:
                continue
            unit_task = dict(task)
            option = next(
                (opt for opt in task.get("claim_options", [])
                 if str(opt.get("id")) == str(medal_id)),
                None,
            )
            if option:
                unit_task["selected_option_label"] = option.get("label") or unit_task.get("label")
            units.append((unit_task, str(medal_id)))
        return units

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
                if not enabled:
                    continue
                if task_type == TaskType.MEDAL and isinstance(claim_id, (list, tuple)):
                    for unit_task, unit_claim_id in self._expand_medal_units(site, handler, task, claim_id):
                        yield site, handler, unit_task, unit_claim_id
                elif task_type == TaskType.CHAT and task.get("chat_selection"):
                    unit_task = dict(task)
                    unit_task["unit_id"] = str(claim_id)
                    yield site, handler, unit_task, None
                elif task_type == TaskType.CHAT and hasattr(handler, "shotbox_messages"):
                    for unit_task, unit_claim_id in self._expand_chat_units(handler, task):
                        yield site, handler, unit_task, unit_claim_id
                else:
                    yield site, handler, task, claim_id

    def _expand_chat_units(self, handler, task):
        """将多条喊话展开为单条执行单元，每条消息独立 execution_key。"""
        messages = handler.shotbox_messages()
        for message in messages:
            unit_task = dict(task)
            unit_task["unit_id"] = message
            unit_task["selected_option_label"] = f"“{message}”"
            yield unit_task, None

    CHAT_SEND_MAX_ATTEMPTS = 3
    CHAT_SEND_RETRY_SECONDS = 1

    def _send_chat_with_confirmation(self, handler, message, send):
        """发送后用同一喊话区快照确认消息，再供反馈解析复用。"""
        snapshot = getattr(handler, "message_confirmation_snapshot", None)
        observe = getattr(handler, "observe_chat_message", None)
        if not all(callable(item) for item in (snapshot, observe)):
            # 仅兼容测试替身；生产 Handler 都继承 ISiteHandler。
            return send(message)
        baseline = snapshot(message)
        if not baseline.get("valid", False):
            # 无效快照不能证明消息未出现；绝不因此重发，避免好学式连发。
            return False, f"喊话区确认不可用：{baseline.get('reason') or '快照无效'}"
        last_detail = "发送失败"
        for attempt in range(1, self.CHAT_SEND_MAX_ATTEMPTS + 1):
            logger.info(f"{handler.site_name} - [喊话] “{message}” -> 第 {attempt} 次发送")
            try:
                handler._chat_confirmation_in_progress = True
                outcome = send(message)
            except Exception as e:
                outcome = (False, f"发送异常：{e}")
            finally:
                handler._chat_confirmation_in_progress = False
            success = bool(outcome and outcome[0]) if isinstance(outcome, tuple) else bool(outcome)
            detail = str(outcome[1] or "") if isinstance(outcome, tuple) and len(outcome) > 1 else ""
            if success:
                handler.wait_feedback()
                observation = observe(message, baseline)
                if not observation.snapshot_valid:
                    return False, f"喊话区确认不可用：{observation.reason or '快照无效'}"
                if observation.sent:
                    handler._reuse_shoutbox_snapshot = True
                    handler._chat_observation = observation
                    logger.info(f"{handler.site_name} - [喊话] “{message}” -> 已在喊话区确认")
                    return True, detail or "消息已发送"
                last_detail = observation.reason or "喊话区未确认消息"
            else:
                last_detail = detail or "发送请求失败"
            logger.warning(f"{handler.site_name} - [喊话] “{message}” -> 第 {attempt} 次发送后未确认")
            if attempt < self.CHAT_SEND_MAX_ATTEMPTS:
                time.sleep(self.CHAT_SEND_RETRY_SECONDS)
        return False, f"连续 {self.CHAT_SEND_MAX_ATTEMPTS} 次发送后未在喊话区确认：{last_detail}"

    def _run_task(self, handler, task, claim_task_id=None, skip_if_no_claim=False):
        """执行单个任务，并统一记录任务进度、喊话内容与反馈。"""
        now = datetime.now(tz=pytz.timezone(settings.TZ)).strftime("%Y-%m-%d %H:%M:%S")
        task_label = task.get("selected_option_label") or task.get("label") or task.get("id")
        task_name = display_task(handler.site_name, task_label, task.get("task_type"))
        # CLAIM 执行键带上 exam_id，使不同任务申领独立跳过/重试。
        # 单条喊话展开后 unit_id 是消息内容。
        chat_unit_message = task.get("unit_id") if task.get("task_type") == TaskType.CHAT else None
        unit_id = str(claim_task_id) if (task.get("task_type") == TaskType.CLAIM or task.get("claim_options")) and claim_task_id else chat_unit_message
        sent_messages = []
        original_send = getattr(handler, "send_messagebox", None)
        # 仅对未展开的多消息 CHAT 包装 tracked_send；单条展开单元直接调用 send_messagebox。
        if task.get("task_type") == TaskType.CHAT and callable(original_send) and chat_unit_message is None:
            def tracked_send(message=None, *args, **kwargs):
                message = str(message or "")
                message_name = f"[喊话] “{message}”"
                if message:
                    sent_messages.append(message)
                    logger.info(f"{handler.site_name} - {message_name} -> 开始发送")
                outcome = self._send_chat_with_confirmation(handler, message, original_send)
                if message:
                    success = bool(outcome and outcome[0]) if isinstance(outcome, tuple) else bool(outcome)
                    detail = str(outcome[1] or "") if isinstance(outcome, tuple) and len(outcome) > 1 else ""
                    phase = "发送确认成功" if success else "发送确认失败"
                    if detail in {"发送成功", "消息发送成功", "消息已发送", ""}:
                        detail = ""
                    logger.info(f"{handler.site_name} - {message_name} -> {phase}{f' -> {detail}' if detail else ''}")
                return outcome
            handler.send_messagebox = tracked_send
        if task.get("task_type") != TaskType.CHAT:
            logger.info(f"{handler.site_name} - {task_name} - 开始执行")
        try:
            needs_claim_id = task.get("task_type") == TaskType.CLAIM or task.get("claim_options")
            if chat_unit_message is not None:
                # 展开后的单条喊话执行单元：直接发送该消息并获取反馈。
                ok, text = self._send_chat_with_confirmation(handler, chat_unit_message, original_send)
                if ok:
                    sent_messages.append(chat_unit_message)
                raw = TaskResult.ok(text if ok else "发送失败") if ok else TaskResult.fail(str(text))
            elif needs_claim_id:
                if skip_if_no_claim and not claim_task_id:
                    return {
                        "date": now, "site": handler.site_name, "domain": handler.domain,
                        "task_id": task.get("id"), "task_label": task_label,
                        "task_type": task.get("task_type", TaskType.GENERIC),
                        "success": True, "status": "未配置，跳过",
                        "execution_key": execution_key(handler.domain, task.get("id"), unit_id),
                        "terminal_success": True,
                        "retryable": False,
                    }
                raw = task["func"](claim_task_id) if claim_task_id is not None else task["func"]()
            else:
                raw = task["func"]()
            result = self.normalize_result(raw)
            feedback = None
            if task.get("task_type") == TaskType.CHAT and result.success and self.plugin.config.get_feedback:
                feedback = handler.get_feedback(chat_unit_message) if chat_unit_message else handler.get_feedback()
            status = result.message
            if task.get("task_type") == TaskType.CHAT and result.success and sent_messages:
                status = f"已发送“{'；'.join(sent_messages)}”"
            record = {
                "date": now, "site": handler.site_name, "domain": handler.domain,
                "task_id": task["id"], "task_label": task_label,
                "task_type": task.get("task_type", TaskType.GENERIC),
                "success": result.success, "status": status,
                "execution_key": execution_key(handler.domain, task["id"], unit_id),
                "terminal_success": result.success,
                "retryable": not result.success,
            }
            if sent_messages:
                record["messages"] = sent_messages
            if feedback:
                record["feedback"] = feedback
            if result.rewards:
                record["rewards"] = result.rewards
            if task.get("task_type") == TaskType.CHAT:
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
                "execution_key": execution_key(handler.domain, task.get("id"), unit_id),
                "terminal_success": False,
                "retryable": True,
            }
        finally:
            if task.get("task_type") == TaskType.CHAT:
                handler._reuse_shoutbox_snapshot = False
                handler._chat_observation = None
            if task.get("task_type") == TaskType.CHAT and callable(original_send):
                handler.send_messagebox = original_send


    def _schedule_failed(self, records, is_retry=False):
        """记录仍失败的任务，供主 cron 后续重试。"""
        failed = [record for record in records if is_retryable_failure(record)]
        if not failed or self.plugin.config.retry_count <= 0:
            return
        self.plugin.retry_records = failed

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
        last_chat_handler = None
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
                # CLAIM 与下拉 CHAT 读取选择值；空下拉与正式运行一致，跳过执行。
                claim_id = None
                if task.get("task_type") == TaskType.CLAIM or task.get("chat_selection"):
                    task["claim_key"] = claim_task_key(site, task)
                    claim_id = self.plugin.claim_task_id(task["claim_key"]) or None
                if task.get("task_type") == TaskType.CHAT and task.get("chat_selection"):
                    if not claim_id:
                        continue
                    unit_task = dict(task)
                    unit_task["unit_id"] = str(claim_id)
                    record = self._run_task(handler, unit_task, skip_if_no_claim=True)
                    records.append(record)
                    last_chat_handler = handler
                # CHAT 多条喊话拆分为单条执行单元，与正式运行一致。
                elif task.get("task_type") == TaskType.CHAT and hasattr(handler, "shotbox_messages"):
                    for unit_task, _ in self._expand_chat_units(handler, task):
                        if last_chat_handler is handler:
                            time.sleep(getattr(handler, "message_interval", cfg.interval_cnt))
                        record = self._run_task(handler, unit_task, skip_if_no_claim=True)
                        records.append(record)
                        last_chat_handler = handler
                else:
                    record = self._run_task(handler, task, claim_task_id=claim_id, skip_if_no_claim=True)
                    records.append(record)
                    last_chat_handler = handler if task.get("task_type") == TaskType.CHAT else None
        self.history.append(records, cfg.history_days)
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
        last_chat_handler = None
        for _, handler, task, claim_id in self._collect_configured_tasks(
            "zm", [(zm_site, zm_handler)]
        ):
            if last_chat_handler is handler:
                time.sleep(getattr(handler, "message_interval", cfg.interval_cnt))
            record = self._run_task(
                handler,
                task,
                claim_task_id=claim_id,
                skip_if_no_claim=True,
            )
            records.append(record)
            last_chat_handler = handler

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
                    # 当前 run_zm 已在执行；注册 now+3s 会因同一执行锁被跳过，
                    # 并导致后续没有未来任务。顺延 24h 保持独立调度存活。
                    next_time = now + timedelta(hours=24)
                    logger.warning("织梦邮件时间已过期，未发现更新邮件，24 小时后重新检查")
                else:
                    diff = int((next_time - now).total_seconds())
                    logger.info(f"距下次织梦执行还有 {diff // 3600} 小时 {(diff % 3600) // 60} 分钟")
            except Exception as e:
                logger.error(f"解析织梦邮件时间失败：{e}")
                next_time = now + timedelta(seconds=3)
        else:
            logger.warning("未获取到织梦邮件时间，24 小时后重新检查")
            next_time = now + timedelta(hours=24)

        self.plugin.save_config()
        self.plugin.reschedule_zm(next_time)

    def retry_failed(self):
        """在主 cron 内对失败单元连续重试，每个单元最多 retry_count 次。"""
        retry_count = int(getattr(self.plugin.config, "retry_count", 0) or 0)
        if retry_count <= 0:
            return []
        max_attempts = retry_count
        pending = list(getattr(self.plugin, "retry_records", None) or [])
        if not pending:
            return []

        terminal_keys = self.history.terminal_keys_today()
        pending = [
            record for record in pending
            if is_retryable_failure(record)
            and record_execution_key(record) not in terminal_keys
        ]
        self.plugin.retry_records = pending
        if not pending:
            logger.info("失败重试：待重试执行单元均已终态成功或不可重试，无需执行")
            return []

        all_retry_records = []
        for attempt in range(1, max_attempts + 1):
            still_failing = [
                record for record in self.plugin.retry_records
                if is_retryable_failure(record)
                and record_execution_key(record) not in self.history.terminal_keys_today()
            ]
            if not still_failing:
                logger.info(f"失败重试：第 {attempt - 1} 轮后全部终态成功或不可重试")
                break
            self.plugin.retry_records = still_failing
            logger.info(f"失败重试：第 {attempt}/{max_attempts} 轮，待重试 {len(still_failing)} 个单元")
            records = self.run(retry_only=True)
            all_retry_records.extend(records or [])
            # 更新失败记录：仅保留仍可重试的单元，成功或不可重试的移出。
            self.plugin.retry_records = [
                record for record in (records or []) if is_retryable_failure(record)
            ]
            # run 返回空列表表示锁冲突，保留失败状态退出。
            if not records:
                logger.warning("失败重试：获取不到执行锁，本轮终止")
                break
        # 重试结束后，保留仍失败的单元供下次 cron 处理。
        self.plugin.retry_records = [
            record for record in all_retry_records if is_retryable_failure(record)
        ]
        return all_retry_records

    @staticmethod
    def normalize_result(raw):
        # TaskResult（鸭子类型：MoviePilot 跨路径加载时 isinstance 可能失败）
        if hasattr(raw, "success") and hasattr(raw, "message") and not isinstance(raw, (tuple, dict)):
            return TaskResult(
                bool(raw.success),
                str(raw.message) if raw.message is not None else "",
                getattr(raw, "feedback", None),
                getattr(raw, "rewards", None) or [],
                getattr(raw, "purchased_medal_ids", None) or [],
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
                raw.get("purchased_medal_ids") or [],
            )
        text = "执行完成" if raw is None else str(raw)
        failed = any(word in text.lower() for word in ("失败", "异常", "error"))
        return TaskResult(not failed, text)
