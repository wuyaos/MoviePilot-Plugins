"""Single submission, fresh readback even on exceptions; caller owns site lock."""
from datetime import datetime
import re
from html import unescape
from .models import SignResult, SignStatus
from .verification import normalize_evidence


def sanitize_sample(html: str) -> str:
    """保留页面标题和 DOM 结构，移除脚本、Cookie/凭据值等敏感内容。"""
    text = html or ""
    text = re.sub(r"<script\b[^>]*>.*?</script\s*>", "", text, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style\s*>", "", text, flags=re.I | re.S)
    text = re.sub(r"<meta\b[^>]*(?:set-cookie|cookie)[^>]*>", "", text, flags=re.I)
    text = re.sub(r"(?i)(?:set-cookie|authorization|bearer|cookie)\s*[:=][^<\n]*", "", text)

    def clean_tag(match):
        tag = match.group(0)
        tag = re.sub(r"(?i)(\s+(?:value|content|data-[\w-]*(?:token|cookie|secret))\s*=\s*)([\"\'])[^\"\']*\2", r"\1\2[redacted]\2", tag)
        tag = re.sub(r"(?i)(\s+(?:name|id)\s*=\s*[\"\'](?:formhash|csrf[^\"\']*|token|cookie|password)[\"\'])", r"\1", tag)
        return tag

    text = re.sub(r"<[^>]+>", clean_tag, text)
    return unescape(text).strip()


def run_page(adapter, bound_uid="", readonly=False, bind=None, business_date=None, sample_sink=None):
    day = business_date or datetime.now().astimezone().date().isoformat()

    def save_sample(page, result):
        if sample_sink and result.status in (SignStatus.UNCONFIRMED, SignStatus.AUTH_FAILED):
            try:
                sample_sink(sanitize_sample(page), result.status)
            except Exception:
                pass

    try:
        page = adapter.fetch_page()
        uid = adapter.verifier.identity(page)
        if not uid or (bound_uid and uid != bound_uid):
            result = SignResult(SignStatus.UNCONFIRMED, "页面身份缺失或冲突")
            save_sample(page, result)
            return result
        if bind and not bound_uid:
            bind(uid)
        evidence = adapter.verifier.parse(page, uid, day)
        result = normalize_evidence(evidence, uid, day, before_submit=True)
        if readonly or result.confirmed:
            save_sample(page, result)
            return result
        if not adapter.verifier.token(page) or not evidence or not evidence.button_text or result.status != SignStatus.FAILED:
            result = SignResult(SignStatus.UNCONFIRMED, "未确认本人当日未签到，不提交", evidence=evidence)
            save_sample(page, result)
            return result
    except Exception:
        return SignResult(SignStatus.UNCONFIRMED, "签到前读取不可达或解析异常")
    try:
        adapter.submit(page)
    except Exception:
        pass
    finally:
        try:
            after = adapter.fetch_page()
            evidence = adapter.verifier.parse(after, uid, day)
            result = normalize_evidence(evidence, uid, day)
            if result.confirmed and hasattr(adapter.verifier, "reward"):
                result.reward = adapter.verifier.reward(after, uid, day)
            save_sample(after, result)
        except Exception:
            result = SignResult(SignStatus.UNCONFIRMED, "新页面不可达或解析异常，需只读复核")
    return result
