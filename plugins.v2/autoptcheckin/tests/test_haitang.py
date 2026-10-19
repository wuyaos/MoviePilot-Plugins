"""海棠新版 attendance.php POST 表单适配测试。"""
import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]


def package(name, path=None):
    module = types.ModuleType(name)
    module.__path__ = [str(path or ROOT)]
    sys.modules[name] = module
    return module


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


package("app")
package("app.core")
package("app.plugins")
package("app.plugins.autoptcheckin", ROOT)
helper_package = package("app.plugins.autoptcheckin.helper", ROOT / "helper")
sites_package = package("app.plugins.autoptcheckin.sites", ROOT / "sites")
package("app.utils")

settings = types.SimpleNamespace(PROXY=None, USER_AGENT="test-agent")
config_module = types.ModuleType("app.core.config")
config_module.settings = settings
sys.modules["app.core.config"] = config_module
logger = types.SimpleNamespace(
    info=lambda *args, **kwargs: None,
    warning=lambda *args, **kwargs: None,
    error=lambda *args, **kwargs: None,
)
log_module = types.ModuleType("app.log")
log_module.logger = logger
sys.modules["app.log"] = log_module
sites_package._ISiteSigninHandler = object

http_module = types.ModuleType("app.utils.http")
http_module.RequestUtils = object
sys.modules["app.utils.http"] = http_module
site_module = types.ModuleType("app.utils.site")
site_module.SiteUtils = types.SimpleNamespace(
    is_logged_in=lambda html: "member-page" in (html or ""),
)
sys.modules["app.utils.site"] = site_module
string_module = types.ModuleType("app.utils.string")
string_module.StringUtils = types.SimpleNamespace(url_equal=lambda left, right: left == right)
sys.modules["app.utils.string"] = string_module

post_helper = load(
    "app.plugins.autoptcheckin.helper.attendance_post_helper",
    ROOT / "helper/attendance_post_helper.py",
)
helper_package.attendance_post_helper = post_helper
Haitang = load(
    "app.plugins.autoptcheckin.sites.haitang",
    ROOT / "sites/haitang.py",
).Haitang

UNSIGNED_HTML = """
<html><body>member-page
<form method="post" action="attendance.php">
<input type="hidden" name="action" value="sign">
<button type="submit">立即签到</button>
</form>
<table><tr><td class="att-cell att-today">19<div>今天</div></td></tr></table>
</body></html>
"""
POST_RESPONSE_HTML = "<html><body>签到操作完成</body></html>"
SIGNED_HTML = """
<html><body>member-page 今日已签到
<table><tr><td class="att-cell att-signed">19<div>✓ +350点</div></td></tr></table>
</body></html>
"""


class Response:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code


class FakeRequest:
    def __init__(self, get_htmls):
        self.get_htmls = list(get_htmls)
        self.posts = []

    def get_res(self, url):
        return Response(self.get_htmls.pop(0))

    def post_res(self, url, data):
        self.posts.append((url, data))
        return Response(POST_RESPONSE_HTML)


class HaitangTests(unittest.TestCase):
    def test_button_submit_form_is_detected(self):
        self.assertEqual(
            post_helper._AttendancePostHandler.detect_attendance_state(UNSIGNED_HTML),
            post_helper.ATTENDANCE_FORM,
        )

    def test_signin_posts_action_and_confirms_refetched_page(self):
        request = FakeRequest([UNSIGNED_HTML, SIGNED_HTML])
        handler = Haitang()
        handler._build_request = lambda **kwargs: request

        success, message = handler.signin({"name": "海棠", "cookie": "cookie"})

        self.assertTrue(success)
        self.assertEqual(message, "签到成功")
        self.assertEqual(
            request.posts,
            [("https://www.htpt.cc/attendance.php", {"action": "sign"})],
        )

    def test_already_signed_does_not_post(self):
        request = FakeRequest([SIGNED_HTML])
        handler = Haitang()
        handler._build_request = lambda **kwargs: request

        success, message = handler.signin({"name": "海棠", "cookie": "cookie"})

        self.assertTrue(success)
        self.assertEqual(message, "今日已签到")
        self.assertEqual(request.posts, [])


if __name__ == "__main__":
    unittest.main()
