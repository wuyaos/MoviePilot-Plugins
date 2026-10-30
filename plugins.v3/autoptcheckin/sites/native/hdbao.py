"""HDBao native POST declaration; message node awaits calibration."""
from ...core.nexus import NexusSignin
from ...core.sitemodel import RecordSpec


class HDBao(NexusSignin):
    id = "hdbao"
    name = "HDBao"
    url = "https://hdbao.cc/"
    attendance_path = "/attendance.php"
    # TODO(batch2): V2 confirms POST and text variants, not a message-node selector.
    record_spec = RecordSpec(
        '',
        {"今天已经签到过": "signed", "请勿重复刷新": "signed", "已经签到": "signed",
         "签到成功": "signed", "签到已得": "signed", "获得": "signed",
         "连续签到": "signed", "未签到": "unsigned"},
    )
