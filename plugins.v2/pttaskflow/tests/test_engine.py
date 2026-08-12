"""任务引擎非阻塞运行状态测试。"""
import importlib.util
from pathlib import Path
import sys
import threading
import types
import unittest

ROOT = Path(__file__).parents[1]
PACKAGE = "pttaskflow_engine_test"


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
package(f"{PACKAGE}.core", ROOT / "core")
app = types.ModuleType("app")
app.__path__ = []
sys.modules["app"] = app
app_core = types.ModuleType("app.core")
app_core.__path__ = []
sys.modules["app.core"] = app_core
app_config = types.ModuleType("app.core.config")
app_config.settings = types.SimpleNamespace(TZ="Asia/Shanghai")
sys.modules["app.core.config"] = app_config
app_log = types.ModuleType("app.log")
app_log.logger = types.SimpleNamespace(info=lambda *args, **kwargs: None)
sys.modules["app.log"] = app_log
load(f"{PACKAGE}.core.models", ROOT / "core/models.py")
task_log = types.ModuleType(f"{PACKAGE}.core.task_log")
task_log.TaskLogger = types.SimpleNamespace(run_end=lambda *args, **kwargs: None)
sys.modules[f"{PACKAGE}.core.task_log"] = task_log
engine_module = load(f"{PACKAGE}.core.engine", ROOT / "core/engine.py")
TaskEngine = engine_module.TaskEngine


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = TaskEngine(types.SimpleNamespace(_stop_event=threading.Event()))

    def test_run_if_idle_distinguishes_busy_from_empty_result(self):
        self.engine._lock.acquire()
        try:
            self.assertIsNone(self.engine.run_if_idle())
            self.assertEqual(self.engine.run(), [])
        finally:
            self.engine._lock.release()

        self.engine._run_locked = lambda *args: []
        self.assertEqual(self.engine.run_if_idle(), [])


if __name__ == "__main__":
    unittest.main()
