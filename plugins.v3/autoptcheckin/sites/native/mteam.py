"""M-Team has keepalive login semantics, never an attendance action."""
from urllib.parse import urljoin
from ...core.credentials import CredentialSpec
from ...core.models import LoginResult, LoginStatus, SignResult
from ...core.sitemodel import RecordSpec, SignContext, SiteModule


_MTEAM_OTP_SUBMIT_SELECTORS = (
    'text=登 錄',
    'text=登录',
    'text=登錄',
    'xpath=//*[self::button or self::div or self::span or self::input or @role="button"]['
    'contains(normalize-space(.), "登") or contains(@value, "登")]',
    '[role=button]:has-text("登")',
    'button[type=submit]',
    'input[type=submit]',
)


def _wait_for_mteam_index(page, timeout):
    try:
        page.wait_for_url("**/index**", timeout=timeout)
        return True
    except Exception:
        return "/index" in page.url


def _submit_mteam_otp(page):
    """Submit the SPA 2FA form, allowing OTP-only auto-submit first."""
    if _wait_for_mteam_index(page, timeout=3000):
        return True
    for selector in _MTEAM_OTP_SUBMIT_SELECTORS:
        try:
            locator = page.locator(selector).first
            if locator.count():
                locator.click()
                break
        except Exception:
            continue
    else:
        page.keyboard.press("Enter")
    return _wait_for_mteam_index(page, timeout=15000)


class MTorrent(SiteModule):
    id = "mteam"
    name = "M-Team"
    url = "https://kp.m-team.cc/"

    @classmethod
    def match(cls, url: str) -> bool:
        """V2 多域名口径：hostname 任一段含 m-team 即命中（m-team.cc/m-team.io）。"""
        from urllib.parse import urlsplit
        host = (urlsplit(url).hostname or "").removeprefix("www.")
        return "m-team" in host.split(".")
    credential = CredentialSpec(kind="password", cookie_sources=())
    login_capable = True
    emulate = False
    hook_implemented = False
    record_spec = RecordSpec('//*[@id="batch2-message-pending-calibration"]', {})

    def signin(self, ctx: SignContext) -> SignResult:
        result = ctx.result(status="skipped", message="hook_not_implemented")
        result.metadata["reason"] = "hook_not_implemented"
        return result

    def keepalive_login(self, info):
        """登录 M-Team 并持久化浏览器 storage_state，不执行签到或保活动作。"""
        from ...core.cloak import CloakSession, state_path
        base = info.get("url") or "https://kp.m-team.cc/"
        username, password = info.get("mteam_username", ""), info.get("mteam_password", "")
        if not username or not password:
            return LoginResult(LoginStatus.AUTH_FAILED, "缺少 M-Team 账号或密码")
        state = state_path(self.id)

        def launch(state_file):
            with CloakSession(state=state_file, url=base) as browser:
                browser.goto(base)
                active = browser.evaluate("() => !!document.querySelector('a[href*=\"logout\"], [data-testid*=\"logout\"]') || !!localStorage.getItem('token')")
                if active:
                    return True, ""
                browser.goto(urljoin(base, "/login"))
                browser.fill("#username", username)
                browser.fill("#password", password)
                has_totp = browser.evaluate("() => !!document.querySelector('input[autocomplete=one-time-code], input[name*=totp i], input[name*=otp i]')")
                if has_totp and info.get("mteam_totp"):
                    import pyotp
                    browser.fill('input[autocomplete="one-time-code"], input[name*="totp" i], input[name*="otp" i]',
                                 pyotp.TOTP(info["mteam_totp"]).now())
                two_fa = browser.evaluate(
                    "() => /\u96d9\u91cd\u8a8d\u8b49|\u9a8c\u8b49\u78bc|\u90f5\u7bb1/.test(document.body.innerText) &&"
                    " !!document.querySelector('input[name*=code i], input[name*=otp i], input[type=text][name*=auth i]')"
                )
                if two_fa:
                    # 站点提示页含「帳號被禁用?」等通用文案，仅为提示非封禁；要求 6 位验证码，TOTP 可自动填。
                    pass  # 落到下方 #otp-code 分支处理
                browser.click('button[type="submit"]')
                if not _wait_for_mteam_index(browser.page, timeout=15000):
                    # 双重认证页：#otp-code（6 位验证码，TOTP 密钥可算）——填入后二次提交。
                    otp = browser.page.locator('#otp-code').first
                    if otp.count() and info.get("mteam_totp"):
                        import pyotp
                        otp.fill(pyotp.TOTP(info["mteam_totp"]).now())
                        browser.page.wait_for_timeout(800)
                        _submit_mteam_otp(browser.page)
                if "/index" not in browser.page.url:
                    feature = browser.evaluate("() => document.body.innerText.slice(0,300)")
                    return False, "登录未到达 /index：" + str(feature)
                browser.save_state(state)
                return True, "M-Team 保活登录成功"

        try:
            if state.exists():
                try:
                    ok, message = launch(state)
                except Exception:
                    state.unlink(missing_ok=True)
                    ok, message = False, "存档恢复失败"
                if ok:
                    return LoginResult(LoginStatus.LOGIN_OK, "已恢复 M-Team 登录态")
                state.unlink(missing_ok=True)
                if "邮箱验证码" in message:
                    return LoginResult(LoginStatus.UNCONFIRMED, message)
            ok, message = launch(None)
            status = LoginStatus.LOGIN_OK if ok else (
                LoginStatus.UNCONFIRMED if "邮箱验证码" in message else LoginStatus.AUTH_FAILED)
            return LoginResult(status, message)
        except Exception as exc:
            return LoginResult(LoginStatus.UNCONFIRMED, "M-Team CloakBrowser 登录异常：" + type(exc).__name__ + "：" + str(exc)[:200])
