"""站点基类：身份、HTTP 原语、任务组合和喊话确认。

具体站点只声明 ``site_name/domain/tasks/shoutbox``，确有差异时覆写小型原语
（例如特殊发送 API）；不得把配置、历史、调度写进站点类。
"""
import time
from typing import List

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.db.site_oper import SiteOper
from app.log import logger

from .models import TaskResult
from .shoutbox import ShoutboxProfile, observe, parse_snapshot


class Site:
    """可组合任务的站点基类。"""

    site_name = ""
    domain = ""
    match_keywords = ()
    tasks: List = []
    shoutbox = ShoutboxProfile()
    message_interval = None

    def __init__(self, site_info: dict, use_proxy=False, interval=30,
                 collect_feedback=True, feedback_timeout=5, cookie_refresher=None):
        self.site_info = dict(site_info)
        self.site_id = site_info.get("id")
        self.site_name = site_info.get("name") or type(self).site_name
        self.domain = site_info.get("domain") or type(self).domain
        self.url = (site_info.get("url") or "").rstrip("/")
        self.cookie = site_info.get("cookie") or ""
        self.ua = site_info.get("ua") or "Mozilla/5.0"
        self.message_interval = type(self).message_interval or max(0, int(interval))
        self.collect_feedback = bool(collect_feedback)
        self.feedback_timeout = max(0, min(10, int(feedback_timeout)))
        self.cookie_refresher = cookie_refresher
        self.request_error = ""
        self.session = self._build_session(use_proxy)

    @classmethod
    def matches(cls, site_info: dict) -> bool:
        blob = f"{site_info.get('name', '')} {site_info.get('domain', '')}".lower()
        terms = cls.match_keywords or (cls.site_name, cls.domain)
        return any(str(term).lower() in blob for term in terms if term)

    def _build_session(self, use_proxy):
        session = requests.Session()
        retry = Retry(total=2, backoff_factor=1, status_forcelist=[500, 502, 503, 504],
                      allowed_methods=frozenset(["GET", "POST"]), raise_on_status=False)
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session.headers.update({"Cookie": self.cookie, "User-Agent": self.ua, "Referer": self.url})
        if use_proxy:
            try:
                from app.core.config import settings
                proxy = getattr(settings, "PROXY", None)
                if isinstance(proxy, str) and proxy:
                    session.proxies.update({"http": proxy, "https": proxy})
                elif isinstance(proxy, dict):
                    session.proxies.update(proxy)
            except Exception as error:
                logger.warning(f"{self.site_name} - 读取代理失败：{error}")
        return session

    @staticmethod
    def _cookie_expired(response):
        if response.status_code == 401:
            return True
        if response.status_code == 403:
            # 403 可能是 WAF 拦截或 Cookie 失效；仅当响应含登录表单时视为 Cookie 失效。
            text = (getattr(response, "text", "") or "")[:10000].lower()
            return "type=\"password\"" in text or "type='password'" in text
        final_url = str(getattr(response, "url", "") or "").lower()
        if any(term in final_url for term in ("login.php", "takelogin")):
            return True
        text = (getattr(response, "text", "") or "")[:10000].lower()
        is_html = "<html" in text or "<!doctype" in text
        has_login_form = ("type=\"password\"" in text or "type='password'" in text)
        return is_html and has_login_form and any(
            term in text for term in ("login.php", "takelogin", "请先登录", "用户登录")
        )

    def _request(self, method, path, **kwargs):
        self.request_error = ""
        for attempt in range(2):
            try:
                response = self.session.request(
                    method, f"{self.url}{path}", timeout=15, **kwargs)
            except Exception as error:
                self.request_error = f"请求异常：{error}"
                logger.error(f"{self.site_name} - {method} {path} 失败：{error}")
                return None
            if self._cookie_expired(response):
                if attempt == 0 and self.cookie_refresher:
                    cookie = self.cookie_refresher()
                    if cookie:
                        self.cookie = cookie
                        self.session.headers.update({"Cookie": cookie})
                        continue
                    self.request_error = "CookieCloud Cookie 获取失败"
                elif self.cookie_refresher:
                    self.request_error = "CookieCloud Cookie 已失效"
                else:
                    self.request_error = "MP Cookie 已失效"
                logger.warning(f"{self.site_name} - {method} {path} -> {self.request_error}")
                return None
            if response.status_code >= 400:
                self.request_error = f"HTTP {response.status_code}"
                logger.warning(f"{self.site_name} - {method} {path} -> {self.request_error}")
                return None
            return response
        return None

    def get(self, path: str, params=None):
        return self._request("GET", path, params=params)

    def post(self, path: str, data=None):
        return self._request("POST", path, data=data)

    def get_username(self):
        try:
            for item in SiteOper().get_userdata_latest():
                if getattr(item, "domain", "") == self.domain and getattr(item, "username", None):
                    return item.username
        except Exception as error:
            logger.error(f"{self.site_name} - 获取用户名失败：{error}")
        return None

    def send_message(self, message: str) -> TaskResult:
        """默认 NexusPHP 喊话发送。特殊站点只覆写本原语。"""
        response = self.get("/shoutbox.php", params={
            "shbox_text": message, "shout": "我喊", "sent": "yes", "type": "shoutbox",
        })
        return TaskResult.ok("消息已发送") if response else TaskResult.fail(
            self.request_error or "喊话请求失败")

    def before_send(self, message: str):
        """特殊站点发送前置条件；返回 TaskResult 时中止本次喊话。"""
        return None

    def read_shoutbox(self):
        return self.get(self.shoutbox.path)

    def extract_feedback(self, html: str, username: str, message: str):
        """默认按 Profile 从单次快照确认用户消息并关联反馈。"""
        rows, reason = parse_snapshot(html, self.shoutbox)
        if reason:
            from .shoutbox import Observation
            return Observation(False, False, reason=reason, retry_allowed=False)
        configured = []
        for task in self.tasks:
            configured.extend(getattr(task, "messages", []) or [])
        return observe(rows, self.shoutbox, username, message, configured or [message])

    def feedback_result(self, message: str, observation, negative_terms=()):
        rewards = []
        if self.collect_feedback and observation.feedback:
            text = observation.feedback.text
            rewards.append({
                "type": self.reward_type(text), "description": text, "amount": "", "unit": "",
                "is_negative": any(term in text for term in negative_terms),
            })
        return TaskResult.ok(f"已发送“{message}”", rewards=rewards)

    def send_and_confirm(self, message: str, negative_terms=()) -> TaskResult:
        """CHAT 模板：前置检查→发送→直接结果短路→快照确认→统一结果。"""
        username = (self.get_username() or "").strip()
        if not username:
            return TaskResult.fail("未获取到站点用户名，停止发送以避免重复喊话")
        blocked = self.before_send(message)
        if blocked is not None:
            return blocked
        sent = self.send_message(message)
        if not sent.success or sent.rewards:
            return sent
        wait = min(10, max(0, int(self.shoutbox.confirmation_wait_seconds)))
        if self.collect_feedback:
            wait = max(wait, self.feedback_timeout)
        if wait:
            time.sleep(wait)
        response = self.read_shoutbox()
        if not response:
            return TaskResult.fail(self.request_error or "喊话区确认不可用")
        observation = self.extract_feedback(response.text, username, message)
        if not observation.valid or not observation.sent:
            return TaskResult.fail(observation.reason)
        return self.feedback_result(message, observation, negative_terms)

    @staticmethod
    def reward_type(text: str) -> str:
        """统一奖励分类：站点自定义积分均归魔力值。"""
        lower = (text or "").lower()
        for kind, terms in (
            ("上传量", ("上传",)),
            ("下载量", ("下载",)),
            ("魔力值", ("魔力", "电力", "工分", "火花", "啤酒瓶", "幸运星", "象草")),
            ("VIP", ("vip",)),
        ):
            if any(term in lower for term in terms):
                return kind
        return "raw_feedback"

    def claim_task(self, task_id: str) -> TaskResult:
        response = self.post("/ajax.php", data={"action": "claimTask", "params[exam_id]": task_id})
        if not response:
            return TaskResult.fail(self.request_error or "任务申领请求失败")
        try:
            payload = response.json()
        except Exception:
            return TaskResult.fail("任务申领响应不是 JSON")
        message = str(payload.get("msg") or payload.get("message") or "申领完成")
        success = payload.get("success", payload.get("ret") in (0, "0"))
        if success:
            return TaskResult.ok(message)
        if any(term in message for term in (
                "有其他进行中的任务", "已有进行中的任务", "已有其他任务进行中",
                "任务已领取", "已经领取", "已领取", "已经完成", "已完成",
                "认领人数已达上限", "领取人数已达上限", "人数已达上限")):
            return TaskResult.idempotent(message)
        return TaskResult.business(message)
