"""ourbits 账密兜底登录：表单解析、验证码放弃、成功/失败判定。Offline only."""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parents[3] / "plugins.v3"))
from autoptcheckin.integrations.ourbits import login

LOGIN_PAGE = ('<html><form method="post" action="takelogin.php">'
              '<input type="hidden" name="secret" value="token-1">'
              '<input type="text" name="username" value="">'
              '<input type="password" name="password" value="">'
              '<input type="submit" value="登录"></form></html>')
CAPTCHA_PAGE = ('<html><form method="post" action="takelogin.php">'
                '<input type="hidden" name="secret" value="token-1">'
                '<input type="text" name="imagestring" value="">'
                '<input type="text" name="username" value="">'
                '<input type="password" name="password" value=""></form></html>')
HOME_LOGGED_IN = '<html><a href="logout.php">退出</a></html>'
HOME_ANONYMOUS = '<html><a href="login.php">登录</a></html>'


class Http:
    def __init__(self, pages):
        self.pages = list(pages)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(("get", url))
        return SimpleNamespace(text=self.pages.pop(0)) if self.pages else None

    def post(self, url, *, data=None, json=None, headers=None):
        self.calls.append(("post", url, data))
        return SimpleNamespace(text=self.pages.pop(0)) if self.pages else None


INFO = {'ourbits_username': 'user1', 'ourbits_password': 'pass1'}


def test_missing_credentials_is_auth_failed():
    result = login(Http([]), {})
    assert result.status == "auth_failed"
    assert "未配置账号密码" in result.message


def test_captcha_login_page_gives_up_clearly():
    http = Http([CAPTCHA_PAGE])
    result = login(http, INFO)
    assert result.status == "unconfirmed"
    assert "验证码" in result.message
    assert [x[0] for x in http.calls] == ["get"]


def test_success_posts_credentials_and_hidden_fields():
    http = Http([LOGIN_PAGE, HOME_LOGGED_IN])
    result = login(http, INFO)
    assert result.status == "login_ok"
    assert "账密登录成功" in result.message
    assert [x[0] for x in http.calls] == ["get", "post"]
    assert http.calls[1][1].endswith("takelogin.php")
    assert http.calls[1][2] == {"secret": "token-1", "username": "user1", "password": "pass1"}


def test_302_home_fallback_confirms_login():
    http = Http([LOGIN_PAGE, HOME_ANONYMOUS, HOME_LOGGED_IN])
    result = login(http, INFO)
    assert result.status == "login_ok"
    assert [x[0] for x in http.calls] == ["get", "post", "get"]


def test_wrong_password_is_auth_failed():
    http = Http([LOGIN_PAGE, HOME_ANONYMOUS, HOME_ANONYMOUS])
    result = login(http, INFO)
    assert result.status == "auth_failed"
    assert "认证失败" in result.message


TFA_PAGE = ('<html><form method="post" action="takelogin.php">'
            '<input type="hidden" name="secret" value="token-1">'
            '<input type="text" name="2fa_code" value="">'
            '<input type="text" name="username" value="">'
            '<input type="password" name="password" value=""></form></html>')


def test_totp_configured_fills_2fa_code():
    import pyotp
    secret = 'GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ'
    info = {**INFO, 'ourbits_totp': secret}
    http = Http([TFA_PAGE, HOME_LOGGED_IN])
    result = login(http, info)
    assert result.status == "login_ok"
    assert http.calls[1][2]['2fa_code'] == pyotp.TOTP(secret).now()


def test_totp_absent_omits_2fa_code():
    http = Http([TFA_PAGE, HOME_LOGGED_IN])
    result = login(http, INFO)
    assert result.status == "login_ok"
    assert '2fa_code' not in http.calls[1][2]
