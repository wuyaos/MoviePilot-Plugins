"""好学（FluxTorrent）适配回归：全部合成响应，不发真实网络请求。"""
import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).parents[3] / "plugins.v3" / "pttaskflow"
PACKAGE = "pttaskflow_hxpt_test"


def package(name, path):
    module = types.ModuleType(name)
    module.__path__ = [str(path)]
    sys.modules[name] = module


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


package(PACKAGE, ROOT)
package(f"{PACKAGE}.core", ROOT / "core")
package(f"{PACKAGE}.actions", ROOT / "actions")
package(f"{PACKAGE}.sites", ROOT / "sites")
# MoviePilot 宿主依赖（app.*）必须先于 core/task.py 注入，后者 import app.sdk.events。
app = types.ModuleType("app")
app.__path__ = []
sys.modules["app"] = app
app_core = types.ModuleType("app.core")
app_core.__path__ = []
sys.modules["app.core"] = app_core
app_config = types.ModuleType("app.sdk.config")
app_config.settings = types.SimpleNamespace(TZ="Asia/Shanghai")
sys.modules["app.core.config"] = app_config
app_schemas = types.ModuleType("app.schemas")
app_schemas.__path__ = []
app_schemas.NotificationType = types.SimpleNamespace(SiteMessage="SiteMessage")
sys.modules["app.schemas"] = app_schemas
app_event = types.ModuleType("app.sdk.events")


class _EventManager:
    @staticmethod
    def register(*args, **kwargs):
        return lambda func: func


app_event.Event = type("Event", (), {})
app_event.eventmanager = _EventManager()
sys.modules["app.sdk.events"] = app_event
app_types = types.ModuleType("app.schemas.types")
app_types.EventType = types.SimpleNamespace(PluginAction="PluginAction")
sys.modules["app.schemas.types"] = app_types
app_plugins = types.ModuleType("app.plugins")
app_plugins._PluginBase = object
sys.modules["app.plugins"] = app_plugins
db = types.ModuleType("app.db")
db.__path__ = []
sys.modules["app.db"] = db
site_oper = types.ModuleType("app.db.oper")
site_oper.SiteOper = type("SiteOper", (), {})
sys.modules["app.db.oper"] = site_oper
log = types.ModuleType("app.log")
log.logger = types.SimpleNamespace(error=lambda *a, **k: None, warning=lambda *a, **k: None, info=lambda *a, **k: None)
sys.modules["app.log"] = log
load(f"{PACKAGE}.core.models", ROOT / "core/models.py")
load(f"{PACKAGE}.core.task_keys", ROOT / "core/task_keys.py")
load(f"{PACKAGE}.core.task", ROOT / "core/task.py")
load(f"{PACKAGE}.core.shoutbox", ROOT / "core/shoutbox.py")

load(f"{PACKAGE}.core.site", ROOT / "core/site.py")
hxpt = load(f"{PACKAGE}.sites.hxpt", ROOT / "sites/hxpt.py")

HxPT = hxpt.HxPT


class Resp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        if isinstance(self._payload, str):
            raise ValueError("not json")
        return self._payload

    @property
    def text(self):
        return self._payload if isinstance(self._payload, str) else "{}"


class FakeSite:
    request_error = ""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, path, params=None):
        self.calls.append(("GET", path))
        return self.responses.pop(0)

    def post(self, path, data=None, json=None):
        self.calls.append(("POST", path, json))
        return self.responses.pop(0)


def envelope(code=0, checked=None, reward=None, streak=None, message="ok"):
    data = {}
    if checked is not None:
        data["checked_today"] = checked
    if reward is not None:
        data["reward"] = reward
    if streak is not None:
        data["streak"] = streak
    return {"code": code, "message": message, "data": data}


class HxPTCsrfTests(unittest.TestCase):
    def site(self, cookie="session=fake; flux_csrf=old%2Btoken"):
        return HxPT({"id": 1, "url": "https://www.hxpt.org", "cookie": cookie})

    def response(self, code=200, payload=None):
        from requests import Response
        import json
        response = Response()
        response.status_code = code
        response._content = json.dumps(payload or envelope()).encode()
        response.url = "https://www.hxpt.org/api/v1/me/csrf"
        return response

    def test_cookie_header_becomes_jar_and_updated_csrf_is_used(self):
        from unittest.mock import patch
        site = self.site()
        self.assertNotIn("Cookie", site.session.headers)
        site.session.cookies.set("flux_csrf", "new%2Btoken", domain="www.hxpt.org", path="/")
        with patch.object(site.session, "request", return_value=self.response()) as request:
            site.post("/api/v1/tasks/claim", json={})
        self.assertEqual(request.call_count, 1)
        self.assertEqual(request.call_args.kwargs["headers"]["x-csrf-token"], "new+token")
        self.assertFalse(request.call_args.kwargs["allow_redirects"])
        self.assertEqual(request.call_args.kwargs["json"], {})
        self.assertEqual(site.session.get_adapter(site.url).max_retries.total, 0)

    def test_missing_csrf_bootstraps_once_then_posts(self):
        from unittest.mock import patch
        site = self.site("session=fake")
        calls = []

        def request(method, url, **kwargs):
            calls.append((method, url, kwargs))
            if method == "GET":
                site.session.cookies.set("flux_csrf", "boot%2Ftoken", domain="www.hxpt.org", path="/")
            return self.response()

        with patch.object(site.session, "request", side_effect=request):
            site.post("/api/v1/tasks/claim", json={"task_id": 2})
        self.assertEqual([c[0] for c in calls], ["GET", "POST"])
        self.assertTrue(calls[0][1].endswith("/api/v1/me/csrf"))
        self.assertEqual(calls[1][2]["headers"]["x-csrf-token"], "boot/token")

    def test_foreign_csrf_is_not_used_and_missing_token_does_not_post(self):
        from unittest.mock import patch
        site = self.site("session=fake")
        site.session.cookies.set("flux_csrf", "foreign", domain="other.invalid", path="/")
        with patch.object(site.session, "request", return_value=self.response()) as request:
            self.assertIsNone(site.post("/api/v1/shoutbox", json={"message": "fixture"}))
        self.assertEqual(request.call_count, 1)
        self.assertEqual(request.call_args.args[0], "GET")
        self.assertIn("未发送", site.request_error)

    def test_rejected_post_is_not_refreshed_or_replayed(self):
        from unittest.mock import Mock, patch
        site = self.site()
        site.cookie_refresher = Mock(return_value="session=refreshed")
        response = self.response(403, envelope(code=403))
        with patch.object(site.session, "request", return_value=response) as request:
            self.assertIs(site.post("/api/v1/shoutbox", json={"message": "fixture"}), response)
        self.assertEqual(request.call_count, 1)
        site.cookie_refresher.assert_not_called()
        self.assertIn("403", site.request_error)

    def test_post_timeout_records_type_not_secret(self):
        from unittest.mock import patch
        site = self.site()
        with patch.object(site.session, "request", side_effect=TimeoutError("SECRET")) as request:
            self.assertIsNone(site.post("/api/v1/tasks/claim", json={"task_id": 2}))
        self.assertEqual(request.call_count, 1)
        self.assertIn("TimeoutError", site.request_error)
        self.assertNotIn("SECRET", site.request_error)

    def test_other_sites_keep_their_default_retry_policy(self):
        from importlib import import_module
        Site = import_module(f"{PACKAGE}.core.site").Site
        site = Site({"url": "https://fixture.invalid", "cookie": "session=fake"})
        self.assertIn("POST", site.session.get_adapter(site.url).max_retries.allowed_methods)
        self.assertIn("Cookie", site.session.headers)


class HxPTJsonChatTests(unittest.TestCase):
    now = 1800000000
    message = "好好学习天天向上"

    def row(self, row_id, username="fixture", message=None, offset=0):
        from datetime import datetime, timezone
        return {"id": row_id, "username": username,
                "message": self.message if message is None else message,
                "created_at": datetime.fromtimestamp(self.now + offset, timezone.utc).isoformat()}

    def run_chat(self, before, after, receipt=None):
        from unittest.mock import Mock, patch
        site = HxPT({"id": 1, "url": "https://www.hxpt.org", "cookie": "session=fake"})
        site.get_username = Mock(return_value="fixture")
        site.get = Mock(side_effect=[Resp({"code": 0, "data": before}),
                                     Resp({"code": 0, "data": after})])
        site.post = Mock(return_value=receipt if receipt is not None else Resp(envelope()))
        with patch.object(hxpt.time, "time", side_effect=[self.now, self.now + 5]), \
                patch.object(hxpt.time, "sleep"):
            result = site.send_and_confirm(self.message, HxPT.tasks[0].negatives)
        site.post.assert_called_once_with("/api/v1/shoutbox", json={"message": self.message})
        self.assertEqual([call.args[0] for call in site.get.call_args_list],
                         ["/api/v1/shoutbox", "/api/v1/shoutbox"])
        return result

    def test_new_exact_user_message_confirms(self):
        result = self.run_chat([self.row(10, offset=-100)], [self.row(11, offset=1)])
        self.assertTrue(result.success and result.terminal)
        self.assertFalse(result.rewards)

    def test_old_same_message_cannot_confirm(self):
        row = self.row(10, offset=-100)
        result = self.run_chat([row], [row])
        self.assertFalse(result.success or result.retryable)

    def test_other_user_same_message_cannot_confirm(self):
        result = self.run_chat([], [self.row(11, username="fixture2", offset=1)])
        self.assertFalse(result.success or result.retryable)

    def test_unseen_but_old_message_cannot_confirm(self):
        result = self.run_chat([], [self.row(11, offset=-3600)])
        self.assertFalse(result.success or result.retryable)

    def test_new_loss_feedback_is_negative(self):
        result = self.run_chat([], [self.row(12, "system", "系统提示：@fixture 丢失 2 火花", 2),
                                    self.row(11, offset=1)])
        self.assertTrue(result.success)
        self.assertEqual(result.rewards[0]["type"], "魔力值")
        self.assertTrue(result.rewards[0]["is_negative"])
        self.assertIn("丢失", result.rewards[0]["description"])

    def test_feedback_for_other_username_is_not_attributed(self):
        result = self.run_chat([], [self.row(11, offset=1),
                                    self.row(12, "system", "@fixture2 获得 2 火花", 2)])
        self.assertTrue(result.success)
        self.assertFalse(result.rewards)

    def test_old_feedback_is_not_attributed(self):
        old = self.row(10, "system", "@fixture 获得 2 火花", -10)
        result = self.run_chat([old], [old, self.row(11, offset=1)])
        self.assertTrue(result.success)
        self.assertFalse(result.rewards)

    def test_other_user_cannot_spoof_system_feedback(self):
        result = self.run_chat([], [self.row(11, offset=1),
                                    self.row(12, "other", "系统提示：@fixture 获得 2 火花", 2)])
        self.assertTrue(result.success)
        self.assertFalse(result.rewards)

    def test_feedback_alone_is_not_proof_of_sent_message(self):
        result = self.run_chat([], [self.row(12, "system", "@fixture 获得 2 火花", 2)])
        self.assertFalse(result.success or result.retryable)

    def test_duplicate_new_own_messages_are_ambiguous(self):
        result = self.run_chat([], [self.row(11, offset=1), self.row(12, offset=2)])
        self.assertFalse(result.success or result.retryable)

    def test_rejected_post_can_still_be_confirmed_by_read(self):
        receipt = Resp(envelope(code=403))
        receipt.status_code = 403
        result = self.run_chat([], [self.row(11, offset=1)], receipt)
        self.assertTrue(result.success)

    def test_rejected_post_without_new_message_does_not_retry(self):
        receipt = Resp(envelope(code=403))
        receipt.status_code = 403
        result = self.run_chat([], [], receipt)
        self.assertFalse(result.success or result.retryable)
        self.assertIn("403", result.message)

    def test_malformed_baseline_prevents_post(self):
        from unittest.mock import Mock
        site = HxPT({"url": "https://www.hxpt.org"})
        site.get_username = Mock(return_value="fixture")
        site.get = Mock(return_value=Resp({"code": 0, "data": [{"id": 10}]}))
        site.post = Mock()
        result = site.send_and_confirm(self.message)
        self.assertFalse(result.success)
        site.post.assert_not_called()

    def test_json_error_envelope_is_not_snapshot(self):
        self.assertIsNone(HxPT._chat_rows(Resp({"code": 403, "data": []})))
        self.assertIsNone(HxPT._chat_rows(Resp({"code": 0, "data": {}})))
        self.assertEqual(HxPT._chat_rows(Resp({"code": 0, "data": []})), [])


class HxPTDeclarationTests(unittest.TestCase):

    def test_negatives_include_loss_word(self):
        self.assertIn("丢失", HxPT.tasks[0].negatives)
        self.assertIn("失去", HxPT.tasks[0].negatives)

    def test_tasks_composition(self):
        types_names = [type(task).__name__ for task in HxPT.tasks]
        self.assertEqual(types_names, ["Chat", "Claim"])
        ids = {str(option["id"]) for option in HxPT.tasks[1].options}
        self.assertEqual(ids, {"2", "3"})


class ClaimTaskTests(unittest.TestCase):

    def test_claim_success_with_reward(self):
        site = FakeSite([Resp(envelope(code=0, reward=5000, message="ok"))])
        result = HxPT.claim_task(site, "2")
        self.assertTrue(result.success and result.terminal)
        self.assertIn("5000", result.message)
        self.assertEqual(site.calls, [("POST", "/api/v1/tasks/claim", {"task_id": 2})])

    def test_claim_quota_full_is_idempotent(self):
        site = FakeSite([Resp(envelope(code=1005, message="认领人数已达上限"))])
        result = HxPT.claim_task(site, "2")
        self.assertTrue(result.success and result.terminal)

    def test_claim_business_rejection(self):
        site = FakeSite([Resp(envelope(code=1006, message="次数不足"))])
        result = HxPT.claim_task(site, "3")
        self.assertFalse(result.success)
        self.assertFalse(result.retryable)

    def test_claim_eligibility_lacking_is_idempotent(self):
        # 站点把「资格不足」归为永久性拒绝（含“资格”字样），按幂等处理不重试。
        site = FakeSite([Resp(envelope(code=1006, message="资格不足"))])
        result = HxPT.claim_task(site, "3")
        self.assertTrue(result.success and result.terminal)

    def test_claim_invalid_id_is_retryable_fail(self):
        result = HxPT.claim_task(FakeSite([]), "abc")
        self.assertFalse(result.success)
        self.assertTrue(result.retryable)

    def test_claim_non_json_is_unknown_without_replay(self):
        result = HxPT.claim_task(FakeSite([Resp("<html>err</html>")]), "2")
        self.assertFalse(result.success)
        self.assertFalse(result.retryable)


if __name__ == "__main__":
    unittest.main()
