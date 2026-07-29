"""RailgunPT 站点适配。

groupchatzone 独有站点（炮姐PT），仅通用签到+喊话，无特殊反馈解析。
- 站点框架：NexusPHP
- 访问地址：https://bilibili.download
"""
from .capabilities import CapabilityHandler
from ..base.base_task import BaseTask
from ..base.decorator import task_info, TaskType
from ..base.result import TaskResult


class RailgunptHandler(CapabilityHandler):
    @staticmethod
    def get_site_name():
        return "RailgunPT"

    @staticmethod
    def get_site_domain():
        return "bilibili.download"

    def match(self) -> bool:
        return "railgun" in self.site_name.lower() or "bilibili.download" in self.domain

    def shoutbox_profile(self):
        from ..base.shoutbox import FeedbackDirection, ShoutboxProfile
        return ShoutboxProfile(
            path="/shoutbox.php?type=shoutbox",
            row_xpath="//td[contains(@class, 'shoutrow')]",
            direction=FeedbackDirection.BEFORE,
            message_terms=lambda message: ["炮姐", message.split("，")[-1]],
            confirmation_wait_seconds=2,
        )


class Tasks(BaseTask):
    def __init__(self, cookie=None):
        super().__init__(None)

    @task_info("{client_name}签到", "执行RailgunPT签到", TaskType.CHECKIN)
    def daily_checkin(self):
        return self.client.attendance()

    @task_info("{client_name}喊话", "执行RailgunPT喊话", TaskType.CHAT)
    def daily_shotbox(self):
        ok, msg = self.client.send_messagebox("炮姐，求魔力")
        return TaskResult.ok(msg) if ok else TaskResult.fail(msg)
