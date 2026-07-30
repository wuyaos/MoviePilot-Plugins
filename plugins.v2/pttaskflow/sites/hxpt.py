"""好学：签到、AJAX 喊话与任务申领。"""
from ..core.shoutbox import Direction, ShoutboxProfile
from ..core.site import Site
from ..core.task import Chat, Checkin, Claim


class HxPT(Site):
    site_name = "好学"
    domain = "haoxue.net"
    domain_aliases = ("hxpt.org",)
    shoutbox = ShoutboxProfile(
        path="/shoutbox.php?ajax_chat=1&type=",
        direction=Direction.BEFORE,
        is_feedback=lambda row, _username: "系统提示：" in row.text,
        message_terms=lambda _message: ["好好学习", "天天向上"],
        retry_on_unconfirmed=False,
        confirmation_wait_seconds=3,
    )
    tasks = [
        Checkin(),
        Chat(messages=["好好学习天天向上"],
             negatives=("丢失", "消费", "疲劳", "明天再", "继续吧")),
        Claim(options=[
            {"id": "2", "label": "精进研习社"},
            {"id": "4", "label": "测（管理组任务）"},
        ]),
    ]

    def send_message(self, message):
        # 好学的确认入口与普通 NexusPHP 不同；发送仍使用兼容的 shoutbox endpoint。
        return super().send_message(message)
