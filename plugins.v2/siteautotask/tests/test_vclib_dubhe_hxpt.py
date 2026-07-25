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

    def get_username(self):
        return self.site_info.get("username")

    def send_messagebox(self, message=None, callback=None):
        self._last_message_result = message
        return True, message


cap.CapabilityHandler = CapabilityHandler
sys.modules["siteautotask.sites.capabilities"] = cap
vclib = load("siteautotask.sites.vclib", ROOT / "sites/vclib.py")
dubhe = load("siteautotask.sites.dubhe", ROOT / "sites/dubhe.py")
hxpt = load("siteautotask.sites.hxpt", ROOT / "sites/hxpt.py")


class Response:
    def __init__(self, text="", payload=None, status=200):
        self._payload = payload
        self.text = text if text or payload is None else __import__("json").dumps(payload, ensure_ascii=False)
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


VCLIB_HOMEPAGE_COMPLETED = (
    '<html><body>名称:每周任务_上传量,指标1:上传增量,要求: 10 GB,当前: 10.00 GB,结果: <span>完成！</span></body></html>'
)
VCLIB_HOMEPAGE_UNCOMPLETED = (
    '<html><body>名称:每周任务_上传量,指标1:上传增量,要求: 10 GB,当前: 3.00 GB,结果: <span>未完成</span></body></html>'
)


class VclibTests(unittest.TestCase):
    def test_match(self):
        self.assertTrue(vclib.VclibHandler(make_info(domain="vclib.online")).match())

    def test_claim_task(self):
        info = make_info(domain="vclib.online", url="https://pt.vclib.online")
        info["session"].post.return_value = Response(payload={"msg": "领取成功"})
        self.assertEqual(vclib.VclibHandler(info).claim_task("2"), "领取成功")

    def test_task_status_completed(self):
        info = make_info(domain="vclib.online", url="https://pt.vclib.online")
        info["session"].get.return_value = Response(text=VCLIB_HOMEPAGE_COMPLETED)
        status = vclib.VclibHandler(info).get_task_status_from_homepage()
        self.assertEqual(status["status"], "completed")

    def test_task_status_uncompleted(self):
        info = make_info(domain="vclib.online", url="https://pt.vclib.online")
        info["session"].get.return_value = Response(text=VCLIB_HOMEPAGE_UNCOMPLETED)
        status = vclib.VclibHandler(info).get_task_status_from_homepage()
        self.assertEqual(status["status"], "uncompleted")

    def test_exchange_already_done(self):
        info = make_info(domain="vclib.online", url="https://pt.vclib.online")
        info["session"].get.return_value = Response(text="当前5000魔力值")
        info["session"].post.return_value = Response(text="今日已兑换")
        ok, msg = vclib.VclibHandler(info).exchange_upload_bonus()
        self.assertTrue(ok)
        self.assertIn("已兑换", msg)

    def test_task_metadata(self):
        h = vclib.VclibHandler(make_info(domain="vclib.online"))
        tasks = vclib.Tasks()
        tasks.client = h
        meta = {i["name"]: i["task_type"] for i in tasks.get_registered_tasks()}
        self.assertIn("weekly_upload_claim_and_exchange", meta)
        self.assertEqual(meta["weekly_bonus_claim"], "claim")


DUBHE_SHOUTBOX = """
<html><body><table>
<tr><td class="shoutrow"><span class="nowrap">other</span><span class="date">12:00</span> test</td></tr>
<tr><td class="shoutrow"><span class="nowrap">admin</span><span class="date">12:01</span> wuyaos 获得上传量10G</td></tr>
</table></body></html>
"""


class DubheTests(unittest.TestCase):
    def handler(self, info):
        session = Mock()
        session.get.return_value = Response(text=info.get("html", DUBHE_SHOUTBOX))
        session.post.return_value = Response(payload={"msg": "ok"})
        info = dict(info)
        info["session"] = session
        info.setdefault("url", "https://dubhe.to")
        info.setdefault("name", "天枢")
        info.setdefault("domain", "dubhe.to")
        info.setdefault("username", "wuyaos")
        return dubhe.DubheHandler(info), session

    def test_match(self):
        h, _ = self.handler({})
        self.assertTrue(h.match())

    def test_feedback_parse_upload(self):
        h, _ = self.handler({})
        h.send_messagebox("求上传")
        feedback = h.get_feedback("求上传")
        self.assertEqual(feedback["rewards"][0]["type"], "上传量")

    def test_task_metadata(self):
        h, _ = self.handler({})
        tasks = dubhe.Tasks()
        tasks.client = h
        meta = {i["name"]: i["task_type"] for i in tasks.get_registered_tasks()}
        self.assertEqual(meta["daily_shotbox"], "chat")


HXPT_SHOUTBOX = """
<html><body><table>
<tr><td class="shoutrow"><span class="date">12:00</span> 系统提示：wuyaos 获得火花奖励</td></tr>
<tr><td class="shoutrow"><span class="date">12:01</span> @wuyaos 求火花</td></tr>
</table></body></html>
"""


class HxptTests(unittest.TestCase):
    def handler(self, info):
        session = Mock()
        session.get.return_value = Response(text=info.get("html", HXPT_SHOUTBOX))
        info = dict(info)
        info["session"] = session
        info.setdefault("url", "https://haoxue.net")
        info.setdefault("name", "好学")
        info.setdefault("domain", "haoxue.net")
        info.setdefault("username", "wuyaos")
        return hxpt.HxptHandler(info), session

    def test_match(self):
        h, _ = self.handler({})
        self.assertTrue(h.match())

    def test_feedback_parse_spark(self):
        h, _ = self.handler({})
        ok, msg = h.send_messagebox("求火花")
        self.assertTrue(ok)
        feedback = h.get_feedback("求火花")
        self.assertEqual(feedback["rewards"][0]["type"], "火花")

    def test_task_metadata(self):
        h, _ = self.handler({})
        tasks = hxpt.Tasks()
        tasks.client = h
        meta = {i["name"]: i["task_type"] for i in tasks.get_registered_tasks()}
        self.assertEqual(meta["daily_shotbox"], "chat")


if __name__ == "__main__":
    unittest.main()
