from ..core.credentials import CredentialSpec
from ..core.models import SignResult, SignStatus
from ..verifiers.fengchao import verify


class Fengchao:
    credential_spec = CredentialSpec(kind="api", cookie_sources=())
    login_capable = False
    base = "https://fengchao.chat"
    prefix = "/api/integrations/moviepilot/v1"

    def __init__(self, client):
        self.client = client

    def request(self, method, path, **kwargs):
        payload = self.client.request(method, self.prefix + path, **kwargs).json()
        if not isinstance(payload, dict) or payload.get("code") not in (None, 0):
            raise ValueError("invalid_api_response")
        data = payload.get("data")
        if not isinstance(data, dict):
            raise ValueError("missing_api_data")
        return data

    def run(self, readonly=False):
        if readonly:
            return verify(self.request("GET", "/status"))
        result = SignResult(SignStatus.UNCONFIRMED, "蜂巢提交结果未确认")
        try:
            result = verify(self.request("POST", "/check-in", json={}), submitted=True)
        except Exception:
            pass  # Never retry a possibly committed submission.
        finally:
            try:
                readback = verify(self.request("GET", "/status"))
                if not result.confirmed:
                    result = readback
            except Exception:
                pass  # A valid check-in API response remains authoritative.
        return result

    def sync(self, cached_identity=None):
        identity = cached_identity or {}
        identity_fresh = False
        try:
            fresh = self.request("GET", "/me")
            if fresh.get("userId") or fresh.get("account") or fresh.get("status", {}).get("account"):
                identity, identity_fresh = fresh, True
        except Exception:
            pass
        status = self.request("GET", "/status")
        identity_status = identity.get("status") or {}
        identity_account = identity_status.get("account") or identity.get("account") or {}
        identity_checkin = identity_status.get("checkIn") or identity.get("checkIn") or {}
        status_account = status.get("account") or {}
        status_checkin = status.get("checkIn") or {}
        account = {**status_account, **identity_account}
        checkin = {**status_checkin, **identity_checkin}
        info = {"uid": str(identity.get("userId") or account.get("uid") or ""),
                "displayName": account.get("displayName") or account.get("username"),
                "points": account.get("points", 0),
                "currentStreak": checkin.get("currentStreak", 0),
                "maxStreak": checkin.get("maxStreak", 0),
                "lastCheckInDate": checkin.get("lastCheckInDate") or "",
                "unreadNotificationCount": account.get("unreadNotificationCount"),
                "checkedInToday": checkin.get("checkedInToday")}
        if not info["uid"].strip():
            raise ValueError("sync_unconfirmed")
        return info, identity if identity_fresh else None


SITE = {"id":"fengchao", "name":"蜂巢", "domain":"fengchao.chat", "source":"插件适配",
        "signin_capable":True, "login_capable":False,
        "fields":[{"key":"fengchao_api_key","label":"Bearer Token","type":"password"}]}
ADAPTER = Fengchao
