"""RetroToon: V2-derived declaration; production verification remains gated."""
from lxml import html
from ...core.models import LoginPage
from ...core.nexus import NexusSignin
from ...core.sitemodel import RecordSpec


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
