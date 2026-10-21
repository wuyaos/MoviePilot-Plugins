"""HDSky 复用适配器“已签到”判定；提交后仍必须有本人当日记录。"""
from .nexus import NexusVerifier


class HDSkyVerifier(NexusVerifier):
    button_xpath = '//*[@id="showup" or @id="sign_in" or @id="showupbutton"][self::a or self::button or self::input]'
    signed_texts = ('已签到',)
