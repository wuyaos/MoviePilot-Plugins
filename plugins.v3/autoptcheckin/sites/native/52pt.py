"""52PT: 滑块签到（2026-10-22 确认，非 bakatest 问答）；仅模拟登录，答题类模块已废弃。

滑块签到需要浏览器拖动验证，HTTP 流程无法完成；如需实现须接入 CloakBrowser
滑块轨迹模拟，属后续批次。当前 signin_applicable=False（registry 答题/滑块类排除），
仅保留模拟登录（访问页面确认登录态）。
"""
from ...core.nexus import NexusSignin
from ...core.sitemodel import RecordSpec


class Pt52(NexusSignin):
    id = '52pt'
    name = '52PT'
    url = 'https://52pt.site/'
    attendance_path = '/'
    hook_implemented = False
    signin_capable = False
    # 滑块流程未实现；消息选择器为默认链回退，未校准
    record_spec = RecordSpec('//*[@id="batch2-message-pending-calibration"]',
                             {'今天已经签过到了': 'signed', '未签到': 'unsigned'})
