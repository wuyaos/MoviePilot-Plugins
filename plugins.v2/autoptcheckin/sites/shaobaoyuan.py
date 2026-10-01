# input: 烧包乐园站点 Cookie、UA、代理配置
# output: 烧包乐园 attendance.php 验证码签到处理器
# pos: AutoPtCheckin 站点适配层，复用 NexusPHP 验证码签到通用基类
from app.plugins.autoptcheckin.helper.attendance_captcha_helper import _AttendanceCaptchaHandler


class ShaoBao(_AttendanceCaptchaHandler):
    """
    烧包乐园签到：attendance.php 展示验证码表单，需提交 imagehash + imagestring。
    """
    site_url = "ptsbao.club"
    _signin_url = "https://ptsbao.club/attendance.php"
