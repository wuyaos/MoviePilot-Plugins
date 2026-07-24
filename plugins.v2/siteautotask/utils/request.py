"""统一请求工具。

合并 ptautotask 的 CustomRequests（简陋、5 秒超时、json 不容错）与
groupchatzone 的 ISiteHandler 请求层（session + 重试 + browser 兜底）。

关键改进：
1. session + Retry 适配器，超时 15 秒（ptautotask 仅 5 秒）
2. json 容错：非 JSON / 302 跳登录 → 返回明确错误，不再抛 Expecting value
3. browser 渲染兜底（render 站点）
"""
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.core.config import settings
from app.log import logger
from app.helper.browser import PlaywrightHelper


# 默认请求超时（秒）
DEFAULT_TIMEOUT = 15
# 请求重试策略
RETRY_TOTAL = 3
RETRY_BACKOFF = 1
RETRY_STATUS = [403, 404, 500, 502, 503, 504]


def build_session(cookie: str, ua: str, use_proxy: bool, referer: str = "") -> requests.Session:
    """构建带重试与默认头的请求会话。"""
    session = requests.Session()
    retries = Retry(
        total=RETRY_TOTAL,
        backoff_factor=RETRY_BACKOFF,
        status_forcelist=RETRY_STATUS,
        allowed_methods=frozenset(["GET", "POST"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries, pool_connections=1, pool_maxsize=1)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    headers = {
        "User-Agent": ua or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/132.0.0.0 Safari/537.36 Edg/132.0.0.0",
        "Cookie": cookie or "",
        "Referer": referer or "",
    }
    session.headers.update(headers)

    if use_proxy:
        proxies = _resolve_proxies()
        if proxies:
            session.proxies = proxies

    return session


def _resolve_proxies():
    """解析系统代理为 requests 需要的字典格式。"""
    try:
        proxy = getattr(settings, "PROXY", None)
        if not proxy:
            return None
        if isinstance(proxy, str):
            return {"http": proxy, "https": proxy}
        if isinstance(proxy, dict):
            return proxy
    except Exception as e:
        logger.warning(f"解析代理配置失败: {e}")
    return None


def parse_json_response(response, fallback_msg: str = "响应解析失败") -> dict:
    """安全解析 JSON 响应。

    修复 ptautotask 的 response.json() 不容错问题：
    - 302 跳登录页（HTML）→ 返回 {success:False, msg:"cookie 失效，请检查站点 cookie"}
    - 空响应 / 非 JSON → 返回明确错误
    """
    if response is None:
        return {"success": False, "msg": fallback_msg}

    # 302 跳登录页：后端返回 HTML 而非 JSON
    if response.status_code in (301, 302):
        return {"success": False, "msg": "请求被重定向，可能 cookie 失效，请检查站点 cookie"}
    if response.status_code != 200:
        return {"success": False, "msg": f"请求失败，状态码: {response.status_code}"}

    text = (response.text or "").strip()
    if not text:
        return {"success": False, "msg": "响应为空，可能 cookie 失效或被重定向"}

    try:
        return response.json()
    except ValueError:
        # 响应非 JSON（可能是登录页 HTML）
        if "<html" in text.lower() or "<!doctype" in text.lower():
            return {"success": False, "msg": "响应为 HTML 而非 JSON，可能 cookie 失效，请检查站点 cookie"}
        return {"success": False, "msg": f"响应解析失败: {text[:100]}"}


def _get_browser_page_source(handler, url: str) -> Optional[str]:
    """通过 PlaywrightHelper 获取页面源码（render 站点）。"""
    proxies = None
    if handler.use_proxy:
        try:
            proxy_url = None
            if isinstance(settings.PROXY, dict):
                proxy_url = settings.PROXY.get("http") or settings.PROXY.get("https")
            elif isinstance(settings.PROXY, str):
                proxy_url = settings.PROXY
            if proxy_url:
                proxies = {"server": proxy_url}
        except Exception as e:
            logger.warning(f"解析代理配置失败: {e}")

    try:
        return PlaywrightHelper().get_page_source(
            url=url, cookies=handler.site_cookie, ua=handler.ua, proxies=proxies
        )
    except Exception as e:
        logger.error(f"BrowserHelper 请求异常: {e}")
        return None


def _post_via_browser(handler, url: str, data: dict = None) -> Optional[str]:
    """通过 PlaywrightHelper 执行 POST 请求（render 站点）。"""
    proxies = None
    if handler.use_proxy:
        try:
            proxy_url = None
            if isinstance(settings.PROXY, dict):
                proxy_url = settings.PROXY.get("http") or settings.PROXY.get("https")
            elif isinstance(settings.PROXY, str):
                proxy_url = settings.PROXY
            if proxy_url:
                proxies = {"server": proxy_url}
        except Exception as e:
            logger.warning(f"解析代理配置失败: {e}")

    def post_action(page):
        js_data = data or {}
        return page.evaluate("""
            async (data) => {
                const formData = new URLSearchParams();
                for (const [key, value] of Object.entries(data)) {
                    formData.append(key, value);
                }
                const response = await fetch(window.location.href, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                    body: formData
                });
                return await response.text();
            }
        """, js_data)

    try:
        return PlaywrightHelper().action(
            url=url, callback=post_action, cookies=handler.site_cookie,
            ua=handler.ua, proxies=proxies,
        )
    except Exception as e:
        logger.error(f"BrowserHelper POST请求异常: {e}")
        return None


def send_get(handler, url: str, params: dict = None, rt_method: callable = None):
    """发送 GET 请求。

    render 站点优先 browser 兜底，否则走 session。
    返回 rt_method(response) 或 response 本身；失败返回 None。
    """
    try:
        if handler.render:
            html_text = _get_browser_page_source(handler, url)
            if html_text:
                response = handler.MockResponse(html_text)
                return rt_method(response) if rt_method else response

        response = handler.session.get(url, params=params, timeout=(3.05, DEFAULT_TIMEOUT))
        response.raise_for_status()
        return rt_method(response) if rt_method else response
    except Exception as e:
        logger.error(f"GET请求失败 [{handler.site_name}] {url}: {e}")
        return None


def send_post(handler, url: str, data: dict = None, rt_method: callable = None):
    """发送 POST 请求。

    render 站点优先 browser 兜底，否则走 session。
    返回 rt_method(response) 或 response 本身；失败返回 None。
    """
    try:
        if handler.render:
            html_text = _post_via_browser(handler, url, data)
            if html_text:
                response = handler.MockResponse(html_text)
                return rt_method(response) if rt_method else response

        response = handler.session.post(url, data=data, timeout=(3.05, DEFAULT_TIMEOUT))
        response.raise_for_status()
        return rt_method(response) if rt_method else response
    except Exception as e:
        logger.error(f"POST请求失败 [{handler.site_name}] {url}: {e}")
        return None
