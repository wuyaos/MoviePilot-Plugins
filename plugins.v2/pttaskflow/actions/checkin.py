"""签到动作策略。只负责站点请求与响应语义，不读配置、不写历史。"""
from lxml import etree

from ..core.models import TaskResult


class NexusPHPCheckin:
    """默认 NexusPHP ``/attendance.php`` 签到策略。"""

    path = "/attendance.php"
    success_terms = ("签到成功", "已经签到", "已签到", "已领取")

    def execute(self, site) -> TaskResult:
        response = site.get(self.path)
        if not response:
            return TaskResult.fail(site.request_error or "签到请求失败")
        root = etree.HTML(response.text or "")
        if root is None:
            return TaskResult.fail("签到页面解析失败")
        text = " ".join(part.strip() for part in root.xpath("//body//text()") if part.strip())
        if any(term in text for term in self.success_terms):
            return TaskResult.idempotent(text[:200] or "今日已签到")
        return TaskResult.business(text[:200] or "签到结果未识别")


class FluxTorrentCheckin:
    """好学（FluxTorrent）``/api/v1/attendance`` JSON 签到策略。

    流程：GET 回读 → checked_today 即幂等成功；否则 POST checkin 后**强制再回读**，
    只有回读 checked_today=True 才记成功（提交回执只拼奖励信息，不单独定成功）。
    """

    status_path = "/api/v1/attendance"
    checkin_path = "/api/v1/attendance/checkin"

    @staticmethod
    def _envelope(response):
        if response is None:
            return None
        try:
            payload = response.json()
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        return payload, data

    def execute(self, site) -> TaskResult:
        pre = self._envelope(site.get(self.status_path))
        if pre is None:
            return TaskResult.fail("签到状态接口不可读（非 JSON 或请求失败）")
        payload, data = pre
        if data.get("checked_today") is True:
            return TaskResult.idempotent("今日已签到")
        if payload.get("code") not in (0, "0"):
            return TaskResult.business(
                f"签到状态未确认：{payload.get('message') or payload.get('code')}")
        receipt = self._envelope(site.post(self.checkin_path, json={}))
        after = self._envelope(site.get(self.status_path))
        if after is None:
            return TaskResult.fail("已提交签到，但回读未确认（状态接口不可读）")
        if after[1].get("checked_today") is True:
            parts = []
            reward = (receipt or ({}, {}))[1].get("reward")
            streak = (receipt or ({}, {}))[1].get("streak")
            if reward is not None:
                parts.append(f"+{reward} 魔力")
            if streak is not None:
                parts.append(f"连续 {streak} 天")
            return TaskResult.ok("签到成功" + ("（" + "，".join(parts) + "）" if parts else ""))
        return TaskResult.business("已提交签到，但回读仍为未签到")
