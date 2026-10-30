"""lp-bits declaration: NexusPHP standard attendance, migrated from the qnap custom entry."""
from ...core.nexus import NexusSignin
from ...core.sitemodel import RecordSpec


class LpBits(NexusSignin):
    id = "lpbits"
    name = "LP-Bits"
    url = "https://lp-bits.com/"
    attendance_path = "/attendance.php"
    signed_marker = '//a[@href="attendance.php" and contains(.,"Attend got:")]'
    record_spec = RecordSpec(
        '',
        {'今天已经签到过': 'signed', '请勿重复刷新': 'signed', '已经签到': 'signed', '签到成功': 'signed', '签到已得': 'signed', '获得': 'signed', '连续签到': 'signed', '今天已签到': 'signed', '未签到': 'unsigned'},
    )
