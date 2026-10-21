"""白兔: V2-derived declaration; production verification remains gated."""
from ...core.api_signin import ApiSignin
from ...core.sitemodel import RecordSpec


class Hares(ApiSignin):
    id = 'hares'
    name = '白兔'
    url = 'https://club.hares.top/'
    attendance_path = '/'
    hook_implemented = True
    record_spec = RecordSpec(source="response_json", response_field='code', status_map={0: 'signed'})
    # GET attendance.php?action=sign is an action, never a pre-read.
    action_path = '/attendance.php?action=sign'
