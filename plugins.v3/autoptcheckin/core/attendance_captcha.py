"""V2 attendance imagehash protocol, without its submission retry loop."""
import re
from urllib.parse import urljoin, urlsplit

from lxml import html

from .models import LoginPage
from .nexus import SigninForm
from .sitemodel import SignContext


def _trace(ctx, **info):
    """识别过程与失败原因都留证：qnap 日志不落盘时，metadata 是唯一现场。"""
    trace = dict(getattr(ctx, "captcha_trace", None) or {})
    trace.update(info)
    ctx.captcha_trace = trace


def solve_attendance_captcha(ctx: SignContext, page: LoginPage, form: SigninForm, *, max_len: int | None = 6) -> bool:
    if ctx.ocr is None or ctx.cancel.is_set():
        _trace(ctx, error="ocr_unavailable" if ctx.ocr is None else "cancelled")
        return False
    hashes = [value for key, value in form.data if key == "imagehash"]
    if len(hashes) != 1 or not hashes[0]:
        _trace(ctx, error="imagehash_missing")
        return False
    # Match the already selected POST form, not an unrelated page-wide image.
    forms = [node for node in html.fromstring(page.text).forms
             if node.method.upper() == "POST"
             and urljoin(page.url, node.get("action") or page.url) == form.action]
    if len(forms) != 1:
        _trace(ctx, error="post_form_not_found")
        return False
    images = forms[0].xpath('.//img[contains(@src, "image.php")]/@src')
    if len(images) != 1:
        _trace(ctx, error="captcha_image_not_found")
        return False
    image_url = urljoin(page.url, images[0])
    # OCR forwards the site's Cookie, so never forward it to another origin.
    if urlsplit(image_url)[:2] != urlsplit(form.action)[:2]:
        _trace(ctx, error="captcha_image_cross_origin")
        return False
    for engine in ("ddddocr", "ocrhelper"):
        if ctx.cancel.is_set():
            _trace(ctx, error="cancelled")
            return False
        try:
            # ctx.ocr downloads the image with credentials and this Referer.
            # SiQi has no upper length bound; common attendance defaults to six.
            code = ctx.ocr(image_url=image_url, referer=page.url, min_len=4, max_len=max_len,
                           retry_times=1, engine=engine, charset="alnum")
        except Exception:
            code = None
            _trace(ctx, engine=engine, error="ocr_error")
        if isinstance(code, str) and re.fullmatch(r"[A-Za-z0-9]{4,}", code) and (max_len is None or len(code) <= max_len):
            _trace(ctx, code=code, engine=engine, length=len(code))
            form.data[:] = [(key, value) for key, value in form.data if key != "imagestring"]
            form.data.append(("imagestring", code))
            form.referer = page.url
            return True
    _trace(ctx, error="ocr_no_match")
    return False
