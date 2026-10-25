"""BTSchool daily entry: disappearance on the authenticated homepage means signed."""
from lxml import html

from ...core.get_signin import GetSignin
from ...core.models import Evidence, LoginStatus, SignStatus
from ...core.sitemodel import RecordSpec, page_available


class BTSchool(GetSignin):
    verified = True
    id = 'btschool'
    name = 'BTSchool'
    url = 'https://pt.btschool.club/'
    attendance_path = '/'
    action_path = '/index.php?action=addbonus'
    use_default_message = False
    record_spec = RecordSpec('//a[contains(@href,"action=addbonus")]', {})
    entry = '//a[contains(@href,"action=addbonus")]'

    def read_before(self, ctx, page):
        if page_available(page) and self.parse_login(page).status != LoginStatus.AUTH_FAILED:
            tree = html.fromstring(page.text)
            # Absence is meaningful only on a logged-in homepage, not a challenge/error page.
            if (tree.xpath('//a[contains(@href,"userdetails.php?id=")]')
                    and tree.xpath('//a[@href="logout.php"]')
                    and not tree.xpath(self.entry)):
                return ctx.result(status=SignStatus.ALREADY, evidence=Evidence(status='signed'))
        return super().read_before(ctx, page)

    def discover_form(self, ctx, page):
        if len(html.fromstring(page.text).xpath(self.entry)) != 1:
            return None
        return super().discover_form(ctx, page)

    def read_after(self, ctx, page):
        result = self.read_before(ctx, page)
        if result.status == SignStatus.ALREADY:
            result.status = SignStatus.SUCCESS
        return result
