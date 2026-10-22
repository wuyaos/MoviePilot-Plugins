"""海棠 action=sign POST; synthetic message selectors await production sampling."""
from lxml import html
from urllib.parse import urljoin

from ...core.nexus import NexusSignin, SigninForm
from ...core.sitemodel import RecordSpec


class Haitang(NexusSignin):
    id = "haitang"
    name = "海棠"
    url = "https://www.htpt.cc/"
    verified = True  # Pilot authorization, not production HTML verification.
    signed_marker = '//span[b[contains(text(), "今日已签到")]] | //a[contains(@class, "faqlink") and contains(text(), "签到已得")]'
    # pilot-calibrated 2026-10-21 real page
    record_spec = RecordSpec(
        '//*[@id="attendance-message"] | //button[@id="sign_in" and not(//*[@id="attendance-message"])]',
        {"未签到": "unsigned", "今日已签到": "signed", "今天已签到": "signed",
         "今天已经签到": "signed", "签到成功": "signed", "本次签到获得": "signed"})

    def discover_form(self, ctx, page):
        tree = html.fromstring(page.text)
        if tree.xpath('//form[contains(@action,"attendance.php")]//*[self::button or self::input][@type="submit" and @disabled]'):
            return None
        # The calendar repeats action=sign; only the primary daily button is eligible.
        primary = tree.xpath('//form[@method="post" and @action="attendance.php"]'
                             '[input[@name="action" and @value="sign"]]'
                             '[button[@type="submit" and not(@disabled)][contains(.,"立即签到")]]')
        if len(primary) == 1:
            return SigninForm(urljoin(self.url, self.attendance_path), [("action", "sign")])
        if len(primary) > 1:
            return None
        form = super().discover_form(ctx, page)
        if form is None:
            if tree.forms:
                return None
            buttons = tree.xpath('//button[@id="sign_in" and not(@disabled)]')
            if len(buttons) != 1:
                return None
            form = SigninForm(urljoin(self.url, self.attendance_path), [])
        form.data = [(key, value) for key, value in form.data if key != "action"]
        form.data.append(("action", "sign"))
        return form
