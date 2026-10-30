"""Muxuege declaration from the V2 copy; message node awaits batch2 calibration."""
from ...core.nexus import NexusSignin
from ...core.sitemodel import RecordSpec


class Muxuege(NexusSignin):
    id = "muxuege"
    name = "慕雪阁"
    url = "https://pt.muxuege.org/"
    attendance_path = "/attendance.php"
    # Explicit synthetic placeholder, not a production selector.
    record_spec = RecordSpec(
        '',
        {'今天已经签到过': 'signed', '请勿重复刷新': 'signed', '已经签到': 'signed', '签到成功': 'signed', '签到已得': 'signed', '获得': 'signed', '连续签到': 'signed', '今天已签到': 'signed', '本次签到获得': 'signed', '未签到': 'unsigned'},
    )
