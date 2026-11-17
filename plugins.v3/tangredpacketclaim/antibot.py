# input: 站点 Cookie、requests Session、插件数据读写
# output: antibot token（X-RedPacket-Token/Device 请求头）
# pos: 不可躺红包 antibot 适配：challenge → pow/turnstile 求解 → verify → token 缓存
"""不可躺红包 antibot（人机验证）适配。

站点流程（自 tangpt 首页脚本逆向）：
1. POST /api/redpacket/antibot/challenge（头 X-RedPacket-Device），返回
   {mode: disabled|pow|turnstile, challenge_id, site_key?, action?, salt?, difficulty_bits?}
2. mode=disabled 直接放行；pow 在本地解 SHA-256 前导零位；
   turnstile 先由 CloakBrowser 渲染一次（headless 单次 25s 预算）；浏览器失败
   时按站点脚本同款语义降级：challenge {fallback:1} → mode=pow 本地求解。
3. POST /api/redpacket/antibot/verify 提交解，返回
   {token, expires_at, max_uses, risk_level, method, token_id}。
4. 后续 claim 请求带 X-RedPacket-Token + X-RedPacket-Device；HTTP 428 表示
   token 失效/耗尽，清缓存重新验证。

device id 与 token 均持久化到插件数据（antibot_device / antibot_token），
device 跨轮复用，token 按 expires_at/max_uses 复用。
"""
from __future__ import annotations

import hashlib
import json
import random
import threading
import time
from typing import Any, Callable, Dict, Optional

import requests

ANTIBOT_CHALLENGE = "/api/redpacket/antibot/challenge"
ANTIBOT_VERIFY = "/api/redpacket/antibot/verify"
DEVICE_DATA_KEY = "antibot_device"
TOKEN_DATA_KEY = "antibot_token"
POW_MAX_ATTEMPTS = 5_000_000
POW_MAX_ATTEMPTS = 5_000_000
TURNSTILE_PAGE_TIMEOUT_MS = 30_000
# 浏览器 Turnstile 只给一次短预算：站点自身脚本对 Turnstile 也只等 12s 就降级
# fallback PoW；qnap CloakBrowser 长时间无回调时不必反复烧时间。
TURNSTILE_TOKEN_TIMEOUT_MS = 25_000


class AntibotError(RuntimeError):
    """人机验证流程失败。"""


def solve_pow(salt: str, challenge_id: str, difficulty_bits: int,
              max_attempts: int = POW_MAX_ATTEMPTS) -> int:
    """与站点 redpacket-pow-worker.js 同算法：sha256(salt:challenge_id:nonce) 前
    difficulty_bits 位二进制为 0。"""
    bits = max(int(difficulty_bits or 0), 0)
    if bits <= 0:
        return 0
    prefix = f"{salt}:{challenge_id}:"
    nonce = random.randrange(1_000_000_000)
    full_nibbles, rem = divmod(bits, 4)
    for _ in range(max_attempts):
        digest = hashlib.sha256((prefix + str(nonce)).encode("utf-8")).hexdigest()
        if full_nibbles and digest[:full_nibbles] != "0" * full_nibbles:
            nonce += 1
            continue
        if rem:
            nibble = int(digest[full_nibbles], 16)
            if nibble >> (4 - rem):
                nonce += 1
                continue
        return nonce
    raise AntibotError(f"PoW 求解超过 {max_attempts} 次未成功（difficulty_bits={bits}）")


def solve_turnstile_in_browser(base_url: str, cookie: str, site_key: str, action: str,
                               headless: bool, timeout_ms: int = TURNSTILE_TOKEN_TIMEOUT_MS) -> str:
    """用宿主 CloakBrowser 打开站点页面，渲染 Turnstile 并取 token。

    同步 Playwright 不能跑在宿主事件循环线程，参照 autoptcheckin 的
    run_isolated：独立线程 + 阻塞 join。
    """
    outcome: list = []

    def invoke():
        try:
            outcome.append((True, _browser_impl(base_url, cookie, site_key, action, headless, timeout_ms)))
        except BaseException as exc:  # noqa: BLE001 - 原样传回调用线程
            outcome.append((False, exc))

    worker = threading.Thread(target=invoke, daemon=True)
    worker.start()
    worker.join(timeout=(timeout_ms + TURNSTILE_PAGE_TIMEOUT_MS) / 1000 + 30)
    if worker.is_alive():
        raise AntibotError("浏览器人机验证超时未返回")
    if not outcome:
        raise AntibotError("浏览器人机验证无结果")
    ok, value = outcome[0]
    if ok:
        return value
    raise value


def _browser_impl(base_url: str, cookie: str, site_key: str, action: str,
                  headless: bool, timeout_ms: int) -> str:
    try:
        from app.sdk.browser import launch_browser_context
    except ImportError as exc:
        raise AntibotError("宿主浏览器组件不可用（app.sdk.browser）") from exc
    from urllib.parse import urlsplit

    context = None
    try:
        kwargs = {"headless": headless, "humanize": True, "locale": "zh-CN"}
        context = launch_browser_context(**kwargs)
        page = context.new_page()
        host = urlsplit(base_url).hostname or ""
        if cookie:
            cookies = []
            for pair in cookie.split(";"):
                key, sep, value = pair.strip().partition("=")
                if sep:
                    cookies.append({"name": key, "value": value, "domain": host, "path": "/"})
            if cookies:
                context.add_cookies(cookies)
        page.goto(f"{base_url}/index.php", wait_until="domcontentloaded",
                  timeout=TURNSTILE_PAGE_TIMEOUT_MS)
        token = page.evaluate(
            """async ({siteKey, action, timeoutMs}) => {
                const loadScript = () => new Promise((res, rej) => {
                    if (window.turnstile && window.turnstile.render) return res();
                    const s = document.createElement('script');
                    s.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
                    s.onload = res;
                    s.onerror = () => rej(new Error('turnstile 脚本加载失败'));
                    document.head.appendChild(s);
                });
                await loadScript();
                return await new Promise((res, rej) => {
                    const c = document.createElement('div');
                    document.body.appendChild(c);
                    let done = false;
                    const finish = (fn, v) => { if (!done) { done = true; fn(v); } };
                    const guard = setTimeout(() => finish(rej, new Error('人机验证 token 超时')), timeoutMs);
                    const id = turnstile.render(c, {
                        sitekey: siteKey,
                        action: action || 'redpacket_claim',
                        execution: 'execute',
                        appearance: 'interaction-only',
                        callback: t => { clearTimeout(guard); finish(res, t); },
                        'error-callback': code => { clearTimeout(guard); finish(rej, new Error('turnstile 错误码 ' + code)); },
                        'timeout-callback': () => { clearTimeout(guard); finish(rej, new Error('turnstile 组件超时')); }
                    });
                    if (typeof turnstile.execute === 'function') turnstile.execute(id);
                });
            }""",
            {"siteKey": site_key, "action": action or "redpacket_claim", "timeoutMs": timeout_ms},
        )
        if not token:
            raise AntibotError("浏览器未返回 Turnstile token")
        return token
    finally:
        if context:
            try:
                context.close()
            except Exception:
                pass


class AntibotClient:
    """antibot token 获取与缓存；HTTP 请求复用插件 requests Session（带站点 Cookie）。"""

    def __init__(self, base_url: str, cookie: str, data_get: Callable[[str], Any],
                 data_set: Callable[[str, Any], None], log=None):
        self.base_url = base_url.rstrip("/")
        self.cookie = cookie or ""
        self._data_get = data_get
        self._data_set = data_set
        self._log = log or (lambda *a, **k: None)
        self._lock = threading.Lock()
        self._disabled_until = 0.0
        self._disabled_until = 0.0
    # ---- device / token 持久化 ------------------------------------------

    def device(self) -> str:
        device = self._data_get(DEVICE_DATA_KEY)
        if isinstance(device, str) and device.strip():
            return device.strip()
        chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        device = "".join(random.choice(chars) for _ in range(32))
        self._data_set(DEVICE_DATA_KEY, device)
        return device

    def cached_token(self) -> Optional[Dict[str, Any]]:
        raw = self._data_get(TOKEN_DATA_KEY)
        if not raw:
            return None
        try:
            state = raw if isinstance(raw, dict) else json.loads(raw)
        except (ValueError, TypeError):
            self.invalidate()
            return None
        token = (state or {}).get("token")
        if not token:
            self.invalidate()
            return None
        now = int(time.time())
        if int(state.get("expires_at") or 0) <= now + 5:
            return None
        max_uses = int(state.get("max_uses") or 0)
        used = int(state.get("used") or 0)
        if max_uses and used >= max_uses:
            self.invalidate()
            return None
        return state

    def invalidate(self) -> None:
        self._data_set(TOKEN_DATA_KEY, "")

    def mark_used(self) -> None:
        state = self._data_get(TOKEN_DATA_KEY)
        if isinstance(state, dict):
            state["used"] = int(state.get("used") or 0) + 1
            self._data_set(TOKEN_DATA_KEY, state)

    # ---- 对外接口 --------------------------------------------------------

    def claim_headers(self) -> Dict[str, str]:
        state = self.cached_token()
        if not state:
            return {}
        return {"X-RedPacket-Token": state["token"], "X-RedPacket-Device": self.device()}

    def ensure_token(self, session: requests.Session) -> Optional[Dict[str, Any]]:
        """确保存在可用 token；mode=disabled 返回 None。并发下用锁串行化。"""
        with self._lock:
            state = self.cached_token()
            if state:
                return state
            if time.time() < self._disabled_until:
                return None
            challenge = self._api(session, ANTIBOT_CHALLENGE, data={})
            mode = str((challenge or {}).get("mode") or "")
            if not challenge or challenge.get("ok") is False:
                raise AntibotError(str(challenge.get("message") or "antibot challenge 请求失败"))
            if mode == "disabled":
                self._disabled_until = time.time() + 3600
                self._log("antibot 未启用（mode=disabled），直接领取")
                return None
            mode, verify_payload, effective = self._solve_challenge(session, challenge)
            if mode == "disabled":
                # 主流程或 fallback 通道都可能返回 disabled：统一短路
                self._disabled_until = time.time() + 3600
                return None
            verify = self._api(session, ANTIBOT_VERIFY,
                               data={"challenge_id": effective.get("challenge_id"),
                                     "mode": mode, **verify_payload})
            if not verify or verify.get("ok") is False or not verify.get("token"):
                raise AntibotError(str((verify or {}).get("message") or "antibot verify 失败"))
            state = {
                "token": verify["token"],
                "expires_at": int(verify.get("expires_at") or 0),
                "max_uses": int(verify.get("max_uses") or 0),
                "used": 0,
                "risk_level": verify.get("risk_level") or "normal",
                "method": verify.get("method") or "",
                "token_id": verify.get("token_id") or "",
            }
            self._data_set(TOKEN_DATA_KEY, state)
            self._log(f"antibot token 获取成功 method={state['method']} "
                      f"max_uses={state['max_uses']} expires_at={state['expires_at']}")
            return state

    # ---- 内部 ------------------------------------------------------------

    def _solve_challenge(self, session: requests.Session,
                         challenge: Dict[str, Any]) -> tuple:
        """按 challenge.mode 求解，返回 (mode, verify_payload, 生效 challenge)。

        turnstile 先浏览器渲染一次（headless，真实 Chrome 实测同款渲染 9.9s 可
        拿 token；qnap CloakBrowser 会被 Cloudflare 卡死，故不做 headful 重试）；
        失败后走站点自带的降级通道：challenge {fallback:1} → mode=pow 本地求解，
        与站点脚本「Turnstile 12s watchdog → fallback」语义一致。
        """
        mode = str(challenge.get("mode") or "")
        if mode == "pow":
            self._log("antibot 走 PoW 验证（纯本地计算）")
            return mode, self._pow_payload(challenge), challenge
        if mode == "turnstile":
            try:
                token = self._solve_turnstile(challenge)
            except AntibotError as err:
                self._log(f"Turnstile 浏览器验证失败，降级 fallback PoW：{err}")
                return self._fallback_pow(session)
            self._log("antibot 走 Turnstile 验证（CloakBrowser）")
            return mode, {"turnstile_token": token}, challenge
        raise AntibotError(f"未知 antibot 模式：{mode}")

    def _fallback_pow(self, session: requests.Session) -> tuple:
        """站点降级通道：challenge {fallback:1} → pow 本地求解。"""
        challenge = self._api(session, ANTIBOT_CHALLENGE, data={"fallback": 1})
        if not challenge or challenge.get("ok") is False:
            raise AntibotError(str((challenge or {}).get("message")
                                   or "antibot fallback challenge 请求失败"))
        mode = str(challenge.get("mode") or "")
        if mode == "disabled":
            return mode, {}, challenge
        if mode != "pow":
            raise AntibotError(f"antibot fallback 返回未知模式：{mode}，无法降级")
        self._log("antibot fallback 走 PoW 验证（纯本地计算）")
        return mode, self._pow_payload(challenge), challenge

    @staticmethod
    def _pow_payload(challenge: Dict[str, Any]) -> Dict[str, Any]:
        nonce = solve_pow(str(challenge.get("salt")), str(challenge.get("challenge_id")),
                          int(challenge.get("difficulty_bits") or 0))
        # 站点脚本恒定提交 confirm（「本人操作」勾选，未弹窗时为 0）；服务端实测
        # 接受 confirm=0/1/缺省，此处与站点客户端保持一致提交 0。
        return {"nonce": nonce, "confirm": 0}

    def _solve_turnstile(self, challenge: Dict[str, Any]) -> str:
        site_key = str(challenge.get("site_key") or "")
        action = str(challenge.get("action") or "redpacket_claim")
        if not site_key:
            raise AntibotError("challenge 缺少 site_key，无法进行 Turnstile 验证")
        try:
            return solve_turnstile_in_browser(self.base_url, self.cookie, site_key,
                                              action, headless=True)
        except Exception as err:
            raise AntibotError(f"Turnstile 浏览器验证失败（headless）：{err}") from err

    def _api(self, session: requests.Session, path: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            resp = session.post(f"{self.base_url}{path}", data=data, timeout=15,
                                headers={"X-RedPacket-Device": self.device()})
        except requests.RequestException as err:
            raise AntibotError(f"antibot 接口请求失败：{path}，{err}") from err
        try:
            return resp.json()
        except ValueError:
            raise AntibotError(f"antibot 接口非 JSON 响应 HTTP {resp.status_code}: {(resp.text or '')[:120]}")
