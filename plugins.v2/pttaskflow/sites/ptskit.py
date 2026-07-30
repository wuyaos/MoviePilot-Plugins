"""PTSKit：签到、申领和顶部魔力反馈喊话。"""
from ..core.shoutbox import Direction, ShoutboxProfile
from ..core.site import Site
from ..core.task import Chat, Checkin, Claim


class PTSKit(Site):
    site_name = "Ptskit"
    domain = "ptskit.org"
    @classmethod
    def matches(cls, site_info):
        """PTS 仅按精确域名或明确名称匹配，避免把 ptsbao 误识别为 PTS。"""
        domain = (site_info.get("domain") or "").lower().strip()
        name = (site_info.get("name") or "").lower().strip()
        return domain == cls.domain or "ptskit" in domain or name in {"pts", "ptskit"}
    shoutbox = ShoutboxProfile(
        direction=Direction.EXTERNAL,
        external_feedback_xpath="//div[contains(@class, 'magic-reward-top') and contains(@class, 'system-msg')]",
        message_terms=lambda message: [message],
        confirmation_wait_seconds=2,
    )
    tasks = [
        Checkin(),
        Claim(options=[
            {"id": "15", "label": "永久邀请奖励"},
            {"id": "14", "label": "魔力值奖励3"},
            {"id": "13", "label": "魔力值奖励1"},
            {"id": "12", "label": "魔力值任务2"},
        ]),
        Chat(messages=["求魔力"]),
    ]
