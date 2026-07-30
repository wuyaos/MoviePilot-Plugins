"""NexusPHP 勋章购买 Action。"""
import json
from lxml import etree
from ..core.models import TaskResult


class NexusMedalAction:
    def __init__(self, default_medal_id, medal_names=None):
        self.default_medal_id = str(default_medal_id)
        self.medal_names = medal_names or {}

    def purchase(self, site, medal_id):
        medal_id = str(medal_id or self.default_medal_id)
        response = site.get("/medal.php")
        if not response:
            return TaskResult.fail("勋章页面请求失败")
        html = etree.HTML(response.text or "")
        buttons = html.xpath(f'//input[@data-id="{medal_id}"]') if html is not None else []
        if buttons:
            button = buttons[0]
            value = (button.get("value") or "").strip()
            if button.get("disabled") is not None or any(x in value for x in ("已经购买", "已购买")):
                return TaskResult.idempotent(f"{self.medal_names.get(medal_id, medal_id)}勋章未过期，跳过续购")
            if "需要更多魔力值" in value:
                return TaskResult.business(f"{self.medal_names.get(medal_id, medal_id)}勋章魔力不足")
        response = site.post("/ajax.php", {"action": "buyMedal", "params[medal_id]": medal_id})
        if not response:
            return TaskResult.fail("购买勋章请求失败")
        try:
            payload = json.loads(response.text)
        except Exception:
            return TaskResult.fail("购买勋章响应解析失败")
        message = payload.get("message") or payload.get("msg") or payload.get("info") or "无返回信息"
        if payload.get("ret") in (0, "0") or payload.get("success") is True:
            return TaskResult.ok(f"{self.medal_names.get(medal_id, medal_id)}勋章购买成功：{message}")
        if any(term in str(message) for term in ("已经购买", "已拥有", "已购买", "already", "未到期")):
            return TaskResult.idempotent(f"勋章已拥有：{message}")
        return TaskResult.business(f"勋章购买失败：{message}")
