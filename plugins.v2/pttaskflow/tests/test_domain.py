"""不依赖 MoviePilot 运行时的领域骨架测试。"""
import importlib.util
from pathlib import Path
import sys
import types
import unittest


ROOT = Path(__file__).parents[1]
PACKAGE = "pttaskflow_test"


def _package(name, path):
    module = types.ModuleType(name)
    module.__path__ = [str(path)]
    sys.modules[name] = module


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# 构造最小包层级，避免导入插件入口 __init__.py 和 MoviePilot app 依赖。
_package(PACKAGE, ROOT)
_package(f"{PACKAGE}.core", ROOT / "core")
_package(f"{PACKAGE}.actions", ROOT / "actions")
MODELS = _load(f"{PACKAGE}.core.models", ROOT / "core/models.py")
KEYS = _load(f"{PACKAGE}.core.task_keys", ROOT / "core/task_keys.py")
CHECKIN_ACTION = _load(f"{PACKAGE}.actions.checkin", ROOT / "actions/checkin.py")
TASK = _load(f"{PACKAGE}.core.task", ROOT / "core/task.py")
CONFIG = _load(f"{PACKAGE}.core.config", ROOT / "core/config.py")
SHOUTBOX = _load(f"{PACKAGE}.core.shoutbox", ROOT / "core/shoutbox.py")


class FakeSite:
    site_id = 7
    site_name = "测试站"
    domain = "example.org"

    def send_and_confirm(self, message, negatives):
        return MODELS.TaskResult.ok(f"已发送“{message}”")

    def claim_task(self, task_id):
        return MODELS.TaskResult.ok(f"已申领 {task_id}")


class DomainTests(unittest.TestCase):
    def setUp(self):
        self.site = FakeSite()

    def test_task_labels_do_not_include_site_name(self):
        tasks = [TASK.Checkin(action=object()), TASK.Chat(messages=["喊话"]),
                 TASK.Claim(options=[]), TASK.Medal(action=object()),
                 TASK.Exchange(action=object()), TASK.Lottery(action=object())]
        for task in tasks:
            self.assertNotIn(self.site.site_name, task.label(self.site))

    def test_checkin_control_key_is_stable(self):
        task = TASK.Checkin(action=object())
        control = task.controls(self.site)[0]
        self.assertEqual(control.kind, MODELS.ControlKind.SWITCH)
        self.assertEqual(control.key, "task_7_daily_checkin")

    def test_chat_expands_each_message_to_independent_unit(self):
        task = TASK.Chat(messages=["第一条", "第二条"])
        config = {task.key(self.site): True}
        units = task.expand(self.site, config)
        self.assertEqual([unit.argument for unit in units], ["第一条", "第二条"])
        self.assertNotEqual(units[0].execution_key, units[1].execution_key)
        self.assertTrue(task.run(self.site, units[0]).success)

    def test_chat_select_one_uses_selected_message(self):
        task = TASK.Chat(options=[
            {"id": "upload", "label": "求上传", "message": "炮姐，求上传"},
            {"id": "bonus", "label": "求魔力", "message": "炮姐，求魔力"},
        ])
        units = task.expand(self.site, {task.key(self.site): "bonus"})
        self.assertEqual(len(units), 1)
        self.assertEqual(units[0].argument, "炮姐，求魔力")

    def test_claim_select_one(self):
        task = TASK.Claim(options=[{"id": "5", "label": "天天快乐"}])
        units = task.expand(self.site, {task.key(self.site): "5"})
        self.assertEqual(units[0].execution_key, "example.org:claim:5")
        self.assertEqual(task.run(self.site, units[0]).message, "已申领 5")

    def test_legacy_global_config_migrates(self):
        config = CONFIG.PluginConfig.from_dict({"chat_sites": [7], "interval_cnt": 42})
        self.assertEqual(config.site_ids, [7])
        self.assertEqual(config.interval, 42)

    def test_external_feedback_without_relative_age_is_accepted(self):
        profile = SHOUTBOX.ShoutboxProfile(
            direction=SHOUTBOX.Direction.EXTERNAL,
            row_xpath="//div[@class='chat']",
            external_feedback_xpath="//div[@class='reward']",
        )
        html = "<div class='chat'>wuyaos 求魔力</div><div class='reward'>@wuyaos 获得10魔力</div>"
        rows, reason = SHOUTBOX.parse_snapshot(html, profile)
        self.assertFalse(reason)
        observation = SHOUTBOX.observe(rows, profile, "wuyaos", "求魔力", ["求魔力"])
        self.assertTrue(observation.sent)
        self.assertEqual(observation.feedback.source, "external")

    def test_shoutbox_observes_message_and_feedback(self):
        profile = SHOUTBOX.ShoutboxProfile()
        html = """
        <table>
          <tr><td class='shoutrow'>[1分钟前] 系统 @wuyaos 获得 10 魔力</td></tr>
          <tr><td class='shoutrow'>[1分钟前] wuyaos 炮姐，求魔力</td></tr>
        </table>
        """
        rows, reason = SHOUTBOX.parse_snapshot(html, profile)
        self.assertFalse(reason)
        observation = SHOUTBOX.observe(rows, profile, "wuyaos", "炮姐，求魔力", ["炮姐，求魔力"])
        self.assertTrue(observation.sent)
        self.assertIn("获得 10 魔力", observation.feedback.text)


if __name__ == "__main__":
    unittest.main()
