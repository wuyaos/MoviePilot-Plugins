"""躺平标准任务申领。"""
from ..core.site import Site
from ..core.task import Claim


class TangPT(Site):
    site_name = "躺平"
    domain = "tangpt.top"
    tasks = [
        Claim(options=[
            {"id": "7", "label": "我想试试"},
            {"id": "6", "label": "YES"},
            {"id": "5", "label": "苍蝇腿"},
            {"id": "4", "label": "VIP"},
            {"id": "3", "label": "BUG"},
            {"id": "2", "label": "TEST"},
        ]),
    ]
