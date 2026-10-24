import json
import re
from dataclasses import replace
from ..core.credentials import CredentialSpec
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
            state = {"user_id": uid, "canCheckIn": attrs.get("canCheckIn"),
                     "lastCheckinTime": attrs.get("lastCheckinTime") or "",
                     "totalContinuousCheckIn": attrs.get("totalContinuousCheckIn")}
            return page + "\n<!-- forum-signin-api-state " + json.dumps(state, ensure_ascii=False) + " -->"
        except Exception:
            return page

    def fetch_page(self):
        credential = self._credential()
        response = self._homepage(credential.value if credential else "")
        if self.verifier.identity(self._text(response) or ""):
            return self._attach_api_state(response)
        refreshed = self._refresh_remember()
        if refreshed and self.verifier.identity(refreshed.text or ""):
            return self._attach_api_state(refreshed)
        logged_in = self._login()
        return self._attach_api_state(logged_in) if logged_in else self._text(response)

    def submit(self, page):
        token = self.verifier.token(page)
        return self.client.request("POST", "/api/checkin", headers={
            "x-csrf-token": token, "Origin": self.base, "Referer": self.base + "/"})


SITE = {"id":"yaowan", "name":"药丸", "domain":"invites.fun", "source":"插件适配",
        "signin_capable":True, "login_capable":True,
        "fields":[{"key":"yaowan_cookie","label":"Cookie","type":"password"},
                  {"key":"yaowan_username","label":"账号","type":"text"},
                  {"key":"yaowan_password","label":"密码","type":"password"}]}
ADAPTER = Yaowan
