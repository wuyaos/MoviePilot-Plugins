"""YemaPT: V2-derived declaration; production verification remains gated."""
from ...core.api_signin import ApiSignin
from ...core.sitemodel import RecordSpec


class YemaPT(ApiSignin):
    id = 'yema'
    name = 'YemaPT'
    url = 'https://yemapt.org/'
    attendance_path = '/'
    hook_implemented = True
    record_spec = RecordSpec(source="response_json", response_field="success", status_map={True: "signed", False: "unsigned"})
    action_path = '/api/consumer/checkIn'
