# DEPRECATED: 原生实现见 sites/native/；此副本仅用于 registry 元数据发现与未迁移域名兜底，签到/登录执行路径已不使用（除 pilot 试点回退）。
# input: PlayLet 站点 Cookie、UA、代理配置
# output: PlayLet attendance.php 验证码签到处理器
# pos: AutoPtCheckin 站点适配层，复用 NexusPHP 验证码签到通用基类
from app.plugins.autoptcheckin.helper.attendance_captcha_helper import _AttendanceCaptchaHandler


class PlayLet(_AttendanceCaptchaHandler):
    """
    PlayLet 签到：attendance.php 展示验证码表单，需提交 imagehash + imagestring。
    """
    site_url = "playlet.cc"
    _signin_url = "https://playlet.cc/attendance.php"
