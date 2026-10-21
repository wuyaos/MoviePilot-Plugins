"""HDSky AJAX captcha flow; selectors are synthetic-fixture aligned, not production proof."""
import json
import re
from urllib.parse import urlencode, urljoin

from lxml import html

from ...core.nexus import NexusSignin, SigninForm
from ...core.sitemodel import RecordSpec, page_available


class HDSky(NexusSignin):
    id = "hdsky"
    name = "HDSky"
    url = "https://hdsky.me/"
    attendance_path = "/index.php"
    verified = True  # Pilot authorization only, not a claim of verified production HTML.
    record_spec = RecordSpec(
        '//*[@id="showup" or @id="sign_in" or @id="showupbutton"][self::a or self::button or self::input]',
        {"未签到": "unsigned", "已签到": "signed"})

    def discover_form(self, ctx, page):
        buttons = html.fromstring(page.text).xpath(self.record_spec.message)
        if len(buttons) != 1 or buttons[0].get("disabled") is not None:
            return None
        return SigninForm(urljoin(self.url, "/showup.php"), [("action", "showup")])

    def solve_captcha(self, ctx, page, form):
        if ctx.ocr is None:
            return False
        for engine in ("ddddocr", "ocrhelper"):
            if ctx.cancel.is_set():
                return False
            response = ctx.http.post(urljoin(self.url, "/image_code_ajax.php"), data=[("action", "new")])
            if not page_available(response):
                return False
            payload = json.loads(response.text)
            image_hash = payload.get("code")
            if not payload.get("success") or not isinstance(image_hash, str) or not image_hash:
                return False
            image_url = urljoin(self.url, "/image.php") + "?" + urlencode({"action": "regimage", "imagehash": image_hash})
            code = ctx.ocr(image_url=image_url, referer=page.url, min_len=6, max_len=6,
                           retry_times=1, engine=engine, charset="alnum")
            if isinstance(code, str) and re.fullmatch(r"[A-Za-z0-9]{6}", code):
                form.data.extend([("imagehash", image_hash), ("imagestring", code)])
                return True
        return False
