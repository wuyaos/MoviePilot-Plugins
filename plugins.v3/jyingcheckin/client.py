"""聚影 jying.top 账密协议客户端（B 路径）。

协议要点（浏览器取证 + docs/jyingcheckin-plan.md 修订 2）：
- 登录 POST /api/app/login/（账密）→ Bearer token，7 天绝对过期，无 refresh；
  多端登录互不踢线，token 失效即整段重登。
- 统计 GET /api/app/checkin/stats/ → {status:"success", checked_today, can_checkin, ...}（status 风格 envelope）。
- 签到 POST /api/app/checkin/do/；幸运签 POST /api/app/checkin/luck-draw/（accountMutation 守卫头待真实运行校准）。
- 本模块只做纯协议（不抛网络异常、不做重试/续登编排），编排归插件入口 run_once。
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import requests

logger = logging.getLogger("JyingCheckin")

BASE_URL = "https://www.jying.top"
LOGIN_PATH = "/api/app/login/"
STATS_PATH = "/api/app/checkin/stats/"
DO_PATH = "/api/app/checkin/do/"
LUCK_PATH = "/api/app/checkin/luck-draw/"
# token 7 天绝对过期（实测 app_user_token_expires = 登录时刻 + 7 天）；
# 本地仅用于展示/预判，真正的失效判据是 401。
TOKEN_TTL_SECONDS = 7 * 24 * 3600
REQUEST_TIMEOUT = 20


@dataclass
class ApiResult:
    """统一协议结果：ok=HTTP 与 envelope 均可解析；auth 失效单独标记供上层续登。"""

    ok: bool
    auth_expired: bool = False
    status: str = ""          # 站点 envelope 的 status 字段（success/error/...）
    message: str = ""         # 站点原文 message/error 文案
    data: dict[str, Any] = field(default_factory=dict)
    http_status: int = 0
    error: str = ""           # 本地错误（网络/解析）


@dataclass
class LoginResult:
    ok: bool
    token: str = ""
    user_id: Any = None
    expires_at: float = 0.0
    message: str = ""
    error: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


def _extract_token(payload: Any) -> str:
    """从登录响应宽容提取 token：data.token / token / data.token.value。"""
    if not isinstance(payload, dict):
        return ""
    for container in (payload, payload.get("data") or {}):
        if not isinstance(container, dict):
            continue
        token = container.get("token") or container.get("access_token")
        if isinstance(token, dict):
            token = token.get("value")
        if isinstance(token, str) and token:
            return token
    return ""


def _extract_user_id(payload: Any) -> Any:
    """从登录/统计响应宽容提取 user id（幸运签守卫头用，取不到为 None）。"""
    if not isinstance(payload, dict):
        return None
    for container in (payload, payload.get("data") or {}, payload.get("user") or {},
                      (payload.get("data") or {}).get("user") if isinstance(payload.get("data"), dict) else {}):
        if not isinstance(container, dict):
            continue
        for key in ("user_id", "userId", "id", "uid"):
            value = container.get(key)
            if value is not None and not isinstance(value, (dict, list)):
                return value
    return None


def _extract_message(payload: Any) -> str:
    if isinstance(payload, dict):
        for key in ("message", "msg", "error", "detail"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
    return ""


class JyingClient:
    """jying.top /api/app/* 协议封装。"""

    def __init__(self, base_url: str = BASE_URL, timeout: int = REQUEST_TIMEOUT):
        self._base = base_url.rstrip("/")
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Origin": self._base,
            "Referer": self._base + "/",
        })

    # ---- 协议方法 -------------------------------------------------------

    def login(self, username: str, password: str) -> LoginResult:
        """账密登录换 token。站点无 refresh 接口，token 失效即整段重登。"""
        if not username or not password:
            return LoginResult(ok=False, message="缺少账号或密码")
        try:
            resp = self._session.post(
                self._base + LOGIN_PATH,
                json={"username": username, "password": password},
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            return LoginResult(ok=False, error=f"network: {exc.__class__.__name__}")
        try:
            payload = resp.json()
        except ValueError:
            payload = {}
        token = _extract_token(payload)
        if resp.status_code != 200 or not token:
            message = _extract_message(payload) or f"HTTP {resp.status_code}"
            logger.info("聚影登录失败：%s", message)
            return LoginResult(ok=False, message=message, raw=payload if isinstance(payload, dict) else {})
        return LoginResult(
            ok=True,
            token=token,
            user_id=_extract_user_id(payload),
            expires_at=time.time() + TOKEN_TTL_SECONDS,
            raw=payload if isinstance(payload, dict) else {},
        )

    def stats(self, token: str) -> ApiResult:
        """签到统计（含 checked_today / can_checkin），也用作 token 存活探测。"""
        return self._get(STATS_PATH, token)

    def do_checkin(self, token: str) -> ApiResult:
        """普通签到。请求体按空 JSON 对象（对齐 Key 通道幂等约定，B 通道待真实校准）。"""
        return self._post(DO_PATH, token, json_body={})

    def luck_draw(self, token: str, user_id: Any = None) -> ApiResult:
        """幸运签。accountMutation 守卫头取值待校准：user_id 已知才携带。"""
        headers = {}
        if user_id is not None:
            headers["X-Expected-App-User-Id"] = str(user_id)
            headers["X-App-User-Token"] = token
        return self._post(LUCK_PATH, token, json_body={}, extra_headers=headers)

    # ---- 内部 -----------------------------------------------------------

    def _auth_headers(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def _get(self, path: str, token: str) -> ApiResult:
        try:
            resp = self._session.get(self._base + path, headers=self._auth_headers(token), timeout=self._timeout)
        except requests.RequestException as exc:
            return ApiResult(ok=False, error=f"network: {exc.__class__.__name__}")
        return self._parse(resp)

    def _post(self, path: str, token: str, json_body: dict | None = None,
              extra_headers: dict[str, str] | None = None) -> ApiResult:
        headers = self._auth_headers(token)
        if extra_headers:
            headers.update(extra_headers)
        try:
            resp = self._session.post(self._base + path, json=json_body if json_body is not None else {},
                                      headers=headers, timeout=self._timeout)
        except requests.RequestException as exc:
            return ApiResult(ok=False, error=f"network: {exc.__class__.__name__}")
        return self._parse(resp)

    def _parse(self, resp: requests.Response) -> ApiResult:
        """解析 status 风格 envelope；401/403 标记 auth_expired 供上层整段重登。"""
        if resp.status_code in (401, 403):
            return ApiResult(ok=False, auth_expired=True, http_status=resp.status_code,
                             message=_extract_message(self._safe_json(resp)))
        try:
            payload = resp.json()
        except ValueError:
            return ApiResult(ok=False, http_status=resp.status_code,
                             error=f"non-json: HTTP {resp.status_code}")
        if not isinstance(payload, dict):
            return ApiResult(ok=False, http_status=resp.status_code, error="non-object envelope")
        status = str(payload.get("status") or ("success" if resp.status_code == 200 and payload.get("success") else ""))
        return ApiResult(
            ok=resp.status_code == 200 and status in ("success", "ok"),
            status=status,
            message=_extract_message(payload),
            data=payload,
            http_status=resp.status_code,
        )

    @staticmethod
    def _safe_json(resp: requests.Response) -> Any:
        try:
            return resp.json()
        except ValueError:
            return {}
