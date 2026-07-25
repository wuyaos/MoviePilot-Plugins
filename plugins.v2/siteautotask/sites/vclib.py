"""Vc-Lib（vclib）站点适配。

ptautotask 独有站点，标准 NexusPHP，但含复杂任务：
- 每周上传任务申领 + 状态检查 + 未完成则魔力兑换上传量
- 每周魔力值任务申领

迁移改进：上游用 stateless requests + verify=False + 自定义 headers，
迁移后走统一 session（已有 cookie/ua/referer），移除不安全的 verify=False。
"""
import re
from typing import Optional, Tuple

from app.log import logger

from .capabilities import CapabilityHandler
from ..base.base_task import BaseTask
from ..base.decorator import task_info, TaskType
from ..base.result import TaskResult
from ..utils.request import parse_json_response


class VclibHandler(CapabilityHandler):
    @staticmethod
    def get_claim_options():
        """可申领任务选项，id 为站点 exam_id。Vc-Lib 未在 MP 配置，沿用上游已知 task_id。"""
        return [
            {"id": "2", "label": "每周上传任务"},
            {"id": "3", "label": "每周魔力值任务"},
        ]

    def __init__(self, site_info: dict):
        super().__init__(site_info)
        self.bonus_url = self.site_url + "/mybonus.php?action=exchange"

    @staticmethod
    def get_site_name():
        return "Vc-Lib"

    @staticmethod
    def get_site_domain():
        return "vclib.online"

    def match(self) -> bool:
        return "vclib" in self.domain or "vc-lib" in self.site_name.lower()

    def claim_task(self, task_id: str, callback=None):
        response = self._send_post_request(
            self.site_url + "/ajax.php",
            data={"action": "claimTask", "params[exam_id]": task_id})
        if response is None:
            return "申领失败"
        result = parse_json_response(response, "申领失败")
        return result.get("msg", "未知错误")

    def get_task_status_from_homepage(self) -> dict:
        """从首页获取每周上传任务状态。

        返回 {status: completed/uncompleted/not_exist/error, message, current, requirement}
        """
        try:
            response = self.session.get(self.site_url + "/index.php", timeout=(3.05, 15))
            if response.status_code != 200:
                return {"status": "error", "message": f"获取首页失败，HTTP状态码: {response.status_code}"}
            html = response.text
            if "未登录" in html or "该页面必须在登录后才能访问" in html:
                return {"status": "error", "message": "Cookie已失效，请重新登录"}

            # 匹配每周上传任务块
            pattern = (r'名称[：:]\s*每周任务_上传量.*?指标1[：:]\s*上传增量,\s*要求[：:]\s*'
                       r'([\d.]+)\s*([A-Za-z]+),\s*当前[：:]\s*([\d.]+)\s*([A-Za-z]+),\s*'
                       r'结果[：:]\s*(?:<span[^>]*>)?(.*?)(?:</span>)?(?:<br|$|</font)')
            match = re.search(pattern, html, re.S)
            if not match:
                pattern2 = (r'每周任务_上传量.*?要求[：:]\s*([\d.]+)\s*([A-Za-z]+).*?'
                           r'当前[：:]\s*([\d.]+)\s*([A-Za-z]+).*?结果[：:]\s*'
                           r'(?:<span[^>]*>)?(.*?)(?:</span>)?(?:<br|$|</font)')
                match = re.search(pattern2, html, re.S)
            if match:
                requirement = f"{match.group(1)} {match.group(2)}"
                current = f"{match.group(3)} {match.group(4)}"
                result_text = match.group(5).strip()
                is_completed = "完成" in result_text and "未完成" not in result_text
                return {"status": "completed" if is_completed else "uncompleted",
                        "message": result_text, "requirement": requirement, "current": current}

            if "每周任务_上传量" in html and "完成！" in html and "未完成" not in html:
                return {"status": "completed", "message": "完成！",
                        "requirement": "10 GB", "current": "10.00 GB"}
            return {"status": "not_exist", "message": "未找到每周上传任务"}
        except Exception as e:
            logger.error(f"Vc-Lib：获取任务状态异常：{e}")
            return {"status": "error", "message": f"解析异常: {e}"}

    def _get_current_bonus(self) -> Optional[float]:
        """获取当前魔力值。"""
        try:
            response = self.session.get(self.bonus_url, timeout=(3.05, 15))
            if response.status_code != 200:
                return None
            match = re.search(r'当前([\d,.]+)\s*魔力值', response.text)
            if match:
                return float(match.group(1).replace(',', '').strip())
        except Exception as e:
            logger.error(f"Vc-Lib：获取魔力值异常：{e}")
        return None

    def exchange_upload_bonus(self, option: int = 2) -> Tuple[bool, str]:
        """魔力值兑换上传量。

        option: 0=1GB(300魔力) 1=5GB(800魔力) 2=10GB(1300魔力) 3=100GB(10000魔力)
        """
        try:
            magic = self._get_current_bonus()
            if magic is not None and magic < 1300:
                return False, f"魔力值不足 (当前{magic}, 需要1300)"
            response = self.session.post(self.bonus_url, data={"option": str(option), "submit": "交换"},
                                         timeout=(3.05, 15))
            if response.status_code != 200:
                return False, f"兑换请求失败，HTTP状态码: {response.status_code}"
            html = response.text
            if "兑换成功" in html or "成功兑换" in html:
                return True, "魔力值兑换上传量成功"
            if "魔力值不足" in html or "您的魔力值不足" in html:
                return False, "魔力值不足，无法兑换上传量"
            if "今日已兑换" in html or "已兑换过" in html or "系统限制" in html:
                return True, "今日已兑换过上传量"
            if "未登录" in html or ("登录" in html and "请" in html):
                return False, "Cookie已失效，请重新登录"
            if "上传量" in html and "增加" in html:
                return True, "魔力值兑换上传量成功"
            return True, "兑换上传量请求已发送"
        except Exception as e:
            logger.error(f"Vc-Lib：兑换上传量异常：{e}")
            return False, f"兑换异常: {e}"


class Tasks(BaseTask):
    def __init__(self, cookie=None):
        super().__init__(None)

    @task_info("{client_name}签到", "执行Vc-Lib签到", TaskType.CHECKIN)
    def daily_checkin(self):
        return self.client.attendance()

    @task_info("每周上传任务", "领取每周上传任务，未完成则兑换上传量", TaskType.GENERIC)
    def weekly_upload_claim_and_exchange(self):
        results = []
        claim = self.client.claim_task("2")
        is_success = any(kw in claim for kw in ("OK", "领取成功", "成功", "已完成", "已领取", "任务已领取"))
        results.append(f"{'✅' if is_success else '❌'} 任务领取: {claim}")
        status = self.client.get_task_status_from_homepage()
        if status.get("status") == "error":
            results.append(f"❌ 获取任务状态失败: {status.get('message')}")
            return TaskResult.fail("\n".join(results))
        if status.get("status") == "not_exist":
            results.append("⚠️ 未找到每周上传任务，跳过兑换")
            return TaskResult.ok("\n".join(results))
        results.append(f"任务状态: 当前 {status.get('current', '未知')} / 要求 {status.get('requirement', '未知')}")
        if status.get("status") == "uncompleted":
            results.append("⏳ 任务未完成，开始兑换上传量...")
            ok, msg = self.client.exchange_upload_bonus(option=2)
            results.append(f"{'✅' if ok else '❌'} 兑换上传量: {msg}")
            return TaskResult.ok("\n".join(results)) if ok else TaskResult.fail("\n".join(results))
        results.append(f"✅ 任务已完成（{status.get('message')}），跳过兑换")
        return TaskResult.ok("\n".join(results))

    @task_info("{client_name}任务申领", "申领Vc-Lib任务", TaskType.CLAIM)
    def claim(self, task_id=None):
        return self.client.claim_task(task_id)
