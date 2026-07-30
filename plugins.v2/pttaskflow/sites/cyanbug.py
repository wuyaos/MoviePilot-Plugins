"""大青虫：签到与双消息喊话。"""
from ..core.shoutbox import Direction, ShoutboxProfile
from ..core.site import Site
from ..core.task import Chat, Checkin


class Cyanbug(Site):
    site_name = "大青虫"
    domain = "cyanbug.net"
    message_interval = 60
    shoutbox = ShoutboxProfile(
        direction=Direction.BEFORE,
        message_terms=lambda message: ["青虫娘", message.split("，")[-1]],
        confirmation_wait_seconds=2,
    )
    tasks = [
        Checkin(),
        Chat(messages=["青虫娘，求上传", "青虫娘，求魔力"],
             negatives=("没有理", "明天再来", "不要继续刷屏")),
    ]
