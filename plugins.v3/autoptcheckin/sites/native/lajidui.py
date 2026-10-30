"""LaJiDui declaration from the V2 copy; message node awaits batch2 calibration."""
from ...core.nexus import NexusSignin
from ...core.attendance_captcha import solve_attendance_captcha
from ...core.sitemodel import RecordSpec


class LaJiDui(NexusSignin):
    id = "lajidui"
    name = "垃圾堆"
    url = "https://pt.lajidui.top/"
    attendance_path = "/attendance.php"
    # Explicit synthetic placeholder, not a production selector.
    record_spec = RecordSpec(
        '',
        {'今天已经签到过': 'signed', '请勿重复刷新': 'signed', '已经签到': 'signed', '签到成功': 'signed', '签到已得': 'signed', '获得': 'signed', '连续签到': 'signed', '未签到': 'unsigned'},
    )

    def solve_captcha(self, ctx, page, form):
        solved = solve_attendance_captcha(ctx, page, form)
        if solved:
            # V2 submits only these two fields, not unrelated form controls.
            form.data[:] = [(key, value) for key, value in form.data
                            if key in {"imagehash", "imagestring"}]
        return solved
