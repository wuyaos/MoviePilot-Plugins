"""52PT：首页解析动态签到链接 → CloakBrowser 滑块+按钮两段式签到。"""
from ...core.models import LoginPage, SignResult
from ...core.nexus import NexusSignin, SigninForm
from ...core.sitemodel import RecordSpec, SignContext


class Pt52(NexusSignin):
    id = "52pt"
    name = "52PT"
    url = "https://52pt.site/"
    # 内联滑块在 torrents.php（独立 52bakatestdate 页面已暂停，2026-10-23 采样）。
    # 2026-10-28 凌晨取证（.ralph/52pt-recon-20261028.md）：torrents.php 滑块移除、
    # 52bakatestdate.php 与 nebuirobot.php 均死链，站点签到入口整体下线，且公告明确
    # 「利用脚本自动签到，最少扣除魔力值5200……直到劝退」。转显式无签到能力（仅保留
    # 登录轨）；适配代码保留，待站点真恢复签到再启用。
    attendance_path = "/torrents.php"
    signin_capable = False
    login_notice = "公告禁止脚本自动签到"
    record_spec = RecordSpec('', {'今天已经签过到了': 'signed', '未签到': 'unsigned'})

    def signin(self, ctx: SignContext) -> SignResult:
        # 无签到能力时拦截：与仅登录声明站同义（native 通道 run_native_site 亦有同口径门禁）。
        result = ctx.result(status="skipped", message="signin_not_applicable")
        result.metadata["reason"] = "signin_not_applicable"
        return result

    def discover_form(self, ctx, page):
        # 内联滑块就在当前页（torrents.php）；合成表单占位承载动作。
        return SigninForm(page.url, [])

    def submit(self, ctx, form):
        # 内联滑块在 torrents.php 本页；不点击「签到赚魔力」入口（独立页已暂停）。
        # 站点当前无签到能力（signin_capable=False），动作链保留待恢复时直接可用。
        steps = ("slider", "sign_button")
        # 页面动作与落点快照经客户端 actor 执行（session 线程亲和，7e8635a6 P1-2）。
        ctx.http.run_page_action(steps)
        content, url = ctx.http.page_snapshot()
        ctx.cloak_read = LoginPage(content, url, 200)
