"""Vc-Lib：签到、每周上传复合任务、任务申领。"""
import re
from ..core.models import TaskResult
from ..core.site import Site
from ..core.task import ActionTask, Checkin, Claim


class VclibWeeklyAction:
    def execute(self, site):
        claim = site.claim_task("2")
        if not claim.success:
            return claim
        status = site.get_task_status_from_homepage()
        if status["status"] == "error":
            return TaskResult.fail(f"任务状态读取失败：{status['message']}")
        if status["status"] in ("not_exist", "completed"):
            return TaskResult.ok(f"{claim.message}；任务状态：{status['message']}")
        result = site.exchange_upload_bonus(2)
        if result.success:
            return TaskResult.ok(f"{claim.message}；{result.message}")
        return result


class Vclib(Site):
    site_name = "Vc-Lib"
    domain = "vclib.online"
    tasks = [
        Checkin(),
        ActionTask("weekly_upload_claim_and_exchange", VclibWeeklyAction(), "每周上传任务"),
        Claim(options=[{"id": "3", "label": "每周魔力值任务"}]),
    ]

    def get_task_status_from_homepage(self):
        response = self.get("/index.php")
        if not response:
            return {"status": "error", "message": self.request_error or "获取首页失败"}
        html = response.text
        pattern = (r"每周任务_上传量.*?要求[：:]\s*([\d.]+)\s*([A-Za-z]+).*?"
                   r"当前[：:]\s*([\d.]+)\s*([A-Za-z]+).*?结果[：:]\s*(.*?)(?:<br|$|</font)")
        match = re.search(pattern, html, re.S)
        if not match:
            return {"status": "not_exist", "message": "未找到每周上传任务"}
        result = re.sub(r"<[^>]+>", "", match.group(5)).strip()
        completed = "完成" in result and "未完成" not in result
        return {"status": "completed" if completed else "uncompleted", "message": result}

    def exchange_upload_bonus(self, option=2):
        response = self.post("/mybonus.php?action=exchange", {"option": str(option), "submit": "交换"})
        if not response:
            return TaskResult.fail(self.request_error or "兑换请求失败")
        html = response.text
        if any(x in html for x in ("兑换成功", "成功兑换", "今日已兑换", "已兑换过", "系统限制")):
            return TaskResult.idempotent("魔力值兑换上传量成功或今日已兑换")
        if "魔力值不足" in html:
            return TaskResult.business("魔力值不足，无法兑换上传量")
        return TaskResult.business("兑换结果未确认")
