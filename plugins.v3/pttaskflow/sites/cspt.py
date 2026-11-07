"""财神标准任务申领。"""
from ..core.site import Site
from ..core.task import Claim


class CSPT(Site):
    site_name = "财神"
    domain = "cspt.top"
    tasks = [
        Claim(options=[
            {"id": "6", "label": "南财神"},
            {"id": "5", "label": "西财神"},
            {"id": "3", "label": "东财神"},
        ]),
    ]
