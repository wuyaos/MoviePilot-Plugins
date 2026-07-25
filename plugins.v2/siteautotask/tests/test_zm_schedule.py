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
    def test_main_cron_always_triggers_medal(self):
        engine = ENGINE.TaskEngine.__new__(ENGINE.TaskEngine)
        engine.plugin = types.SimpleNamespace(config=types.SimpleNamespace(medal_cron=""))
        engine._lock = ENGINE.threading.Lock()
        engine._run_locked = Mock(return_value=[{"task_id": "regular"}])
        engine.run_medal = Mock()

        records = engine.run_scheduled()

        self.assertEqual(records, [{"task_id": "regular"}])
        engine.run_medal.assert_called_once_with()

    def test_main_cron_still_triggers_medal_with_dedicated_cron(self):
        engine = ENGINE.TaskEngine.__new__(ENGINE.TaskEngine)
        engine.plugin = types.SimpleNamespace(config=types.SimpleNamespace(medal_cron="0 8 * * *"))
        engine._lock = ENGINE.threading.Lock()
        engine._run_locked = Mock(return_value=[])
        engine.run_medal = Mock()

        engine.run_scheduled()

        engine.run_medal.assert_called_once_with()

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
        engine = ENGINE.TaskEngine.__new__(ENGINE.TaskEngine)
        engine.plugin = plugin
        engine.history = plugin.history
        engine._build_handler = Mock(return_value=handler)
        engine._run_task = Mock(return_value={"task_id": "mypt_buy_medal", "success": True})

        notify_module = types.ModuleType("siteautotask.core.notify")
        notify_module.send_summary = Mock()
        sys.modules["siteautotask.core.notify"] = notify_module

        records = engine._run_medal_locked()

        self.assertEqual(len(records), 1)
        engine._run_task.assert_called_once()
        self.assertEqual(engine._run_task.call_args.kwargs["claim_task_id"], ["8"])

class ClaimSelectionTests(unittest.TestCase):
    def test_selected_claim_enables_task_without_switch(self):
        config = types.SimpleNamespace(
            chat_sites=[13], history_days=30, get_feedback=False, medal_cron="configured"
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
