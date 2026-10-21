"""HDUpt: V2-derived declaration; production verification remains gated."""
from ...core.get_signin import GetSignin
from ...core.sitemodel import RecordSpec


class HDUpt(GetSignin):
    id = 'hdupt'
    name = 'HDUpt'
    url = 'https://pt.hdupt.com/'
    attendance_path = '/'
    hook_implemented = True
    action_path = '/added.php?action=qiandao'
    record_spec = RecordSpec('//*[@id="batch2-message-pending-calibration"]', {})
    signed_marker = '//span[@id="yiqiandao"]'
    # Numeric action replies are ignored; only the fresh marker is evidence.
