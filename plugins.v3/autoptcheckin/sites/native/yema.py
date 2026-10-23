"""YemaPT page-action sign-in using the shared CloakBrowser flow."""
from .generic import build_generic_sites
from ...core.sitemodel import RecordSpec

_base = next(site for site in build_generic_sites() if site.id == "yema")


class YemaPT(_base):
    id = "yema"
    name = "YemaPT"
    url = "https://yemapt.org/"
    attendance_path = "/"
    emulate = True
    hook_implemented = True
    record_spec = RecordSpec(
        '//*[@id="batch2-message-pending-calibration"]',
        {"签到成功": "signed", "签到已得": "signed", "今天已经签到过": "signed", "未签到": "unsigned"},
    )
