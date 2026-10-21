"""HDCity declaration; Single GET sign hook; safe message node awaits calibration."""
from ...core.get_signin import GetSignin
from ...core.sitemodel import RecordSpec


class HDCity(GetSignin):
    id = "hdcity"
    name = "城市"
    url = "https://hdcity.city/"
    # /sign triggers signing; both pre-read and readback must stay on the homepage.
    attendance_path = "/"
    hook_implemented = True
    action_path = '/sign'
    # Safe-page message selector remains pending production calibration.
    record_spec = RecordSpec(
        '//*[@id="batch2-message-pending-calibration"]',
        {"本次签到获得魅力": "signed", "Got extra": "signed", "已签到": "signed",
         "Already checked in today": "signed", "未签到": "unsigned"},
    )
