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
            if line.strip() not in {"", "🕐", "🕒"} and not _TIMEZONE_NOISE_LINE.search(line)]
    return "\n".join(kept)

class RetroToon(NexusSignin):
    id = 'retrotoon'
    name = 'RetroToon'
    url = 'https://retrotoon.world/'
    attendance_path = '/attendance.php'
    record_spec = RecordSpec('//*[contains(concat(" ", normalize-space(@class), " "), " rt-form-card ")][.//*[contains(normalize-space(string(.)), "Daily Reward")]]', {'already claimed': 'signed', 'claimed today': 'signed', 'reward claimed': 'signed', 'reward already collected': 'signed', 'come back tomorrow': 'signed'})
    # 站点每日 9 点重置：重置前读到的已签只改消息归属（昨日已签），不拦提交。
    reset_hour = 9

    def discover_form(self, ctx, page):
        tree = html.fromstring(page.text)
        # 不提交时区设置表单；claim 可由 input 或 button 提供。
        claims = tree.xpath('//form[translate(@method,"POST","post")="post"]'
                            '[.//input[@name="csrf_token"]]'
                            '[.//*[self::input or self::button][@name="claim"]]')
        if len(claims) != 1:
            return None
        scoped = LoginPage(html.tostring(claims[0], encoding='unicode'), page.url)
        form = super().discover_form(ctx, scoped)
        if form is None:
            return None
        data = dict(form.data)
        return form if data.get('csrf_token') and 'claim' in data else None

    @staticmethod
    def _claim_available(page):
        tree = html.fromstring(page.text)
        return bool(tree.xpath('//form[.//*[self::input or self::button][@name="claim"]]'))

    def _read_reward(self, ctx, page, *, before):
        from ...core.models import Evidence, LoginStatus, SignStatus
        from ...core.sitemodel import page_available
        if page_available(page) and self.parse_login(page).status != LoginStatus.AUTH_FAILED:
            # V2 顺序：领取表单优先于日历和完成提示，隐藏旧提示不得阻止领取。
            if self._claim_available(page):
                return ctx.result(status=SignStatus.UNCONFIRMED, message='今日奖励尚未领取',
                                  evidence=Evidence(status='unsigned'))
            tree = html.fromstring(page.text)
            today = tree.xpath('//*[contains(concat(" ", normalize-space(@class), " "), " att-cal-cell--today ")]')
            if len(today) == 1 and (
                    'att-cal-cell--claimed' in (today[0].get('class') or '').split() or
                    today[0].xpath('.//*[contains(concat(" ", normalize-space(@class), " "), " att-cal-claimed-tag ")]')):
                summary = ' '.join(today[0].itertext()).strip()
                return ctx.result(status=SignStatus.ALREADY if before else SignStatus.SUCCESS,
                                  message=('今日已签到' if before else '签到成功') + (f' | {summary}' if summary else ''),
                                  evidence=Evidence(status='signed', raw_summary=summary))
        result = super()._read_before(ctx, page) if before else super().read_after(ctx, page)
        return self._trim(result)

    def read_before(self, ctx: SignContext, page: LoginPage | None) -> SignResult:
        return self.note_daily_reset(self._read_reward(ctx, page, before=True))

    def read_after(self, ctx: SignContext, page: LoginPage | None) -> SignResult:
        return self._read_reward(ctx, page, before=False)

    @staticmethod
    def _trim(result: SignResult) -> SignResult:
        from ...core.models import SignStatus
        if result.message:
            result.message = _strip_timezone_noise(result.message)
            if result.status in (SignStatus.ALREADY, SignStatus.SUCCESS):
                prefix = '今日已签到' if result.status == SignStatus.ALREADY else '签到成功'
                result.message = prefix + (f' | {result.message}' if result.message else '')
        return result
