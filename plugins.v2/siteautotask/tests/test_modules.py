import importlib.util
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

CONFIG = load("siteautotask_config", ROOT / "core/config.py")
TASK_KEYS = load("siteautotask_task_keys", ROOT / "core/task_keys.py")
sys.modules["siteautotask.core.task_keys"] = TASK_KEYS
FORM = load("siteautotask_form", ROOT / "ui/form.py")
FEEDBACK = load("siteautotask_feedback", ROOT / "utils/feedback.py")
sys.modules["siteautotask_feedback"] = FEEDBACK
DISPLAY = load("siteautotask_display", ROOT / "utils/display.py")
PAGE = load("siteautotask_page", ROOT / "ui/page.py")


class FakeHistory:
    def latest(self, limit):
        return [{
            "date": "2026-01-01 00:00:00",
            "records": [{
                "site": "测试站", "task_label": "喊话", "success": True,
                "status": "完成", "feedback": {"rewards": [{"type": "上传量", "description": "10G"}]},
            }],
        }]


class FakePlugin:
    config = CONFIG.PluginConfig(chat_sites=[1])
    _raw_config = {"task_1_chat": True}
    history = FakeHistory()

    def support_site_options(self):
        return [{"id": 1, "name": "测试站", "domain": "test.example", "tasks": [{
            "id": "test_chat", "name": "chat", "label": "喊话", "hint": "测试", "task_type": "chat",
        }]}]

    def task_enabled(self, key):
        return bool(self._raw_config.get(key, False))


class ModuleTests(unittest.TestCase):
    def test_config_round_trip_and_defaults(self):
        cfg = CONFIG.PluginConfig.from_dict({"enabled": True, "retry_count": "3"})
        self.assertTrue(cfg.enabled)
        self.assertEqual(cfg.retry_count, 3)
        self.assertEqual(CONFIG.PluginConfig.from_dict(cfg.to_dict()).cron, cfg.cron)
        self.assertNotIn("task_switches", cfg.to_dict())

    def test_form_groups_site_tasks(self):
        form, data = FORM.build_form(FakePlugin())
        self.assertEqual(data["chat_sites"], [1])
        text = repr(form)
        self.assertIn("task_1_chat", text)
        self.assertNotIn("task_switches.", text)
        self.assertIn("测试站", text)
        self.assertNotIn("VExpansionPanel", text)
        self.assertIn("retry_count", text)
        self.assertIn("retry_notify", text)
        self.assertIn("chat_sites", text)

    def test_page_has_overview_and_history(self):
        page = PAGE.build_page(FakePlugin())
        text = repr(page)
        self.assertIn("运行统计概览", text)
        self.assertIn("VExpansionPanel", text)
        self.assertIn("执行历史记录", text)
        self.assertIn("共 1 次运行", text)
        self.assertIn("⬆️ 10G", text)
        self.assertIn("✅", text)

    def test_page_contains_feedback_reward(self):
        page = PAGE.build_page(FakePlugin())
        text = repr(page)
        self.assertIn("10G", text)
        self.assertIn("⬆️", text)

    def test_display_task_removes_repeated_site_and_type(self):
        self.assertEqual(DISPLAY.display_task("青蛙", "青蛙喊话", "chat"), "喊话")
        self.assertEqual(DISPLAY.display_task("LongPT", "LongPT任务申领", "claim"), "任务申领")
        self.assertEqual(DISPLAY.display_task("青蛙", "每日1k蝌蚪", "exchange"), "[兑换] 每日1k蝌蚪")


if __name__ == "__main__":
    unittest.main()
