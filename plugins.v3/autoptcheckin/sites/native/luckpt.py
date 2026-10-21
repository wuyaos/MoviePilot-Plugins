"""LuckPT declaration from the V2 copy; message node awaits batch2 calibration."""
from ...core.nexus import NexusSignin
from ...core.sitemodel import RecordSpec


class LuckPT(NexusSignin):
    id = "luckpt"
    name = "LuckPT"
    url = "https://pt.luckpt.de/"
    attendance_path = "/attendance.php"
    # Explicit synthetic placeholder, not a production selector.
    record_spec = RecordSpec(
        '//*[@id="batch2-message-pending-calibration"]',
        {'今天已经签到过': 'signed', '请勿重复刷新': 'signed', '已经签到': 'signed', '签到成功': 'signed', '签到已得': 'signed', '获得': 'signed', '连续签到': 'signed', '今天已签到': 'signed', '未签到': 'unsigned'},
    )
