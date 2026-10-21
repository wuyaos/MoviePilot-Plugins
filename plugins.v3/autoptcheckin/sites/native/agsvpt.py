"""AGSVPT native attendance form declaration."""
from ...core.nexus import NexusSignin
from ...core.sitemodel import RecordSpec


class Agsvpt(NexusSignin):
    id = "agsvpt"
    name = "AGSVPT"
    url = "https://www.agsvpt.com/"
    attendance_path = "/attendance.php"
    # TODO(batch2): V2 confirms POST/text variants; production message node needs calibration.
    record_spec = RecordSpec(
        '//*[@id="batch2-message-pending-calibration"]',
        {"已经签到": "signed", "已經簽到": "signed", "今天已经签到": "signed",
         "今日已签到": "signed", "請勿重複刷新": "signed", "签到成功": "signed",
         "簽到成功": "signed", "未签到": "unsigned"},
    )
