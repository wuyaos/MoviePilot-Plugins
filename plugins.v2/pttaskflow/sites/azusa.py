"""梓喵：带动态 CSRF 的任务申领。"""
import re
from ..core.site import Site
from ..core.task import Claim


class Azusa(Site):
    site_name = "梓喵"
    domain = "azusa.wiki"
    tasks = [Claim(options=[
        {"id": "11", "label": "每日任务4（魔力+上传）"}, {"id": "9", "label": "每日任务3（做种积分）"},
        {"id": "7", "label": "每日任务2（上传+做种积分）"}, {"id": "6", "label": "每日任务1（发种）"},
        {"id": "15", "label": "月度任务5（发种+保种+上传）"}, {"id": "14", "label": "月度任务4（发种）"},
        {"id": "13", "label": "月度任务3（保种+上传）"}, {"id": "12", "label": "月度任务2（保种+上传）"},
        {"id": "8", "label": "月度任务1（发种）"}, {"id": "10", "label": "七日任务2（发种）"},
        {"id": "5", "label": "七日任务1（保种）"},
    ])]

    def __init__(self, site_info, **kwargs):
        super().__init__(site_info, **kwargs)
        # 梓喵 ajax.php 要求 X-Requested-With 头，否则可能返回登录页。
        self.session.headers.update({"X-Requested-With": "XMLHttpRequest"})

    def claim_task(self, task_id):
        response = self.get("/task.php")
        if not response:
            return self._technical("读取任务页面失败")
        match = re.search(r"csrf_token=([a-f0-9]{40})", response.text or "", re.I)
        if not match:
            return self._technical("未获取到 CSRF Token")
        response = self.post(f"/ajax.php?csrf_token={match.group(1)}",
                             {"action": "claimTask", "params[exam_id]": task_id})
        if not response:
            return self._technical(self.request_error or "任务领取请求失败（可能被站点 WAF 拦截）")
        try:
            payload = response.json()
            message = payload.get("msg") or payload.get("message") or "未知结果"
            return self._business(str(message))
        except Exception:
            return self._technical("任务领取响应解析失败")

    @staticmethod
    def _technical(message):
        from ..core.models import TaskResult
        return TaskResult.fail(message)

    @staticmethod
    def _business(message):
        from ..core.models import TaskResult
        return TaskResult.ok(message) if any(x in message for x in ("成功", "已领取", "OK")) else TaskResult.business(message)
