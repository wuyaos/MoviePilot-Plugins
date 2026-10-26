"""52PT：首页解析动态签到链接 → CloakBrowser 滑块+按钮两段式签到。"""
from .generic import build_generic_sites
from ...core.models import SignResult, SignStatus
from ...core.nexus import NexusSignin, SigninForm
from ...core.sitemodel import RecordSpec

_base = next(site for site in build_generic_sites() if site.id == "52pt")


class Pt52(_base):
    name = "52PT"
    url = "https://52pt.site/"
    # 内联滑块在 torrents.php（独立 52bakatestdate 页面已暂停，2026-10-23 采样）。
    attendance_path = "/torrents.php"
    hook_implemented = True
    record_spec = RecordSpec('//*[@id="batch2-message-pending-calibration"]',
                             {'今天已经签过到了': 'signed', '未签到': 'unsigned'})

    def read_before(self, ctx, page):
        base = super().read_before(ctx, page)
        if base.status == SignStatus.ALREADY or base.metadata.get('reason') == 'identity_conflict':
            return base
        from lxml import html as _html
        links = _html.fromstring(page.text or '').xpath('//a[contains(@href, "52bakatestdate")]/@href')
        if not links:
            # 签到后入口消失（用户实证）：入口缺失=已签证据。
            result = SignResult(SignStatus.ALREADY, '签到入口已消失（今日已签）')
            result.metadata['action'] = 'sign'
            return result
        return base

    def discover_form(self, ctx, page):
        # 内联滑块就在当前页（torrents.php）；合成表单占位承载动作。
        return SigninForm(page.url, [])

    def submit(self, ctx, form):
        from ...core.models import LoginPage
        # 内联滑块在 torrents.php 本页；不点击「签到赚魔力」入口（独立页已暂停）。
        steps = list(getattr(self, 'cloak_steps', ()) or ('slider', 'sign_button'))
        # 页面动作与落点快照经客户端 actor 执行（session 线程亲和，7e8635a6 P1-2）。
        ctx.http.run_page_action(steps)
        content, url = ctx.http.page_snapshot()
        ctx.cloak_read = LoginPage(content, url, 200)
