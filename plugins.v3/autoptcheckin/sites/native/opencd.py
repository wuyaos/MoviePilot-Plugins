"""OpenCD: V2-derived declaration; production verification remains gated."""
import re
from urllib.parse import urljoin, urlsplit
from lxml import html
from ...core.nexus import SigninForm
from ...core.sitemodel import page_available

from ...core.api_signin import ApiSignin
from ...core.sitemodel import RecordSpec


class OpenCD(ApiSignin):
    verified = True
    id = 'opencd'
    name = 'OpenCD'
    url = 'https://www.open.cd/'
    attendance_path = '/'
    hook_implemented = True
    record_spec = RecordSpec(source="response_json", response_field='state', status_map={'success': 'signed'})
    signed_marker = '//a[@href="/plugin_sign-in.php?cmd=show-log" or @href="plugin_sign-in.php?cmd=show-log"]'

    def discover_form(self, ctx, page):
        page = ctx.http.get(self.url + 'plugin_sign-in.php')
        if not page_available(page) or self.parse_login(page).status == 'auth_failed' or ctx.ocr is None:
            return None
        forms = html.fromstring(page.text).xpath('//form[@id="frmSignin"]')
        if len(forms) != 1:
            return None
        hashes = forms[0].xpath('.//input[@name="imagehash"]/@value')
        images = forms[0].xpath('.//img/@src')
        if len(hashes) != 1 or not hashes[0] or len(images) != 1:
            return None
        image_url = urljoin(page.url, images[0])
        if urlsplit(image_url)[:2] != urlsplit(self.url)[:2]:
            return None
        for engine in ('ddddocr', 'ocrhelper'):
            if ctx.cancel.is_set():
                return None
            try:
                code = ctx.ocr(image_url=image_url, referer=page.url, min_len=6, max_len=6,
                               retry_times=1, engine=engine, charset='alnum')
            except Exception:
                code = None
            if isinstance(code, str) and re.fullmatch(r'[A-Za-z0-9]{6}', code):
                return SigninForm(self.url + 'plugin_sign-in.php?cmd=signin',
                                  [('imagehash', hashes[0]), ('imagestring', code)])
        return None

    def perform_action(self, ctx, form):
        return ctx.http.post(form.action, data=form.data)
