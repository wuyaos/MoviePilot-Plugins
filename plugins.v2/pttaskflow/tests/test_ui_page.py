"""数据页当天奖励统计测试。"""
import importlib.util
from datetime import datetime, timedelta
from pathlib import Path
import sys
import types
import unittest

import pytz

ROOT = Path(__file__).parents[1]
app = types.ModuleType("app")
app.__path__ = []
sys.modules["app"] = app
app_core = types.ModuleType("app.core")
app_core.__path__ = []
sys.modules["app.core"] = app_core
app_config = types.ModuleType("app.core.config")
app_config.settings = types.SimpleNamespace(TZ="Asia/Shanghai")
sys.modules["app.core.config"] = app_config
spec = importlib.util.spec_from_file_location("pttaskflow_ui_page_test", ROOT / "ui/page.py")
page = importlib.util.module_from_spec(spec)
spec.loader.exec_module(page)


class PageTests(unittest.TestCase):
    @staticmethod
    def _run(date_text, reward_type):
        return {
            "date": date_text,
            "records": [{
                "rewards": [{"type": reward_type, "description": "奖励"}],
            }],
        }

    def test_today_rewards_excludes_previous_day(self):
        now = datetime.now(tz=pytz.timezone("Asia/Shanghai"))
        today = now.strftime("%Y-%m-%d 08:00:00")
        yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d 23:00:00")

        history = [self._run(yesterday, "上传量"), self._run(today, "魔力值")]
        self.assertEqual(page._today_rewards(history), "✨×1")
        self.assertEqual(page._today_rewards([self._run(yesterday, "上传量")]), "")


if __name__ == "__main__":
    unittest.main()
