"""NovaHD 标准签到与任务申领。"""
from ..core.site import Site
from ..core.task import Checkin, Claim


class NovaHD(Site):
    site_name = "NovaHD"
    domain = "novahd.top"
    tasks = [
        Checkin(),
        Claim(options=[
            {"id": "3", "label": "保种任务"},
            {"id": "2", "label": "转种任务"},
        ]),
    ]
