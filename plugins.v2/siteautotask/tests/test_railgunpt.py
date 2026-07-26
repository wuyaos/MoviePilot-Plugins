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

railgunpt = load("siteautotask.sites.railgunpt", ROOT / "sites/railgunpt.py")


def make_info(**kwargs):
    info = {"url": "https://bilibili.download", "cookie": "ck", "ua": "ua", "render": False}
    info.update(kwargs)
    return info


class RailgunptTests(unittest.TestCase):
    def test_match_by_name(self):
        h = railgunpt.RailgunptHandler(make_info(name="RailgunPT", domain="bilibili.download"))
        self.assertTrue(h.match())

    def test_match_by_domain(self):
        h = railgunpt.RailgunptHandler(make_info(name="其它", domain="bilibili.download"))
        self.assertTrue(h.match())

    def test_no_match_other_site(self):
        h = railgunpt.RailgunptHandler(make_info(name="13City", domain="13city.org"))
        self.assertFalse(h.match())

    def test_checkin(self):
        h = railgunpt.RailgunptHandler(make_info())
        tasks = railgunpt.Tasks()
        tasks.client = h
        self.assertIn("签到", tasks.daily_checkin())

    def test_shotbox_message_content(self):
        session = Mock()
        session.get.return_value = Mock(text="ok")
        h = railgunpt.RailgunptHandler(make_info(session=session))
        tasks = railgunpt.Tasks()
        tasks.client = h
        tasks.daily_shotbox()
        # 确认发送的消息内容是“炮姐，求魔力”
        _, kwargs = session.get.call_args
        self.assertEqual(kwargs["params"]["shbox_text"], "炮姐，求魔力")

    def test_task_metadata(self):
        h = railgunpt.RailgunptHandler(make_info())
        tasks = railgunpt.Tasks()
        tasks.client = h
        meta = {item["name"]: item["task_type"] for item in tasks.get_registered_tasks()}
        self.assertEqual(meta["daily_checkin"], "checkin")
        self.assertEqual(meta["daily_shotbox"], "chat")


if __name__ == "__main__":
    unittest.main()
