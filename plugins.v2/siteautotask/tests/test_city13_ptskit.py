import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock

ROOT = Path(__file__).parents[1]
for name in ("siteautotask", "siteautotask.sites", "siteautotask.base", "siteautotask.utils"):
    module = types.ModuleType(name)
    module.__path__ = [str(ROOT / name.split(".")[-1])] if name != "siteautotask" else [str(ROOT)]
    sys.modules.setdefault(name, module)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


app = types.ModuleType("app")
core = types.ModuleType("app.core")
config = types.ModuleType("app.core.config")
config.settings = types.SimpleNamespace(PROXY=None, TZ="UTC")
log = types.ModuleType("app.log")
log.logger = types.SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None, error=lambda *a, **k: None)
helper = types.ModuleType("app.helper")
helper_browser = types.ModuleType("app.helper.browser")
helper_browser.PlaywrightHelper = Mock()
for name, module in (("app", app), ("app.core", core), ("app.core.config", config), ("app.log", log),
                     ("app.helper", helper), ("app.helper.browser", helper_browser)):
    sys.modules[name] = module

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
        self.interval_cnt = int(info.get('interval_cnt', 2))
        self.feedback_timeout = int(info.get('feedback_timeout', 5))
        def _no_wait(): pass
        self.wait_feedback = _no_wait
        self.site_url = info.get("url", "").strip().rstrip("/")
        self.site_name = info.get("name", "").strip()
        self.domain = info.get("domain", "")
        self.session = info.get("session", Mock())
        self._last_message_result = None
        self._blessing_status = {}

    def _send_get_request(self, url, params=None, rt_method=None):
        return self.session.get(url, params=params)

    def _send_post_request(self, url, data=None, rt_method=None):
        return self.session.post(url, data=data)

    def get_username(self):
        return self.site_info.get("username")

    def claim_task(self, task_id):
        return "claimed"


cap.CapabilityHandler = CapabilityHandler
sys.modules["siteautotask.sites.capabilities"] = cap
city13 = load("siteautotask.sites.city13", ROOT / "sites/city13.py")
ptskit = load("siteautotask.sites.ptskit", ROOT / "sites/ptskit.py")


class Response:
    def __init__(self, text, status=200):
        self.text = text
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


CITY13_SHOUTBOX = """
<html><body><table>
<tr><td class="shoutrow"><span class="date">12:00</span> wuyaos 求啤酒瓶</td></tr>
<tr><td class="shoutrow"><span class="date">12:01</span> 掌管啤酒瓶的神 听到了你的愿望 @wuyaos 啤酒瓶+1</td></tr>
</table></body></html>
"""

CITY13_MEDAL_OWNED = """
<html><body><div class="medal-card purchased">
<div class="medal-name">诸神赐福</div>
<div class="medal-action"><button class="buy" data-id="11">已购买</button></div>
</div></body></html>
"""


class City13Tests(unittest.TestCase):
    def handler(self, info):
        session = Mock()
        session.get.return_value = Response(info.get("shoutbox_html", CITY13_SHOUTBOX))
        session.post.return_value = Response(info.get("ajax_html", '{"ret":0,"msg":"ok"}'))
        info = dict(info)
        info["session"] = session
        info.setdefault("url", "https://13city.org")
        info.setdefault("name", "13City")
        info.setdefault("domain", "13city.org")
        info.setdefault("username", "wuyaos")
        return city13.City13Handler(info), session

    def test_match_and_feedback_parse(self):
        handler, _ = self.handler({"thirteencity_auto_buy_blessing": False})
        self.assertTrue(handler.match())
        ok, msg = handler.send_messagebox("求啤酒瓶")
        self.assertTrue(ok)
        self.assertIn("啤酒瓶", msg)
        feedback = handler.get_feedback("求啤酒瓶")
        self.assertEqual(feedback["rewards"][0]["type"], "啤酒瓶")

    def test_message_not_in_shoutbox_fails(self):
        # 群聊区没有用户消息 → 失败
        html = '<html><body><table><tr><td class="shoutrow"><span class="date">12:00</span> other 求啤酒瓶</td></tr></table></body></html>'
        handler, _ = self.handler({"shoutbox_html": html})
        ok, msg = handler.send_messagebox("求啤酒瓶")
        self.assertFalse(ok)
        self.assertIn("未显示", msg)

    def test_buy_blessing_already_owned(self):
        handler, _ = self.handler({"thirteencity_auto_buy_blessing": True, "shoutbox_html": CITY13_MEDAL_OWNED})
        # 勋章页返回已拥有 → 不触发购买
        ok, msg = handler.buy_blessing_medal()
        self.assertTrue(ok)
        self.assertIn("诸神赐福", msg)

    def test_task_metadata(self):
        handler, _ = self.handler({})
        tasks = city13.Tasks()
        tasks.client = handler
        meta = {item["name"]: item["task_type"] for item in tasks.get_registered_tasks()}
        self.assertEqual(meta["buy_blessing"], "medal")
        self.assertEqual(meta["daily_shotbox"], "chat")
        self.assertEqual(meta["claim"], "claim")
        # 合并后不再有 daily_claim_task / monthly_claim_task
        self.assertNotIn("daily_claim_task", meta)
        self.assertNotIn("monthly_claim_task", meta)

    def test_claim_options(self):
        opts = city13.City13Handler.get_claim_options()
        ids = [o["id"] for o in opts]
        self.assertIn("2", ids)
        self.assertIn("6", ids)
        # claim 调用时传入 task_id
        handler, _ = self.handler({})
        tasks = city13.Tasks()
        tasks.client = handler
        tasks.client.claim_task = lambda tid: f"申领{tid}"
        self.assertIn("申领6", tasks.claim("6"))


PTSKIT_REWARD = """
<html><body>
<div class="magic-reward-top system-msg">[系统]用户「wuyaos」获得魔力值 500</div>
</body></html>
"""

PTSKIT_ALREADY = """
<html><body>
<div class="magic-reward-top system-msg">[系统]用户「wuyaos」今日已领取过</div>
</body></html>
"""


class PtskitTests(unittest.TestCase):
    def handler(self, info):
        session = Mock()
        session.get.return_value = Response(info.get("html", PTSKIT_REWARD))
        info = dict(info)
        info["session"] = session
        info.setdefault("url", "https://pt.ptskit.org")
        info.setdefault("name", "PTS")
        info.setdefault("domain", "ptskit.org")
        info.setdefault("username", "wuyaos")
        return ptskit.PtskitHandler(info), session

    def test_match_and_magic_reward(self):
        handler, _ = self.handler({})
        self.assertTrue(handler.match())
        ok, msg = handler.send_messagebox("求魔力值")
        self.assertTrue(ok)
        self.assertIn("魔力值", msg)
        feedback = handler.get_feedback("求魔力值")
        self.assertEqual(feedback["rewards"][0]["type"], "魔力值")

    def test_already_claimed_is_success(self):
        handler, _ = self.handler({"html": PTSKIT_ALREADY})
        ok, msg = handler.send_messagebox("求魔力值")
        self.assertTrue(ok)
        self.assertIn("已领取过", msg)

    def test_task_metadata(self):
        handler, _ = self.handler({})
        tasks = ptskit.Tasks()
        tasks.client = handler
        meta = {item["name"]: item["task_type"] for item in tasks.get_registered_tasks()}
        self.assertEqual(meta["claim"], "claim")
        self.assertEqual(meta["daily_shotbox"], "chat")


if __name__ == "__main__":
    unittest.main()
