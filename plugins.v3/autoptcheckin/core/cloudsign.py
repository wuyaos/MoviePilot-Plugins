# -*- coding: utf-8 -*-
"""Browserless 云签引擎（BQL）：audiences / mua_xloli / vclib 三个 CF 盾站。

设计约束（与 qingyukb/MoviePilot-Plugins 的差异）：
- 不引入其 200 行全量注入脚本与通用规则引擎，只保留「solve → reconnect → 注入 → 提交 → verify」
  主干与三站小规则；签到结果判定用各站关键词在云签会话内完成（CF 挡住本地 HTTP 回读，
  无法复用 RecordSpec 回读，这一点是有意偏离并在 AGENTS.md 记录）。
- 失败分类遵守插件既有语义：solve/验证未完成 → protocol_pending（下轮重入队）；
  BQL 请求/鉴权/网络失败 → network_error；仅提交后回读明确未签 → failed。
- 消息不含 token，只含 Browserless host，避免密钥进历史与通知。
"""
from __future__ import annotations

import json
import logging
import urllib.parse
from dataclasses import dataclass
from typing import Any

import requests

logger = logging.getLogger(__name__)

DEFAULT_BROWSERLESS_URL = "https://production-sfo.browserless.io"
# 注入脚本自身等待预算之外的 evaluate 步骤余量，防止脚本在等待循环里被步骤超时掐死
INJECT_STEP_MARGIN_MS = 12000
DEFAULT_RECONNECT_WAIT_MS = 60000
DEFAULT_SOLVE_TIMEOUT_MS = 40000

# 走云签的站点（CF 盾仿真站）；配置了 token 才实际分流
CLOUD_SITES = ("audiences", "mua_xloli", "vclib")

# 各站小规则：路径 / 提交方式 / 等待预算 / 判定关键词。
# submit=auto 两段式（solve 拿 token → reconnect 留会话 → 第二段注入+兜底 POST+verify）；
# submit=click 单段式（solve 后原生点击提交按钮，mua_xloli 沿用 qingyukb 实测选择器）。
CLOUD_RULES: dict[str, dict[str, Any]] = {
    "audiences": {
        "path": "/attendance.php",
        "submit": "auto",
        "before_wait": 15000,
        "solve_timeout": DEFAULT_SOLVE_TIMEOUT_MS,
        "auto_wait": 30000,
        "wait": 15000,
        "verify": "/attendance.php",
        "verify_wait": 15000,
        "success": ["签到成功", "簽到成功", "成功签到", "签到完成", "领取成功"],
        "already": ["今日已签到", "今天已经签到", "您今天已经签到", "已经签到", "已签到",
                    "今日已领取", "已连续签到", "明日再来", "明天再来"],
        "pending": ["验证通过后将自动完成签到", "完成人机验证即可领取今日爆米花奖励"],
    },
    "mua_xloli": {
        # 2026-10-24: 单段 click 在已签页等不到提交表单（qnap 实测 10s 超时误判 network_error），
        # 与 audiences 同款两段式：第一段回读即可判 already，未签才注入提交。
        "path": "/attendance.php",
        "submit": "auto",
        "before_wait": 15000,
        "solve_timeout": DEFAULT_SOLVE_TIMEOUT_MS,
        "auto_wait": 30000,
        "wait": 8000,
        "verify": "/attendance.php",
        "verify_wait": 15000,
        "success": ["签到成功", "簽到成功"],
        "already": ["今日已签到", "今天已经签到", "您今天已经签到", "已经签到", "已签到"],
        "pending": [],
    },
    "vclib": {
        # DOM 未校准：保守两段式，靠注入脚本的表单兜底 POST；首版可能签不上，按 diag 迭代
        "path": "/attendance.php",
        "submit": "auto",
        "before_wait": 15000,
        "solve_timeout": DEFAULT_SOLVE_TIMEOUT_MS,
        "auto_wait": 30000,
        "wait": 8000,
        "success": ["签到成功", "簽到成功"],
        "already": ["今日已签到", "今天已经签到", "已签到"],
        # 2026-10-26: 原词表 ["验证", "人机"] 单字宽泛匹配——站点公告/导航含「验证」即误判
        # 「仍待人机验证」（00:06 轮实况）。改为 audiences 同款完整短语，仅真验证引导文案命中。
        "pending": ["完成人机验证", "人机验证", "验证通过后"],
    },
}


class CloudSignError(Exception):
    """BQL 请求层失败。kind: auth / quota / transient / request"""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind
        self.message = message


@dataclass
class CloudResult:
    status: str  # success / failed / protocol_pending / network_error
    message: str


def enabled(site_id: str) -> bool:
    return site_id in CLOUD_SITES


def configured(config: dict) -> bool:
    url = str((config or {}).get("browserless_url") or "").strip()
    token = str((config or {}).get("browserless_token") or "").strip()
    return bool(token) or bool(url and url != DEFAULT_BROWSERLESS_URL)


def bql_endpoint(address: str, token: str = "") -> str:
    """规范化 BrowserQL 端点：根地址自动补 /stealth/bql；已以 /bql 结尾的原样保留。"""
    address, token = str(address or "").strip(), str(token or "").strip()
    if not address:
        address = DEFAULT_BROWSERLESS_URL
    parsed = urllib.parse.urlparse(address)
    if parsed.scheme not in {"http", "https"}:
        raise CloudSignError("request", f"Browserless 地址必须以 http:// 或 https:// 开头：{parsed.scheme}")
    path = parsed.path.rstrip("/")
    if not path.endswith("/bql"):
        path = (path + "/bql") if path.endswith("/stealth") else (path + "/stealth/bql")
    query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    if token:
        query["token"] = token
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, path, "",
                                    urllib.parse.urlencode(query), ""))


def session_endpoint(address: str, token: str) -> str:
    """reconnect 返回的会话地址不含 token，只补查询参数、不改路径（含 /e/<uuid> 前缀）。"""
    address = str(address or "").strip()
    if not address:
        return ""
    if not token:
        return address
    parsed = urllib.parse.urlparse(address)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    query["token"] = token
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, "",
                                    urllib.parse.urlencode(query), ""))


def _host(address: str) -> str:
    try:
        return urllib.parse.urlparse(address).hostname or address
    except (ValueError, AttributeError):
        return address


def _bql_request(endpoint: str, payload: dict, timeout: float) -> dict:
    try:
        resp = requests.post(endpoint, json=payload, timeout=timeout)
    except requests.exceptions.Timeout as exc:
        raise CloudSignError("transient", f"云签请求超时（{_host(endpoint)}）") from exc
    except requests.exceptions.RequestException as exc:
        raise CloudSignError("transient", f"云签请求失败（{_host(endpoint)}）：{type(exc).__name__}") from exc
    if resp.status_code in (401, 403):
        raise CloudSignError("auth", f"云签鉴权失败（{_host(endpoint)} HTTP {resp.status_code}），请检查 Browserless Token")
    if resp.status_code == 429:
        raise CloudSignError("quota", f"云签配额超限（{_host(endpoint)} HTTP 429）")
    if resp.status_code != 200:
        raise CloudSignError("request", f"云签请求异常（{_host(endpoint)} HTTP {resp.status_code}）")
    try:
        data = resp.json()
    except ValueError as exc:
        raise CloudSignError("request", f"云签响应不是 JSON（{_host(endpoint)}）") from exc
    if not isinstance(data.get("data"), dict):
        # 校验级错误（非执行失败）：没有 data 可用，保持异常语义
        raise CloudSignError("request", f"云签 GraphQL 错误：{json.dumps((data.get('errors') or [])[:1], ensure_ascii=False)[:200]}")
    result = data["data"]
    errors = data.get("errors") or []
    if errors:
        # 2026-10-25 官方语义（docs.browserless.io → BQL Error Handling）：
        # 失败步骤不中止 mutation，HTTP 200 下 errors[] 与 data 并存，失败字段为 null、
        # 其余字段照常执行。errors 不抛：响应里的回读 HTML（after/verifyPage）是分类仲裁
        # 所需证据（如 evaluate 撞导航时页面可能已自动签到），调用方按分类结果消费。
        result["_errors"] = [
            f"{e.get('path')[0] if isinstance(e.get('path'), list) and e.get('path') else '?'}: {str(e.get('message') or '')[:120]}"
            for e in errors
        ]
        logger.warning("云签 BQL 步骤失败（继续按回读分类）：%s", result["_errors"])
    return result


def _error_suffix(data: dict) -> str:
    """把 _bql_request 记录的步骤失败摘要拼进结果消息，便于诊断（不改变状态分类）。"""
    errors = data.get("_errors") or []
    if not errors:
        return ""
    return f"；BQL步骤失败[{'; '.join(errors[:2])}]"


def cookie_objects(cookie: str, url: str) -> list[dict]:
    """「k=v; k2=v2」→ BQL CookieInput 列表（域取签到页 host，浏览器侧安全属性从 URL 推断）。"""
    host = urllib.parse.urlparse(url).hostname
    if not host or not cookie.strip():
        return []
    items = []
    for chunk in cookie.split(";"):
        if "=" not in chunk:
            continue
        name, _, value = chunk.strip().partition("=")
        if not name:
            continue
        items.append({"name": name.strip(), "value": value.strip(), "domain": host,
                      "path": "/", "secure": url.startswith("https")})
    return items


def _solve_query() -> str:
    return """mutation CloudSolve($cookies:[CookieInput!]! $url:String! $beforeWait:Float! $solveTimeout:Float! $reconnectTimeout:Float!) {
      cookies(cookies:$cookies){cookies{name}}
      goto(url:$url,waitUntil:domContentLoaded){status}
      waitBefore:waitForTimeout(time:$beforeWait){time}
      solve:solve(timeout:$solveTimeout){found solved token}
      session:reconnect(timeout:$reconnectTimeout){browserQLEndpoint}
      after:html{html}
    }"""


def _click_query() -> str:
    return """mutation CloudClick($cookies:[CookieInput!]! $url:String! $beforeWait:Float! $solveTimeout:Float! $selector:String! $turnstileWait:Float! $wait:Float!) {
      cookies(cookies:$cookies){cookies{name}}
      goto(url:$url,waitUntil:domContentLoaded){status}
      waitBefore:waitForTimeout(time:$beforeWait){time}
      solve:solve(timeout:$solveTimeout){found solved}
      waitForTurnstile:waitForSelector(selector:$selector,timeout:$turnstileWait,visible:true){selector time}
      submit:click(selector:$selector){selector time}
      waitAfter:waitForTimeout(time:$wait){time}
      after:html{html}
    }"""


def _inject_query(with_verify: bool) -> str:
    verify = ""
    variables = ("$cookies:[CookieInput!]! $url:String! $beforeWait:Float! $wait:Float!"
                 " $autoSubmit:String! $autoTimeout:Float!")
    if with_verify:
        variables += " $verifyUrl:String! $verifyWait:Float!"
        verify = """verify:goto(url:$verifyUrl,waitUntil:domContentLoaded){status}
      waitForVerify:waitForTimeout(time:$verifyWait){time}
      verifyPage:html{html}"""
    return f"""mutation CloudSubmit({variables}) {{
      cookies(cookies:$cookies){{cookies{{name}}}}
      goto(url:$url,waitUntil:domContentLoaded){{status}}
      waitBefore:waitForTimeout(time:$beforeWait){{time}}
      submit:evaluate(content:$autoSubmit,timeout:$autoTimeout){{value}}
      waitAfter:waitForTimeout(time:$wait){{time}}
      autoDiag:evaluate(content:"JSON.stringify(window.__ptsignin_auto || null)"){{value}}
      response:evaluate(content:"JSON.stringify(window.__ptsignin_response || null)"){{value}}
      after:html{{html}}
      {verify}
    }}"""


def inject_script(token: str, rule: dict) -> str:
    """简化版 token 注入脚本：回填 → 调回调 → 仍未提交则同源表单兜底 POST。

    每步写 window.__ptsignin_auto / sessionStorage；结果写 window.__ptsignin_response。
    脚本预算 rule['auto_wait']，调用方 evaluate 超时必须是 auto_wait + INJECT_STEP_MARGIN_MS。
    """
    pending = json.dumps([str(w) for w in (rule.get("pending") or [])], ensure_ascii=False)
    return """(async () => {
  const solveToken = %s;
  const pendingWords = %s;
  const waitBudget = %d;
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const diag = {url: location.href, token: false, src: null, cb: null, post: null, still: null, text: ''};
  const save = () => { try { window.__ptsignin_auto = diag; sessionStorage.setItem('__ptsignin_auto', JSON.stringify(diag)); } catch (err) {} };
  save();
  const deadline = Date.now() + waitBudget;
  const picker = () => {
    const roots = [document];
    for (let i = 0; i < roots.length; i += 1) {
      roots[i].querySelectorAll('*').forEach((el) => { if (el.shadowRoot && roots.indexOf(el.shadowRoot) < 0) roots.push(el.shadowRoot); });
    }
    return (selector) => {
      const found = [];
      roots.forEach((root) => root.querySelectorAll(selector).forEach((node) => { if (found.indexOf(node) < 0) found.push(node); }));
      return found;
    };
  };
  let pick = picker();
  const readApi = () => { try { return (window.turnstile && typeof window.turnstile.getResponse === 'function') ? (window.turnstile.getResponse() || '').trim() : ''; } catch (err) { return ''; } };
  const putToken = (value) => pick('input[name=cf-turnstile-response], textarea[name=cf-turnstile-response]').forEach((node) => { node.value = value; node.dispatchEvent(new Event('input', {bubbles: true})); node.dispatchEvent(new Event('change', {bubbles: true})); });
  let token = (solveToken || '').trim();
  if (token) diag.src = 'solve';
  while (!token && Date.now() < deadline) {
    await sleep(250);
    pick = picker();
    const inputs = pick('input[name=cf-turnstile-response], textarea[name=cf-turnstile-response]');
    token = (inputs.map((n) => (n.value || '').trim()).filter(Boolean)[0] || '') || readApi();
    if (token) diag.src = 'late';
  }
  diag.token = !!token;
  if (token) putToken(token);
  const callSiteCallback = () => {
    const node = pick('[data-callback]')[0];
    const name = node ? node.getAttribute('data-callback') : null;
    const cands = [name, 'onTurnstileSuccess', 'onSuccess', 'turnstileCallback', 'callback'].filter(Boolean);
    for (const cand of cands) {
      try { if (typeof window[cand] === 'function') { window[cand](token); diag.cb = cand; return true; } } catch (err) {}
    }
    return false;
  };
  const stillPending = () => { const text = (document.body && document.body.innerText) || ''; return pendingWords.some((w) => w && text.indexOf(w) !== -1); };
  const formDiag = () => {
    const form = pick('form').filter((f) => /attendance/i.test(f.getAttribute('action') || ''))[0] || pick('form[action]')[0] || null;
    if (!form) return null;
    const data = new FormData(form);
    const submit = form.querySelector('button[type="submit"], input[type="submit"], button:not([type])');
    if (submit && submit.name && !submit.disabled && !data.has(submit.name)) data.append(submit.name, submit.value || '');
    if (token) data.set('cf-turnstile-response', token);
    return {form, data};
  };
  if (!callSiteCallback()) {
    while (Date.now() < deadline && (!pendingWords.length || stillPending())) {
      await sleep(500);
      if (callSiteCallback()) break;
    }
  }
  diag.still = pendingWords.length ? stillPending() : null;
  const packed = formDiag();
  if (packed && (diag.still !== false || !diag.cb)) {
    const action = new URL(packed.form.getAttribute('action') || location.href, location.href);
    if (action.origin !== location.origin) { diag.post = 'post-blocked'; }
    else {
      try {
        const resp = await fetch(action.href, {method: 'POST', credentials: 'same-origin', body: packed.data});
        window.__ptsignin_response = {status: resp.status, url: resp.url, text: await resp.text()};
        diag.post = resp.status;
      } catch (err) { diag.post = 'error'; }
    }
  }
  diag.text = ((document.body && document.body.innerText) || '').slice(0, 300);
  save();
  return JSON.stringify(diag);
})()""" % (json.dumps(token or ""), pending, int(rule.get("auto_wait") or 30000))


def _classify(html: str, rule: dict) -> str:
    """按 success → already → pending 顺序匹配关键词（成功页常带「已连续签到 N 天」，先判成功）。"""
    text = html or ""
    for word in rule.get("success") or []:
        if word in text:
            return "success"
    for word in rule.get("already") or []:
        if word in text:
            return "already"
    for word in rule.get("pending") or []:
        if word in text:
            return "pending"
    return "unknown"


def _page_text(html: str, limit: int = 160) -> str:
    import re
    text = re.sub(r"<[^>]+>", " ", html or "")
    return " ".join(text.split())[:limit]


def _result(kind: str, message: str) -> CloudResult:
    return CloudResult(kind, message)


def sign(site_id: str, base_url: str, cookie: str, config: dict) -> CloudResult:
    """执行云签。返回 CloudResult，status 已是插件结果枚举。"""
    rule = CLOUD_RULES.get(site_id)
    if not rule:
        return _result("network_error", "云签未适配该站点")
    base_url = str(base_url or "").strip().rstrip("/")
    target = base_url + rule["path"]
    cookies = cookie_objects(cookie, target)
    if not cookies:
        return _result("failed", "云签缺少数据：站点 Cookie 为空或格式无效")
    url = str((config or {}).get("browserless_url") or "").strip()
    token = str((config or {}).get("browserless_token") or "").strip()
    try:
        endpoint = bql_endpoint(url, token)
    except CloudSignError as exc:
        return _result("network_error", exc.message)
    try:
        if rule.get("submit") == "click":
            return _sign_click(endpoint, token, target, cookies, rule)
        return _sign_auto(endpoint, token, target, cookies, rule)
    except CloudSignError as exc:
        return _result("network_error", exc.message)


def _sign_click(endpoint: str, token: str, target: str, cookies: list, rule: dict) -> CloudResult:
    data = _bql_request(endpoint, {
        "query": _click_query(),
        "variables": {
            "cookies": cookies, "url": target,
            "beforeWait": rule.get("before_wait", 12000),
            "solveTimeout": rule.get("solve_timeout", DEFAULT_SOLVE_TIMEOUT_MS),
            "selector": rule["click_selector"],
            "turnstileWait": 10000, "wait": rule.get("wait", 6000),
        },
    }, timeout=75)
    html = str((data.get("after") or {}).get("html") or "")
    state = _classify(html, rule)
    result = _state_result(state, rule, clicked=True, page_html=html)
    if result.status != "success":
        return CloudResult(result.status, f"{result.message}{_error_suffix(data)}")
    return result


def _sign_auto(endpoint: str, token: str, target: str, cookies: list, rule: dict) -> CloudResult:
    stage1 = _bql_request(endpoint, {
        "query": _solve_query(),
        "variables": {
            "cookies": cookies, "url": target,
            "beforeWait": rule.get("before_wait", 15000),
            "solveTimeout": rule.get("solve_timeout", DEFAULT_SOLVE_TIMEOUT_MS),
            "reconnectTimeout": DEFAULT_RECONNECT_WAIT_MS,
        },
    }, timeout=75)
    # 第一段页面若已能判定成功/已签，不必再跑第二段
    state = _classify(str((stage1.get("after") or {}).get("html") or ""), rule)
    if state in ("success", "already"):
        return _state_result(state, rule)
    solve_token = str(((stage1.get("solve") or {}).get("token")) or "").strip()
    if not solve_token:
        return _result("protocol_pending", f"云签 solve 失败：未获取到 Turnstile token{_error_suffix(stage1)}")
    session_url = session_endpoint(str(((stage1.get("session") or {}).get("browserQLEndpoint")) or ""), token)
    stage2_endpoint = session_url or endpoint
    verify = rule.get("verify")
    variables = {
        "cookies": cookies, "url": target, "beforeWait": 3000,
        "wait": rule.get("wait", 6000),
        "autoSubmit": inject_script(solve_token, rule),
        "autoTimeout": int(rule.get("auto_wait") or 30000) + INJECT_STEP_MARGIN_MS,
    }
    if verify:
        variables["verifyUrl"] = base_target(target, verify)
        variables["verifyWait"] = rule.get("verify_wait", 8000)
    stage2 = _bql_request(stage2_endpoint, {
        "query": _inject_query(bool(verify)), "variables": variables,
    }, timeout=100)
    page = (stage2.get("verifyPage") or {}).get("html") or (stage2.get("after") or {}).get("html") or ""
    state = _classify(str(page), rule)
    if state == "unknown":
        # 提交响应里再兜底找一次（verify 未配/跳转时 after 可能还是结果页）
        resp = _parse_response(stage2.get("response"))
        if resp and _classify(str(resp.get("text") or ""), rule) in ("success", "already"):
            state = "success"
    if state == "unknown":
        diag = _diag_hint(stage2.get("autoDiag"))
        err = _error_suffix(stage2)
        return _result("failed", f"云签提交后未确认签到：页面未见成功/已签标记{'；' + diag if diag else ''}{err}")
    return _state_result(state, rule)


def base_target(target: str, path: str) -> str:
    return urllib.parse.urljoin(target, path)


def _parse_response(raw: Any) -> dict | None:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip() and raw.strip() != "null":
        try:
            value = json.loads(raw)
            return value if isinstance(value, dict) else None
        except ValueError:
            return None
    return None


def _diag_hint(raw: Any) -> str:
    diag = _parse_response(raw)
    if not diag:
        return ""
    parts = []
    if diag.get("token") is False:
        parts.append("token 未回填")
    if diag.get("post") not in (None, True):
        parts.append(f"兜底POST={diag.get('post')}")
    if diag.get("still") is True:
        parts.append("页面仍提示待验证")
    return "；".join(parts)


def _state_result(state: str, rule: dict, clicked: bool = False, page_html: str = "") -> CloudResult:
    if state == "success":
        return _result("success", "云签成功")
    if state == "already":
        return _result("success", "云签回读：今日已签到")
    if state == "pending":
        return _result("protocol_pending", "云签验证未完成：页面仍提示待人机验证")
    verb = "点击提交" if clicked else "提交"
    snippet = _page_text(page_html)
    suffix = f"，片段「{snippet}」" if snippet else ""
    return _result("failed", f"云签{verb}后未确认签到：页面未见成功/已签标记{suffix}")

__all__ = ["CLOUD_SITES", "CloudResult", "CloudSignError", "bql_endpoint", "configured",
           "cookie_objects", "enabled", "session_endpoint", "sign"]
