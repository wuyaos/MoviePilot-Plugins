"""天枢：签到与随机反馈双消息喊话。"""
from ..core.shoutbox import Direction, Observation, ShoutboxProfile
from ..core.site import Site
from ..core.task import Chat, Checkin


class Dubhe(Site):
    site_name = "天枢"
    domain = "dubhe.to"
    domain_aliases = ("dubhe.site",)
    shoutbox = ShoutboxProfile(
        direction=Direction.BEFORE,
        message_terms=lambda message: ["天枢", message.split("，")[-1]],
        confirmation_wait_seconds=2,
    )
    tasks = [
        Checkin(),
        Chat(messages=["天枢娘，求魔力", "天枢娘，求上传"]),
    ]

    def extract_feedback(self, html, username, message):
        observation = super().extract_feedback(html, username, message)
        # 天枢无反馈是大概率现象；发送 HTTP 成功即视为成功，不因快照未捕获用户消息而失败。
        if observation.valid and not observation.sent:
            return Observation(True, True, reason="未解析到反馈")
        return observation
