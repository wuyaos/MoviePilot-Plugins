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

    def _send_get_request(self, url, params=None, rt_method=None):
        resp = self.session.get(url, params=params)
        return rt_method(resp) if rt_method else resp

    def _send_post_request(self, url, data=None, rt_method=None):
        resp = self.session.post(url, data=data)
        return rt_method(resp) if rt_method else resp

    def attendance(self):
        return "签到成功"

    def send_messagebox(self, message=None, callback=None):
        self._last_message_result = message
        return True, message

    @staticmethod
    def shotbox_messages():
        return ["青虫娘，求上传", "青虫娘，求魔力"]


cap.CapabilityHandler = CapabilityHandler
sys.modules["siteautotask.sites.capabilities"] = cap
car = load("siteautotask.sites.car", ROOT / "sites/car.py")
cspt = load("siteautotask.sites.cspt", ROOT / "sites/cspt.py")
cyanbug = load("siteautotask.sites.cyanbug", ROOT / "sites/cyanbug.py")
azusa = load("siteautotask.sites.azusa", ROOT / "sites/azusa.py")


class Response:
    def __init__(self, payload=None, text=None, status=200):
        self._payload = payload
        self.text = text if text is not None else (__import__("json").dumps(payload, ensure_ascii=False) if payload else "")
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")

    def json(self):
        if self._payload is not None:
            return self._payload
        return __import__("json").loads(self.text)


def make_info(**kw):
    info = {"session": Mock(), "url": "", "name": "", "domain": ""}
    info.update(kw)
    return info


class CarTests(unittest.TestCase):
    def test_match_by_domain(self):
        self.assertTrue(car.CarHandler(make_info(domain="carpt.net")).match())
        self.assertFalse(car.CarHandler(make_info(domain="other.com")).match())

    def test_claim_task_parses_json(self):
        info = make_info(domain="carpt.net", url="https://carpt.net")
        info["session"].post.return_value = Response(payload={"msg": "领取成功"})
        self.assertEqual(car.CarHandler(info).claim_task("5"), "领取成功")

    def test_task_metadata(self):
        h = car.CarHandler(make_info(domain="carpt.net"))
        tasks = car.Tasks()
        tasks.client = h
        meta = {i["name"]: i["task_type"] for i in tasks.get_registered_tasks()}
        self.assertEqual(meta["claim"], "claim")
        self.assertEqual(meta["daily_checkin"], "checkin")


class CsptTests(unittest.TestCase):
    def test_match_by_domain_and_name(self):
        self.assertTrue(cspt.CsptHandler(make_info(domain="cspt.top")).match())
        self.assertTrue(cspt.CsptHandler(make_info(name="财神")).match())

    def test_claim_task_failure(self):
        info = make_info(domain="cspt.top", url="https://cspt.top")
        info["session"].post.return_value = Response(payload={"msg": "今日已领取"})
        self.assertEqual(cspt.CsptHandler(info).claim_task("5"), "今日已领取")

    def test_task_metadata(self):
        h = cspt.CsptHandler(make_info(domain="cspt.top"))
        tasks = cspt.Tasks()
        tasks.client = h
        meta = {i["name"]: i["task_type"] for i in tasks.get_registered_tasks()}
        self.assertEqual(meta["claim"], "claim")


class AzusaTests(unittest.TestCase):
    def test_match_and_claim_task(self):
        info = make_info(name="梓喵", domain="azusa.wiki", url="https://azusa.wiki")
        csrf_token = "a" * 40
        info["session"].get.return_value = Response(text=f"ajax.php?csrf_token={csrf_token}")
        info["session"].post.return_value = Response(payload={"msg": "任务认领成功"})
        handler = azusa.AzusaHandler(info)
        self.assertTrue(handler.match())
        self.assertEqual(handler.session.headers["X-Requested-With"], "XMLHttpRequest")
        self.assertEqual(handler.claim_task("11"), "任务认领成功")
        self.assertEqual(handler.session.post.call_args.args[0],
                         f"https://azusa.wiki/ajax.php?csrf_token={csrf_token}")
        self.assertEqual(handler.session.post.call_args.kwargs["data"], {
            "action": "claimTask", "params[exam_id]": "11",
        })

    def test_claim_requires_csrf_token(self):
        info = make_info(name="梓喵", domain="azusa.wiki", url="https://azusa.wiki")
        info["session"].get.return_value = Response(text="<html>no token</html>")
        handler = azusa.AzusaHandler(info)
        self.assertIn("CSRF Token", handler.claim_task("11"))
        info["session"].post.assert_not_called()

    def test_claim_403_explains_missing_session_cookie(self):
        info = make_info(name="梓喵", domain="azusa.wiki", url="https://azusa.wiki")
        csrf_token = "b" * 40
        info["session"].get.return_value = Response(text=f"csrf_token={csrf_token}")
        handler = azusa.AzusaHandler(info)
        handler._send_post_request = Mock(return_value=None)
        handler._last_request_error = "403 Client Error"
        self.assertIn("PHPSESSID", handler.claim_task("11"))

    def test_claim_options_match_task_page(self):
        options = azusa.AzusaHandler.get_claim_options()
        self.assertEqual({item["id"] for item in options}, {
            "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15",
        })
        self.assertEqual(options[0]["label"], "每日任务4（魔力+上传）")


class CyanbugTests(unittest.TestCase):
    def test_match_by_name_or_domain(self):
        # Cyanbug 名为“大青虫”，domain 或 name 命中即可匹配
        self.assertTrue(cyanbug.CyanbugHandler(make_info(name="大青虫", domain="cyanbug.net")).match())
        self.assertTrue(cyanbug.CyanbugHandler(make_info(domain="cyanbug.net")).match())
        # domain 为 13city 且 name 不含“大青虫”时不匹配
        self.assertFalse(cyanbug.CyanbugHandler(make_info(name="13City", domain="13city.org")).match())

    def test_shotbox_sends_multiple(self):
        h = cyanbug.CyanbugHandler(make_info(domain="cyanbug.net"))
        tasks = cyanbug.Tasks()
        tasks.client = h
        result = tasks.daily_shotbox()
        self.assertTrue(result.success)
        self.assertIn("青虫娘", result.message)

    def test_task_metadata(self):
        h = cyanbug.CyanbugHandler(make_info(domain="cyanbug.net"))
        tasks = cyanbug.Tasks()
        tasks.client = h
        meta = {i["name"]: i["task_type"] for i in tasks.get_registered_tasks()}
        self.assertEqual(meta["daily_shotbox"], "chat")
        self.assertEqual(meta["daily_checkin"], "checkin")


if __name__ == "__main__":
    unittest.main()
