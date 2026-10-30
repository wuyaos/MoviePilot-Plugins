"""YemaPT page-action sign-in using the shared CloakBrowser flow."""
from ...core.nexus import PageActionSignin
from ...core.sitemodel import RecordSpec


class YemaPT(PageActionSignin):
    id = "yema"
    name = "YemaPT"
    url = "https://www.yemapt.org/"
    attendance_path = "/#/user/growth"
    cloak_steps = ("altcha", "sign_button")
    emulate = True
    slow = True
    slow_timeout = 90000
    record_spec = RecordSpec(
        '//button[contains(., "签到")]',
        {'已签到': 'signed', '签到成功': 'signed', '签到已得': 'signed', '立即签到': 'unsigned'},
    )
