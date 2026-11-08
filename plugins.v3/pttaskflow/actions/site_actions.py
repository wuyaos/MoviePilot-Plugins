from ..core.models import TaskResult

class ZhuqueSkillAction:
    def execute(self, site):
        headers = site._csrf_headers()
        if not headers:
            return TaskResult.fail(site.request_error or "朱雀 CSRF 获取失败")
        payload = site.get_user_info(headers)
        if payload is None:
            return TaskResult.fail(site.request_error or "朱雀角色信息请求失败")
        if not site.skill_is_due(payload):
            return TaskResult.business("技能尚未到可释放时间")
        response = site.post("/api/gaming/fireGenshinCharacterMagic",
                             headers=headers, json={"all": 1, "resetModal": True})
        if response is None:
            return TaskResult.fail(site.request_error or "朱雀技能释放失败")
        try:
            body = response.json()
        except (TypeError, ValueError):
            return TaskResult.fail("朱雀技能接口返回非 JSON")
        if body.get("status") != 200:
            return TaskResult.business(str(body.get("message") or "朱雀技能未释放"))
        confirmed = site.get_user_info(headers)
        if confirmed is None:
            return TaskResult.fail(site.request_error or "朱雀技能结果回读失败")
        if site.skill_is_due(confirmed):
            return TaskResult.fail("朱雀技能提交后未进入可确认状态")
        data = body.get("data") if isinstance(body.get("data"), dict) else {}
        bonus = data.get("bonus")
        return TaskResult.ok(
            f"技能释放成功{f'，获得{bonus}灵石' if bonus is not None else ''}",
            rewards=[{"type": "bonus", "description": "朱雀技能奖励", "amount": bonus, "unit": "灵石"}]
            if isinstance(bonus, (int, float)) else [],
        )


class ZhuqueLevelUpAction:
    def execute(self, site, target_level=79):
        headers = site._csrf_headers()
        if not headers:
            return TaskResult.fail(site.request_error or "朱雀 CSRF 获取失败")
        response = site.post("/api/gaming/trainGenshinCharacter",
                             headers=headers, json={"resetModal": False, "level": int(target_level)})
        if response is None:
            return TaskResult.fail(site.request_error or "朱雀一键升级失败")
        try:
            body = response.json()
        except (TypeError, ValueError):
            return TaskResult.fail("朱雀升级接口返回非 JSON")
        if body.get("status") == 200:
            return TaskResult.ok(f"一键升级成功，目标等级 {int(target_level)}")
        message = body.get("message") or body.get("error") or "朱雀升级未完成"
        if response.status_code == 400:
            return TaskResult.business(f"升级受限：{message}")
        return TaskResult.business(str(message))


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
