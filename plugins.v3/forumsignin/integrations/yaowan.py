import json
import re
from dataclasses import replace
from datetime import datetime
from ..core.credentials import CredentialSpec
from ..core.models import SignResult, SignStatus
from ..core.runner import sanitize_sample
from ..core.verification import normalize_evidence
from ..http_client import response_text
from ..verifiers.yaowan import YaowanVerifier


class Yaowan:
    credential_spec = CredentialSpec(refresh="flarum_remember")
    login_capable = True
    base = "https://invites.fun"
    page_path = "/"
    verifier = YaowanVerifier()

    def __init__(self, client):
        self.client = client

    def _credential(self):
        return getattr(self.client, "credential", None)

    def _set_cookie(self, cookie):
        credential = self._credential()
        if credential is not None:
            self.client.credential = replace(credential, value=cookie)

    def _homepage(self, cookie=""):
        headers = {"Accept":"text/html,application/xhtml+xml", "Upgrade-Insecure-Requests":"1"}
        if cookie:
            headers["Cookie"] = cookie
        response = self.client.request("GET", "/", headers=headers)
        return response

    def _text(self, response):
        return self.client.text(response) if hasattr(self.client, "text") else response_text(response)

    def _refresh_remember(self):
        credential = self._credential()
        raw = credential.value if credential else ""
        match = re.search(r"(?:^|;\s*)flarum_remember=([^;]+)", raw)
        if not match:
            return None
        response = self._homepage("flarum_remember=" + match.group(1))
        session = response.cookies.get("flarum_session")
        csrf = re.search(r'"csrfToken"\s*:\s*"([^"]+)"', self._text(response) or "")
        if session and csrf and self.verifier.identity(self._text(response) or ""):
            self._set_cookie(f"flarum_remember={match.group(1)}; flarum_session={session}")
            return response
        return None

    def _login(self):
        credential = self._credential()
        if credential is None or not credential.username or not credential.password:
            return None
        initial = self._homepage()
        csrf = re.search(r'"csrfToken"\s*:\s*"([^"]+)"', self._text(initial) or "")
        session = initial.cookies.get("flarum_session")
        if not csrf or not session:
            return None
        self._set_cookie(f"flarum_session={session}")
        response = self.client.request("POST", "/login", headers={
            "x-csrf-token":csrf.group(1), "Origin":self.base, "Referer":self.base + "/",
            "Content-Type":"application/json"}, json={"identification":credential.username,
            "password":credential.password,"remember":True})
        remember = response.cookies.get("flarum_remember")
        new_session = response.cookies.get("flarum_session")
        if not remember or not new_session:
            return None
        cookie = f"flarum_remember={remember}; flarum_session={new_session}"
        self._set_cookie(cookie)
        return self._homepage(cookie)

    def _attach_api_state(self, response):
        page = self._text(response) or ""
        uid = self.verifier.identity(page)
        if not uid:
            return page
        try:
            state_response = self.client.request("GET", f"/api/users/{uid}")
            payload = state_response.json()
            data = payload.get("data") if isinstance(payload, dict) else None
            attrs = data.get("attributes") if isinstance(data, dict) else None
            if str(data.get("id")) != uid or not isinstance(attrs, dict):
                return page
            state = {"user_id": uid, "canCheckin": attrs.get("canCheckin", attrs.get("canCheckIn")),
                     "lastCheckinTime": attrs.get("lastCheckinTime") or "",
                     "totalContinuousCheckIn": attrs.get("totalContinuousCheckIn")}
            return page + "\n<!-- forum-signin-api-state " + json.dumps(state, ensure_ascii=False) + " -->"
        except Exception:
            return page

    def fetch_page(self, allow_login=True):
        credential = self._credential()
        response = self._homepage(credential.value if credential else "")
        if self.verifier.identity(self._text(response) or ""):
            return self._attach_api_state(response)
        refreshed = self._refresh_remember()
        if refreshed and self.verifier.identity(self._text(refreshed) or ""):
            return self._attach_api_state(refreshed)
        if not allow_login:  # 只读核验不 POST /login（AGENTS.md 约束）
            return self._text(response)
        logged_in = self._login()
        return self._attach_api_state(logged_in) if logged_in else self._text(response)

    def submit(self, page):
        token = self.verifier.token(page)
        return self.client.request("POST", "/api/checkin", headers={
            "x-csrf-token": token, "Origin": self.base, "Referer": self.base + "/"})

    def run(self, readonly=False, bound_uid="", bind=None, business_date=None, sample_sink=None):
        """API 驱动签到：判定只信 /api/users/{uid} 状态；单次提交后无条件复核。"""
        day = business_date or datetime.now().astimezone().date().isoformat()

        def save_sample(page, result):
            if sample_sink and result.status in (SignStatus.UNCONFIRMED, SignStatus.AUTH_FAILED):
                try:
                    sample_sink(sanitize_sample(page), result.status)
                except Exception:
                    pass
        try:
            page = self.fetch_page(allow_login=not readonly)
        except PermissionError:
            return SignResult(SignStatus.AUTH_FAILED, "凭证已失效或无权限，未提交")
        except (ConnectionError, TimeoutError, OSError):
            return SignResult(SignStatus.NETWORK_ERROR, "药丸页面网络连接失败")
        except Exception:
            return SignResult(SignStatus.UNCONFIRMED, "药丸页面获取失败")
        uid = self.verifier.identity(page)
        if not uid:
            result = SignResult(SignStatus.AUTH_FAILED, "药丸身份未确认，凭证可能已失效")
            save_sample(page, result)
            return result
        if bound_uid and uid != bound_uid:
            result = SignResult(SignStatus.UNCONFIRMED, "药丸身份与绑定不一致")
            save_sample(page, result)
            return result
        if bind and not bound_uid:
            bind(uid)
        evidence = self.verifier.judge(page, uid, day)
        result = normalize_evidence(evidence, uid, day, before_submit=True)
        if readonly or result.confirmed:
            return result
        if result.status != SignStatus.FAILED:
            result = SignResult(SignStatus.UNCONFIRMED, "未确认本人当日未签到，不提交", evidence=evidence)
            save_sample(page, result)
            return result
        try:
            self.submit(page)
        except Exception:
            pass  # Never retry a possibly committed submission.
        finally:
            try:
                after = self.fetch_page()
                evidence = self.verifier.judge(after, uid, day)
                result = normalize_evidence(evidence, uid, day)
                save_sample(after, result)
            except PermissionError:
                result = SignResult(SignStatus.AUTH_FAILED, "凭证已失效或无权限，需只读复核")
            except (ConnectionError, TimeoutError, OSError):
                result = SignResult(SignStatus.NETWORK_ERROR, "复核时网络连接失败，需只读复核")
            except Exception:
                result = SignResult(SignStatus.UNCONFIRMED, "复核页面不可达或解析异常，需只读复核")
        return result


SITE = {"id":"yaowan", "name":"药丸", "domain":"invites.fun", "source":"插件适配",
        "signin_capable":True, "login_capable":True,
        "fields":[{"key":"yaowan_cookie","label":"Cookie","type":"password"},
                  {"key":"yaowan_username","label":"账号","type":"text"},
                  {"key":"yaowan_password","label":"密码","type":"password"}]}
ADAPTER = Yaowan
