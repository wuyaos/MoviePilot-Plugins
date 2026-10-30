"""M-Team has keepalive login semantics, never an attendance action."""
from urllib.parse import urljoin
from ...core.credentials import CredentialSpec
from ...core.models import LoginResult, LoginStatus, SignResult
from ...core.sitemodel import RecordSpec, SignContext, SiteModule


_MTEAM_AUTH_JS = """() => {
  const ls = window.localStorage;
  return {authed: !!(ls.getItem('auth') || ls.getItem('token') || ls.getItem('jwt')),
          logout: !!document.querySelector('a[href*="logout"], [data-testid*="logout"]'),
          url: location.href};
}"""
# 2FA 默认 tab 就是「雙重認證碼」(TOTP)；「郵箱驗證碼」只是同页另一个 tab，不需要 IMAP。
_MTEAM_OTP_INPUT = '#otp-code, input[autocomplete="one-time-code"], input[name*="otp" i]'
_MTEAM_2FA_HINTS = ("郵箱驗證碼", "邮箱验证码", "雙重認證", "双重认证", "two-factor", "2FA")
# 真实按钮优先：`text=` 会命中外层容器，点上去等于点空处（qnap 2026-10-29 实测失败根因）。
_MTEAM_OTP_SUBMIT_SELECTORS = (
    'button[type="submit"]',
    'input[type="submit"]',
    'button:has-text("登")',
    '[role=button]:has-text("登")',
    'text="登 錄"',
    'text="登錄"',
    'text="登录"',
    'xpath=//*[self::button or self::div or self::span or self::input or @role="button"]['
    'contains(normalize-space(.), "登") or contains(@value, "登")]',
)


def _wait_for_mteam_index(page, timeout):
    try:
        page.wait_for_url("**/index**", timeout=timeout)
        return True
    except Exception:
        return "/index" in page.url


def _submit_mteam_otp(page):
    """提交 SPA 2FA 表单；点错元素（text= 命中容器）就换下一个候选，直到离开 2FA 页。"""
    if _wait_for_mteam_index(page, timeout=3000):
        return True
    for selector in _MTEAM_OTP_SUBMIT_SELECTORS:
        try:
            locator = page.locator(selector).first
            if not locator.count():
                continue
            before = page.url
            locator.click()
        except Exception:
            continue
        if _wait_for_mteam_index(page, timeout=4000) or page.url != before:
            return True
    try:
        page.keyboard.press("Enter")
    except Exception:
        pass
    return _wait_for_mteam_index(page, timeout=15000)


def _mteam_logged_in(browser, base):
    """受保护页 + JWT 双条件判活：只看 localStorage 会把失效 token 当已登录。

    三态实测（qnap 2026-10-30）：无存档时 /index 不跳转且 auth 为空；有效存档 auth
    为 JWT 且停在 /index；篡改 token 时站点把 /index 弹回 /login。
    """
    browser.goto(urljoin(base, "/index"))
    browser.page.wait_for_timeout(2000)
    try:
        signal = browser.evaluate(_MTEAM_AUTH_JS)
    except Exception:
        return False
    if "/login" in str(signal.get("url", "")):
        return False
    return bool(signal.get("authed")) or bool(signal.get("logout"))


def _needs_manual_2fa(message):
    """繁体/简体/英文任一 2FA 文案都算「需人工」——繁体站不该被当成普通失败反复重试。"""
    text = str(message or "")
    return any(hint in text for hint in _MTEAM_2FA_HINTS)


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
    # 保活语义：无签到实现，仅浏览器真实登录（能力声明，registry 不再复合推断）。
    signin_capable = False
    emulate = False
    hook_implemented = False
    record_spec = RecordSpec('//*[@id="batch2-message-pending-calibration"]', {})

    def signin(self, ctx: SignContext) -> SignResult:
        result = ctx.result(status="skipped", message="hook_not_implemented")
        result.metadata["reason"] = "hook_not_implemented"
        return result

    def keepalive_login(self, info):
        """登录 M-Team 并持久化浏览器 storage_state，不执行签到或保活动作。"""
        import time as _time
        from pathlib import Path as _Path
        from ...core.cloak import CloakSession, run_isolated, state_path
        base = info.get("url") or "https://kp.m-team.cc/"
        username, password = info.get("mteam_username", ""), info.get("mteam_password", "")
        if not username or not password:
            return LoginResult(LoginStatus.AUTH_FAILED, "缺少 M-Team 账号或密码")
        state = state_path(self.id)
        cooldown = _Path(str(state) + ".cooldown")
        if cooldown.exists():
            age = _time.time() - cooldown.stat().st_mtime
            if age < 86400:
                hours = int((86400 - age) // 3600)
                return LoginResult(LoginStatus.UNCONFIRMED,
                                   f"M-Team 双重认证 24 小时内已失败一次（{hours} 小时后重试）："
                                   "请核对配置项 mteam_totp 是否为账号「雙重認證碼」密钥，"
                                   "或用浏览器人工登录一次（会话约 40 天有效）")

        flags = {"otp_attempted": False}

        def launch(state_file):
            flags["otp_attempted"] = False
            with CloakSession(state=state_file, url=base) as browser:
                if _mteam_logged_in(browser, base):
                    return True, ""
                browser.goto(urljoin(base, "/login"))
                browser.fill("#username", username)
                browser.fill("#password", password)
                has_totp = browser.evaluate("() => !!document.querySelector('input[autocomplete=one-time-code], input[name*=totp i], input[name*=otp i]')")
                if has_totp and info.get("mteam_totp"):
                    import pyotp
                    browser.fill('input[autocomplete="one-time-code"], input[name*="totp" i], input[name*="otp" i]',
                                 pyotp.TOTP(info["mteam_totp"]).now())
                browser.click('button[type="submit"]')
                if not _wait_for_mteam_index(browser.page, timeout=15000):
                    # 双重认证页：先等输入框渲染出来，避免 DOM 未就绪就判定「无验证码框」。
                    try:
                        browser.page.wait_for_selector(_MTEAM_OTP_INPUT, timeout=15000)
                    except Exception:
                        pass
                    otp = browser.page.locator(_MTEAM_OTP_INPUT).first
                    if otp.count() and info.get("mteam_totp"):
                        import pyotp
                        code = pyotp.TOTP(info["mteam_totp"]).now()
                        try:
                            otp.click()
                        except Exception:
                            pass
                        otp.fill(code)
                        browser.page.wait_for_timeout(600)
                        try:
                            if (otp.input_value() or "").strip() != code:
                                otp.fill(code)
                        except Exception:
                            pass
                        flags["otp_attempted"] = True
                        _submit_mteam_otp(browser.page)
                if "/index" not in browser.page.url:
                    if flags["otp_attempted"]:
                        # 已填 TOTP 仍停留 2FA 页：码被拒或限流——冷却 24h 防反复触发风控。
                        cooldown.parent.mkdir(parents=True, exist_ok=True)
                        cooldown.write_text("otp-rejected", encoding="utf-8")
                        return False, ("双重认证未通过（已自动填入 mteam_totp 并提交，仍停留 2FA 页）："
                                       "请核对配置项 mteam_totp，或用浏览器人工登录一次")
                    return False, "登录未到达 /index（当前 " + browser.page.url + "）"
                browser.save_state(state)
                return True, "M-Team 保活登录成功"

        try:
            if state.exists():
                try:
                    ok, message = run_isolated(lambda: launch(state))
                except Exception:
                    state.unlink(missing_ok=True)
                    ok, message = False, "存档恢复失败"
                if ok:
                    return LoginResult(LoginStatus.LOGIN_OK, "已恢复 M-Team 登录态")
                state.unlink(missing_ok=True)
                if _needs_manual_2fa(message):
                    return LoginResult(LoginStatus.UNCONFIRMED, message)
            ok, message = run_isolated(lambda: launch(None))
            status = LoginStatus.LOGIN_OK if ok else (
                LoginStatus.UNCONFIRMED if _needs_manual_2fa(message) else LoginStatus.AUTH_FAILED)
            return LoginResult(status, message)
        except Exception as exc:
            return LoginResult(LoginStatus.UNCONFIRMED, "M-Team CloakBrowser 登录异常：" + type(exc).__name__ + "：" + str(exc)[:200])
