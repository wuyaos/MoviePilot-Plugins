"""M-Team API keepalive declaration, not a Nexus attendance flow."""
from ...core.credentials import CredentialSpec
from ...core.models import SignResult
from ...core.sitemodel import RecordSpec, SignContext, SiteModule


class MTorrent(SiteModule):
    id = "mteam"
    name = "M-Team"
    # V2 derives api.<domain> from the managed URL; preserve its multi-domain match.
    url = ""
    credential = CredentialSpec(kind="api", cookie_sources=())
    hook_implemented = False
    # No HTML message or sign-state semantics are established by updateLastBrowse.
    record_spec = RecordSpec('//*[@id="batch2-message-pending-calibration"]', {})

    def signin(self, ctx: SignContext) -> SignResult:
        result = ctx.result(status="skipped", message="hook_not_implemented")
        result.metadata["reason"] = "hook_not_implemented"
        return result
