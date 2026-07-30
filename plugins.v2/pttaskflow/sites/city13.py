"""13City：签到、做种任务、啤酒瓶喊话和诸神赐福勋章。"""
import json
from lxml import etree
from ..core.models import TaskResult
from ..core.site import Site
from ..core.task import ActionTask, Chat, Checkin, Claim, TaskType


class City13BlessingAction:
    def execute(self, site):
        ok, message = site.ensure_blessing_medal(auto_buy=True)
        return TaskResult.ok(message) if ok else TaskResult.business(message)


class City13(Site):
    site_name = "13City"
    domain = "13city.org"
    match_keywords = ("13city",)
    medal_id = "11"
    medal_name = "诸神赐福"
    tasks = [
        Checkin(),
        ActionTask("buy_blessing", City13BlessingAction(), "诸神赐福勋章", task_type=TaskType.MEDAL),
        Claim(options=[{"id": "2", "label": "每日做种"}, {"id": "6", "label": "每月做种"}]),
        Chat(messages=["掌管啤酒瓶的神请赐予我啤酒瓶"]),
    ]

    def __init__(self, site_info, **kwargs):
        super().__init__(site_info, **kwargs)
        self._blessing_status = {"medal_status": "未检查", "purchase_status": "未触发"}

    def before_send(self, message):
        ok, detail = self.ensure_blessing_medal(auto_buy=False)
        return None if ok else TaskResult.business(detail)

    def send_message(self, message):
        response = self.get("/shoutbox.php", params={
            "shbox_text": message, "shout": "我喊", "sent": "yes", "type": "shoutbox",
        })
        return TaskResult.ok("消息已发送") if response else TaskResult.fail(
            self.request_error or "13City 喊话请求失败")

    def ensure_blessing_medal(self, auto_buy=False):
        response = self.get("/medal.php?q=&sort=category")
        if not response:
            return (True, "无法确认勋章状态，继续执行喊话") if not auto_buy else (False, "获取勋章页面失败")
        html = etree.HTML(response.text or "")
        cards = html.xpath(f"//div[contains(@class, 'medal-card')][.//button[@data-id='{self.medal_id}']]")
        owned = any("purchased" in (card.get("class") or "") for card in cards)
        if owned:
            self._blessing_status.update(medal_status="已拥有", purchase_status="无需购买")
            return True, f"已拥有{self.medal_name}勋章"
        if not auto_buy:
            self._blessing_status.update(medal_status="未拥有", purchase_status="未开启自动购买")
            return True, f"未拥有{self.medal_name}勋章，继续执行喊话"
        result = self.post("/ajax.php", {"action": "buyMedal", "params[medal_id]": self.medal_id})
        if not result:
            return False, f"购买{self.medal_name}失败"
        try:
            payload = json.loads(result.text)
        except Exception:
            return False, "购买勋章响应解析失败"
        message = payload.get("msg") or payload.get("message") or "购买完成"
        if payload.get("ret") in (0, "0") or payload.get("success") is True:
            self._blessing_status.update(medal_status="已购买", purchase_status="购买成功")
            return True, message
        return False, message
