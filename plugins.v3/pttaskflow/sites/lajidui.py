"""垃圾堆标准任务申领。"""
from ..core.site import Site
from ..core.task import Claim


class Lajidui(Site):
    site_name = "垃圾堆"
    domain = "lajidui.top"
    tasks = [
        Claim(options=[{"id": "1", "label": "保种计划"}]),
    ]
