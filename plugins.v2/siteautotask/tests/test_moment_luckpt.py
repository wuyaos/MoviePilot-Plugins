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

    def nearby_shoutbox_rows(self, message, max_rows=5):
        from lxml import etree
        response = getattr(self, "_last_shoutbox_snapshot", None)
        if not response:
            return []
        root = etree.HTML(response.text or "")
        rows = [" ".join(t.strip() for t in row.xpath(".//td//text()") if t.strip())
                for row in root.xpath("//tr[td]")]
        username = self.get_username()
        for index, text in enumerate(rows):
            if username not in text or message not in text:
                continue
            candidates = list(reversed(rows[max(0, index - max_rows):index]))
            if getattr(type(self), "FEEDBACK_ROWS_BOTH", False):
                candidates.extend(rows[index + 1:index + 1 + max_rows])
            return candidates
        return []


cap.CapabilityHandler = CapabilityHandler
sys.modules["siteautotask.sites.capabilities"] = cap
moment = load("siteautotask.sites.moment", ROOT / "sites/moment.py")
luckpt = load("siteautotask.sites.luckpt", ROOT / "sites/luckpt.py")


class Response:
    def __init__(self, text="", status=200):
        self.text = text
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


MOMENT_SHOUTBOX = """
<html><body><table>
<tr><td class="shoutrow"><span class="date">12:00</span> 【wuyaos的女友】获得上传量10G</td></tr>
</table></body></html>
"""


class MomentTests(unittest.TestCase):
    def handler(self, info):
        session = Mock()
        session.get.return_value = Response(text=info.get("html", MOMENT_SHOUTBOX))
        info = dict(info)
        info["session"] = session
        info.setdefault("url", "https://m-team.io")
        info.setdefault("name", "Moment")
        info.setdefault("domain", "m-team.io")
        info.setdefault("username", "wuyaos")
        return moment.MomentHandler(info), session

    def test_match(self):
        h, _ = self.handler({})
        self.assertTrue(h.match())

    def test_feedback_parse(self):
        h, _ = self.handler({})
        ok, msg = h.send_messagebox("求上传")
        self.assertTrue(ok)
        self.assertIn("女友", msg)

    def test_feedback_can_appear_below_sent_message(self):
        html = """
        <html><body><table>
        <tr><td class=\"shoutrow\">wuyaos开站纪念勋章 茄子</td></tr>
        <tr><td class=\"shoutrow\">【wuyaos的女友】她轻轻笑：“这张我喜欢光。” 奖励 +884 魔力。</td></tr>
        </table></body></html>
        """
        handler, _ = self.handler({"html": html})
        handler._reuse_shoutbox_snapshot = True
        handler._last_shoutbox_snapshot = Response(html)
        feedback = handler.get_feedback("茄子")
        self.assertIn("+884 魔力", feedback["rewards"][0]["description"])

    def test_task_metadata(self):
        h, _ = self.handler({})
        tasks = moment.Tasks()
        tasks.client = h
        meta = {i["name"]: i["task_type"] for i in tasks.get_registered_tasks()}
        self.assertEqual(meta["daily_shotbox"], "chat")


LUCKPT_WISH = """
<html><body>
<div class="wish-bubble-system"><div class="wish-content">@wuyaos 幸运池听到了你的愿望，增加了100幸运星</div></div>
</body></html>
"""

LUCKPT_CHAT = """
<html><body>
<div class="chat-message-container"><div class="chat-content">@wuyaos 求幸运</div></div>
</body></html>
"""


class LuckptTests(unittest.TestCase):
    def handler(self, info):
        session = Mock()
        session.get.return_value = Response(text=info.get("html", LUCKPT_WISH))
        info = dict(info)
        info["session"] = session
        info.setdefault("url", "https://pt.luckpt.de")
        info.setdefault("name", "LuckPT")
        info.setdefault("domain", "luckpt.de")
        info.setdefault("username", "wuyaos")
        return luckpt.LuckptHandler(info), session

    def test_match_by_name(self):
        h, _ = self.handler({"name": "LuckPT"})
        self.assertTrue(h.match())

    def test_match_by_alt_name(self):
        h, _ = self.handler({"name": "幸运"})
        self.assertTrue(h.match())

    def test_wish_feedback_parse(self):
        h, _ = self.handler({})
        ok, msg = h.send_messagebox("求幸运")
        self.assertTrue(ok)
        self.assertIn("幸运池", msg)

    def test_chat_fallback(self):
        h, _ = self.handler({"html": LUCKPT_CHAT})
        ok, msg = h.send_messagebox("求幸运")
        self.assertTrue(ok)
        self.assertIn("@wuyaos", msg)

    def test_task_uses_real_wish_phrase(self):
        handler, _ = self.handler({})
        tasks = luckpt.Tasks()
        tasks.client = handler
        result = tasks.daily_shotbox()
        self.assertTrue(result.success)
        self.assertEqual(handler._last_message_result, "@wuyaos 幸运池听到了你的愿望，增加了100幸运星")

    def test_task_metadata(self):
        h, _ = self.handler({})
        tasks = luckpt.Tasks()
        tasks.client = h
        meta = {i["name"]: i["task_type"] for i in tasks.get_registered_tasks()}
        self.assertEqual(meta["daily_shotbox"], "chat")


if __name__ == "__main__":
    unittest.main()
