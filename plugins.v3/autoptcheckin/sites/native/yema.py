"""YemaPT: V2-derived declaration; production verification remains gated."""
from ...core.api_signin import ApiSignin
from ...core.sitemodel import RecordSpec


class YemaPT(ApiSignin):
    id = 'yema'
    name = 'YemaPT'
    url = 'https://yemapt.org/'
    attendance_path = '/'
    # 用户裁决：yema 暂停签到，仅模拟登录（布尔 API 空消息待查）
    signin_capable = False
    browserless = True  # 布尔 API 前读需浏览器过盾（yemapt growth 页）
    hook_implemented = True
    record_spec = RecordSpec(source="response_json", response_field="success", status_map={True: "signed", False: "unsigned"})
    action_path = '/api/consumer/checkIn'
