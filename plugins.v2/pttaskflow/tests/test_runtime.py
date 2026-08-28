"""插件运行编排、重试与织梦锁竞争测试。"""
import importlib.util
from pathlib import Path
import sys
import threading
import types
import unittest

ROOT = Path(__file__).parents[1]
PACKAGE = "pttaskflow_runtime_test"


def package(name, path):
    module = types.ModuleType(name)
    module.__path__ = [str(path)]
    sys.modules[name] = module
    return module


def module(name, **attrs):
    value = types.ModuleType(name)
    for key, item in attrs.items():
        setattr(value, key, item)
    sys.modules[name] = value
    return value


plugin_package = package(PACKAGE, ROOT)
package(f"{PACKAGE}.core", ROOT / "core")
package(f"{PACKAGE}.sites", ROOT / "sites")
package(f"{PACKAGE}.ui", ROOT / "ui")
app = package("app", ROOT)
package("app.core", ROOT)
package("app.schemas", ROOT)
package("app.db", ROOT)

class EventManager:
    @staticmethod
    def register(*args, **kwargs):
        return lambda func: func


module("app.core.event", Event=object, eventmanager=EventManager())
module("app.schemas.types", EventType=types.SimpleNamespace(PluginAction="PluginAction"))
module("app.db.site_oper", SiteOper=type("SiteOper", (), {}))
module("app.log", logger=types.SimpleNamespace(
    info=lambda *args, **kwargs: None,
    warning=lambda *args, **kwargs: None,
))
module("app.plugins", _PluginBase=object)
module(f"{PACKAGE}.core.config", PluginConfig=type("PluginConfig", (), {}),
       filter_stale_site_ids=lambda site_ids, valid_ids: site_ids,
       migrate_legacy_config=lambda raw: raw)
module(f"{PACKAGE}.core.cookie_cache", CookieCache=type("CookieCache", (), {}))
module(f"{PACKAGE}.core.engine", TaskEngine=type("TaskEngine", (), {}))
module(f"{PACKAGE}.core.history", HistoryStore=type("HistoryStore", (), {}))
module(f"{PACKAGE}.core.notify", send_summary=lambda *args, **kwargs: None)
module(f"{PACKAGE}.core.scheduler", TaskScheduler=type("TaskScheduler", (), {}))
module(f"{PACKAGE}.sites", match_site=lambda site: None)
module(f"{PACKAGE}.ui.form", build_form=lambda plugin: None)
module(f"{PACKAGE}.ui.page", build_page=lambda plugin: None)

spec = importlib.util.spec_from_file_location(
    PACKAGE, ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
plugin_module = importlib.util.module_from_spec(spec)
sys.modules[PACKAGE] = plugin_module
spec.loader.exec_module(plugin_module)
PtTaskFlow = plugin_module.PtTaskFlow


class FakeEngine:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def run(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)

    def run_if_idle(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.original_send_summary = plugin_module.send_summary

    def tearDown(self):
        plugin_module.send_summary = self.original_send_summary

    @staticmethod
    def _record(success=False, retryable=True):
        return {
            "execution_key": "zmpt.cc:daily_shotbox:upload",
            "success": success,
            "retryable": retryable,
        }

    def _plugin(self, responses, retry_count=1, retry_interval=0):
        plugin = object.__new__(PtTaskFlow)
        plugin.config = types.SimpleNamespace(
            retry_count=retry_count,
            retry_interval=retry_interval,
            last_zm_execution_time="",
            zm_cooldown=3600,
            zm_mail_time="",
        )
        plugin._stop_event = threading.Event()
        plugin._zm_retry_at = None
        plugin.engine = FakeEngine(responses)
        plugin.runtime_sites = lambda: []
        return plugin

    def test_retry_failures_succeeds_and_wait_is_interruptible(self):
        failed = [self._record()]
        plugin = self._plugin([[self._record()], [self._record(True, False)]], retry_count=2)
        summaries = []
        plugin_module.send_summary = lambda *args, **kwargs: summaries.append((args, kwargs))

        self.assertEqual(plugin._retry_failures(failed), set())
        self.assertEqual(len(plugin.engine.calls), 2)
        self.assertEqual(len(summaries), 2)

        stopped = self._plugin(
            [[self._record(True, False)]], retry_count=1, retry_interval=10)
        stopped._stop_event.set()
        self.assertEqual(stopped._retry_failures(failed), {failed[0]["execution_key"]})
        self.assertEqual(stopped.engine.calls, [])

    def test_zm_lock_contention_reschedules_without_marking_execution(self):
        plugin = self._plugin([None], retry_interval=10)
        refreshed = []
        plugin._refresh_plugin_schedule = lambda: refreshed.append(True)

        self.assertEqual(plugin.run_zm(), [])
        self.assertEqual(plugin.config.last_zm_execution_time, "")
        self.assertIsNotNone(plugin._zm_retry_at)
        self.assertEqual(refreshed, [True])

    def test_zm_retries_retryable_failure_before_next_day(self):
        failed = [self._record()]
        plugin = self._plugin([failed, [self._record(True, False)]], retry_count=1)
        saved = []
        refreshed = []
        plugin.save_config = lambda: saved.append(True)
        plugin._refresh_plugin_schedule = lambda: refreshed.append(True)
        plugin_module.send_summary = lambda *args, **kwargs: None

        self.assertEqual(plugin.run_zm(), failed)
        self.assertEqual(len(plugin.engine.calls), 2)
        self.assertTrue(plugin.config.last_zm_execution_time)
        self.assertEqual(saved, [True])
        self.assertEqual(refreshed, [True])

    def test_manual_run_excludes_zm_domain(self):
        records = [self._record(True, False)]
        plugin = self._plugin([records])
        plugin_module.send_summary = lambda *args, **kwargs: None

        self.assertEqual(plugin.run_manual(), records)
        self.assertEqual(len(plugin.engine.calls), 1)
        self.assertEqual(plugin.engine.calls[0]["exclude_domains"], {"zmpt.cc"})


if __name__ == "__main__":
    unittest.main()
