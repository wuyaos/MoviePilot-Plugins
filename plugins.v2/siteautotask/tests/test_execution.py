import importlib.util
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]

for name in ("siteautotask", "siteautotask.core"):
    module = types.ModuleType(name)
    module.__path__ = [str(ROOT / name.split(".")[-1])] if name != "siteautotask" else [str(ROOT)]
    sys.modules.setdefault(name, module)

spec = importlib.util.spec_from_file_location(
    "siteautotask.core.execution", ROOT / "core" / "execution.py")
execution = importlib.util.module_from_spec(spec)
spec.loader.exec_module(execution)


class ExecutionKeyTests(unittest.TestCase):
    def test_key_without_unit(self):
        self.assertEqual(execution.execution_key("qingwapt.com", "qingwa_daily_exchange"),
                         "qingwapt.com:qingwa_daily_exchange")

    def test_key_with_unit(self):
        self.assertEqual(execution.execution_key("azusa.wiki", "azusa_claim", "9"),
                         "azusa.wiki:azusa_claim:9")


class RecordKeyTests(unittest.TestCase):
    def test_new_record_with_key(self):
        record = {"execution_key": "azusa.wiki:azusa_claim:9", "domain": "azusa.wiki",
                  "task_id": "azusa_claim"}
        self.assertEqual(execution.record_execution_key(record), "azusa.wiki:azusa_claim:9")

    def test_old_record_falls_back(self):
        record = {"domain": "qingwapt.com", "task_id": "qingwa_daily_exchange", "success": True}
        self.assertEqual(execution.record_execution_key(record), "qingwapt.com:qingwa_daily_exchange")

    def test_old_record_with_unit_falls_back(self):
        record = {"domain": "cangbao.ge", "task_id": "cangbao_daily_shotbox",
                  "unit_id": "阁主，求上传", "success": True}
        self.assertEqual(execution.record_execution_key(record),
                         "cangbao.ge:cangbao_daily_shotbox:阁主，求上传")


class TerminalSuccessTests(unittest.TestCase):
    def test_new_terminal_true(self):
        self.assertTrue(execution.is_terminal_success({"terminal_success": True, "success": False}))

    def test_new_terminal_false(self):
        self.assertFalse(execution.is_terminal_success({"terminal_success": False, "success": True}))

    def test_old_success_fallback(self):
        self.assertTrue(execution.is_terminal_success({"success": True}))

    def test_old_failure_fallback(self):
        self.assertFalse(execution.is_terminal_success({"success": False}))


class RetryableFailureTests(unittest.TestCase):
    def test_retryable_tech_failure(self):
        self.assertTrue(execution.is_retryable_failure(
            {"retryable": True, "success": False}))

    def test_non_retryable_business_failure(self):
        self.assertFalse(execution.is_retryable_failure(
            {"retryable": False, "success": False}))

    def test_success_not_retryable(self):
        self.assertFalse(execution.is_retryable_failure(
            {"retryable": True, "success": True}))

    def test_old_failure_fallback(self):
        self.assertTrue(execution.is_retryable_failure({"success": False}))


if __name__ == "__main__":
    unittest.main()
