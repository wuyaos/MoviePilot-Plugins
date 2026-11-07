"""好学：AJAX 喊话与任务申领（FluxTorrent API 版）。"""
from datetime import datetime
import re
import time
from http.cookies import SimpleCookie
from urllib.parse import unquote, urlsplit

import requests
from requests.adapters import HTTPAdapter
from ..core.models import TaskResult
from ..core.shoutbox import ChatRow, Observation, ShoutboxProfile
from ..core.site import Site
from ..core.task import Chat, Claim


class HxPT(Site):
    site_name = "好学"
    domain = "haoxue.net"
    domain_aliases = ("hxpt.org",)
    shoutbox = ShoutboxProfile(
        path="/api/v1/shoutbox",
        retry_on_unconfirmed=False,
        confirmation_wait_seconds=3,
    )
    tasks = [
        Chat(messages=["好好学习天天向上"],
             negatives=("扣减", "扣除", "失去", "丢失")),
        # 任务商店（GET /api/v1/tasks）：id=2 本月发布 5 枚种子、id=3 字幕翻译志愿行。
        # id=1 做种研习社本人已领且名额满；晋升档（4-9）需费用/资格，不放进默认项。
        Claim(options=[
            {"id": "2", "label": "本月发布 5 枚种子"},
            {"id": "3", "label": "字幕翻译志愿行"},
        ]),
    ]

    def _build_session(self, use_proxy):
        session = super()._build_session(use_proxy)
        # 好学写接口不可自动重放（也禁止连接层重试）；其他站仍沿用基类。
        for scheme in ("http://", "https://"):
            session.mount(scheme, HTTPAdapter(max_retries=0))
        self._adopt_cookie_header(session)
        return session

    def _adopt_cookie_header(self, session):
        # 静态 Cookie 头会屏蔽响应更新的 jar；转为站点域 Cookie。
        raw = session.headers.pop("Cookie", "")
        parsed = SimpleCookie()
        parsed.load(raw)
        host = urlsplit(self.url).hostname
        if not host:
            return
        for name, morsel in parsed.items():
            # CookieCloud 刷新后不能让其旧 CSRF 覆盖 GET 刚下发的新值。
            if name == "flux_csrf" and any(c.name == name for c in session.cookies):
                continue
            session.cookies.set(name, morsel.value, domain=host, path="/")

    def _csrf_token(self, url):
        # 由 requests 按域/路径选择 Cookie，避免误拿其他域的同名 token。
        prepared = self.session.prepare_request(requests.Request("POST", url))
        parsed = SimpleCookie()
        parsed.load(prepared.headers.get("Cookie", ""))
        token = parsed.get("flux_csrf")
        return unquote(token.value) if token else ""

    def _request(self, method, path, **kwargs):
        if method != "POST":
            return super()._request(method, path, **kwargs)
        self.request_error = ""
        url = path if path.startswith(("http://", "https://")) else f"{self.url}{path}"
        self._adopt_cookie_header(self.session)
        token = self._csrf_token(url)
        if not token:
            # 引导只读一次；不能在写请求拒绝/超时后刷新并重放。
            self.get("/api/v1/me/csrf")
            self._adopt_cookie_header(self.session)
            token = self._csrf_token(url)
        if not token:
            self.request_error = "缺少 CSRF 凭据（flux_csrf），未发送写请求"
            return None
        headers = dict(kwargs.pop("headers", {}) or {})
        headers["x-csrf-token"] = token
        try:
            response = self.session.request(
                method, url, timeout=15, allow_redirects=False, headers=headers, **kwargs)
        except Exception as error:
            # 异常只留类型，不把含 Cookie/URL 参数的原文送进历史。
            self.request_error = f"写请求结果未知（{type(error).__name__}），未重放"
            return None
        if not 200 <= response.status_code < 300:
            self.request_error = f"写请求 HTTP {response.status_code}，未重放"
        return response

    @staticmethod
    def _chat_rows(response):
        if response is None or not 200 <= getattr(response, "status_code", 200) < 300:
            return None
        try:
            payload = response.json()
            if not isinstance(payload, dict) or type(payload.get("code")) is not int or payload["code"] != 0:
                return None
            if not isinstance(payload.get("data"), list):
                return None
            rows = []
            for item in payload["data"]:
                if not isinstance(item, dict) or not str(item.get("id", "")).isdecimal():
                    return None
                if not isinstance(item.get("username"), str) or not isinstance(item.get("message"), str):
                    return None
                created = datetime.fromisoformat(str(item.get("created_at", "")).replace("Z", "+00:00"))
                if created.tzinfo is None:
                    return None
                rows.append(dict(item, _id=int(item["id"]), _time=created.timestamp()))
            return rows
        except (ValueError, TypeError, AttributeError):
            return None

    def send_message(self, message):
        response = self.post(self.shoutbox.path, json={"message": message})
        if response is None:
            return TaskResult.business(self.request_error or "喊话结果未知，未重发")
        if not 200 <= getattr(response, "status_code", 200) < 300:
            return TaskResult.business(f"喊话 HTTP {response.status_code}，未重发")
        try:
            payload = response.json()
        except (ValueError, TypeError):
            return TaskResult.business("喊话回执不是有效 JSON，未重发")
        if not isinstance(payload, dict) or type(payload.get("code")) is not int or payload["code"] != 0:
            code = str(payload.get("code", "")) if isinstance(payload, dict) else ""
            detail = f"业务码 {code}" if code.isdecimal() else "回执未确认"
            return TaskResult.business(f"喊话{detail}，未重发")
        return TaskResult.ok("消息已提交，待回读确认")

    def send_and_confirm(self, message, negative_terms=()):
        # JSON 协议的身份/新旧关联只属于好学，不改变通用 HTML Profile。
        username = (self.get_username() or "").strip()
        if not username:
            return TaskResult.fail("未获取到站点用户名，停止发送以避免重复喊话")
        before = self._chat_rows(self.read_shoutbox())
        if before is None:
            return TaskResult.fail("喊话前快照不可读，未发送")
        baseline = {row["_id"] for row in before}
        highwater = max(baseline, default=0)
        started = time.time()
        try:
            receipt = self.send_message(message)
        except Exception as error:
            receipt = TaskResult.business(f"喊话结果未知（{type(error).__name__}），未重发")
        wait = self.shoutbox.confirmation_wait_seconds
        if self.collect_feedback:
            wait = max(wait, self.feedback_timeout)
        time.sleep(min(10, max(0, wait)))
        try:
            after = self._chat_rows(self.read_shoutbox())
        except Exception:
            after = None
        if after is None:
            return TaskResult.business(f"{receipt.message}；喊话回读不可用，未重发")
        now = time.time()
        fresh = [row for row in after if row["_id"] not in baseline and row["_id"] > highwater
                 and started - 2 <= row["_time"] <= now + 2]
        normalize = lambda text: " ".join(text.split())
        own = [row for row in fresh if row["username"] == username
               and normalize(row["message"]) == normalize(message)]
        if len(own) != 1:
            return TaskResult.business(f"{receipt.message}；未能唯一确认本人本次新消息，未重发")
        target = own[0]
        # 反馈必须是新系统记录，且明确 @本人；不能靠用户名子串或旧奖励猜测。
        mention = re.compile(r"@" + re.escape(username) + r"(?![\w])")
        feedback = None
        for row in sorted(fresh, key=lambda item: item["_id"]):
            if (row["_id"] > target["_id"] and row["username"] in ("系统", "系统提示", "system")
                    and 0 <= row["_time"] - target["_time"] <= self.shoutbox.max_row_age_seconds
                    and mention.search(row["message"])):
                feedback = ChatRow(0, row["message"], 0, "row")
                break
        observation = Observation(True, True, feedback=feedback, retry_allowed=False)
        return self.feedback_result(message, observation, negative_terms)

    def claim_task(self, task_id: str) -> TaskResult:
        """任务商店申领：POST /api/v1/tasks/claim {"task_id": int}。

        旧 NexusPHP exam 接口（ajax.php claimTask）在新版已不存在。
        """
        try:
            body = {"task_id": int(str(task_id).strip())}
        except ValueError:
            return TaskResult.fail(f"非法任务 ID：{task_id}")
        response = self.post("/api/v1/tasks/claim", json=body)
        if response is None:
            return TaskResult.business(self.request_error or "任务申领结果未知，未重放")
        if not 200 <= getattr(response, "status_code", 200) < 300:
            return TaskResult.business(f"申领 HTTP {response.status_code}，未重放")
        try:
            payload = response.json()
        except Exception:
            return TaskResult.business("任务申领响应不是 JSON，结果未知，未重放")
        if not isinstance(payload, dict):
            return TaskResult.business("任务申领响应格式异常，结果未知，未重放")
        message = str(payload.get("message") or payload.get("msg") or "申领完成")
        if type(payload.get("code")) is int and payload["code"] == 0:
            data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
            reward = data.get("reward")
            return TaskResult.ok(f"申领成功（奖励 {reward}）" if reward is not None else message)
        if any(term in message for term in (
                "已领取", "已经领取", "重复", "进行中", "名额", "上限", "资格")):
            return TaskResult.idempotent(message)
        return TaskResult.business(message)
