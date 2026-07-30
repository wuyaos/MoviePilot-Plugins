"""Moment：签到与女友反馈双向关联喊话。"""
from ..core.shoutbox import Direction, ShoutboxProfile
from ..core.site import Site
from ..core.task import Chat, Checkin


class Moment(Site):
    site_name = "Moment"
    domain = "m-team.io"
    match_keywords = ("moment",)
    domain_aliases = ("momentpt.top",)
    message_interval = 120
    shoutbox = ShoutboxProfile(
        path="/shoutbox.php",
        direction=Direction.BOTH,
        is_feedback=lambda row, username: f"【{username}的女友】" in row.text,
        message_terms=lambda message: [message],
        confirmation_wait_seconds=2,
    )
    tasks = [
        Checkin(),
        Chat(messages=["茄子", "保一条"]),
    ]
