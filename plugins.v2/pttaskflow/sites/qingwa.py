"""青蛙：签到、蛙总喊话、每日福利兑换。"""
from lxml import etree
from ..actions.site_actions import QingwaBonusAction
from ..core.models import TaskResult
from ..core.shoutbox import Direction, ShoutboxProfile
from ..core.site import Site
from ..core.task import Chat, Checkin, Exchange


class Qingwa(Site):
    site_name = "青蛙"
    domain = "qingwapt.com"
    bonusshop_api = ""
    getitems_api = ""
    shoutbox = ShoutboxProfile(
        row_xpath="//li",
        direction=Direction.BEFORE,
        message_terms=lambda message: ["蛙总"] if "蛙总" in message else [message],
        confirmation_wait_seconds=2,
    )
    tasks = [
        Checkin(),
        Chat(messages=["蛙总求上传"]),
    ]

    def __init__(self, site_info, **kwargs):
        super().__init__(site_info, **kwargs)
        self.bonusshop_api = f"{self.url}/api/bonus-shop/exchange"
        self.getitems_api = f"{self.url}/api/bonus-shop/getItems"
        self.tasks = [*type(self).tasks, Exchange(QingwaBonusAction(), label="每日1k蝌蚪")]

    def send_message(self, message):
        response = self.get("/shoutbox.php", params={
            "shbox_text": message, "shout": "我喊", "sent": "yes", "type": "shoutbox",
        })
        if not response:
            return TaskResult.fail(self.request_error or "青蛙喊话失败")
        root = etree.HTML(response.text or "")
        feedback = " ".join(root.xpath("//ul[1]/li/text()") if root is not None else []).strip()
        if not feedback:
            return TaskResult.ok(f"已发送“{message}”")
        return TaskResult.ok(f"已发送“{message}”", rewards=[{
            "type": self.reward_type(feedback), "description": feedback,
            "amount": "", "unit": "", "is_negative": False,
        }])
