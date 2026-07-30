"""垃圾堆标准签到与任务申领。"""
from ..core.site import Site
from ..core.task import Checkin, Claim


class Lajidui(Site):
    site_name = "垃圾堆"
    domain = "lajidui.top"
    tasks = [
        Checkin(),
        Claim(options=[{"id": "1", "label": "保种计划"}]),
    ]
