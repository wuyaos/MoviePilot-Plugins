"""织梦 24h 电力冷却调度测试。"""
import importlib.util
import sys
import types
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

ROOT = Path(__file__).parents[1]


def stub_module(name, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module
    return module


stub_module("app")
stub_module("app.core")
stub_module("app.core.config", settings=types.SimpleNamespace(PROXY=None, TZ="UTC"))
stub_module("app.log", logger=types.SimpleNamespace(
    error=lambda *a, **k: None, warning=lambda *a, **k: None, info=lambda *a, **k: None))
stub_module("app.db")
stub_module("app.db.site_oper", SiteOper=Mock)
stub_module("app.utils")
stub_module("app.utils.string", StringUtils=types.SimpleNamespace(get_url_domain=lambda url: "example.com"))
stub_module("app.helper")
stub_module("app.helper.browser", PlaywrightHelper=Mock)
# apscheduler stub
stub_module("apscheduler")
stub_module("apscheduler.schedulers")
stub_module("apscheduler.schedulers.background", BackgroundScheduler=Mock)
stub_module("apscheduler.triggers")
stub_module("apscheduler.triggers.cron", CronTrigger=Mock)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CONFIG = load("siteautotask_config", ROOT / "core/config.py")
SCHEDULER = load("siteautotask_scheduler", ROOT / "core/scheduler.py")

# 加载 sites 包所需的基础模块
load("siteautotask.base.result", ROOT / "base/result.py")
load("siteautotask.base.decorator", ROOT / "base/decorator.py")
load("siteautotask.utils.request", ROOT / "utils/request.py")
handler_base = types.ModuleType("siteautotask.base.site_handler")
handler_base.ISiteHandler = object
sys.modules["siteautotask.base.site_handler"] = handler_base
cap = types.ModuleType("siteautotask.sites.capabilities")


class CapabilityHandler:
    def __init__(self, info):
        self.site_info = info
        self.site_url = info.get("url", "").strip().rstrip("/")
        self.site_name = info.get("name", "").strip()
        self.domain = info.get("domain", "")
        self.session = info.get("session", Mock())
        self.headers = {}
        self.proxies = None

    def _send_get_request(self, url, params=None, rt_method=None):
        resp = self.session.get(url, params=params)
        if rt_method:
            return rt_method(resp)
        return resp


cap.CapabilityHandler = CapabilityHandler
sys.modules["siteautotask.sites.capabilities"] = cap
# stub siteautotask 包及 base_task，使 sites.zm 的相对导入可解析
stub_module("siteautotask")
base_pkg = types.ModuleType("siteautotask.base")
base_pkg.__path__ = [str(ROOT / "base")]
sys.modules["siteautotask.base"] = base_pkg
base_task = types.ModuleType("siteautotask.base.base_task")
base_task.BaseTask = object
sys.modules["siteautotask.base.base_task"] = base_task
# 使 sites.zm 相对导入能解析
pkg = types.ModuleType("siteautotask.sites")
pkg.__path__ = [str(ROOT / "sites")]
sys.modules["siteautotask.sites"] = pkg
ZM = load("siteautotask.sites.zm", ROOT / "sites/zm.py")


class FakeResponse:
    def __init__(self, text=""):
        self.text = text
        self.status_code = 200


class ZmConfigTests(unittest.TestCase):
    def test_zm_fields_roundtrip(self):
        cfg = CONFIG.PluginConfig.from_dict({
            "zm_cooldown": 1800, "zm_mail_time": "2026-07-25 00:23:46",
            "last_zm_execution_time": "2026-07-25T00:22:22+00:00",
        })
        self.assertEqual(cfg.zm_cooldown, 1800)
        self.assertEqual(cfg.zm_mail_time, "2026-07-25 00:23:46")
        d = cfg.to_dict()
        self.assertEqual(d["zm_cooldown"], 1800)
        self.assertEqual(d["zm_mail_time"], "2026-07-25 00:23:46")

    def test_zm_defaults(self):
        cfg = CONFIG.PluginConfig.from_dict({})
        self.assertEqual(cfg.zm_cooldown, 3600)
        self.assertEqual(cfg.zm_mail_time, "")
        self.assertEqual(cfg.last_zm_execution_time, "")


class ZmNextTimeTests(unittest.TestCase):
    """scheduler._compute_zm_next_time 计算逻辑。"""

    def _cfg(self, mail_time=""):
        return types.SimpleNamespace(zm_mail_time=mail_time)

    def _scheduler(self):
        plugin = Mock()
        plugin.selected_sites.return_value = []
        return SCHEDULER.TaskScheduler(plugin)

    def test_no_mail_time_returns_now_plus_24h(self):
        s = self._scheduler()
        cfg = self._cfg("")
        from datetime import datetime
        import pytz
        now = datetime.now(tz=pytz.timezone("UTC"))
        nxt = s._compute_zm_next_time(cfg)
        delta = (nxt - now).total_seconds()
        self.assertAlmostEqual(delta, 24 * 3600, delta=5)

    def test_mail_time_plus_24h(self):
        s = self._scheduler()
        import pytz
        tz = pytz.timezone("UTC")
        now = datetime.now(tz=tz)
        # 邮件时间是 1 小时前 → next_time = 23 小时后
        mail_time = (now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        cfg = self._cfg(mail_time)
        nxt = s._compute_zm_next_time(cfg)
        expected = (now - timedelta(hours=1)) + timedelta(hours=24)
        # 允许几秒误差
        self.assertAlmostEqual((nxt - expected).total_seconds(), 0, delta=5)

    def test_expired_mail_time_returns_now_plus_24h(self):
        s = self._scheduler()
        import pytz
        tz = pytz.timezone("UTC")
        now = datetime.now(tz=tz)
        # 重载时不补执行已过期任务，顺延到 24 小时后。
        mail_time = (now - timedelta(hours=25)).strftime("%Y-%m-%d %H:%M:%S")
        cfg = self._cfg(mail_time)
        nxt = s._compute_zm_next_time(cfg)
        delta = (nxt - now).total_seconds()
        self.assertAlmostEqual(delta, 24 * 3600, delta=5)

    def test_malformed_mail_time_falls_back(self):
        s = self._scheduler()
        cfg = self._cfg("not-a-date")
        nxt = s._compute_zm_next_time(cfg)
        self.assertIsNotNone(nxt)


class SchedulerEntryTests(unittest.TestCase):
    def setUp(self):
        SCHEDULER.CronTrigger = types.SimpleNamespace(
            from_crontab=lambda expression: ("cron", expression)
        )

    def _plugin(self):
        config = types.SimpleNamespace(
            enabled=True, cron="4 0 * * *", retry_count=0, retry_interval=10,
            zm_mail_time="",
        )
        return types.SimpleNamespace(
            config=config,
            run_scheduled=Mock(), run_retry=Mock(), run_zm=Mock(),
            selected_sites=Mock(return_value=[]),
        )

    def test_main_cron_binds_run_scheduled(self):
        plugin = self._plugin()
        scheduler = SCHEDULER.TaskScheduler(plugin)
        services = scheduler.services()
        main = next(service for service in services if service["id"] == "siteautotask")
        self.assertIs(main["func"], plugin.run_scheduled)

    def test_scheduler_only_has_main_cron_retry_and_zm(self):
        plugin = self._plugin()
        scheduler = SCHEDULER.TaskScheduler(plugin)
        services = scheduler.services()
        self.assertEqual(
            {service["id"] for service in services},
            {"siteautotask"},
        )

    def test_scheduler_start_does_not_execute_tasks(self):
        plugin = self._plugin()
        scheduler = SCHEDULER.TaskScheduler(plugin)
        scheduler.start()
        plugin.run_scheduled.assert_not_called()
        plugin.run_retry.assert_not_called()
        plugin.run_zm.assert_not_called()


class ZmMailTimeParseTests(unittest.TestCase):
    """ZmHandler.get_latest_message_time 邮件时间解析。"""

    def _handler(self, html):
        handler = ZM.ZmHandler.__new__(ZM.ZmHandler)
        handler.site_url = "https://zmpt.cc"
        handler.site_name = "织梦"
        handler.domain = "zmpt.cc"
        handler.session = Mock()
        handler.session.get.return_value = FakeResponse(html)
        handler.headers = {}
        handler.proxies = None
        return handler

    def test_parse_latest_power_mail_time(self):
        html = '''<html><body><table>
        <tr><td class="rowfollow">
            <a href="#">收到来自 zmpt 赠送的 电力</a>
            <span title="2026-07-25 00:23:46">2026-07-25</span>
        </td></tr>
        <tr><td class="rowfollow"><a>其他邮件</a><span title="2026-07-24 10:00:00">2026-07-24</span></td></tr>
        </table></body></html>'''
        handler = self._handler(html)
        t = handler.get_latest_message_time()
        self.assertEqual(t, "2026-07-25 00:23:46")

    def test_no_power_mail_returns_none(self):
        html = '<html><body><table><tr><td class="rowfollow"><a>普通邮件</a><span title="2026-07-25 00:00:00">x</span></td></tr></table></body></html>'
        handler = self._handler(html)
        t = handler.get_latest_message_time()
        self.assertIsNone(t)


if __name__ == "__main__":
    unittest.main()


# ===== 勋章延迟恢复测试 =====
# stub engine 依赖
task_keys_mod = types.ModuleType("siteautotask.core.task_keys")
task_keys_mod.site_task_key = lambda site, task: f"{site.get('id','x')}_{task.get('name','x')}"
task_keys_mod.claim_task_key = lambda site, task: f"claim_{site.get('id','x')}_{task.get('name','x')}"
sys.modules["siteautotask.core.task_keys"] = task_keys_mod

history_mod = types.ModuleType("siteautotask.core.history")
class HistoryStore:
    def __init__(self, plugin): pass
    def append(self, *a, **k): pass
    def latest(self, n=10): return []
history_mod.HistoryStore = HistoryStore
sys.modules["siteautotask.core.history"] = history_mod

sites_mod = types.ModuleType("siteautotask.sites")
sites_mod.get_site_handler = lambda info, classes: None
sys.modules["siteautotask.sites"] = sites_mod

core_pkg = types.ModuleType("siteautotask.core")
core_pkg.__path__ = [str(ROOT / "core")]
sys.modules["siteautotask.core"] = core_pkg

ENGINE = load("siteautotask.core.engine", ROOT / "core/engine.py")


class FakeScheduler:
    def __init__(self):
        self.scheduler = self
        self.added = []
    def get_jobs(self):
        return []
    def add_job(self, func, trigger, run_date=None, name=None):
        self.added.append({"func": func, "run_date": run_date, "name": name})


class FakePlugin:
    def __init__(self, config):
        self.config = config
        self.scheduler = FakeScheduler()
        self.history = HistoryStore(self)
        self.save_count = 0
    def save_config(self):
        self.save_count += 1


class MedalDispatchTests(unittest.TestCase):
    def test_main_cron_runs_main_group_and_skips_today_success(self):
        engine = ENGINE.TaskEngine.__new__(ENGINE.TaskEngine)
        engine.plugin = types.SimpleNamespace(config=types.SimpleNamespace())
        engine._lock = ENGINE.threading.Lock()
        engine._run_locked = Mock(return_value=[{"task_id": "regular"}, {"task_id": "medal"}])

        records = engine.run_scheduled()

        self.assertEqual(records, [{"task_id": "regular"}, {"task_id": "medal"}])
        engine._run_locked.assert_called_once_with(
            retry_only=False, manual_only=False, skip_successful=True
        )

    def test_selected_medals_enable_task_without_switch(self):
        config = types.SimpleNamespace(chat_sites=[137], history_days=30)
        handler = types.SimpleNamespace(site_name="myPT", domain="mypt.cc")
        medal_task = {
            "id": "mypt_buy_medal",
            "name": "buy_medal",
            "label": "myPT勋章续购",
            "task_type": ENGINE.TaskType.MEDAL,
            "claim_options": [{"id": "8", "label": "VIP"}],
        }
        plugin = types.SimpleNamespace(
            config=config,
            selected_sites=lambda: [{"id": 137}],
            tasks_for=lambda _handler: [medal_task],
            task_enabled=lambda _key: False,
            claim_task_id=lambda _key: ["8"],
            history=Mock(),
        )
        plugin.history.successful_task_ids_today.return_value = set()
        plugin.history.terminal_keys_today.return_value = set()
        engine = ENGINE.TaskEngine.__new__(ENGINE.TaskEngine)
        engine.plugin = plugin
        engine.history = plugin.history
        engine._lock = ENGINE.threading.Lock()
        engine._build_handler = Mock(return_value=handler)
        engine._run_task = Mock(return_value={"task_id": "mypt_buy_medal", "success": True})

        notify_module = types.ModuleType("siteautotask.core.notify")
        notify_module.send_summary = Mock()
        sys.modules["siteautotask.core.notify"] = notify_module

        records = engine.run_scheduled()

        self.assertEqual(len(records), 1)
        engine._run_task.assert_called_once()
        self.assertEqual(engine._run_task.call_args.kwargs["claim_task_id"], "8")

class ConfiguredTaskCollectionTests(unittest.TestCase):
    def _engine(self, selected_values=None, switches=None):
        selected_values = selected_values or {}
        switches = switches or {}
        ordinary = {"id": "normal", "name": "normal", "task_type": ENGINE.TaskType.CHECKIN}
        zm_chat = {"id": "zm_chat", "name": "zm_chat", "task_type": ENGINE.TaskType.CHAT}
        claim = {
            "id": "claim", "name": "claim", "task_type": ENGINE.TaskType.CLAIM,
            "claim_options": [{"id": "6", "label": "月度任务"}],
        }
        medal = {"id": "medal", "name": "medal", "task_type": ENGINE.TaskType.MEDAL}
        mypt_medal = {
            "id": "mypt_medal", "name": "mypt_medal", "task_type": ENGINE.TaskType.MEDAL,
            "claim_options": [{"id": "8", "label": "VIP"}],
        }
        normal_handler = types.SimpleNamespace(site_name="普通站", domain="normal.test")
        zm_handler = types.SimpleNamespace(
            site_name="织梦", domain="zmpt.cc", get_latest_message_time=Mock()
        )
        sites = [{"id": 1}, {"id": 2}]
        handlers = {1: normal_handler, 2: zm_handler}
        tasks = {
            id(normal_handler): [ordinary, claim, medal, mypt_medal],
            id(zm_handler): [ordinary, zm_chat],
        }
        plugin = types.SimpleNamespace(
            config=types.SimpleNamespace(chat_sites=[1, 2]),
            selected_sites=lambda: sites,
            tasks_for=lambda handler: tasks[id(handler)],
            task_enabled=lambda key: switches.get(key, False),
            claim_task_id=lambda key: selected_values.get(key, ""),
            history=Mock(),
        )
        engine = ENGINE.TaskEngine.__new__(ENGINE.TaskEngine)
        engine.plugin = plugin
        engine.history = plugin.history
        engine._build_handler = lambda site: handlers[site["id"]]
        return engine

    def test_main_collects_all_enabled_except_zm_chat(self):
        engine = self._engine(
            selected_values={"claim_1_claim": "6"},
            switches={"1_normal": True, "1_medal": True, "2_normal": True, "2_zm_chat": True},
        )
        tasks = list(engine._collect_configured_tasks("main"))
        self.assertEqual([task[2]["id"] for task in tasks], ["normal", "claim", "medal", "normal"])
        self.assertEqual(tasks[1][3], "6")
        self.assertEqual(tasks[1][2]["selected_option_label"], "月度任务")
        self.assertEqual([task[1].site_name for task in tasks], ["普通站", "普通站", "普通站", "织梦"])

    def test_empty_dropdown_is_not_collected(self):
        engine = self._engine(switches={"1_normal": True})
        tasks = list(engine._collect_configured_tasks("main"))
        self.assertEqual([task[2]["id"] for task in tasks], ["normal"])

    def test_medal_collects_fixed_switch_and_mypt_selection(self):
        engine = self._engine(
            selected_values={"claim_1_mypt_medal": ["8"]},
            switches={"1_medal": True},
        )
        tasks = list(engine._collect_configured_tasks("medal"))
        self.assertEqual([task[2]["id"] for task in tasks], ["medal", "mypt_medal"])
        self.assertEqual(tasks[1][3], "8")

    def test_zm_scope_contains_only_zm_chat(self):
        engine = self._engine(switches={"1_normal": True, "2_normal": True, "2_zm_chat": True})
        main = list(engine._collect_configured_tasks("main"))
        zm = list(engine._collect_configured_tasks("zm"))
        self.assertEqual([item[2]["id"] for item in main], ["normal", "normal"])
        self.assertEqual([item[2]["id"] for item in zm], ["zm_chat"])
        self.assertEqual(zm[0][1].site_name, "织梦")


class RetryFailedTests(unittest.TestCase):
    def test_retry_keeps_only_enabled_failed_not_successful_today(self):
        history = Mock()
        history.terminal_keys_today.return_value = {"example.com:already_ok"}
        plugin = types.SimpleNamespace(
            config=types.SimpleNamespace(retry_count=3),
            retry_records=[
                {"task_id": "enabled_fail", "success": False},
                {"task_id": "disabled_fail", "success": False},
                {"task_id": "already_ok", "success": False},
            ],
            retry_attempt=1,
        )
        engine = ENGINE.TaskEngine.__new__(ENGINE.TaskEngine)
        engine.plugin = plugin
        engine.history = history
        engine._collect_configured_tasks = Mock(return_value=[
            ({"id": 1}, Mock(), {"id": "enabled_fail"}, None),
            ({"id": 1}, Mock(), {"id": "already_ok"}, None),
        ])
        engine.run = Mock(return_value=[{"task_id": "enabled_fail", "success": True}])

        records = engine.retry_failed()

        # retry_count=3，每轮都重试，成功后不再进入下一轮。
        self.assertEqual(records, [{"task_id": "enabled_fail", "success": True}])
        self.assertEqual(plugin.retry_records, [])
        engine.run.assert_called_once_with(retry_only=True)


class TaskOutputTests(unittest.TestCase):
    def test_chat_record_uses_actual_sent_messages(self):
        handler = types.SimpleNamespace(
            site_name="织梦", domain="zmpt.cc", _last_message_result=None
        )
        sent = []

        def send_messagebox(message):
            sent.append(message)
            return True, "发送成功"

        handler.send_messagebox = send_messagebox
        handler.wait_feedback = lambda: None
        handler.get_feedback = lambda: {
            "rewards": [{"type": "电力", "description": "获得电力50"}]
        }
        task = {
            "id": "zm_daily_shotbox", "label": "织梦喊话",
            "task_type": ENGINE.TaskType.CHAT,
            "func": lambda: (
                handler.send_messagebox("皮总，求上传"),
                handler.send_messagebox("皮总，求电力"),
                ENGINE.TaskResult.ok("完成"),
            )[-1],
        }
        plugin = types.SimpleNamespace(
            config=types.SimpleNamespace(get_feedback=True)
        )
        engine = ENGINE.TaskEngine.__new__(ENGINE.TaskEngine)
        engine.plugin = plugin

        record = engine._run_task(handler, task)

        self.assertEqual(sent, ["皮总，求上传", "皮总，求电力"])
        self.assertEqual(record["status"], "已发送“皮总，求上传；皮总，求电力”")
        self.assertIs(handler.send_messagebox, send_messagebox)


class ManualSupplementTests(unittest.TestCase):
    def test_manual_skips_success_and_runs_failed_or_unseen(self):
        config = types.SimpleNamespace(
            chat_sites=[1], history_days=30, get_feedback=False, retry_count=0
        )
        handler = types.SimpleNamespace(site_name="测试站", domain="example.com")
        tasks = [
            ({"id": "success", "config_key": "1_success", "label": "已成功"}, None),
            ({"id": "failed", "config_key": "1_failed", "label": "曾失败"}, None),
            ({"id": "unseen", "config_key": "1_unseen", "label": "未运行"}, None),
        ]
        history = Mock()
        history.terminal_keys_today.return_value = {"example.com:success"}
        plugin = types.SimpleNamespace(config=config, history=history, retry_records=[])
        engine = ENGINE.TaskEngine.__new__(ENGINE.TaskEngine)
        engine.plugin = plugin
        engine.history = history
        engine._collect_configured_tasks = Mock(return_value=[
            ({"id": 1}, handler, task, claim_id) for task, claim_id in tasks
        ])
        engine._run_task = Mock(side_effect=lambda _handler, task, **_kwargs: {
            "task_id": task["id"], "success": True,
        })
        engine._schedule_failed = Mock()

        notify_module = types.ModuleType("siteautotask.core.notify")
        notify_module.send_summary = Mock()
        sys.modules["siteautotask.core.notify"] = notify_module

        records = engine._run_locked(manual_only=True)

        self.assertEqual([record["task_id"] for record in records], ["failed", "unseen"])
        self.assertEqual(engine._run_task.call_count, 2)
        history.append.assert_called_once()


class ClaimSelectionTests(unittest.TestCase):
    def test_selected_claim_enables_task_without_switch(self):
        config = types.SimpleNamespace(
            chat_sites=[13], history_days=30, get_feedback=False
        )
        handler = types.SimpleNamespace(site_name="测试站", domain="example.com")
        claim_task = {
            "id": "example_claim",
            "name": "claim",
            "label": "测试任务申领",
            "task_type": ENGINE.TaskType.CLAIM,
            "claim_options": [{"id": "6", "label": "月度任务"}],
        }
        history = Mock()
        history.successful_task_ids_today.return_value = set()
        plugin = types.SimpleNamespace(
            config=config,
            selected_sites=lambda: [{"id": 13}],
            tasks_for=lambda _handler: [claim_task],
            task_enabled=lambda _key: False,
            claim_task_id=lambda _key: "6",
            retry_records=[],
            history=history,
        )
        engine = ENGINE.TaskEngine.__new__(ENGINE.TaskEngine)
        engine.plugin = plugin
        engine.history = history
        engine._build_handler = Mock(return_value=handler)
        engine._run_task = Mock(return_value={"task_id": "example_claim", "success": True})
        engine._schedule_failed = Mock()

        notify_module = types.ModuleType("siteautotask.core.notify")
        notify_module.send_summary = Mock()
        sys.modules["siteautotask.core.notify"] = notify_module

        records = engine._run_locked()

        self.assertEqual(len(records), 1)
        engine._run_task.assert_called_once()
        self.assertEqual(engine._run_task.call_args.kwargs["claim_task_id"], "6")

    def test_claim_execution_key_includes_exam_id(self):
        config = types.SimpleNamespace(chat_sites=[13], history_days=30, get_feedback=False)
        handler = types.SimpleNamespace(site_name="梓喵", domain="azusa.wiki")
        claim_task = {
            "id": "azusa_claim",
            "name": "claim",
            "label": "梓喵任务申领",
            "task_type": ENGINE.TaskType.CLAIM,
            "claim_options": [{"id": "9", "label": "每日任务3（做种积分）"}],
        }
        plugin = types.SimpleNamespace(
            config=config,
            selected_sites=lambda: [{"id": 23}],
            tasks_for=lambda _h: [claim_task],
            task_enabled=lambda _key: False,
            claim_task_id=lambda _key: "9",
            retry_records=[],
            history=Mock(),
        )
        plugin.history.successful_task_ids_today.return_value = set()
        plugin.history.terminal_keys_today.return_value = set()
        engine = ENGINE.TaskEngine.__new__(ENGINE.TaskEngine)
        engine.plugin = plugin
        engine.history = plugin.history
        engine._lock = ENGINE.threading.Lock()
        engine._build_handler = Mock(return_value=handler)
        engine._run_task = Mock(return_value={
            "task_id": "azusa_claim", "success": True,
            "execution_key": "azusa.wiki:azusa_claim:9",
        })
        engine._schedule_failed = Mock()
        notify_module = types.ModuleType("siteautotask.core.notify")
        notify_module.send_summary = Mock()
        sys.modules["siteautotask.core.notify"] = notify_module

        records = engine._run_locked()

        self.assertEqual(records[0]["execution_key"], "azusa.wiki:azusa_claim:9")
