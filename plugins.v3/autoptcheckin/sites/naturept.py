# input: NaturePT（自然）站点 Cookie、UA、代理配置
# output: NaturePT attendance.php 验证码签到处理器
# pos: AutoPtCheckin 站点适配层，复用 NexusPHP 验证码签到通用基类
from app.plugins.autoptcheckin.helper.attendance_captcha_helper import _AttendanceCaptchaHandler


class NaturePT(_AttendanceCaptchaHandler):
    """
    NaturePT签到：attendance.php 展示验证码表单，需提交 imagehash + imagestring。
    """
    site_url = "naturept.top"
    _signin_url = "https://naturept.top/attendance.php"
