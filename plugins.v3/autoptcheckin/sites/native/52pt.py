"""52PT slider check-in uses the shared CloakBrowser page-action flow."""
from .generic import build_generic_sites
from ...core.sitemodel import RecordSpec

_base = next(site for site in build_generic_sites() if site.id == "52pt")


class Pt52(_base):
    name = "52PT"
    url = "https://52pt.site/"
    attendance_path = "/"
    hook_implemented = True
    record_spec = RecordSpec('//*[@id="batch2-message-pending-calibration"]',
                             {'今天已经签过到了': 'signed', '未签到': 'unsigned'})
