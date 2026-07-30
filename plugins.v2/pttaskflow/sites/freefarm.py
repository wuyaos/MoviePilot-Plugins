"""自由农场标准签到与任务申领。"""
from ..core.site import Site
from ..core.task import Checkin, Claim


class FreeFarm(Site):
    site_name = "自由农场"
    domain = "0ff.cc"
    tasks = [
        Checkin(),
        Claim(options=[
            {"id": "12", "label": "做种积分"},
            {"id": "11", "label": "发种增量"},
            {"id": "9", "label": "下载增量"},
        ]),
    ]
