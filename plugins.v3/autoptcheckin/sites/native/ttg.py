"""TTG: V2-derived declaration; production verification remains gated."""
import re

from ...core.nexus import NexusSignin, SigninForm
from ...core.sitemodel import RecordSpec


class TTG(NexusSignin):
    id = 'ttg'
    name = 'TTG'
    url = 'https://totheglory.im/'
    attendance_path = '/'
    record_spec = RecordSpec('', {'亲，您今天已签到过，不要太贪哦': 'signed', '您已连续签到': 'signed', '未签到': 'unsigned'})
    pre_read_spec = RecordSpec('//b[@style="color:green;"]', {'已签到': 'signed'})

    def discover_form(self, ctx, page):
        data = []
        for name, pattern in (("signed_timestamp", r'\d{10}'), ("signed_token", r'[^"\r\n]+')):
            values = re.findall(name + r':\s*"(' + pattern + r')"', page.text)
            if len(values) != 1:
                return None
            data.append((name, values[0]))
        return SigninForm(self.url + "signed.php", data)

    def read_after(self, ctx, page):
        result = self.read_before(ctx, page)
        if result.status == "already":
            result.status = type(result.status).SUCCESS
            return result
        return super().read_after(ctx, page)
