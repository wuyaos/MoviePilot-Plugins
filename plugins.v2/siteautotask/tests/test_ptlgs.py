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


class CapabilityHandler:
    def __init__(self, info):
        self.site_info = info
        self.interval_cnt = int(info.get('interval_cnt', 5))
        self.message_interval = getattr(type(self), "MESSAGE_INTERVAL", None) or self.interval_cnt
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
        resp = self.session.get(url, params=params)
        return rt_method(resp) if rt_method else resp

    def _send_post_request(self, url, data=None, rt_method=None):
        resp = self.session.post(url, data=data)
        return rt_method(resp) if rt_method else resp

    def get_username(self):
        return self.site_info.get("username")

    def attendance(self):
        return "签到成功"

    def send_messagebox(self, message=None, callback=None):
        resp = self.session.get(self.site_url + "/shoutbox.php", params={"shbox_text": message})
        text = callback(resp) if callback else resp.text
        self._last_message_result = text
        return True, text


cap = load("siteautotask.sites.capabilities", ROOT / "sites/capabilities.py")
cap.CapabilityHandler = CapabilityHandler
sys.modules["siteautotask.sites.capabilities"] = cap

ptlgs = load("siteautotask.sites.ptlgs", ROOT / "sites/ptlgs.py")


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
        from siteautotask.base.shoutbox import ChatObservation, ChatRow
        handler, _ = self.handler({})
        self.assertTrue(handler.match())
        ok, msg = handler.send_messagebox("黑丝娘 求上传")
        self.assertTrue(ok)
        handler._chat_observation = ChatObservation(True, True, feedback=ChatRow(0, "黑丝娘 @wuyaos 奖赏你 9GB 上传"))
        feedback = handler.get_feedback("黑丝娘 求上传")
        self.assertEqual(feedback["rewards"][0]["type"], "上传量")
        self.assertFalse(feedback["rewards"][0]["is_negative"])

    def test_loss_is_marked_negative(self):
        from siteautotask.base.shoutbox import ChatObservation, ChatRow
        handler, _ = self.handler({"html": PTLGS_SHOUTBOX_LOSS})
        ok, _ = handler.send_messagebox("黑丝娘 求工分")
        self.assertTrue(ok)
        handler._chat_observation = ChatObservation(True, True, feedback=ChatRow(0, "黑丝娘 @wuyaos 你损失了 528 工分"))
        feedback = handler.get_feedback("黑丝娘 求工分")
        self.assertTrue(feedback["rewards"][0]["is_negative"])

    def test_task_metadata(self):
        handler, _ = self.handler({})
        tasks = ptlgs.Tasks()
        tasks.client = handler
        meta = {item["name"]: item["task_type"] for item in tasks.get_registered_tasks()}
        self.assertEqual(meta["daily_shotbox"], "chat")


if __name__ == "__main__":
    unittest.main()
