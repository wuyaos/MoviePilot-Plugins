"""梓喵：带动态 CSRF 的任务申领。

梓喵 WAF 基于 TLS 指纹拦截 requests 的 POST；curl_cffi 模拟 Chrome 指纹可绕过。
"""
import re
from ..core.models import TaskResult
from ..core.site import Site
from ..core.task import Claim

_IDEMPOTENT_TERMS = (
    "有其他进行中的任务", "已有进行中的任务", "已有其他任务进行中",
    "任务已领取", "已经领取", "已领取", "已经完成", "已完成",
    "认领人数已达上限", "领取人数已达上限", "人数已达上限",
)


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
        self.session.headers.update({"X-Requested-With": "XMLHttpRequest"})

    def claim_task(self, task_id):
        # 梓喵 WAF 按 TLS 指纹拦截；GET 和 POST 必须用同一个 curl_cffi Session。
        try:
            from curl_cffi import requests as cffi_requests
        except ImportError:
            cffi_requests = None
        if cffi_requests is not None:
            return self._claim_via_cffi(cffi_requests, task_id)
        return self._claim_via_requests(task_id)

    def _claim_via_cffi(self, cffi_requests, task_id):
        try:
            session = cffi_requests.Session(impersonate="chrome131")
            response = session.get(f"{self.url}/task.php", headers=self._cffi_headers(),
                                   cookies=self._cookies(), timeout=20)
            if response.status_code >= 400:
                return TaskResult.fail(f"读取任务页面失败：HTTP {response.status_code}")
            match = re.search(r"csrf_token=([a-f0-9]{40})", response.text or "", re.I)
            if not match:
                return TaskResult.fail("未获取到 CSRF Token")
            csrf = match.group(1)
            response = session.post(
                f"{self.url}/ajax.php?csrf_token={csrf}",
                data={"action": "claimTask", "params[exam_id]": task_id},
                headers=self._cffi_headers(), cookies=self._cookies(), timeout=20)
            if response.status_code >= 400:
                return TaskResult.fail(f"任务领取请求失败：HTTP {response.status_code}")
            return self._classify(response.json())
        except Exception as error:
            return TaskResult.fail(f"梓喵 curl_cffi 请求异常：{error}")

    def _claim_via_requests(self, task_id):
        response = self.get("/task.php")
        if not response:
            return TaskResult.fail(self.request_error or "读取任务页面失败")
        match = re.search(r"csrf_token=([a-f0-9]{40})", response.text or "", re.I)
        if not match:
            return TaskResult.fail("未获取到 CSRF Token")
        csrf = match.group(1)
        response = self.post(f"/ajax.php?csrf_token={csrf}",
                            {"action": "claimTask", "params[exam_id]": task_id})
        if not response:
            return TaskResult.fail(self.request_error or "任务领取请求失败（WAF 拦截或网络异常）")
        try:
            return self._classify(response.json())
        except Exception:
            return TaskResult.fail("任务领取响应解析失败")

    def _cffi_headers(self):
        return {
            "Cookie": self.cookie,
            "User-Agent": self.ua,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": self.url,
            "Referer": f"{self.url}/task.php",
        }

    def _cookies(self):
        cookies = {}
        for pair in (self.cookie or "").split(";"):
            if "=" in pair:
                k, v = pair.strip().split("=", 1)
                cookies[k] = v
        return cookies

    @staticmethod
    def _classify(payload):
        ret = payload.get("ret")
        msg = str(payload.get("msg") or "")
        data = payload.get("data")
        # 梓喵业务消息在 data 字段（字符串）或 msg 字段。
        detail = str(data) if isinstance(data, str) and data else msg
        if ret in (0, "0") or any(x in detail for x in ("成功", "已领取", "OK")):
            return TaskResult.ok(detail)
        if any(term in detail for term in _IDEMPOTENT_TERMS):
            return TaskResult.idempotent(detail)
        return TaskResult.business(detail)
