# DEPRECATED: 原生实现见 sites/native/；此副本仅用于 registry 元数据发现与未迁移域名兜底，签到/登录执行路径已不使用（除 pilot 试点回退）。
# input: AGSVPT 站点 Cookie、UA、代理配置
# output: AGSVPT attendance.php POST 签到处理器
# pos: AutoPtCheckin 站点适配层，复用无验证码 POST 签到通用基类
from app.plugins.autoptcheckin.helper.attendance_post_helper import _AttendancePostHandler


class Agsvpt(_AttendancePostHandler):
    """AGSVPT 签到：attendance.php 表单无验证码，POST 即签到。"""

    site_url = "agsvpt.com"
    _signin_url = "https://www.agsvpt.com/attendance.php"
    _success_texts = ["签到成功", "簽到成功"]
    _repeat_texts = ["已经签到", "已經簽到", "今天已经签到", "今日已签到", "請勿重複刷新"]
