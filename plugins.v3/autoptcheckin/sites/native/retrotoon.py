"""RetroToon: V2-derived declaration; production verification remains gated."""
from ...core.nexus import NexusSignin
from ...core.sitemodel import RecordSpec


class RetroToon(NexusSignin):
    id = 'retrotoon'
    name = 'RetroToon'
    url = 'https://retrotoon.world/'
    attendance_path = '/attendance.php'
    record_spec = RecordSpec('//*[contains(concat(" ", normalize-space(@class), " "), " rt-form-card ")][.//*[contains(normalize-space(string(.)), "Daily Reward")]]', {'already claimed': 'signed', 'claimed today': 'signed', 'reward claimed': 'signed', 'reward already collected': 'signed', 'come back tomorrow': 'signed'})

    def discover_form(self, ctx, page):
        form = super().discover_form(ctx, page)
        if form is None:
            return None
        data = dict(form.data)
        return form if data.get("csrf_token") and "claim" in data else None
