"""DStudio native attendance declaration; message node awaits calibration."""
from ...core.nexus import NexusSignin
from ...core.sitemodel import RecordSpec


class DStudio(NexusSignin):
    id = "dstudio"
    name = "DStudio"
    url = "https://dstudio.me/"
    attendance_path = "/attendance.php"
    # TODO(batch2): V2 confirms attendance-checkin-form and success/repeat text; calibrate message selector.
    record_spec = RecordSpec(
        '',
        {"今天已经签到过": "signed", "请勿重复刷新": "signed", "已经签到": "signed",
         "今天已签到": "signed", "签到成功": "signed", "签到已得": "signed", "未签到": "unsigned"},
    )
