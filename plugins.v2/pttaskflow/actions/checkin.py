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
        if response is None or not 200 <= getattr(response, "status_code", 200) < 300:
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
        if type(payload.get("code")) is not int or payload["code"] != 0:
            return TaskResult.business(
                f"签到状态未确认：{payload.get('message') or payload.get('code')}")
        if data.get("checked_today") is True:
            return TaskResult.idempotent("今日已签到")
        receipt = None
        submit_error = ""
        try:
            response = site.post(self.checkin_path, json={})
            receipt = self._envelope(response)
            if response is None:
                submit_error = site.request_error or "提交结果未知"
            elif not 200 <= getattr(response, "status_code", 200) < 300:
                submit_error = f"提交 HTTP {response.status_code}"
            elif receipt is None:
                submit_error = "提交响应不是有效 JSON"
            elif type(receipt[0].get("code")) is not int or receipt[0]["code"] != 0:
                code = str(receipt[0].get("code", ""))
                submit_error = f"提交业务码 {code}" if code.isdecimal() else "提交业务拒绝"
        except Exception as error:
            submit_error = f"提交结果未知（{type(error).__name__}），未重放"
        # 无论提交异常/拒绝与否，只读核验一次，不重放写请求。
        try:
            after = self._envelope(site.get(self.status_path))
        except Exception:
            after = None
        if after and type(after[0].get("code")) is int and after[0]["code"] == 0 and after[1].get("checked_today") is True:
            parts = []
            reward = (receipt or ({}, {}))[1].get("reward") if not submit_error else None
            streak = (receipt or ({}, {}))[1].get("streak") if not submit_error else None
            if reward is not None:
                parts.append(f"+{reward} 魔力")
            if streak is not None:
                parts.append(f"连续 {streak} 天")
            return TaskResult.ok("签到成功" + ("（" + "，".join(parts) + "）" if parts else ""))
        detail = "状态接口不可读" if after is None else "未取得今日已签到证据"
        return TaskResult.business(f"{submit_error or '已提交签到'}；回读{detail}")
