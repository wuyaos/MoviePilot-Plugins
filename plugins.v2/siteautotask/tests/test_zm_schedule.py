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

    def test_no_mail_time_returns_now_plus_3s(self):
        s = self._scheduler()
        cfg = self._cfg("")
        from datetime import datetime
        import pytz
        now = datetime.now(tz=pytz.timezone("UTC"))
        nxt = s._compute_zm_next_time(cfg)
        delta = (nxt - now).total_seconds()
        self.assertGreaterEqual(delta, 2)
        self.assertLessEqual(delta, 5)

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

    def test_expired_mail_time_returns_now_plus_3s(self):
        s = self._scheduler()
        import pytz
        tz = pytz.timezone("UTC")
        now = datetime.now(tz=tz)
        # 邮件时间是 25 小时前 → 已过期 → now+3s
        mail_time = (now - timedelta(hours=25)).strftime("%Y-%m-%d %H:%M:%S")
        cfg = self._cfg(mail_time)
        nxt = s._compute_zm_next_time(cfg)
        delta = (nxt - now).total_seconds()
        self.assertGreaterEqual(delta, 2)
        self.assertLessEqual(delta, 5)

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


class MedalResumeTests(unittest.TestCase):
    def _engine(self, pending_time=""):
        cfg = CONFIG.PluginConfig.from_dict({"medal_pending_time": pending_time})
        plugin = FakePlugin(cfg)
        engine = ENGINE.TaskEngine.__new__(ENGINE.TaskEngine)
        engine.plugin = plugin
        engine.history = plugin.history
        return engine, plugin

    def test_no_pending_does_nothing(self):
        engine, plugin = self._engine("")
        engine.resume_pending_medal()
        self.assertEqual(plugin.scheduler.added, [])
        self.assertEqual(plugin.save_count, 0)

    def test_pending_within_window_registers_remaining(self):
        import pytz
        tz = pytz.timezone("UTC")
        pending = (datetime.now(tz=tz) - timedelta(seconds=60)).isoformat()
        engine, plugin = self._engine(pending)
        engine.resume_pending_medal()
        self.assertEqual(len(plugin.scheduler.added), 1)
        self.assertEqual(plugin.scheduler.added[0]["name"], "siteautotask_medal_delayed")
        # 剩余约 60s
        run_date = plugin.scheduler.added[0]["run_date"]
        remaining = (run_date - datetime.now(tz=tz)).total_seconds()
        self.assertGreater(remaining, 55)
        self.assertLess(remaining, 70)

    def test_pending_expired_immediate_execute(self):
        import pytz
        tz = pytz.timezone("UTC")
        pending = (datetime.now(tz=tz) - timedelta(seconds=200)).isoformat()
        engine, plugin = self._engine(pending)
        engine.resume_pending_medal()
        self.assertEqual(len(plugin.scheduler.added), 1)
        run_date = plugin.scheduler.added[0]["run_date"]
        delay = (run_date - datetime.now(tz=tz)).total_seconds()
        self.assertLess(delay, 5)

    def test_malformed_pending_cleared(self):
        engine, plugin = self._engine("not-a-date")
        engine.resume_pending_medal()
        self.assertEqual(plugin.config.medal_pending_time, "")
        self.assertEqual(plugin.save_count, 1)
        self.assertEqual(plugin.scheduler.added, [])
