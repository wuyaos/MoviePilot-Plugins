"""海棠登录页表单定位；未知结构不推定结果。"""
from .nexus import NexusVerifier


class HaitangVerifier(NexusVerifier):
    button_xpath = '//form[contains(@action,"attendance.php")]//*[self::input or self::button][@type="submit"] | //button[@id="sign_in"]'
    signed_texts = ('今日已签到', '今天已签到', '今天已经签到')
