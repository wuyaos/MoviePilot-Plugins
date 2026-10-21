"""DarkLand: login-only declaration; no independent attendance semantics."""
from ...core.models import SignResult
from ...core.sitemodel import RecordSpec, SignContext, SiteModule


class DarkLand(SiteModule):
    id = 'darkland'
    name = 'DarkLand'
    url = 'https://darkland.top/'
    login_capable = True
    hook_implemented = True
    signin_capable = False
    record_spec = RecordSpec('//*[@id="batch2-message-pending-calibration"]', {})
    # Browser fingerprint homepage/login markers; no attendance action.

    def signin(self, ctx: SignContext) -> SignResult:
        result = ctx.result(status="skipped", message="signin_not_applicable")
        result.metadata["reason"] = "signin_not_applicable"
        return result
