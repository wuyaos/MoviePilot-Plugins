"""好学（FluxTorrent）适配回归：全部合成响应，不发真实网络请求。"""
import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).parents[1]
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
# MoviePilot 宿主依赖（app.*）必须先于 core/task.py 注入，后者 import app.core.event。
app = types.ModuleType("app")
app.__path__ = []
sys.modules["app"] = app
app_core = types.ModuleType("app.core")
app_core.__path__ = []
sys.modules["app.core"] = app_core
app_config = types.ModuleType("app.core.config")
app_config.settings = types.SimpleNamespace(TZ="Asia/Shanghai")
sys.modules["app.core.config"] = app_config
app_schemas = types.ModuleType("app.schemas")
app_schemas.__path__ = []
app_schemas.NotificationType = types.SimpleNamespace(SiteMessage="SiteMessage")
sys.modules["app.schemas"] = app_schemas
app_event = types.ModuleType("app.core.event")


class _EventManager:
    @staticmethod
    def register(*args, **kwargs):
        return lambda func: func


app_event.Event = type("Event", (), {})
app_event.eventmanager = _EventManager()
sys.modules["app.core.event"] = app_event
app_types = types.ModuleType("app.schemas.types")
app_types.EventType = types.SimpleNamespace(PluginAction="PluginAction")
sys.modules["app.schemas.types"] = app_types
app_plugins = types.ModuleType("app.plugins")
app_plugins._PluginBase = object
sys.modules["app.plugins"] = app_plugins
db = types.ModuleType("app.db")
db.__path__ = []
sys.modules["app.db"] = db
site_oper = types.ModuleType("app.db.site_oper")
site_oper.SiteOper = type("SiteOper", (), {})
sys.modules["app.db.site_oper"] = site_oper
log = types.ModuleType("app.log")
log.logger = types.SimpleNamespace(error=lambda *a, **k: None, warning=lambda *a, **k: None, info=lambda *a, **k: None)
sys.modules["app.log"] = log
load(f"{PACKAGE}.core.models", ROOT / "core/models.py")
load(f"{PACKAGE}.core.task_keys", ROOT / "core/task_keys.py")
checkin = load(f"{PACKAGE}.actions.checkin", ROOT / "actions/checkin.py")
load(f"{PACKAGE}.core.task", ROOT / "core/task.py")
load(f"{PACKAGE}.core.shoutbox", ROOT / "core/shoutbox.py")

load(f"{PACKAGE}.core.site", ROOT / "core/site.py")
hxpt = load(f"{PACKAGE}.sites.hxpt", ROOT / "sites/hxpt.py")

HxPT = hxpt.HxPT
FluxTorrentCheckin = checkin.FluxTorrentCheckin
NexusPHPCheckin = checkin.NexusPHPCheckin


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


class FluxTorrentCheckinTests(unittest.TestCase):

    def test_already_today_is_idempotent(self):
        site = FakeSite([Resp(envelope(checked=True))])
        result = FluxTorrentCheckin().execute(site)
        self.assertTrue(result.success and result.terminal and not result.retryable)
        self.assertIn("已签到", result.message)
        self.assertEqual(site.calls, [("GET", "/api/v1/attendance")])

    def test_success_after_submit_and_reread(self):
        site = FakeSite([Resp(envelope(checked=False)),
                         Resp(envelope(reward=600, streak=149)),
                         Resp(envelope(checked=True))])
        result = FluxTorrentCheckin().execute(site)
        self.assertTrue(result.success)
        self.assertIn("签到成功", result.message)
        self.assertIn("+600 魔力", result.message)
        self.assertIn("连续 149 天", result.message)
        self.assertEqual(site.calls, [("GET", "/api/v1/attendance"),
                                      ("POST", "/api/v1/attendance/checkin", {}),
                                      ("GET", "/api/v1/attendance")])

    def test_status_unreadable_is_retryable_fail(self):
        result = FluxTorrentCheckin().execute(FakeSite([Resp("<html>login</html>")]))
        self.assertFalse(result.success)
        self.assertTrue(result.retryable)

    def test_submitted_but_reread_unconfirmed_is_business(self):
        site = FakeSite([Resp(envelope(checked=False)),
                         Resp(envelope()),
                         Resp(envelope(checked=False))])
        result = FluxTorrentCheckin().execute(site)
        self.assertFalse(result.success)
        self.assertFalse(result.retryable)
        self.assertIn("回读", result.message)

    def test_reread_lost_after_submit_is_retryable_fail(self):
        site = FakeSite([Resp(envelope(checked=False)),
                         Resp(envelope()),
                         Resp("<html>boom</html>")])
        result = FluxTorrentCheckin().execute(site)
        self.assertFalse(result.success)
        self.assertTrue(result.retryable)

    def test_nonzero_code_is_business(self):
        result = FluxTorrentCheckin().execute(FakeSite([Resp(envelope(code=403, message="forbidden"))]))
        self.assertFalse(result.success)
        self.assertFalse(result.retryable)
        self.assertIn("forbidden", result.message)

    def test_default_nexusphp_strategy_untouched(self):
        self.assertEqual(NexusPHPCheckin().path, "/attendance.php")


class HxPTDeclarationTests(unittest.TestCase):

    def test_negatives_include_loss_word(self):
        self.assertIn("丢失", HxPT.tasks[1].negatives)
        self.assertIn("失去", HxPT.tasks[1].negatives)

    def test_tasks_composition(self):
        types_names = [type(task).__name__ for task in HxPT.tasks]
        self.assertEqual(types_names, ["Checkin", "Chat", "Claim"])
        self.assertEqual(type(HxPT.tasks[0].action).__name__, "FluxTorrentCheckin")
        ids = {str(option["id"]) for option in HxPT.tasks[2].options}
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

    def test_claim_non_json_is_retryable_fail(self):
        result = HxPT.claim_task(FakeSite([Resp("<html>err</html>")]), "2")
        self.assertFalse(result.success)
        self.assertTrue(result.retryable)


if __name__ == "__main__":
    unittest.main()
