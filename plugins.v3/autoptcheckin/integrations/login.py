"""集成站点的认证检查注入点；未接入检查器时不能声称已登录。"""
from ..core.models import Evidence, LoginResult, LoginStatus


class CredentialLoginProtocol:
    def __init__(self, credential_check=None):
        self.credential_check = credential_check

    def login(self, context=None, uid="") -> LoginResult:
        if self.credential_check is None:
            return LoginResult(LoginStatus.UNCONFIRMED, "login_check_not_available")
        try:
            check = self.credential_check(context)
        except Exception:
            return LoginResult(LoginStatus.UNCONFIRMED, "认证检查不可达")
        evidence = Evidence(uid=check.uid or None, source="api")
        if uid and check.uid and uid != check.uid:
            return LoginResult(LoginStatus.UNCONFIRMED, "认证身份冲突", evidence=evidence)
        status = (LoginStatus.LOGIN_OK if check.status == "valid" else
                  LoginStatus.AUTH_FAILED if check.status == "invalid" else LoginStatus.UNCONFIRMED)
        return LoginResult(status, "认证检查通过" if status == LoginStatus.LOGIN_OK else "认证未通过确认", evidence=evidence)
