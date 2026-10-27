"""RetroToon: V2-derived declaration; production verification remains gated."""
import re
from lxml import html
from ...core.models import LoginPage, SignResult
from ...core.nexus import NexusSignin
from ...core.sitemodel import RecordSpec, SignContext

# The Daily Reward card embeds timezone chrome: "Your day resets at midnight in
# UTC (it is Oct 22, 07:20 there now). Change timezone" and the hidden
# tz-mismatch block "Your device reports ... Use this timezone". Chrome lines
# carry no claim evidence and leaked into the whole notification; they are
# stripped from the display message only. Status mapping keeps running on the
# untrimmed card text in core read_record, so success/signed judgment is
# unchanged.
# Whole-block removal first (text_content() can glue message and chrome onto
# one line when the page carries no inter-element whitespace), then a
# per-line fallback for truncated chrome.
_TIMEZONE_NOISE_BLOCKS = (
    re.compile(r"your day resets.*?change timezone", re.DOTALL | re.IGNORECASE),
    re.compile(r"your device reports.*?use this timezone", re.DOTALL | re.IGNORECASE),
)
_TIMEZONE_NOISE_LINE = re.compile(
    r"your day resets|\(it is .+ there now\)|change timezone"
    r"|your device reports|use this timezone", re.IGNORECASE)


def _strip_timezone_noise(message: str) -> str:
    if not message:
        return message
    for pattern in _TIMEZONE_NOISE_BLOCKS:
        message = pattern.sub("\n", message)
    kept = [line.strip() for line in message.splitlines()
            if line.strip() and not _TIMEZONE_NOISE_LINE.search(line)]
    return "\n".join(kept)

class RetroToon(NexusSignin):
    id = 'retrotoon'
    name = 'RetroToon'
    url = 'https://retrotoon.world/'
    attendance_path = '/attendance.php'
    record_spec = RecordSpec('//*[contains(concat(" ", normalize-space(@class), " "), " rt-form-card ")][.//*[contains(normalize-space(string(.)), "Daily Reward")]]', {'already claimed': 'signed', 'claimed today': 'signed', 'reward claimed': 'signed', 'reward already collected': 'signed', 'come back tomorrow': 'signed'})

    def discover_form(self, ctx, page):
        tree = html.fromstring(page.text)
        # Ignore the separate timezone form; never submit its fields as a reward claim.
        claims = tree.xpath('//form[translate(@method,"POST","post")="post"]'
                            '[.//input[@name="csrf_token"]][.//input[@name="claim"]]')
        if len(claims) != 1:
            return None
        scoped = LoginPage(html.tostring(claims[0], encoding="unicode"), page.url)
        form = super().discover_form(ctx, scoped)
        if form is None:
            return None
        data = dict(form.data)
        return form if data.get("csrf_token") and "claim" in data else None

    def read_before(self, ctx: SignContext, page: LoginPage | None) -> SignResult:
        # 9 点前 already=昨日已签（跳过即可）、未签=照常提交；9 点后页面即今日状态。
        return self._trim(super().read_before(ctx, page))

    def read_after(self, ctx: SignContext, page: LoginPage | None) -> SignResult:
        return self._trim(super().read_after(ctx, page))

    @staticmethod
    def _trim(result: SignResult) -> SignResult:
        # Judgment already happened in ctx.record_result on the untrimmed text.
        if result.message:
            result.message = _strip_timezone_noise(result.message)
        return result
