"""52PT：首页解析动态签到链接 → CloakBrowser 滑块+按钮两段式签到。"""
from .generic import build_generic_sites
from ...core.models import SignResult, SignStatus
from ...core.nexus import NexusSignin, SigninForm
from ...core.sitemodel import RecordSpec

_base = next(site for site in build_generic_sites() if site.id == "52pt")


class Pt52(_base):
    name = "52PT"
    url = "https://52pt.site/"
    # 动态签到页：首页「签到赚魔力」链接指向 52bakatestdateXXXX.php（日期变化）。
    attendance_path = "/"
    hook_implemented = True
    record_spec = RecordSpec('//*[@id="batch2-message-pending-calibration"]',
                             {'今天已经签过到了': 'signed', '未签到': 'unsigned'})

    def read_before(self, ctx, page):
        base = super().read_before(ctx, page)
        if base.status == SignStatus.ALREADY or base.metadata.get('reason') == 'identity_conflict':
            return base
        from lxml import html as _html
        from urllib.parse import urljoin
        links = _html.fromstring(page.text or '').xpath('//a[contains(@href, "52bakatestdate")]/@href')
        if not links:
            # 签到后入口消失（用户实证）：入口缺失=已签证据。
            result = SignResult(SignStatus.ALREADY, '签到入口已消失（今日已签）')
            result.metadata['action'] = 'sign'
            return result
        ctx.cloak_sign_url = urljoin(self.url, links[0])
        return base

    def discover_form(self, ctx, page):
        if not getattr(ctx, 'cloak_sign_url', None):
            return None
        # 合成表单占位：真实动作用户在 submit 中对动态签到页执行。
        return SigninForm(ctx.cloak_sign_url, [])

    def submit(self, ctx, form):
        from ...core.cloak import run_page_action
        from ...core.models import LoginPage
        page = ctx.http.session.page
        page.goto(ctx.cloak_sign_url, wait_until='domcontentloaded', timeout=30000)
        page.wait_for_timeout(3000)
        run_page_action(ctx.http.session, list(getattr(self, 'cloak_steps', ()) or ('slider', 'sign_button')))
        # 动作后落点页即回读证据；二次 GET 可能重新拿到门页。
        ctx.cloak_read = LoginPage(page.content(), page.url, 200)
