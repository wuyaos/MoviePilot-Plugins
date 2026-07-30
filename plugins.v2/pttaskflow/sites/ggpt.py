"""GGPT：签到与疯狂星期四勋章续购。"""
from ..actions.medal_site import NexusMedalAction
from ..core.site import Site
from ..core.task import Checkin, Medal


class GGPT(Site):
    site_name = "GGPT"
    domain = "gamegamept.com"
    medal_action = NexusMedalAction("35", {"35": "疯狂星期四"})
    tasks = [
        Checkin(),
        Medal(medal_action, label="购买疯狂星期四勋章"),
    ]
