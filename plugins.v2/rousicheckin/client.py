"""PeerGo API 客户端：Cookie Session、登录刷新、签到与通知读取。"""
from __future__ import annotations

from http.cookies import SimpleCookie
from typing import Any, Dict, Optional, Tuple
from uuid import uuid4

import requests


class PeerGoError(RuntimeError):
    """PeerGo API 请求失败。"""


class PeerGoAuthError(PeerGoError):
    """Cookie 与账号认证均不可用。"""


class PeerGoClient:
    BASE_URL = "https://rousi.pro"
    SESSION_PATH = "/api/v1/session"
    ATTENDANCE_PATH = "/api/v1/me/attendance"
    TRAFFIC_PATH = "/api/v1/me/traffic"
    ECONOMY_PATH = "/api/v1/me/economy"
    NOTIFICATIONS_PATH = "/api/v1/me/notifications"
    SESSION_COOKIE_NAME = "__Host-peergo_session"

    def __init__(
        self,
        cookie: str = "",
        *,
        timeout: int = 20,
        proxies: Optional[Dict[str, str]] = None,
        session: Optional[requests.Session] = None,
    ):
        self.timeout = timeout
        self.proxies = proxies
        self.session = session or requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "MoviePilot-RousiCheckin/1.1",
        })
        normalized_cookie = self.normalize_cookie(cookie)
        if normalized_cookie:
            self.session.headers["Cookie"] = normalized_cookie

    def ensure_session(
        self, username: str = "", password: str = ""
    ) -> Tuple[Dict[str, Any], str, bool]:
        """优先复用 Cookie；无效时使用账号密码登录并返回新 Cookie。"""
        session_info = self.get_session()
        if session_info:
            return session_info, self.current_cookie(), False
        if not username or not password:
            raise PeerGoAuthError("Cookie 已失效，且未配置完整账号密码")
        self.session.headers.pop("Cookie", None)
        self.session.cookies.clear()
        session_info = self.login(username, password)
        cookie = self.current_cookie()
        if not cookie:
            raise PeerGoAuthError("登录成功但未获取到 Session Cookie")
        return session_info, cookie, True

    def get_session(self) -> Optional[Dict[str, Any]]:
        response = self._request("GET", self.SESSION_PATH, allow_unauthorized=True)
        if response.status_code in (204, 401):
            return None
        body = self._json(response)
        if not isinstance(body.get("user"), dict) or not body.get("csrf_token"):
            raise PeerGoError("会话响应缺少 user 或 csrf_token")
        return body

    def login(self, username: str, password: str) -> Dict[str, Any]:
        response = self._request(
            "POST",
            self.SESSION_PATH,
            json={"identifier": username, "password": password, "remember_me": True},
            allow_unauthorized=True,
        )
        body = self._json(response, require_success=False)
        if not response.ok:
            if response.status_code == 428:
                raise PeerGoAuthError("账号启用了两步验证，暂不支持自动登录")
            if response.status_code == 429:
                raise PeerGoAuthError("登录尝试过于频繁，请稍后重试")
            raise PeerGoAuthError(self._error_message(body, response.status_code, "账号或密码错误"))
        if not isinstance(body.get("user"), dict) or not body.get("csrf_token"):
            raise PeerGoAuthError("登录响应缺少 user 或 csrf_token")
        return body

    def get_attendance(self) -> Dict[str, Any]:
        return self._get_json(self.ATTENDANCE_PATH)

    def claim_attendance(self, csrf_token: str, mode: str = "fixed") -> Dict[str, Any]:
        response = self._request(
            "POST",
            self.ATTENDANCE_PATH,
            headers={
                "X-CSRF-Token": csrf_token,
                "Idempotency-Key": str(uuid4()),
            },
            json={"mode": mode},
        )
        return self._json(response)

    def get_traffic(self) -> Dict[str, Any]:
        return self._get_json(self.TRAFFIC_PATH)

    def get_economy(self) -> Dict[str, Any]:
        return self._get_json(self.ECONOMY_PATH)

    def get_notifications(self, limit: int = 20, offset: int = 0) -> Dict[str, Any]:
        response = self._request(
            "GET",
            self.NOTIFICATIONS_PATH,
            params={"limit": limit, "offset": offset, "unread_only": "false"},
        )
        return self._json(response)

    def current_cookie(self) -> str:
        values = []
        for cookie in self.session.cookies:
            if cookie.name == self.SESSION_COOKIE_NAME:
                values.append(f"{cookie.name}={cookie.value}")
        if values:
            return "; ".join(values)
        return self.normalize_cookie(self.session.headers.get("Cookie", ""))

    @classmethod
    def normalize_cookie(cls, value: str) -> str:
        text = str(value or "").strip()
        if text.lower().startswith("cookie:"):
            text = text.split(":", 1)[1].strip()
        if not text:
            return ""
        parsed = SimpleCookie()
        try:
            parsed.load(text)
        except Exception:
            return text
        if cls.SESSION_COOKIE_NAME in parsed:
            morsel = parsed[cls.SESSION_COOKIE_NAME]
            return f"{cls.SESSION_COOKIE_NAME}={morsel.value}"
        return text

    def _get_json(self, path: str) -> Dict[str, Any]:
        return self._json(self._request("GET", path))

    def _request(self, method: str, path: str, allow_unauthorized: bool = False, **kwargs):
        response = self.session.request(
            method,
            f"{self.BASE_URL}{path}",
            timeout=self.timeout,
            proxies=self.proxies,
            **kwargs,
        )
        if not allow_unauthorized and response.status_code in (401, 403):
            raise PeerGoAuthError(f"会话认证失败（HTTP {response.status_code}）")
        return response

    def _json(self, response, require_success: bool = True) -> Dict[str, Any]:
        try:
            body = response.json()
        except ValueError as error:
            raise PeerGoError(f"响应不是 JSON（HTTP {response.status_code}）") from error
        if not isinstance(body, dict):
            raise PeerGoError(f"响应格式异常（HTTP {response.status_code}）")
        if require_success and not response.ok:
            raise PeerGoError(self._error_message(body, response.status_code, "请求失败"))
        return body

    @staticmethod
    def _error_message(body: Dict[str, Any], status: int, fallback: str) -> str:
        detail = body.get("detail") or body.get("message") or body.get("title") or fallback
        return f"{detail}（HTTP {status}）"
