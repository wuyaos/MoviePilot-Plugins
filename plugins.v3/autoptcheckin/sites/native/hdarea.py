"""HDArea native declaration; direct POST hook; production message node awaits calibration."""
from ...core.nexus import NexusSignin, SigninForm
from ...core.sitemodel import RecordSpec


class HDArea(NexusSignin):
    id = "hdarea"
    name = "好大"
    url = "https://hdarea.club/"
    attendance_path = "/"
    hook_implemented = True
    record_spec = RecordSpec(
        '//*[@id="batch2-message-pending-calibration"]',
        {"此次签到您获得": "signed", "请不要重复签到哦": "signed", "未签到": "unsigned"},
    )

    def discover_form(self, ctx, page):
        return SigninForm(self.url + 'sign_in.php', [('action', 'sign_in')])
