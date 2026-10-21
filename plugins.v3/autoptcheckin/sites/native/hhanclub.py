"""Hhanclub declaration; Single GET with Referer; safe message node awaits calibration."""
from ...core.get_signin import GetSignin
from ...core.sitemodel import RecordSpec


class Hhanclub(GetSignin):
    id = "hhanclub"
    name = "憨憨"
    url = "https://hhanclub.net/"
    # attendance.php GET signs immediately; never use it for pre-read/readback.
    attendance_path = "/"
    hook_implemented = True
    action_path = '/attendance.php'
    action_referer = True
    # Safe-page message node remains pending production calibration.
    record_spec = RecordSpec(
        '//*[@id="batch2-message-pending-calibration"]',
        {"今天已经签到过": "signed", "今天已签到": "signed", "已经签到": "signed",
         "请勿重复刷新": "signed", "签到成功": "signed", "本次签到获得": "signed",
         "已连续签到": "signed", "未签到": "unsigned"},
    )
