"""LuckPT 勋章中心分类奖励领取 Action。"""
from lxml import etree

from ..core.models import TaskResult

# 已领取类文案：终态成功，不重试。
_CLAIMED_TERMS = ("已经领取", "已领取", "已经购买", "已拥有", "already claimed")


class LuckptMedalRewardAction:
    """领取 medal_collection.php 中可领取的分类奖励。

    页面按钮由 JS 经 ``POST ajax.php`` 发送
    ``action=claimMedalCategoryReward`` + ``params[category_id]`` +
    ``params[reward_type]``，响应 ``ret == 0`` 表示成功。
    典型奖励：分类 8「工具支持纪念套装」的 ``bonus_daily`` 每日幸运星。
    """

    def _find_claimable(self, site):
        """读取勋章中心，返回 [(category, reward_type, label)]；请求失败返回 None。"""
        response = site.get("/medal_collection.php")
        if not response:
            return None
        html = etree.HTML(response.text or "")
        if html is None:
            return []
        rewards = []
        for button in html.xpath(
            '//button[contains(concat(" ", normalize-space(@class), " "), " claim-reward ")'
            ' and not(@disabled)]'
        ):
            category = (button.get("data-category") or "").strip()
            reward_type = (button.get("data-type") or "").strip()
            label = (button.get("data-reward-label") or "").strip()
            if category and reward_type:
                rewards.append((category, reward_type, label or reward_type))
        return rewards

    def execute(self, site) -> TaskResult:
        rewards = self._find_claimable(site)
        if rewards is None:
            return TaskResult.fail(site.request_error or "勋章中心页面请求失败")
        if not rewards:
            return TaskResult.idempotent("无可领取的勋章奖励")

        claimed, failed = [], []
        for category, reward_type, label in rewards:
            response = site.post("/ajax.php", data={
                "action": "claimMedalCategoryReward",
                "params[category_id]": category,
                "params[reward_type]": reward_type,
            })
            if not response:
                failed.append(f"{label}：{site.request_error or '领取请求失败'}")
                continue
            try:
                payload = response.json()
            except Exception:
                failed.append(f"{label}：领取响应不是 JSON")
                continue
            message = str(payload.get("msg") or payload.get("message") or "无返回信息")
            if payload.get("ret") in (0, "0") or payload.get("success") is True:
                claimed.append((label, message))
            elif any(term in message for term in _CLAIMED_TERMS):
                claimed.append((label, "已领取"))
            else:
                failed.append(f"{label}：{message}")

        if failed:
            return TaskResult.business("；".join(failed))
        reward_items = [
            {
                "type": "魔力值",
                "description": f"{label}：{message}",
                "amount": "", "unit": "", "is_negative": False,
            }
            for label, message in claimed
        ]
        summary = "领取成功：" + "、".join(
            label if message == "领取成功" else f"{label}({message})"
            for label, message in claimed
        )
        return TaskResult.ok(summary, rewards=reward_items)
