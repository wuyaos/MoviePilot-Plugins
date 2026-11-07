"""NovaHD 标准任务申领。"""
from ..core.site import Site
from ..core.task import Claim


class NovaHD(Site):
    site_name = "NovaHD"
    domain = "novahd.top"
    tasks = [
        Claim(options=[
            {"id": "3", "label": "保种任务"},
            {"id": "2", "label": "转种任务"},
        ]),
    ]
