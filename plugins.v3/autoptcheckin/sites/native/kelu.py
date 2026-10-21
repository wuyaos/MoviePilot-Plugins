"""Kelu declaration from the V2 copy; message node awaits batch2 calibration."""
from ...core.attendance_captcha import solve_attendance_captcha
from ...core.nexus import NexusSignin
from ...core.sitemodel import RecordSpec


class Kelu(NexusSignin):
    id = "kelu"
    name = "可撸"
    url = "https://our.kelu.one/"
    attendance_path = "/attendance.php"
    hook_implemented = True
    # Explicit synthetic placeholder, not a production selector.
    # Production message selector remains pending batch2 calibration (V2 has no scoped node).
    record_spec = RecordSpec(
        '//*[@id="batch2-message-pending-calibration"]',
        {'今天已经签到过': 'signed', '今天已經簽到過': 'signed', '请勿重复刷新': 'signed', '請勿重複刷新': 'signed', '已经签到': 'signed', '已經簽到': 'signed', '今天已经签到': 'signed', '今天已經簽到': 'signed', '今天已簽到': 'signed', '今日已簽到': 'signed', '今日已签到': 'signed', '签到成功': 'signed', '簽到成功': 'signed', '签到已得': 'signed', '簽到已得': 'signed', '未签到': 'unsigned'},
    )

    def solve_captcha(self, ctx, page, form):
        return solve_attendance_captcha(ctx, page, form)
