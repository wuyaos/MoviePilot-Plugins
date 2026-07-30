"""RailgunPT 单站适配原型。

标准站点文件只声明：身份、任务组合、喊话 Profile；不定义 Tasks 类、不写配置/UI/历史。
"""
from ..core.shoutbox import Direction, ShoutboxProfile
from ..core.site import Site
from ..core.task import Chat, Checkin


class RailgunPT(Site):
    site_name = "RailgunPT"
    domain = "bilibili.download"
    match_keywords = ("railgun", "bilibili.download")

    shoutbox = ShoutboxProfile(
        path="/shoutbox.php?type=shoutbox",
        row_xpath="//td[contains(@class, 'shoutrow')]",
        direction=Direction.BEFORE,
        message_terms=lambda message: ["炮姐", message.split("，")[-1]],
        confirmation_wait_seconds=2,
    )

    tasks = [
        Checkin(),
        Chat(messages=["炮姐，求魔力"]),
    ]
