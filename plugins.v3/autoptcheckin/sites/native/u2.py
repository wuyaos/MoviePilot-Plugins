"""U2 image-choice submission; only a fresh showup anchor confirms success.

9 点前页面的已签 anchor 属昨日：已签=跳过本轮、未签照常提交（与 retrotoon 同口径，不做时间门控）；
9 点后页面即今日状态。站点每日 9 点重置，签到动作本身不依赖小时判断。
"""
import random
from urllib.parse import urljoin

from lxml import html

from ...core.nexus import NexusSignin, SigninForm
from ...core.sitemodel import RecordSpec


class U2(NexusSignin):
    id = 'u2'
    name = 'U2'
    url = 'https://u2.dmhy.org/'
    attendance_path = '/showup.php'
    hook_implemented = True
    record_spec = RecordSpec('//a[@href="showup.php"]', {'已签到': 'signed', 'Show Up': 'signed', 'Показать': 'signed', '已簽到': 'signed'})
    # 站点每日 9 点重置：重置前读到的已签只改消息归属（昨日已签），不拦提交。
    reset_hour = 9


    def discover_form(self, ctx, page):
        action = self.url + 'showup.php?action=show'
        forms = [form for form in html.fromstring(page.text).forms
                 if form.method.upper() == 'POST'
                 and urljoin(page.url, form.get('action', '')) == action]
        if len(forms) != 1:
            return None
        form = forms[0]
        data = []
        for name in ('_csrf', 'req', 'hash', 'form'):
            values = form.xpath('.//input[@name=$name]/@value', name=name)
            if len(values) != 1 or not values[0]:
                return None
            data.append((name, values[0]))
        choices = form.xpath('.//input[@type="submit" and @name and @value and not(@disabled)]')
        if not choices:
            return None
        choice = random.choice(choices)
        data.extend([('message', '一切随缘~'), (choice.get('name'), choice.get('value'))])
        return SigninForm(action, data)
