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
        self.site_url = info.get("url", "").strip().rstrip("/")
        self.site_name = info.get("name", "").strip()
        self.domain = info.get("domain", "")
        self.session = info.get("session", Mock())
        self._last_message_result = None
        self._blessing_status = {}

    def _send_get_request(self, url, params=None, rt_method=None):
        resp = self.session.get(url, params=params)
        return rt_method(resp) if rt_method else resp

    def _send_post_request(self, url, data=None, rt_method=None):
        resp = self.session.post(url, data=data)
        return rt_method(resp) if rt_method else resp

    def get_username(self):
        return self.site_info.get("username")

    def attendance(self):
        return "签到成功"

    def get_message_list(self):
        return self.site_info.get("message_list", [])

    def set_message_read(self, message_id):
        return None

    def send_messagebox(self, message=None, callback=None):
        # 模拟 groupchatzone 父类发送：走 GET，返回 (True, 解析文本)
        resp = self.session.get(self.site_url + "/shoutbox.php", params={"shbox_text": message})
        text = callback(resp) if callback else resp.text
        self._last_message_result = text
        return True, text


cap.CapabilityHandler = CapabilityHandler
sys.modules["siteautotask.sites.capabilities"] = cap
ptlgs = load("siteautotask.sites.ptlgs", ROOT / "sites/ptlgs.py")
vicomo = load("siteautotask.sites.vicomo", ROOT / "sites/vicomo.py")


class Response:
    def __init__(self, text, status=200):
        self.text = text
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


PTLGS_SHOUTBOX_REWARD = """
<html><body><table>
<tr><td class="shoutrow"><span class="date">12:00</span> 黑丝娘 奖赏你 @wuyaos 获得100上传量</td></tr>
</table></body></html>
"""

PTLGS_SHOUTBOX_LOSS = """
<html><body><table>
<tr><td class="shoutrow"><span class="date">12:00</span> 黑丝娘 @wuyaos 你损失了50工分 明天再来吧</td></tr>
</table></body></html>
"""


class PtlgsTests(unittest.TestCase):
    def handler(self, info):
        session = Mock()
        session.get.return_value = Response(info.get("html", PTLGS_SHOUTBOX_REWARD))
        info = dict(info)
        info["session"] = session
        info.setdefault("url", "https://ptlgs.org")
        info.setdefault("name", "PTLGS")
        info.setdefault("domain", "ptlgs.org")
        info.setdefault("username", "wuyaos")
        return ptlgs.PtlgsHandler(info), session

    def test_match_and_upload_reward(self):
        handler, _ = self.handler({})
        self.assertTrue(handler.match())
        ok, msg = handler.send_messagebox("黑丝娘 求上传")
        self.assertTrue(ok)
        self.assertIn("上传", msg)
        feedback = handler.get_feedback("黑丝娘 求上传")
        self.assertEqual(feedback["rewards"][0]["type"], "上传量")
        self.assertFalse(feedback["rewards"][0]["is_negative"])

    def test_loss_is_marked_negative(self):
        handler, _ = self.handler({"html": PTLGS_SHOUTBOX_LOSS})
        ok, _ = handler.send_messagebox("黑丝娘 求工分")
        self.assertTrue(ok)
        feedback = handler.get_feedback("黑丝娘 求工分")
        self.assertTrue(feedback["rewards"][0]["is_negative"])

    def test_task_metadata(self):
        handler, _ = self.handler({})
        tasks = ptlgs.Tasks()
        tasks.client = handler
        meta = {item["name"]: item["task_type"] for item in tasks.get_registered_tasks()}
        self.assertEqual(meta["daily_shotbox"], "chat")


VICOMO_MESSAGES = [
    {"id": "1", "topic": "第一条"},
    {"id": "2", "topic": "系统：感谢 @wuyaos 的求象草，获得象草+10"},
]


class VicomoTests(unittest.TestCase):
    def handler(self, info):
        session = Mock()
        session.get.return_value = Response(info.get("html", "<html></html>"))
        session.post.return_value = Response(info.get("boss_html", "<html></html>"))
        info = dict(info)
        info["session"] = session
        info.setdefault("url", "https://ptvicomo.net")
        info.setdefault("name", "象站")
        info.setdefault("domain", "ptvicomo.net")
        info.setdefault("username", "wuyaos")
        info.setdefault("message_list", VICOMO_MESSAGES)
        return vicomo.VicomoHandler(info), session

    def test_match_and_message_feedback(self):
        handler, _ = self.handler({})
        self.assertTrue(handler.match())
        ok, msg = handler.send_messagebox("小象求象草")
        self.assertTrue(ok)
        self.assertIn("象草", msg)
        feedback = handler.get_feedback("小象求象草")
        self.assertEqual(feedback["rewards"][0]["type"], "象草")

    def test_task_metadata(self):
        handler, _ = self.handler({})
        tasks = vicomo.Tasks()
        tasks.client = handler
        meta = {item["name"]: item["task_type"] for item in tasks.get_registered_tasks()}
        self.assertIn("daily_vs_boss", meta)
        self.assertEqual(meta["daily_shotbox"], "chat")


if __name__ == "__main__":
    unittest.main()
