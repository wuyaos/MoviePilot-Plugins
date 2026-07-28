import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock

ROOT = Path(__file__).parents[1]

# 测试时构造最小包环境，避免启动 MoviePilot。
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

# 真实依赖替身
app = types.ModuleType("app")
core = types.ModuleType("app.core")
config = types.ModuleType("app.core.config")
config.settings = types.SimpleNamespace(PROXY=None, TZ="UTC")
log = types.ModuleType("app.log")
log.logger = types.SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None, error=lambda *a, **k: None)
for name, module in (("app", app), ("app.core", core), ("app.core.config", config), ("app.log", log)):
    sys.modules[name] = module

result = load("siteautotask.base.result", ROOT / "base/result.py")
decorator = load("siteautotask.base.decorator", ROOT / "base/decorator.py")
request = load("siteautotask.utils.request", ROOT / "utils/request.py")
handler_base = types.ModuleType("siteautotask.base.site_handler")
handler_base.ISiteHandler = object
sys.modules["siteautotask.base.site_handler"] = handler_base
cap = types.ModuleType("siteautotask.sites.capabilities")
class CapabilityHandler:
    def __init__(self, info):
        self.site_name = info.get("name", "")
        self.domain = info.get("domain", "")
        self.session = info["session"]
        self.site_cookie = ""
    def claim_task(self, task_id):
        return "claimed"
    def attendance(self):
        return "checked"
cap.CapabilityHandler = CapabilityHandler
sys.modules["siteautotask.sites.capabilities"] = cap
longpt = load("siteautotask.sites.longpt", ROOT / "sites/longpt.py")


class Response:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status_code = status
        self.text = __import__("json").dumps(payload, ensure_ascii=False)
    def json(self):
        return self.payload


class LongPTTests(unittest.TestCase):
    def handler(self, payload):
        session = Mock()
        session.post.return_value = Response(payload)
        session.get.return_value = Response(payload)
        return longpt.LongPTHandler({"name": "LongPT", "domain": "longpt.org", "session": session}), session

    def test_match_and_chat_success(self):
        handler, session = self.handler({"code": 0, "msg": "喊话成功"})
        ok, text = handler.send_messagebox("求上传")
        self.assertTrue(ok)
        self.assertEqual(text, "喊话成功")
        self.assertEqual(handler.get_feedback("求上传")["rewards"][0]["type"], "raw_feedback")
        session.post.assert_called_once()

    def test_chat_options_are_single_choice_messages(self):
        self.assertEqual(longpt.LongPTHandler.get_chat_options(), [
            {"id": "龙宝，求上传", "label": "求上传"},
            {"id": "龙宝，求魔力", "label": "求魔力"},
        ])

    def test_lottery_already_joined_is_idempotent_success(self):
        handler, _ = self.handler({"code": -1, "msg": "今天已经参加"})
        self.assertEqual(handler.daily_lottery(), (True, "今天已经参加"))

    def test_lottery_failure(self):
        handler, _ = self.handler({"code": 500, "msg": "服务暂不可用"})
        ok, message = handler.daily_lottery()
        self.assertFalse(ok)
        self.assertIn("服务", message)

    def test_task_metadata_types(self):
        handler, _ = self.handler({"code": 0, "msg": "ok"})
        tasks = longpt.Tasks()
        tasks.client = handler
        types_ = {item["name"]: item["task_type"] for item in tasks.get_registered_tasks()}
        self.assertEqual(types_["daily_lottery"], "lottery")
        self.assertEqual(types_["daily_shotbox"], "chat")


if __name__ == "__main__":
    unittest.main()
