"""LuckPT：签到与许愿池外部反馈喊话。"""
from ..core.shoutbox import Direction, ShoutboxProfile
from ..core.site import Site
from ..core.task import Chat, Checkin


class LuckPT(Site):
    site_name = "LuckPT"
    domain = "luckpt.de"
    match_keywords = ("luckpt", "幸运")
    shoutbox = ShoutboxProfile(
        direction=Direction.EXTERNAL,
        row_xpath="//div[contains(@class, 'chat-message-container')]",
        external_feedback_xpath="//div[contains(@class, 'wish-bubble-system')]//div[contains(@class, 'wish-content')]",
        message_terms=lambda message: [message],
        confirmation_wait_seconds=2,
    )
    tasks = [
        Checkin(),
        Chat(messages=["幸运池祈愿"]),
    ]
