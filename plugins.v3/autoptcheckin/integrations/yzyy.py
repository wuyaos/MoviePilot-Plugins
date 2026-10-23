"""yzyy（Discuz）账密登录：Cookie 有效直接用，失效用账号密码换新 Cookie（全 HTTP）。"""
from ..core.models import LoginResult, LoginStatus

BASE = "https://yzyy.org"


def logged_in(http):
    page = http.get(BASE + "/")
    if page is None or not page_available(getattr(page, "text", "")):
        return False
    text = page.text or ""
    return "action=logout" in text


def page_available(text):
    return bool(text)


def login(http, info):
    """Cookie 有效 → LOGIN_OK；失效且配置了账号密码 → Discuz 表单登录换新 Cookie。"""
    if logged_in(http):
        return LoginResult(LoginStatus.LOGIN_OK, "yzyy Cookie 有效")
    username = info.get("yzyy_username", "")
    password = info.get("yzyy_password", "")
    if not username or not password:
        return LoginResult(LoginStatus.AUTH_FAILED, "yzyy Cookie 已失效，且未配置账号密码")
    page = http.get(BASE + "/member.php?mod=logging&action=login")
    if page is None:
        return LoginResult(LoginStatus.UNCONFIRMED, "yzyy 登录页不可达")
    import re
    match = re.search(r'name="formhash"\s+value="([a-f0-9]+)"', page.text or "")
    if not match:
        return LoginResult(LoginStatus.UNCONFIRMED, "yzyy 登录页未取到 formhash")
    formhash = match.group(1)
    login_page = http.post(
        BASE + "/member.php?mod=logging&action=login&loginsubmit=yes&loginfield=auto",
        data={"formhash": formhash, "referer": BASE + "/forum.php", "loginfield": "auto",
              "username": username, "password": password, "questionid": "0", "answer": "",
              "cookietime": "2592000"},
        headers={"Origin": BASE, "Referer": BASE + "/member.php?mod=logging&action=login"})
    if login_page is not None and "欢迎" in (login_page.text or ""):
        pass
    if logged_in(http):
        return LoginResult(LoginStatus.LOGIN_OK, "yzyy 账密登录成功")
    return LoginResult(LoginStatus.AUTH_FAILED, "yzyy 账号认证失败")
