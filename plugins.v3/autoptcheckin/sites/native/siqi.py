"""思齐: V2-derived declaration; production verification remains gated."""
from ...core.nexus import NexusSignin
from ...core.attendance_captcha import solve_attendance_captcha
from ...core.sitemodel import RecordSpec


class SiQi(NexusSignin):
    verified = True
    id = 'siqi'
    name = '思齐'
    url = 'https://si-qi.xyz/'
    attendance_path = '/attendance.php'
    hook_implemented = True
    record_spec = RecordSpec('//*[@id="batch2-message-pending-calibration"]', {'您今天已经签到过了': 'signed', '未签到': 'unsigned'})
    signed_marker = '//*[contains(concat(" ", normalize-space(@class), " "), " attend-success-effect ")]'
    # Full V2 reward expression retained for production message calibration.
    reward_pattern = r'这是您的第.*?次签到，已连续签到.*?天'

    def solve_captcha(self, ctx, page, form):
        solved = solve_attendance_captcha(ctx, page, form, max_len=None)
        if solved:
            # V2 submits only these two fields, not unrelated form controls.
            form.data[:] = [(key, value) for key, value in form.data
                            if key in {"imagehash", "imagestring"}]
        return solved
