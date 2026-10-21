from ..core.credentials import CredentialSpec
from .login import CredentialLoginProtocol
ROUSI_CREDENTIALS = CredentialSpec(kind="cookie", refresh="password", identity_field="uid")
class RousiProtocol(CredentialLoginProtocol):
    credentials = ROUSI_CREDENTIALS
    def signin(self, context): raise NotImplementedError("阶段1仅协议骨架")
