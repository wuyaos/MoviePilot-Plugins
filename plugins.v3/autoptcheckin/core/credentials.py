"""凭证只在内存中流转；持久化仅保存明确失效候选的指纹。"""
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Callable, Literal

@dataclass(frozen=True)
class CredentialSpec:
    kind: Literal["cookie", "api"] = "cookie"
    cookie_sources: tuple[str, ...] = ("cookiecloud", "managed_site", "local_cookie")
    refresh: Literal["password"] | None = None
    identity_field: str = "uid"

@dataclass(frozen=True)
class Credential:
    source: str
    value: str = field(repr=False)
    uid: str = ""

    @property
    def fingerprint(self) -> str:
        return sha256(self.value.encode()).hexdigest()

@dataclass(frozen=True)
class CredentialCheck:
    status: Literal["valid", "invalid", "maintenance", "rate_limited", "timeout", "network_error"]
    uid: str = ""

@dataclass
class CredentialResolution:
    credential: Credential | None
    status: str
    reason: str = ""

class CredentialResolver:
    def __init__(self, invalid_fingerprints: set[str] | None = None):
        self.invalid_fingerprints = invalid_fingerprints if invalid_fingerprints is not None else set()

    def select_cookie(self, candidates: dict[str, Credential], bound_uid: str = '') -> CredentialResolution:
        """试点先选择 Cookie；身份校验在 runner 的新页面前读中执行。"""
        for source in CredentialSpec().cookie_sources:
            candidate = candidates.get(source)
            if candidate is None or not candidate.value:
                continue
            if bound_uid and candidate.uid and candidate.uid != bound_uid:
                return CredentialResolution(None, 'identity_conflict', '凭证账号冲突')
            if candidate.fingerprint not in self.invalid_fingerprints:
                return CredentialResolution(candidate, 'valid')
        return CredentialResolution(None, 'auth_failed', '站点管理中缺少可用 Cookie')

    def resolve(self, spec: CredentialSpec, candidates: dict[str, Credential], bound_uid: str,
                validate: Callable[[Credential], CredentialCheck],
                refresh: Callable[[], Credential] | None = None) -> CredentialResolution:
        explicitly_invalid = False
        for source in spec.cookie_sources:
            candidate = candidates.get(source)
            if candidate is None or not candidate.value:
                continue
            if candidate.uid and bound_uid and candidate.uid != bound_uid:
                return CredentialResolution(None, "identity_conflict", "凭证账号与绑定账号不符")
            if candidate.fingerprint in self.invalid_fingerprints:
                explicitly_invalid = True
                continue
            try:
                check = validate(candidate)
            except Exception:
                return CredentialResolution(None, "network_error", "凭证校验不可达，未触发续期")
            if check.uid and bound_uid and check.uid != bound_uid:
                return CredentialResolution(None, "identity_conflict", "页面账号与绑定账号不符")
            if check.status == "valid":
                if not check.uid or not bound_uid:
                    return CredentialResolution(None, "unconfirmed", "缺少绑定或回读身份")
                return CredentialResolution(Credential(source, candidate.value, check.uid), "valid")
            if check.status != "invalid":
                return CredentialResolution(None, check.status, "未明确失效，不续期或切换凭证")
            explicitly_invalid = True
            self.invalid_fingerprints.add(candidate.fingerprint)
        # 无候选不等同于明确认证失效；阶段1不做静默首次登录。
        if explicitly_invalid and spec.refresh == "password" and refresh:
            try:
                candidate = refresh()
                check = validate(candidate)
            except Exception:
                return CredentialResolution(None, "network_error", "续期校验不可达")
            if check.uid and bound_uid and check.uid != bound_uid:
                return CredentialResolution(None, "identity_conflict", "续期账号冲突，未保存")
            if check.status == "valid" and check.uid and bound_uid:
                return CredentialResolution(Credential(candidate.source, candidate.value, check.uid), "valid")
            return CredentialResolution(None, "unconfirmed", "续期未通过身份校验")
        return CredentialResolution(None, "auth_failed", "没有已验证凭证")
