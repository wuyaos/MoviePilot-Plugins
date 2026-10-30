"""DigitalCore: login-only declaration; no independent attendance semantics."""
from ...core.models import SignResult
from ...core.sitemodel import RecordSpec, SignContext, SiteModule


class DigitalCore(SiteModule):
    id = 'digitalcore'
    name = 'DigitalCore'
    url = 'https://digitalcore.club/'
    login_capable = True
    signin_capable = False
    record_spec = RecordSpec('', {})
    # api/v1/status user.id or user.username is login evidence, not attendance.

    def signin(self, ctx: SignContext) -> SignResult:
        result = ctx.result(status="skipped", message="signin_not_applicable")
        result.metadata["reason"] = "signin_not_applicable"
        return result
