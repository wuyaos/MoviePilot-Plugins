"""朱雀: V2-derived declaration; production verification remains gated."""
import json
from lxml import html
from ...core.nexus import SigninForm
from ...core.models import RewardSummary

from ...core.api_signin import ApiSignin
from ...core.sitemodel import RecordSpec


class ZhuQue(ApiSignin):
    id = 'zhuque'
    name = '朱雀'
    url = 'https://zhuque.in/'
    attendance_path = '/'
    hook_implemented = True
    # 朱雀无每日签到：fireGenshinCharacterMagic 是技能动作回执，不作为签到能力暴露
    # （配置页不渲染签到开关，签到轨标 signin_not_supported）。适配代码保留待站点真出签到再启用。
    signin_capable = False
    record_spec = RecordSpec(source="response_json", response_field="status", status_map={200: "signed"})

    def discover_form(self, ctx, page):
        tokens = html.fromstring(page.text).xpath('//meta[@name="x-csrf-token"]/@content')
        if len(tokens) != 1 or not tokens[0]:
            return None
        return SigninForm(self.url + 'api/gaming/fireGenshinCharacterMagic', [('x-csrf-token', tokens[0])])

    def perform_action(self, ctx, form):
        return ctx.http.post(form.action, headers=dict(form.data), json={"all": 1, "resetModal": "true"})

    def receipt_result(self, ctx, receipt):
        result = super().receipt_result(ctx, receipt)
        if result.status == "success":
            payload = json.loads(receipt.text)
            data = payload.get('data')
            bonus = data.get('bonus') if isinstance(data, dict) else None
            if type(bonus) in (int, float):
                result.reward = RewardSummary(reported=str(bonus), unit="魔力")
        return result
