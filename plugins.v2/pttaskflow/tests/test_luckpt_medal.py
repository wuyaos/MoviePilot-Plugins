"""LuckPT 勋章奖励领取 Action 的无网络回归测试。"""
import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).parents[1]
PACKAGE = "pttaskflow_medal_test"


def package(name, path):
    module = types.ModuleType(name); module.__path__ = [str(path)]; sys.modules[name] = module


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module
    spec.loader.exec_module(module); return module


package(PACKAGE, ROOT)
package(f"{PACKAGE}.core", ROOT / "core")
package(f"{PACKAGE}.actions", ROOT / "actions")
package(f"{PACKAGE}.sites", ROOT / "sites")
models = load(f"{PACKAGE}.core.models", ROOT / "core/models.py")
load(f"{PACKAGE}.core.task_keys", ROOT / "core/task_keys.py")
load(f"{PACKAGE}.core.task", ROOT / "core/task.py")
app = types.ModuleType("app"); app.__path__ = []; sys.modules["app"] = app
db = types.ModuleType("app.db"); db.__path__ = []; sys.modules["app.db"] = db
site_oper = types.ModuleType("app.db.site_oper"); site_oper.SiteOper = type("SiteOper", (), {})
sys.modules["app.db.site_oper"] = site_oper
log = types.ModuleType("app.log")
log.logger = types.SimpleNamespace(error=lambda *a, **k: None, warning=lambda *a, **k: None)
sys.modules["app.log"] = log
shoutbox = load(f"{PACKAGE}.core.shoutbox", ROOT / "core/shoutbox.py")
load(f"{PACKAGE}.core.site", ROOT / "core/site.py")
luckpt_site = load(f"{PACKAGE}.sites.luckpt", ROOT / "sites/luckpt.py")


MEDAL_PAGE = """
<html><body><div class="collection-category" data-category-id="8">
<div class="claim-bar">
<button class="btn primary claim-reward" data-category="8" data-type="bonus_daily"
  data-reward-label="幸运星 ×1000">领取 幸运星 ×1000</button>
<button class="btn claim-reward" data-category="9" data-type="bonus_daily"
  data-reward-label="幸运星 ×500" disabled>已经领取</button>
</div>
</div></body></html>
"""

MEDAL_EMPTY = """
<html><body><div class="collection-category" data-category-id="8">
<div class="claim-bar"><button class="btn claim-reward" data-category="8"
  data-type="bonus_daily" disabled>已经领取</button></div>
</div></body></html>
"""


class Response:
    def __init__(self, text="", payload=None):
        self.text = text
        self._payload = payload

    def json(self):
        return self._payload


class FakeSite:
    def __init__(self, page_text, post_payloads):
        self.site_name = "LuckPT"
        self.request_error = ""
        self._page_text = page_text
        self._post_payloads = list(post_payloads)
        self.posts = []

    def get(self, path):
        return Response(self._page_text)

    def post(self, path, data=None):
        self.posts.append((path, data))
        payload = self._post_payloads.pop(0)
        if isinstance(payload, Exception):
            raise payload
        return Response("{}", payload)


class LuckptMedalRewardTests(unittest.TestCase):
    def setUp(self):
        self.action = luckpt_site.LuckptMedalRewardAction()

    def test_claim_success_posts_ajax_contract(self):
        site = FakeSite(MEDAL_PAGE, [{"ret": 0, "msg": "领取成功"}])
        result = self.action.execute(site)
        self.assertTrue(result.success)
        self.assertTrue(result.terminal)
        self.assertIn("幸运星 ×1000", result.message)
        self.assertEqual(len(site.posts), 1)
        path, data = site.posts[0]
        self.assertEqual(path, "/ajax.php")
        self.assertEqual(data["action"], "claimMedalCategoryReward")
        self.assertEqual(data["params[category_id]"], "8")
        self.assertEqual(data["params[reward_type]"], "bonus_daily")
        self.assertEqual(result.rewards[0]["type"], "魔力值")
        self.assertIn("幸运星 ×1000", result.rewards[0]["description"])

    def test_nothing_claimable_is_idempotent(self):
        site = FakeSite(MEDAL_EMPTY, [])
        result = self.action.execute(site)
        self.assertTrue(result.success)
        self.assertTrue(result.terminal)
        self.assertIn("无可领取", result.message)
        self.assertEqual(site.posts, [])

    def test_already_claimed_response_is_terminal_success(self):
        site = FakeSite(MEDAL_PAGE, [{"ret": 1, "msg": "您已经领取过该奖励"}])
        result = self.action.execute(site)
        self.assertTrue(result.success)
        self.assertTrue(result.terminal)
        self.assertIn("已领取", result.message)

    def test_site_rejection_is_business_failure(self):
        site = FakeSite(MEDAL_PAGE, [{"ret": 1, "msg": "条件不满足"}])
        result = self.action.execute(site)
        self.assertFalse(result.success)
        self.assertFalse(result.retryable)
        self.assertIn("条件不满足", result.message)

    def test_page_failure_is_retryable(self):
        site = FakeSite(MEDAL_PAGE, [])
        site.get = lambda path: None
        site.request_error = "HTTP 500"
        result = self.action.execute(site)
        self.assertFalse(result.success)
        self.assertTrue(result.retryable)
        self.assertIn("HTTP 500", result.message)

    def test_site_declares_medal_task(self):
        names = [task.name for task in luckpt_site.LuckPT.tasks]
        self.assertIn("claim_medal_reward", names)
        medal = next(t for t in luckpt_site.LuckPT.tasks if t.name == "claim_medal_reward")
        self.assertEqual(medal.task_type, "medal")


if __name__ == "__main__":
    unittest.main()
