"""特殊站点 Action。

Action 只负责请求/解析与结果语义，站点仍持有会话和地址。
"""
from ..core.models import TaskResult


class QingwaBonusAction:
    def execute(self, site):
        try:
            response = site.get(site.getitems_api)
            if not response:
                return TaskResult.fail(site.request_error or "青蛙福利商品请求失败")
            payload = response.json()
            items = payload if isinstance(payload, list) else payload.get("data", payload.get("items", []))
            item_id = next((str(item["id"]) for item in items
                            if "每日福利" in item.get("name", "")
                            and item.get("a_type") == "bonus" and item.get("b_type") == "bonus"), "28")
            response = site.post(site.bonusshop_api, data={"id": item_id, "amount": 1})
            if not response:
                return TaskResult.fail(site.request_error or "青蛙兑换请求失败")
            result = response.json()
            message = result.get("msg") or result.get("message") or "兑换完成"
            if result.get("success") or any(term in message for term in ("超过限购", "已购买", "已兑换")):
                return TaskResult.idempotent(message)
            return TaskResult.business(message)
        except Exception as error:
            return TaskResult.fail(f"青蛙每日福利请求失败：{error}")
