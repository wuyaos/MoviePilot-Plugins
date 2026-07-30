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
