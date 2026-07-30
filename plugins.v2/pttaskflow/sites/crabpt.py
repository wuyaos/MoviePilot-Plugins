"""蟹黄堡标准签到与任务申领。"""
from ..core.site import Site
from ..core.task import Checkin, Claim


class CrabPT(Site):
    site_name = "蟹黄堡"
    domain = "crabpt.vip"
    tasks = [
        Checkin(),
        Claim(options=[
            {"id": "16", "label": "转种员专属任务"},
            {"id": "15", "label": "保种员专属2"},
            {"id": "14", "label": "保种员专属1"},
            {"id": "12", "label": "保种魔王"},
            {"id": "11", "label": "力争全勤奖"},
            {"id": "10", "label": "每月任务2"},
            {"id": "9", "label": "每月任务1"},
            {"id": "2", "label": "test转种项目"},
        ]),
    ]
