"""myPT：签到与多选勋章续购。"""
from ..actions.medal_site import NexusMedalAction
from ..core.site import Site
from ..core.task import Checkin, Medal


class MyPT(Site):
    site_name = "myPT"
    domain = "mypt.cc"
    medal_options = [
        {"id": "8", "label": "VIP（30天）"}, {"id": "7", "label": "白金（365天）"},
        {"id": "6", "label": "铂金（365天）"}, {"id": "5", "label": "黄金（365天）"},
        {"id": "4", "label": "钻石（365天）"}, {"id": "3", "label": "至尊（365天）"},
    ]
    medal_action = NexusMedalAction(
        "8", {item["id"]: item["label"] for item in medal_options}
    )
    tasks = [
        Checkin(),
        Medal(medal_action, options=medal_options, label="勋章续购"),
    ]
