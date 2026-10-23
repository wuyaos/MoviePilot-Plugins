"""CloakBrowser page and HTTP-compatible transport."""
from pathlib import Path
from urllib.parse import urlsplit
from urllib.parse import urlencode, urlsplit

from .models import LoginPage

try:
    from app.sdk.browser import launch_browser_context as launch_context
except ImportError:
    launch_context = None


TURNSTILE_HEADFUL_SITES = {"vclib", "piggo"}


def state_path(site_id):
    """返回插件独立数据目录中的站点浏览器存档路径。"""
    from app.sdk.config import settings
    return Path(settings.PLUGIN_DATA_PATH) / "AutoPtCheckin" / "cloak_state" / f"{site_id}.json"


class CloakSession:
    """封装一次同步 CloakBrowser 上下文，异常向执行层传播。"""
    def __init__(self, *, state=None, cookie="", url="", headless=True, humanize=True, locale="zh-CN"):
        self.state, self.cookie, self.url = state, cookie, url
        self.headless, self.humanize, self.locale = headless, humanize, locale
        self.context = self.page = None

    def __enter__(self):
        launcher = launch_context
        if launcher is None:
            from app.sdk.browser import launch_browser_context as launcher
        kwargs = {"headless": self.headless, "humanize": self.humanize, "locale": self.locale}
        if self.state and Path(self.state).is_file():
            kwargs["storage_state"] = str(self.state)
        try:
            self.context = launcher(**kwargs)
            self.page = self.context.new_page()
            if self.cookie and self.url:
                host = urlsplit(self.url).hostname
                cookies = []
                for pair in self.cookie.split(";"):
                    key, sep, value = pair.strip().partition("=")
                    if sep:
                        cookies.append({"name": key, "value": value, "domain": host, "path": "/"})
                if cookies:
                    self.context.add_cookies(cookies)
            return self
        except Exception:
            self.close()
            raise

    def goto(self, url): return self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
    def fill(self, selector, text): self.page.locator(selector).fill(text)
    def click(self, selector): self.page.locator(selector).click()
    def evaluate(self, js, *args): return self.page.evaluate(js, *args)
    def mouse_move(self, x, y, steps=1): self.page.mouse.move(x, y, steps=steps)
    def save_state(self, path):
        path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
        self.context.storage_state(path=str(path))
    def close(self):
        if self.context:
            self.context.close(); self.context = None
    def __exit__(self, exc_type, exc, tb): self.close()


class CloakHttpClient:
    """映射浏览器页面为 native 签到执行器所需的同步 HTTP 契约。"""
    def __init__(self, http, info, site, shared=None):
        self.http, self.info, self.site = http, info, site
        self.url = info.get("url") or site.url
        cookie = "; ".join(f"{k}={v}" for k, v in http.cookies.items())
        if shared is not None:
            # 轮内共享会话：按站注入 cookie，不重复开关浏览器（生命周期归轮次所有）。
            self.session = shared
            self.shared = True
            host = urlsplit(self.url).hostname
            cookies = []
            for pair in cookie.split(";"):
                key, sep, value = pair.strip().partition("=")
                if sep:
                    cookies.append({"name": key, "value": value, "domain": host, "path": "/"})
            if cookies:
                self.session.context.add_cookies(cookies)
            return
        self.shared = False
        self.session = CloakSession(cookie=cookie, url=self.url,
                                    headless=site.id not in TURNSTILE_HEADFUL_SITES)
        self.session.__enter__()

    def _sync_cookies(self):
        for cookie in self.session.context.cookies(self.url):
            self.http.cookies[cookie["name"]] = cookie["value"]

    def get(self, url, *, referer=None):
        # Piggo may issue its anti-bot cookie only on the site root.  Prime that
        # page before the attendance request; the action page remains the
        # returned page and is still the sole pre-read evidence.
        entry_path = getattr(self.site, "cloak_entry_path", "")
        target = urlsplit(url)
        if entry_path and target.path != entry_path:
            entry = f"{target.scheme}://{target.netloc}{entry_path}"
            self.session.goto(entry)
            self.session.page.wait_for_timeout(15000)
            self._sync_cookies()
        response = self.session.goto(url)
        self.session.page.wait_for_timeout(15000)
        # Piggo can return one 468 challenge response even after the first
        # root visit.  Re-prime the same browser session once; no action is
        # replayed and the final page remains the only evidence.
        if getattr(response, "status", 0) == 468 and entry_path and target.path != entry_path:
            self.session.goto(f"{target.scheme}://{target.netloc}{entry_path}")
            self.session.page.wait_for_timeout(15000)
            self._sync_cookies()
            response = self.session.goto(url)
        self.session.page.wait_for_timeout(15000)
        self._sync_cookies()
        try:
            from pathlib import Path as _P
            log = _P('D:/tmp/cloak_get.log')
            with log.open('a', encoding='utf-8') as f:
                f.write(f"[{getattr(self.site, 'id', '?')}] GET {url} -> {response.status if response else 0} | {self.session.page.title()[:40]} | cookie_n={len(self.http.cookies)}\n")
        except Exception:
            pass
        return LoginPage(self.session.page.content(), self.session.page.url,
                         response.status if response else 0)

    def post(self, url, *, data=None, json=None, headers=None, referer=None):
        import json as json_module
        body = json_module.dumps(json) if json is not None else urlencode(data or [])
        request_headers = {"Content-Type": "application/json; charset=UTF-8" if json is not None
                           else "application/x-www-form-urlencoded; charset=UTF-8", **(headers or {})}
        options = {"method": "POST", "credentials": "include", "headers": request_headers, "body": body}
        if referer: options["referrer"] = referer
        result = self.session.page.evaluate(
            "async ({url, options}) => { const r=await fetch(url,options); return {text:await r.text(),url:r.url,status:r.status}; }",
            {"url": url, "options": options})
        self._sync_cookies()
        return LoginPage(result.get("text", ""), result.get("url") or url, result.get("status") or 0)

    def get_bytes(self, url): return self.http.get_bytes(url)
    def retain_cookies(self, names): return self.http.retain_cookies(names)
    def close(self): self.session.close()


def _wait_for_slider_page_exit(page):
    """等待自由农场滑块验证门页完成延迟跳转；超时保留当前页面供回读判定。"""
    for _ in range(16):
        title = page.title()
        body = page.locator("body").inner_text()
        if "滑动认证" not in title and "滑动认证" not in body and "拖动滑块验证" not in body:
            page.wait_for_timeout(2000)
            return True
        page.wait_for_timeout(1500)
    return False


def _wait_for_locator(page, selectors, timeout_ms=20000):
    """等待延迟渲染的页面动作控件；站点页面可先返回壳再挂载控件。"""
    deadline = timeout_ms
    while deadline >= 0:
        for selector in selectors:
            loc = page.locator(selector).first
            try:
                if loc.count():
                    return loc
            except Exception:
                pass
        if deadline == 0:
            break
        wait = min(500, deadline)
        page.wait_for_timeout(wait)
        deadline -= wait
    return None


def _enabled_sign_button(page):
    """只返回已完成滑块后可提交的按钮，不误点门页提示按钮。"""
    selectors = (
        'button:has-text("提交签到")',
        'input[type="submit"][value*="提交签到"]',
        '#sign-button', '#sign_btn', '[id*="sign"] button',
        'button:has-text("立即签到")', 'button:has-text("点我签到")',
        'button:has-text("签到")', 'a:has-text("立即签到")',
        'a:has-text("签到")', 'input[type="submit"][value*="签到"]',
        'button:has-text("打卡")', 'text=打卡',
    )
    loc = _wait_for_locator(page, selectors)
    if loc is None:
        return None
    try:
        text = (loc.inner_text() or "").strip()
    except Exception:
        text = ""
    if "请先完成滑块" in text or "完成滑块" in text:
        return None
    try:
        if hasattr(loc, "is_enabled") and not loc.is_enabled():
            return None
    except Exception:
        pass
    return loc


def run_page_action(session, steps):
    """CloakBrowser 页面内动作：滑块拖动 / 人工验证 / 签到按钮；步骤缺失不阻断，最终以回读判定。"""
    page = session.page
    results = []
    for step in steps:
        try:
            if step == 'attendance_link':
                # 52PT currently exposes the daily page behind the home/torrent
                # navigation link; open it before looking for the delayed slider.
                link = _wait_for_locator(page, ('a:has-text("签到赚魔力")',))
                if link is None:
                    results.append((step, 'absent'))
                    continue
                link.click()
                page.wait_for_timeout(5000)
                results.append((step, 'clicked'))
            elif step == 'slider':
                handle = _wait_for_locator(page, (
                    '#dragHandler, [class*="dragHandler"], #slider-btn, '
                    '[id*="slider"] .handle, [class*="slider"][class*="handle"], '
                    '[class*="slider"] .handle, [class*="drag"][class*="handle"], '
                    '[class*="slider"] [class*="btn"]',
                ))
                if handle is None:
                    results.append((step, 'absent'))
                    continue
                box = handle.bounding_box()
                parent = handle.locator('xpath=..').bounding_box() or {}
                track = parent or {}
                track_x, track_w = float(track.get('x') or 0), float(track.get('width') or 0)
                start_x = box['x'] + box['width'] / 2
                end_x = (track_x + track_w - box['width'] / 2 - 2) if track_w > box['width'] else start_x + 260
                distance = max(120.0, end_x - start_x)
                page.mouse.move(start_x, box['y'] + box['height'] / 2)
                page.wait_for_timeout(600)
                page.mouse.down()
                page.wait_for_timeout(300)
                page.mouse.move(start_x + distance * 0.55, box['y'] + box['height'] / 2 + 2, steps=10)
                page.mouse.move(start_x + distance * 0.9, box['y'] + box['height'] / 2 - 1, steps=10)
                page.mouse.move(start_x + distance + 1, box['y'] + box['height'] / 2, steps=8)
                page.wait_for_timeout(500)
                page.mouse.up()
                exited = _wait_for_slider_page_exit(page)
                results.append((step, 'dragged' if exited else 'timeout'))
            elif step == 'altcha':
                wrap = page.locator('.altcha-checkbox-wrap').first
                if wrap.count() == 0:
                    results.append((step, 'absent'))
                    continue
                wrap.locator('input').click()
                verified = False
                for _ in range(14):
                    page.wait_for_timeout(1500)
                    if '已验证' in wrap.inner_text():
                        verified = True
                        break
                results.append((step, 'verified' if verified else 'timeout'))
            elif step == 'human_verify':
                # Vc-Lib Turnstile 依赖 headful CloakBrowser；等待响应 token 后才允许后续提交。
                token = page.locator('input[name="cf-turnstile-response"]').first
                if token.count():
                    ok = False
                    for _ in range(40):
                        try:
                            if (token.input_value() or '').strip():
                                ok = True
                                break
                        except Exception:
                            pass
                        page.wait_for_timeout(1500)
                    results.append((step, 'turnstile-ok' if ok else 'turnstile-timeout'))
                    continue
                clicked = False
                for sel in ('text=人工验证', 'text=点击验证', 'text=点击进行人工验证',
                            '[class*="verify"] button', '[class*="captcha"] button',
                            'input[type="button"][value*="验证"]'):
                    loc = page.locator(sel).first
                    if loc.count():
                        loc.click()
                        page.wait_for_timeout(5000)
                        clicked = True
                        break
                results.append((step, 'clicked' if clicked else 'absent'))
            elif step == 'sign_button':
                loc = _enabled_sign_button(page)
                clicked = loc is not None
                if clicked:
                    loc.click()
                    page.wait_for_timeout(5000)
                    page.wait_for_timeout(8000)
                results.append((step, 'clicked' if clicked else 'absent'))
        except Exception:
            results.append((step, 'error'))
    try:
        page.wait_for_load_state('networkidle', timeout=15000)
    except Exception:
        page.wait_for_timeout(8000)
    try:
        from pathlib import Path as _P
        import json as _json
        _P('D:/tmp/action_diag.json').write_text(_json.dumps(
            {'site': getattr(session, 'debug_site', '?'), 'results': results,
             'title': page.title(), 'url': page.url,
             'body': page.locator('body').inner_text()[:300]}, ensure_ascii=False), encoding='utf-8')
    except Exception:
        pass
    return results


def native_cloak_client(site, http, info, config, shared=None):
    """启动声明且名单授权的单次仿真上下文；其余站点保留原 HTTP 客户端。"""
    if not (getattr(site, "emulate", False) and
            site.id in {str(value) for value in config.get("site_browserless", [])}):
        return http
    return CloakHttpClient(http, {**info, "url": info.get("url") or site.url}, site, shared=shared)
