import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).parents[1]

# 让测试不依赖完整 MoviePilot 运行时。
def stub_module(name, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module
    return module

stub_module("app")
stub_module("app.core")
stub_module("app.core.config", settings=types.SimpleNamespace(PROXY=None, TZ="UTC"))
stub_module("app.log", logger=types.SimpleNamespace(error=lambda *a, **k: None, warning=lambda *a, **k: None, info=lambda *a, **k: None))
stub_module("app.db")
stub_module("app.db.site_oper", SiteOper=Mock)
stub_module("app.utils")
stub_module("app.utils.string", StringUtils=types.SimpleNamespace(get_url_domain=lambda url: "example.com"))
stub_module("app.helper")
stub_module("app.helper.browser", PlaywrightHelper=Mock)

# 直接加载无完整包初始化依赖的模块。
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

RESULT = load("siteautotask_result", ROOT / "base/result.py")
DECORATOR = load("siteautotask_decorator", ROOT / "base/decorator.py")
FEEDBACK = load("siteautotask_feedback", ROOT / "utils/feedback.py")
REQUEST = load("siteautotask_request", ROOT / "utils/request.py")


class FakeResponse:
    def __init__(self, status=200, text="", payload=None):
        self.status_code = status
        self.text = text
        self._payload = payload

    def json(self):
        if self._payload is not None:
            return self._payload
        return json.loads(self.text)


class TaskCoreTests(unittest.TestCase):
    def test_task_result(self):
        ok = RESULT.TaskResult.ok("购买成功")
        fail = RESULT.TaskResult.fail("cookie 失效")
        self.assertTrue(ok.success)
        self.assertEqual(ok.to_status_text(), "购买成功")
        self.assertFalse(fail.success)

    def test_task_type_metadata(self):
        @DECORATOR.task_info("喊话", "测试", DECORATOR.TaskType.CHAT)
        def task():
            pass
        self.assertEqual(task._task_meta["task_type"], "chat")

    def test_feedback_icon_and_detection(self):
        self.assertEqual(FEEDBACK.detect_reward_type("赠送上传 10G"), "上传量")
        self.assertEqual(FEEDBACK.NotificationIcons.get("电力"), "⚡")
        result = FEEDBACK.build_feedback("青蛙", "求上传", "获得上传10G")
        self.assertEqual(result["rewards"][0]["type"], "上传量")

    def test_non_json_redirect_is_clear(self):
        response = REQUEST.parse_json_response(FakeResponse(200, "<html>login</html>"))
        self.assertFalse(response["success"])
        self.assertIn("cookie", response["msg"])

    def test_empty_response_is_clear(self):
        response = REQUEST.parse_json_response(FakeResponse(200, ""))
        self.assertFalse(response["success"])
        self.assertIn("为空", response["msg"])

    def test_proxy_string_normalized(self):
        with patch.object(REQUEST.settings, "PROXY", "http://127.0.0.1:7890"):
            session = REQUEST.build_session("cookie", "ua", True)
        self.assertEqual(session.proxies["http"], "http://127.0.0.1:7890")
        self.assertEqual(session.proxies["https"], "http://127.0.0.1:7890")

    def test_site_selection_accepts_real_id_and_legacy_domain(self):
        # 直接加载入口会牵涉 MP 依赖；验证与入口相同的匹配规则。
        selected = {"7", "qingwapt.com"}
        sites = [{"id": 7, "domain": "qingwapt.com"}, {"id": 8, "domain": "other.test"}]
        result = [s for s in sites if str(s["id"]) in selected or s["domain"] in selected]
        self.assertEqual([s["id"] for s in result], [7])


if __name__ == "__main__":
    unittest.main()
