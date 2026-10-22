"""Native BrowserQL transport; site protocols and evidence stay in NexusSignin."""
import json
from urllib.error import URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from .models import LoginPage


def bql_endpoint(address, token=''):
    parsed = urlsplit(address.strip())
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname:
        raise ValueError('Browserless requires an HTTP endpoint')
    path = parsed.path.rstrip('/') or '/chromium'
    if not path.endswith('/bql'):
        path += '/bql' if path.endswith('/stealth') else '/stealth/bql'
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
        variables = {'cookies': [{'name': key, 'value': value, 'url': self.url}
                                 for key, value in self.cookies.items()],
                     'url': url, 'wait': self.wait_ms}
        declarations = '$cookies:[CookieInput!]! $url:String! $wait:Float!'
        steps = ['cookies(cookies:$cookies){cookies{name}}']
        if self.ua:
            declarations += ' $userAgent:String!'
            variables['userAgent'] = self.ua
            steps.append('userAgent(userAgent:$userAgent){time}')
        steps += ['goto(url:$url,waitUntil:domContentLoaded){status}',
                  'solve(timeout:$wait){found solved}',
                  'settle:waitForTimeout(time:$wait){time}']
        if script is not None:
            declarations += ' $script:String!'
            variables['script'] = script
            steps.append('submit:evaluate(content:$script,timeout:30000){value}')
        steps += ['before:html{html}',
                  'location:evaluate(content:"location.href"){value}',
                  'navigation:evaluate(content:' + json.dumps('performance.getEntriesByType("navigation").at(-1)?.responseStatus || 0') + '){value}',
                  'jar:cookies{cookies{name value domain path}}']
        payload = {'query': 'mutation NativeRequest(' + declarations + ') {' + '\n'.join(steps) + '}',
                   'operationName': 'NativeRequest', 'variables': variables}
        request = Request(self.endpoint, data=json.dumps(payload).encode('utf-8'),
                          headers={'Content-Type': 'application/json'}, method='POST')
        with urlopen(request, timeout=self.timeout) as response:
            envelope = json.loads(response.read().decode('utf-8'))
        data = envelope.get('data') or {}
        if not data:
            raise ValueError('BrowserQL returned no data')
        host = urlsplit(self.url).hostname
        for cookie in (data.get('jar') or {}).get('cookies') or []:
            domain = str(cookie.get('domain') or '').lstrip('.')
            if domain and (host == domain or host.endswith('.' + domain)):
                self.cookies[cookie['name']] = cookie['value']
        return data

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
            and config.get('browserless_url')):
        return http
    try:
        return BrowserQLClient(http, {**info, 'url': info.get('url') or site.url}, config,
                               wait_ms=getattr(site, 'browserless_wait_ms', 15000))
    except ValueError:
        return http
