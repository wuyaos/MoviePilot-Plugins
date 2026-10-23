"""M-Team has keepalive login semantics, never an attendance action."""
from urllib.parse import urljoin
from ...core.credentials import CredentialSpec
from ...core.models import LoginResult, LoginStatus, SignResult
from ...core.sitemodel import RecordSpec, SignContext, SiteModule


class MTorrent(SiteModule):
    id = "mteam"
    name = "M-Team"
    url = ""
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
                email_code = browser.evaluate("() => !!document.querySelector('input[type=email][name*=code i], input[name*=emailCode i]')")
                if email_code:
                    return False, "站点要求邮箱验证码，需同网络人工登录一次"
                browser.click('button[type="submit"]')
                try:
                    browser.page.wait_for_url("**/index**", timeout=15000)
                except Exception:
                    pass
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
            return LoginResult(LoginStatus.UNCONFIRMED, "M-Team CloakBrowser 登录异常：" + type(exc).__name__)
