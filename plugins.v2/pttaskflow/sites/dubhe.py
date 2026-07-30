"""天枢：签到与随机反馈双消息喊话。"""
from ..core.shoutbox import Direction, ShoutboxProfile
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
