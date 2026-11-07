"""CARPT 标准任务申领。"""
from ..core.site import Site
from ..core.task import Claim


class CARPT(Site):
    site_name = "CARPT"
    domain = "carpt.net"
    tasks = [
        Claim(options=[
            {"id": "5", "label": "天天快乐任务"},
            {"id": "4", "label": "15天任务(VIP)"},
            {"id": "3", "label": "30天任务"},
            {"id": "2", "label": "7天任务"},
        ]),
    ]
