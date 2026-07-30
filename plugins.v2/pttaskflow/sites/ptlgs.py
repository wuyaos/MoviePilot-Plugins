"""PTLGS：签到与黑丝娘反馈喊话。"""
from ..core.shoutbox import Direction, ShoutboxProfile
from ..core.site import Site
from ..core.task import Chat, Checkin


class PTLGS(Site):
    site_name = "PTLGS"
    domain = "ptlgs.org"
    shoutbox = ShoutboxProfile(
        direction=Direction.BEFORE,
        is_feedback=lambda row, username: (
            "黑丝娘" in row.text and f"@{username}" in row.text
            and any(term in row.text for term in ("奖赏", "获得", "损失", "明天再来"))
        ),
        message_terms=lambda message: ["黑丝娘", message.split("，")[-1]],
        confirmation_wait_seconds=2,
    )
    tasks = [
        Checkin(),
        Chat(messages=["黑丝娘，求工分", "黑丝娘，求上传"], negatives=("损失",)),
    ]
