"""朱雀冷却任务回归：真实引擎/任务声明，所有站点 IO 均为离线替身。"""
import importlib.util
from datetime import datetime
from pathlib import Path
import sys
import threading
import types
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).parents[3] / "plugins.v3" / "pttaskflow"
PACKAGE = "pttaskflow_zhuque_cooldown_test"


def package(name, path):
    module = types.ModuleType(name)
    module.__path__ = [str(path)]
    sys.modules[name] = module


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


package(PACKAGE, ROOT)
for name in ("core", "sites", "actions"):
    package(f"{PACKAGE}.{name}", ROOT / name)
models = load(f"{PACKAGE}.core.models", ROOT / "core/models.py")
load(f"{PACKAGE}.core.task_keys", ROOT / "core/task_keys.py")
tasks = load(f"{PACKAGE}.core.task", ROOT / "core/task.py")
site_stub = types.ModuleType(f"{PACKAGE}.core.site")
site_stub.Site = type("Site", (), {})
sys.modules[site_stub.__name__] = site_stub
zhuque = load(f"{PACKAGE}.sites.zhuque", ROOT / "sites/zhuque.py")
config_stub = types.ModuleType("app.sdk.config")
config_stub.settings = types.SimpleNamespace(TZ="Asia/Shanghai")
log_stub = types.ModuleType(f"{PACKAGE}.core.task_log")
log_stub.TaskLogger = Mock()
with patch.dict(sys.modules, {"app.sdk.config": config_stub, log_stub.__name__: log_stub}):
    engine_module = load(f"{PACKAGE}.core.engine", ROOT / "core/engine.py")


class ZhuqueCooldownTests(unittest.TestCase):
    def test_success_history_does_not_block_two_skill_runs_but_blocks_daily_task(self):
        skill, level_up = zhuque.Zhuque.tasks
        self.assertFalse(skill.daily_dedup)
        self.assertTrue(level_up.daily_dedup)
        self.assertTrue(tasks.Chat().daily_dedup)
        site = zhuque.Zhuque()
        site.site_name = "朱雀"
        skill_unit = models.Unit(skill, site, "zhuque.in:skill_release", "技能释放")
        daily_unit = models.Unit(level_up, site, "zhuque.in:level_up:79", "一键升级")
        keys = {skill_unit.execution_key, daily_unit.execution_key}
        history = types.SimpleNamespace(
            terminal_keys_today=lambda: keys,
            append=Mock(),
        )
        plugin = types.SimpleNamespace(
            _stop_event=threading.Event(), history=history,
            config=types.SimpleNamespace(history_days=30),
        )
        engine = engine_module.TaskEngine(plugin)
        engine.collect_units = Mock(return_value=[skill_unit, daily_unit])
        with patch.object(skill.action, "execute", return_value=models.TaskResult.ok("技能释放成功")) as release, \
                patch.object(level_up.action, "execute") as upgrade:
            for _ in range(2):
                records = engine.run_if_idle(scene="朱雀技能")
                self.assertEqual(len(records), 1)
                self.assertEqual(records[0]["execution_key"], skill_unit.execution_key)
                self.assertTrue(records[0]["terminal"])
            self.assertEqual(release.call_count, 2)
            upgrade.assert_not_called()
        self.assertEqual(history.append.call_count, 2)
        engine._lock.acquire()
        try:
            self.assertIsNone(engine.run_if_idle(scene="朱雀技能"))
        finally:
            engine._lock.release()

    def test_skill_still_calls_all_endpoint_when_only_some_characters_are_ready(self):
        now = datetime.now().timestamp()
        site = types.SimpleNamespace(
            _csrf_headers=Mock(return_value={}),
            get_user_info=Mock(return_value={"data": {"characters": [
                {"info": {"next_time": now - 100}},
                {"info": {"next_time": now + 3600}},
            ]}}),
            post=Mock(return_value=types.SimpleNamespace(json=lambda: {"status": 200, "data": {"bonus": 10}})),
            request_error="",
        )
        site._csrf_headers.return_value = {"x-csrf-token": "offline-placeholder"}
        result = zhuque.Zhuque.tasks[0].action.execute(site)
        self.assertTrue(result.success)
        site.post.assert_called_once_with(
            "/api/gaming/fireGenshinCharacterMagic",
            headers=site._csrf_headers.return_value,
            json={"all": 1, "resetModal": True},
        )

    def test_next_time_retains_original_future_only_algorithm(self):
        site = zhuque.Zhuque()
        site._csrf_headers = Mock(return_value={"offline": True})
        now = datetime.now().timestamp()
        site.get_user_info = Mock(return_value={"data": {"characters": [
            {"info": {"next_time": now - 1}},
            {"info": {"next_time": now + 7200}},
            {"info": {"next_time": now + 3600}},
        ]}})
        self.assertEqual(site.get_skill_next_time(), now + 3600)
        site.get_user_info.return_value = {"data": {"characters": [
            {"info": {"next_time": now - 1}},
        ]}}
        before = datetime.now().timestamp()
        self.assertGreaterEqual(site.get_skill_next_time(), before)
        self.assertLessEqual(site.get_skill_next_time(), datetime.now().timestamp())
        site.get_user_info.return_value = None
        self.assertIsNone(site.get_skill_next_time())


if __name__ == "__main__":
    unittest.main()
