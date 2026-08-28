"""LuckPT：签到、许愿池外部反馈喊话与勋章中心奖励领取。"""
from ..actions.luckpt import LuckptMedalRewardAction
from ..core.shoutbox import Direction, ShoutboxProfile
from ..core.site import Site
from ..core.task import ActionTask, Chat, Checkin, TaskType


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
        ActionTask(
            name="claim_medal_reward",
            action=LuckptMedalRewardAction(),
            label="勋章奖励领取",
            task_type=TaskType.MEDAL,
        ),
    ]
