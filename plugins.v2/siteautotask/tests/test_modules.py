import importlib.util
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

CONFIG = load("siteautotask_config", ROOT / "core/config.py")
FORM = load("siteautotask_form", ROOT / "ui/form.py")
FEEDBACK = load("siteautotask_feedback", ROOT / "utils/feedback.py")
sys.modules["siteautotask_feedback"] = FEEDBACK
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
    config = CONFIG.PluginConfig(chat_sites=[1], task_switches={"test_chat": True})
    history = FakeHistory()

    def support_site_options(self):
        return [{"id": 1, "name": "测试站", "domain": "test.example", "tasks": [{
            "id": "test_chat", "label": "喊话", "hint": "测试", "task_type": "chat",
        }]}]


class ModuleTests(unittest.TestCase):
    def test_config_round_trip_and_defaults(self):
        cfg = CONFIG.PluginConfig.from_dict({"enabled": True, "retry_count": "3", "task_switches": None})
        self.assertTrue(cfg.enabled)
        self.assertEqual(cfg.retry_count, 3)
        self.assertEqual(cfg.task_switches, {})
        self.assertEqual(CONFIG.PluginConfig.from_dict(cfg.to_dict()).cron, cfg.cron)

    def test_form_groups_site_tasks(self):
        form, data = FORM.build_form(FakePlugin())
        self.assertEqual(data["chat_sites"], [1])
        text = repr(form)
        self.assertIn("task_switches.test_chat", text)
        self.assertIn("测试站", text)

    def test_page_contains_feedback_reward(self):
        page = PAGE.build_page(FakePlugin())
        text = repr(page)
        self.assertIn("10G", text)
        self.assertIn("⬆️", text)


if __name__ == "__main__":
    unittest.main()
