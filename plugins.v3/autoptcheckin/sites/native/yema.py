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
        '//button[contains(text(), "签到")] | //*[contains(text(), "签到成功")]'
        ' | //*[contains(text(), "签到已得")] | //*[contains(text(), "已签到")]',
        {'已签到': 'signed', '签到成功': 'signed', '签到已得': 'signed', '立即签到': 'unsigned'},
    )
