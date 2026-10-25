"""瓷器: V2-derived declaration; production verification remains gated."""
from lxml import html
from ...core.nexus import SigninForm

from ...core.api_signin import ApiSignin
from ...core.sitemodel import RecordSpec


class HDChina(ApiSignin):
    verified = True
    id = 'hdchina'
    name = '瓷器'
    url = 'https://hdchina.org/'
    attendance_path = '/index.php'
    hook_implemented = True
    record_spec = RecordSpec(source="response_json", response_field='state', status_map={'success': 'signed'})
    pre_read_spec = RecordSpec('//a[@class="label label-default" and @href="#"]', {"已签到": "signed"})

    def signin(self, ctx):
        ctx.http.retain_cookies({"hdchina"})
        return super().signin(ctx)

    def discover_form(self, ctx, page):
        values = html.fromstring(page.text).xpath('//meta[@name="x-csrf"]/@content')
        if len(values) != 1 or not values[0]:
            return None
        return SigninForm(self.url + 'plugin_sign-in.php?cmd=signin', [('csrf', values[0])])

    def perform_action(self, ctx, form):
        return ctx.http.post(form.action, data=form.data)
