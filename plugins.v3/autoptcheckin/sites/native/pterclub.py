"""PTerClub: V2-derived declaration; production verification remains gated."""
from ...core.api_signin import ApiSignin
from ...core.sitemodel import RecordSpec


class PTerClub(ApiSignin):
    id = 'pterclub'
    name = 'PTerClub'
    url = 'https://pterclub.com/'
    attendance_path = '/'
    hook_implemented = True
    record_spec = RecordSpec(source="response_json", response_field='status', status_map={'1': 'signed'})
    # GET attendance-ajax.php has side effects; status=0 alone proves nothing.
    action_path = '/attendance-ajax.php'
