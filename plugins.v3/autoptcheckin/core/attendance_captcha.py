"""V2 attendance imagehash protocol, without its submission retry loop."""
import re
from urllib.parse import urljoin, urlsplit

from lxml import html

from .models import LoginPage
from .nexus import SigninForm
from .sitemodel import SignContext


def solve_attendance_captcha(ctx: SignContext, page: LoginPage, form: SigninForm, *, max_len: int | None = 6) -> bool:
    if ctx.ocr is None or ctx.cancel.is_set():
        return False
    hashes = [value for key, value in form.data if key == "imagehash"]
    if len(hashes) != 1 or not hashes[0]:
        return False
    # Match the already selected POST form, not an unrelated page-wide image.
    forms = [node for node in html.fromstring(page.text).forms
             if node.method.upper() == "POST"
             and urljoin(page.url, node.get("action") or page.url) == form.action]
    if len(forms) != 1:
        return False
    images = forms[0].xpath('.//img[contains(@src, "image.php")]/@src')
    if len(images) != 1:
        return False
    image_url = urljoin(page.url, images[0])
    # OCR forwards the site's Cookie, so never forward it to another origin.
    if urlsplit(image_url)[:2] != urlsplit(form.action)[:2]:
        return False
    for engine in ("ddddocr", "ocrhelper"):
        if ctx.cancel.is_set():
            return False
        try:
            # ctx.ocr downloads the image with credentials and this Referer.
            # SiQi has no upper length bound; common attendance defaults to six.
            code = ctx.ocr(image_url=image_url, referer=page.url, min_len=4, max_len=max_len,
                           retry_times=1, engine=engine, charset="alnum")
        except Exception:
            code = None
        if isinstance(code, str) and re.fullmatch(r"[A-Za-z0-9]{4,}", code) and (max_len is None or len(code) <= max_len):
            form.data[:] = [(key, value) for key, value in form.data if key != "imagestring"]
            form.data.append(("imagestring", code))
            form.referer = page.url
            return True
    return False
