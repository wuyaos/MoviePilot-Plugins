"""ourbits NexusPHP 密码登录：Cookie 全源失效后的兜底换取通道。

触发语义与 yzyy 一致（native.py password-login hook）：不配置账密时按原有
Cookie 来源链（Cookie 表→本地→CookieCloud）执行；配置账密且 Cookie 失效时
用表单登录换取新 Cookie，由 persist_cookie_result 回写统一 Cookie 表（即反填）。
登录页出现验证码（imagestring）时明确放弃，不硬试。
"""
from urllib.parse import urljoin

from lxml import html

import pyotp
from ..core.models import LoginResult, LoginStatus

BASE = 'https://ourbits.club/'




def _logged_in(page_text: str | None) -> bool:
    if not page_text:
        return False
    return 'logout.php' in page_text or 'usercp.php' in page_text


def login(http, info) -> LoginResult:
    username = (info.get('ourbits_username') or '').strip()
    password = (info.get('ourbits_password') or '').strip()
    if not username or not password:
        return LoginResult(LoginStatus.AUTH_FAILED, 'ourbits Cookie 已失效，且未配置账号密码')
    page = http.get(BASE + 'login.php')
    if page is None:
        return LoginResult(LoginStatus.UNCONFIRMED, 'ourbits 登录页不可达')
    tree = html.fromstring(page.text or '')
    forms = [f for f in tree.xpath('//form') if 'takelogin' in (f.get('action') or '')]
    if len(forms) != 1:
        return LoginResult(LoginStatus.UNCONFIRMED, 'ourbits 登录页未找到登录表单')
    form = forms[0]
    if form.xpath('.//input[@name="imagestring"]'):
        return LoginResult(LoginStatus.UNCONFIRMED, 'ourbits 登录需要验证码，账密登录不可用')
    data = {}
    for box in form.xpath('.//input[@name]'):
        name = box.get('name')
        if name in ('username', 'password'):
            continue
        if box.get('type', 'text').lower() in ('checkbox', 'radio', 'submit', 'image', 'button'):
            continue
        data[name] = box.get('value') or ''
    data['username'] = username
    data['password'] = password
    data['username'] = username
    data['password'] = password
    secret = (info.get('ourbits_totp') or '').strip()
    if secret:
        # 两步验证可选：配置了 TOTP 密钥才填 2fa_code，未配置按无 2FA 直接提交。
        data['2fa_code'] = pyotp.TOTP(secret).now()
    else:
        data.pop('2fa_code', None)
    action = urljoin(BASE, form.get('action'))
    posted = http.post(action, data=data,
                       headers={'Origin': BASE, 'Referer': BASE + 'login.php'})
    if posted is not None and _logged_in(posted.text):
        return LoginResult(LoginStatus.LOGIN_OK, 'ourbits 账密登录成功')
    home = http.get(BASE)
    if home is not None and _logged_in(home.text):
        return LoginResult(LoginStatus.LOGIN_OK, 'ourbits 账密登录成功')
    return LoginResult(LoginStatus.AUTH_FAILED, 'ourbits 账号认证失败（账号、密码或 TOTP 密钥有误）')
