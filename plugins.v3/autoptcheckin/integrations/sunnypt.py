from ..core.credentials import CredentialSpec
from .login import CredentialLoginProtocol
SUNNYPT_CREDENTIALS = CredentialSpec(kind="api_key", refresh="password", identity_field="uid")
class SunnyPtProtocol(CredentialLoginProtocol):
    credentials = SUNNYPT_CREDENTIALS
    def signin(self, context): raise NotImplementedError("阶段1仅协议骨架")
    # TODO: JWT 30 天近过期主动续期须在协议接入迭代实现。
