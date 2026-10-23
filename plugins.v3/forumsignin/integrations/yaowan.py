import re
from dataclasses import replace
from ..core.credentials import CredentialSpec
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
        return self.client.request("GET", "/", headers=headers)

    def _refresh_remember(self):
        credential = self._credential()
        raw = credential.value if credential else ""
        match = re.search(r"(?:^|;\s*)flarum_remember=([^;]+)", raw)
        if not match:
            return None
        response = self._homepage("flarum_remember=" + match.group(1))
        session = response.cookies.get("flarum_session")
        csrf = re.search(r'"csrfToken"\s*:\s*"([^"]+)"', response.text or "")
        if session and csrf and self.verifier.identity(response.text or ""):
            self._set_cookie(f"flarum_remember={match.group(1)}; flarum_session={session}")
            return response
        return None

    def _login(self):
        credential = self._credential()
        if credential is None or not credential.username or not credential.password:
            return None
        initial = self._homepage()
        csrf = re.search(r'"csrfToken"\s*:\s*"([^"]+)"', initial.text or "")
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

    def fetch_page(self):
        credential = self._credential()
        response = self._homepage(credential.value if credential else "")
        if self.verifier.identity(response.text or ""):
            return response.text
        refreshed = self._refresh_remember()
        if refreshed and self.verifier.identity(refreshed.text or ""):
            return refreshed.text
        logged_in = self._login()
        return logged_in.text if logged_in else response.text

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
