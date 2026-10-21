"""NexusHD declaration; direct POST protocol; production verification remains gated."""
from ...core.nexus import NexusSignin, SigninForm
from ...core.sitemodel import RecordSpec


class NexusHD(NexusSignin):
    id = "nexushd"
    name = "NexusHD"
    url = "https://v6.nexushd.org/"
    # V2 directly POSTs signin.php with action=post/content=''; no GET form is proven.
    attendance_path = "/"
    hook_implemented = True
    # Explicit synthetic placeholder, not a production message selector.
    record_spec = RecordSpec(
        '//*[@id="batch2-message-pending-calibration"]',
        {"本次签到获得": "signed", "你今天已经签到过了": "signed", "未签到": "unsigned"},
    )

    def discover_form(self, ctx, page):
        return SigninForm(self.url + 'signin.php', [('action', 'post'), ('content', '')])
