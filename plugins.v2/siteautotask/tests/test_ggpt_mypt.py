"""GGPT/myPT 勋章购买适配测试。"""
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
        self.message_interval = self.interval_cnt
        self.site_url = info.get("url", "").strip().rstrip("/")
        self.site_name = info.get("name", "").strip()
        self.domain = info.get("domain", "")
        self.session = info.get("session", Mock())
        self._last_message_result = None

    def _send_get_request(self, url, params=None, rt_method=None):
        return self.session.get(url, params=params)

    def _send_post_request(self, url, data=None, rt_method=None):
        return self.session.post(url, data=data)

    def get_username(self):
        return self.site_info.get("username")


cap.CapabilityHandler = CapabilityHandler
sys.modules["siteautotask.sites.capabilities"] = cap
ggpt = load("siteautotask.sites.ggpt", ROOT / "sites/ggpt.py")
mypt = load("siteautotask.sites.mypt", ROOT / "sites/mypt.py")


class Response:
    def __init__(self, text, status=200):
        self.text = text
        self.status_code = status


class FakeSession:
    def __init__(self, get_text=None, post_text=None):
        self.get_text = get_text
        self.post_text = post_text
        self.last_post_data = None

    def get(self, url, params=None):
        return Response(self.get_text or "")

    def post(self, url, data=None):
        self.last_post_data = data
        return Response(self.post_text or '{"ret": 0, "msg": "购买成功"}')


class GgptTests(unittest.TestCase):
    def test_match(self):
        h = ggpt.GgptHandler({"name": "GGPT", "domain": "gamegamept.com", "url": "https://gamegamept.com"})
        self.assertTrue(h.match())

    def test_medal_expired_buys(self):
        """按钮可点击=已过期，应触发购买。"""
        medal_page = '<input type="button" class="claim" data-id="35" value="领取">'
        session = FakeSession(get_text=medal_page, post_text='{"ret": 0, "msg": "购买成功"}')
        h = ggpt.GgptHandler({"name": "GGPT", "domain": "gamegamept.com",
                              "url": "https://gamegamept.com", "session": session})
        ok, msg, purchased = h.buy_medal()
        self.assertTrue(ok)
        self.assertIn("购买成功", msg)
        self.assertEqual(purchased, ["35"])

    def test_medal_active_skips(self):
        """按钮 disabled=仍有效，应跳过购买。"""
        medal_page = '<input type="button" data-id="35" value="已经购买" disabled>'
        session = FakeSession(get_text=medal_page)
        h = ggpt.GgptHandler({"name": "GGPT", "domain": "gamegamept.com",
                              "url": "https://gamegamept.com", "session": session})
        ok, msg, purchased = h.buy_medal()
        self.assertTrue(ok)
        self.assertIn("未过期", msg)
        self.assertEqual(purchased, [])

    def test_already_owned_idempotent(self):
        """购买返回已拥有，视为成功。"""
        medal_page = '<input type="button" class="claim" data-id="35" value="领取">'
        session = FakeSession(get_text=medal_page, post_text='{"ret": 1, "msg": "已经购买"}')
        h = ggpt.GgptHandler({"name": "GGPT", "domain": "gamegamept.com",
                              "url": "https://gamegamept.com", "session": session})
        ok, msg, purchased = h.buy_medal()
        self.assertTrue(ok)

    def test_task_metadata(self):
        from siteautotask.base.decorator import TaskType
        handler = ggpt.GgptHandler({"name": "GGPT", "domain": "gamegamept.com",
                                    "url": "https://gamegamept.com"})
        tasks = ggpt.Tasks()
        tasks.client = handler
        meta = {t["name"]: t["task_type"] for t in tasks.get_registered_tasks()}
        self.assertIn("daily_checkin", meta)
        self.assertEqual(meta["buy_medal"], TaskType.MEDAL)
        # GGPT 无 get_claim_options，应为开关而非下拉
        self.assertFalse(hasattr(handler, "get_claim_options"))
        medal_tasks = [t for t in tasks.get_registered_tasks() if t["name"] == "buy_medal"]
        self.assertFalse(medal_tasks[0].get("claim_options"))


class MyptTests(unittest.TestCase):
    def test_match(self):
        h = mypt.MyptHandler({"name": "myPT", "domain": "mypt.cc", "url": "https://mypt.cc"})
        self.assertTrue(h.match())

    def test_claim_options(self):
        opts = mypt.MyptHandler.get_claim_options()
        self.assertEqual(len(opts), 6)
        self.assertIn("VIP", opts[0]["label"])
        self.assertIn("4", [option["id"] for option in opts])

    def test_medal_expired_buys(self):
        medal_page = '<input type="button" class="claim" data-id="8" value="领取">'
        session = FakeSession(get_text=medal_page, post_text='{"ret": 0, "msg": "购买成功"}')
        h = mypt.MyptHandler({"name": "myPT", "domain": "mypt.cc",
                              "url": "https://mypt.cc", "session": session})
        ok, msg, purchased = h.buy_medal("8")
        self.assertTrue(ok)
        self.assertIn("VIP勋章", msg)
        self.assertEqual(purchased, ["8"])

    def test_medal_active_skips(self):
        medal_page = '<input type="button" data-id="8" value="已经购买" disabled>'
        session = FakeSession(get_text=medal_page)
        h = mypt.MyptHandler({"name": "myPT", "domain": "mypt.cc",
                              "url": "https://mypt.cc", "session": session})
        ok, msg, purchased = h.buy_medal("8")
        self.assertTrue(ok)
        self.assertIn("未过期", msg)
        self.assertEqual(purchased, [])

    def test_insufficient_magic_is_successful_skip(self):
        session = FakeSession(get_text='<input type="button" data-id="3" value="需要更多魔力值" disabled>')
        h = mypt.MyptHandler({"name": "myPT", "domain": "mypt.cc",
                              "url": "https://mypt.cc", "session": session})
        ok, msg, purchased = h.buy_medal("3")
        self.assertTrue(ok)
        self.assertIn("至尊勋章魔力不足", msg)
        self.assertEqual(purchased, [])

    def test_no_medal_id(self):
        h = mypt.MyptHandler({"name": "myPT", "domain": "mypt.cc", "url": "https://mypt.cc"})
        ok, msg, purchased = h.buy_medal(None)
        self.assertFalse(ok)
        self.assertIn("未选择", msg)
        self.assertEqual(purchased, [])

    def test_task_metadata(self):
        from siteautotask.base.decorator import TaskType
        handler = mypt.MyptHandler({"name": "myPT", "domain": "mypt.cc", "url": "https://mypt.cc"})
        tasks = mypt.Tasks()
        tasks.client = handler
        meta = {t["name"]: t["task_type"] for t in tasks.get_registered_tasks()}
        self.assertIn("daily_checkin", meta)
        self.assertEqual(meta["buy_medal"], TaskType.MEDAL)
        # myPT 有 get_claim_options，应为下拉


if __name__ == "__main__":
    unittest.main()
