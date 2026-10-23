"""Native BrowserQL transport; site protocols and evidence stay in NexusSignin."""
import json
from urllib.error import URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from .models import LoginPage


def bql_endpoint(address, token=''):
    """Browserless v2 OSS 没有 /bql，用 /function（服务端 Puppeteer 脚本）等价实现。"""
    parsed = urlsplit(address.strip())
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname:
        raise ValueError('Browserless requires an HTTP endpoint')
    path = (parsed.path.rstrip('/') or '') + '/function'
    query = dict(parse_qsl(parsed.query))
    if token:
        query['token'] = token
    return urlunsplit(parsed._replace(path=path, query=urlencode(query), fragment=''))


class BrowserQLClient:
    """Each BQL request owns its browser; only execution-local cookies survive.

    Never replay a possibly accepted action. Nexus' finally performs a fresh read
    even when the action response was lost. Only the initial connection may fall
    back to HTTP, before any browser action has been attempted.
    """
    def __init__(self, http, info, config, *, wait_ms=15000):
        self.http = http
        self.cookies = http.cookies
        self.url = info['url']
        self.ua = info.get('ua') or ''
        self.endpoint = bql_endpoint(config['browserless_url'], config.get('browserless_token', ''))
        self.wait_ms = max(0, min(int(wait_ms), 127500))
        self.timeout = min(300, (2 * self.wait_ms + 999) // 1000 + 45)
        self.started = False
        self.fallback = False
        self.read_url = self.url

    def _request(self, url, script=None):
        """POST /function：服务端 Puppeteer 执行整段流程，返回与旧 BQL 同形的数据。"""
        cfg = {'url': url, 'wait': self.wait_ms,
               'cookies': [{'name': key, 'value': value} for key, value in self.cookies.items()]}
        if self.ua:
            cfg['userAgent'] = self.ua
        if script is not None:
            cfg['script'] = script
        code = (
            'export default async ({ page }) => {'
            ' const cfg = ' + json.dumps(cfg) + ';'
            ' if (cfg.cookies && cfg.cookies.length) {'
            '  try { await page.setCookie(...cfg.cookies.map(c => ({...c, url: cfg.url}))); } catch (e) {}'
            ' }'
            ' if (cfg.userAgent) { try { await page.setUserAgent(cfg.userAgent); } catch (e) {} }'
            ' const resp = await page.goto(cfg.url, {waitUntil: "domcontentloaded", timeout: 60000});'
            ' await new Promise(r => setTimeout(r, cfg.wait));'
            ' let submitResult = null;'
            ' if (cfg.script) { try { submitResult = await page.evaluate(cfg.script); } catch (e) { submitResult = {error: String(e)}; } }'
            ' const html = await page.content();'
            ' const location = page.url();'
            ' const status = resp ? resp.status() : 0;'
            ' const jar = await page.cookies();'
            ' return {html, location, status, jar, submitResult};'
            '}'
        )
        payload = {'code': code}
        request = Request(self.endpoint, data=json.dumps(payload).encode('utf-8'),
                          headers={'Content-Type': 'application/json'}, method='POST')
        with urlopen(request, timeout=self.timeout) as response:
            data = json.loads(response.read().decode('utf-8'))
        if not isinstance(data, dict) or 'html' not in data:
            raise ValueError('Browserless function returned no page data')
        host = urlsplit(self.url).hostname
        for cookie in data.get('jar') or []:
            domain = str(cookie.get('domain') or '').lstrip('.')
            if domain and (host == domain or host.endswith('.' + domain)):
                self.cookies[cookie['name']] = cookie['value']
        # 同形映射：旧 BQL 消费端字段
        return {'before': {'html': data['html']},
                'location': {'value': data['location']},
                'navigation': {'value': data['status']},
                'jar': {'cookies': data['jar']},
                'submit': {'value': data.get('submitResult')}}

    def get(self, url, *, referer=None):
        if self.fallback:
            return self.http.get(url, **({'referer': referer} if referer else {}))
        try:
            data = self._request(url)
        except (URLError, OSError):
            if self.started:
                raise
            self.fallback = True
            return self.http.get(url, **({'referer': referer} if referer else {}))
        self.started = True
        self.read_url = url
        text = (data.get('before') or {}).get('html') or ''
        location = (data.get('location') or {}).get('value') or url
        status = (data.get('navigation') or {}).get('value') or (data.get('goto') or {}).get('status') or 0
        return LoginPage(text, location, int(status))

    def post(self, url, *, data=None, json=None, headers=None, referer=None):
        if self.fallback:
            return self.http.post(url, data=data, json=json, headers=headers, referer=referer)
        # JSON serialization keeps protocol values out of executable JS syntax.
        import json as json_module
        body = json_module.dumps(json) if json is not None else urlencode(data or [])
        request_headers = {'Content-Type': 'application/json; charset=UTF-8' if json is not None
                           else 'application/x-www-form-urlencoded; charset=UTF-8', **(headers or {})}
        options = {'method': 'POST', 'credentials': 'include', 'headers': request_headers, 'body': body}
        if referer:
            options['referrer'] = referer
        script = '(async () => { const r = await fetch(' + json_module.dumps(url) + ', ' + json_module.dumps(options) + '); return JSON.stringify({text:await r.text(),url:r.url,status:r.status}); })()'
        self.started = True
        result = self._request(self.read_url, script)
        value = (result.get('submit') or {}).get('value')
        if isinstance(value, str):
            value = json_module.loads(value)
        if not isinstance(value, dict):
            raise ValueError('BrowserQL action response unavailable')
        return LoginPage(value.get('text', ''), value.get('url') or url, value.get('status') or 0)


def native_browser_client(site, http, info, config):
    if not (getattr(site, 'browserless', False) and config.get('browserless_enabled')
            and site.id in {str(value) for value in config.get('site_browserless', [])}
            and config.get('browserless_url')):
        return http
    try:
        return BrowserQLClient(http, {**info, 'url': info.get('url') or site.url}, config,
                               wait_ms=getattr(site, 'browserless_wait_ms', 15000))
    except ValueError:
        return http
