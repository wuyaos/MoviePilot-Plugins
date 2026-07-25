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
load("siteautotask.utils.content_filter", ROOT / "utils/content_filter.py")
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


cap.CapabilityHandler = CapabilityHandler
sys.modules["siteautotask.sites.capabilities"] = cap
crabpt = load("siteautotask.sites.crabpt", ROOT / "sites/crabpt.py")
lemonhd = load("siteautotask.sites.lemonhd", ROOT / "sites/lemonhd.py")
tangpt = load("siteautotask.sites.tangpt", ROOT / "sites/tangpt.py")


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
    info = {"session": Mock(), "url": "", "name": "", "domain": "", "username": "wuyaos"}
    info.update(kw)
    return info


class CrabptTests(unittest.TestCase):
    def test_match(self):
        h = crabpt.CrabptHandler(make_info(name="蟹黄堡", domain="crabpt.vip"))
        self.assertTrue(h.match())

    def test_claim_task_parses_json_msg(self):
        info = make_info(name="蟹黄堡", domain="crabpt.vip", url="https://crabpt.vip")
        info["session"].post.return_value = Response(payload={"success": True, "msg": "领取成功"})
        h = crabpt.CrabptHandler(info)
        self.assertEqual(h.claim_task("12"), "领取成功")

    def test_claim_task_handles_failure(self):
        info = make_info(name="蟹黄堡", domain="crabpt.vip", url="https://crabpt.vip")
        info["session"].post.return_value = Response(payload={"success": False, "msg": "已领取"})
        h = crabpt.CrabptHandler(info)
        self.assertEqual(h.claim_task("12"), "已领取")

    def test_task_metadata(self):
        h = crabpt.CrabptHandler(make_info(name="蟹黄堡", domain="crabpt.vip"))
        tasks = crabpt.Tasks()
        tasks.client = h
        meta = {i["name"]: i["task_type"] for i in tasks.get_registered_tasks()}
        self.assertEqual(meta["claim"], "claim")
        self.assertEqual(meta["claim"], "claim")
        self.assertEqual(meta["daily_checkin"], "checkin")


class LemonHDTests(unittest.TestCase):
    def test_match(self):
        h = lemonhd.LemonHDHandler(make_info(name="柠檬", domain="lemonhd.club"))
        self.assertTrue(h.match())

    def test_lottery_success(self):
        info = make_info(name="柠檬", domain="lemonhd.club", url="https://lemonhd.club")
        info["session"].post.return_value = Response(text="<html><table><tr><td>恭喜获得 100魔力</td></tr></table></html>")
        h = lemonhd.LemonHDHandler(info)
        ok, msg = h.daily_lottery()
        self.assertTrue(ok)
        self.assertIn("魔力", msg)

    def test_lottery_empty_response(self):
        info = make_info(name="柠檬", domain="lemonhd.club", url="https://lemonhd.club")
        info["session"].post.return_value = Response(text="<html></html>")
        h = lemonhd.LemonHDHandler(info)
        ok, msg = h.daily_lottery()
        self.assertTrue(ok)

    def test_task_metadata(self):
        h = lemonhd.LemonHDHandler(make_info(name="柠檬", domain="lemonhd.club"))
        tasks = lemonhd.Tasks()
        tasks.client = h
        meta = {i["name"]: i["task_type"] for i in tasks.get_registered_tasks()}
        self.assertEqual(meta["daily_lottery"], "lottery")
        self.assertEqual(meta["daily_checkin"], "checkin")


class TangptTests(unittest.TestCase):
    def test_match(self):
        h = tangpt.TangptHandler(make_info(name="躺平", domain="tangpt.top"))
        self.assertTrue(h.match())

    def test_claim_task_multi_ids(self):
        info = make_info(name="躺平", domain="tangpt.top", url="https://www.tangpt.top")
        info["session"].post.return_value = Response(payload={"msg": "领取成功"})
        h = tangpt.TangptHandler(info)
        result = h.claim_task("3")
        self.assertEqual(result, "领取成功")

    def test_task_metadata(self):
        h = tangpt.TangptHandler(make_info(name="躺平", domain="tangpt.top"))
        tasks = tangpt.Tasks()
        tasks.client = h
        meta = {i["name"]: i["task_type"] for i in tasks.get_registered_tasks()}
        self.assertEqual(meta["claim"], "claim")
        self.assertEqual(meta["daily_checkin"], "checkin")


if __name__ == "__main__":
    unittest.main()
