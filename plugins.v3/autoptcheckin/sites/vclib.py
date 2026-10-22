# DEPRECATED: 原生实现见 sites/native/；此副本仅用于 registry 元数据发现与未迁移域名兜底，签到/登录执行路径已不使用（除 pilot 试点回退）。
# input: VC-Lib 站点 Cookie、UA、代理配置
# output: VC-Lib attendance.php 验证码签到处理器
# pos: AutoPtCheckin 站点适配层，复用 NexusPHP 验证码签到通用基类
from app.plugins.autoptcheckin.helper.attendance_captcha_helper import _AttendanceCaptchaHandler


class VCLib(_AttendanceCaptchaHandler):
    """
    VC-Lib 签到：attendance.php 展示验证码表单，需提交 imagehash + imagestring。
    """
    site_url = "pt.vclib.online"
    _signin_url = "https://pt.vclib.online/attendance.php"
