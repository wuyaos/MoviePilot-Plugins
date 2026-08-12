"""任务执行引擎。

引擎只编排 ``Task -> Unit -> TaskResult``，不判断具体任务类型、不解析站点响应。
"""
from datetime import datetime
import threading

import pytz
from app.core.config import settings
from app.log import logger

from .models import TaskResult
from .task_log import TaskLogger


class TaskEngine:
    def __init__(self, plugin):
        self.plugin = plugin
        self._lock = threading.Lock()

    def collect_units(self, debug=False, site_filter="", task_filter="", execution_keys=None,
                      exclude_domains=None):
        """按站点和任务配置收集执行单元。debug=True 时绕过任务启用开关。"""
        units = []
        execution_keys = set(execution_keys or [])
        exclude_domains = set(exclude_domains or [])
        config = self.plugin.raw_config
        for site in self.plugin.runtime_sites(selected_only=not debug):
            if site.domain in exclude_domains:
                continue
            if site_filter and str(site.site_id) != str(site_filter) and site.domain != site_filter:
                continue
            for task in site.tasks:
                if task_filter and task_filter.lower() not in (
                        f"{task.name} {task.label(site)} {task.task_type}".lower()):
                    continue
                if not debug and not task.is_enabled(site, config):
                    continue
                # 调试下拉任务仍需选择参数；普通开关任务则强制展开。
                if debug and not task.is_enabled(site, config):
                    from .models import ControlKind
                    controls = task.controls(site)
                    if controls and controls[0].kind != ControlKind.SWITCH:
                        continue
                    temporary = dict(config)
                    temporary[task.key(site)] = True
                    units.extend(task.expand(site, temporary))
                else:
                    units.extend(task.expand(site, config))
        if execution_keys:
            units = [unit for unit in units if unit.execution_key in execution_keys]
        return units

    def run(self, scene="主定时", debug=False, site_filter="", task_filter="", execution_keys=None,
            exclude_domains=None):
        records = self.run_if_idle(
            scene, debug, site_filter, task_filter, execution_keys, exclude_domains)
        return records if records is not None else []

    def run_if_idle(self, scene="主定时", debug=False, site_filter="", task_filter="",
                    execution_keys=None, exclude_domains=None):
        """执行任务；已有批次持锁时返回 ``None``，与正常空结果区分。"""
        if not self._lock.acquire(blocking=False):
            TaskLogger.run_end(scene, 0, 0, 0, 0)
            return None
        try:
            return self._run_locked(scene, debug, site_filter, task_filter, execution_keys,
                                    exclude_domains)
        finally:
            self._lock.release()

    def _run_locked(self, scene, debug, site_filter, task_filter, execution_keys,
                    exclude_domains):
        # 进入持锁执行后清除历史 stop 信号；未持锁的 run 拿不到锁会直接返回，
        # 因此不会在新一轮运行开始前误清信号。
        self.plugin._stop_event.clear()
        units = self.collect_units(debug=debug, site_filter=site_filter,
                                   task_filter=task_filter, execution_keys=execution_keys,
                                   exclude_domains=exclude_domains)
        terminal_keys = set() if debug else self.plugin.history.terminal_keys_today()
        TaskLogger.run_start(scene, len(units))
        records = []
        success = failed = skipped = 0
        previous = None
        for unit in units:
            if self.plugin._stop_event.is_set():
                logger.info(f"[PtTaskFlow] [{scene}] 收到停止信号，剩余 {len(units) - len(records)} 个单元不再执行")
                break
            if unit.execution_key in terminal_keys:
                skipped += 1
                TaskLogger.unit_skip(scene, unit, "当天已终态成功")
                continue
            if previous and previous.site is unit.site and previous.task is unit.task:
                # 用 Event.wait 替代 time.sleep，收到停止信号时立即唤醒退出。
                if self.plugin._stop_event.wait(unit.site.message_interval):
                    logger.info(f"[PtTaskFlow] [{scene}] 消息间隔等待中被停止信号中断")
                    break
            previous = unit
            TaskLogger.unit_start(scene, unit)
            result = self._execute(unit, scene)
            TaskLogger.unit_result(scene, unit, result)
            success += int(result.success)
            failed += int(not result.success)
            records.append(self._record(unit, result))
        if records:
            self.plugin.history.append(records, self.plugin.config.history_days)
        TaskLogger.run_end(scene, len(records), success, failed, skipped)
        return records

    @staticmethod
    def _execute(unit, scene):
        try:
            result = unit.task.run(unit.site, unit)
            # 用鸭子类型而非 isinstance，避免插件热重载后 TaskResult 跨模块实例不一致。
            if not hasattr(result, "success") or not hasattr(result, "rewards"):
                return TaskResult.fail("任务未返回 TaskResult")
            return result
        except Exception as error:
            TaskLogger.unit_error(scene, unit, error)
            return TaskResult.fail(f"执行异常：{error}")

    @staticmethod
    def _record(unit, result):
        now = datetime.now(tz=pytz.timezone(settings.TZ)).strftime("%Y-%m-%d %H:%M:%S")
        return {
            "date": now,
            "site": unit.site.site_name,
            "domain": unit.site.domain,
            "task_name": unit.task.name,
            "task_type": unit.task.task_type,
            "unit_label": unit.label,
            "execution_key": unit.execution_key,
            "success": result.success,
            "terminal": result.terminal,
            "retryable": result.retryable,
            "status": result.message,
            "rewards": result.rewards,
        }
