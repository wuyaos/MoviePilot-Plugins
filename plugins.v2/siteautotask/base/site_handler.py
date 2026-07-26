"""站点处理器最小抽象：身份、请求、路由和反馈钩子。"""
from abc import ABCMeta, abstractmethod
from typing import Dict, Optional
from app.db.site_oper import SiteOper
from app.log import logger
from app.utils.string import StringUtils
from ..utils.request import build_session, send_get, send_post


class ISiteHandler(metaclass=ABCMeta):
    """不承载具体业务，新增能力请放到 capabilities.py 或站点模块。"""
    class MockResponse:
        def __init__(self, text, status_code=200):
            self.text, self.status_code = text, status_code

    def __init__(self, site_info: dict):
        self.site_info = site_info
        self.site_url = (site_info.get("url") or "").strip().rstrip("/")
        self.site_name = (site_info.get("name") or "").strip()
        self.name_cn = self.site_name
        self.site_cookie = (site_info.get("cookie") or "").strip()
        self.ua = (site_info.get("ua") or "").strip()
        self.render = bool(site_info.get("render", False))
        self.use_proxy = site_info.get("use_proxy", True)
        self.domain = site_info.get("domain") or StringUtils.get_url_domain(self.site_url)
        self.feedback_timeout = int(site_info.get("feedback_timeout", 5))
        self.interval_cnt = int(site_info.get("interval_cnt", 30))
        # 仅 Moment 通过 MESSAGE_INTERVAL 固定间隔，其余站点使用全局配置。
        self.message_interval = getattr(type(self), "MESSAGE_INTERVAL", None) or self.interval_cnt
        self.session = build_session(self.site_cookie, self.ua, self.use_proxy, referer=self.site_url)
        self._last_message_result = None

    def wait_feedback(self):
        """需要延迟反馈的站点（如织梦电力奖励）重写此方法等待。
        默认不等待，避免对无反馈的站点造成不必要的延迟。"""
        return

    @abstractmethod
    def match(self) -> bool:
        ...

    def get_feedback(self, message: str = None) -> Optional[Dict]:
        return None

    def _send_get_request(self, url, params=None, rt_method=None):
        return send_get(self, url, params, rt_method)

    def _send_post_request(self, url, data=None, rt_method=None):
        return send_post(self, url, data, rt_method)

    def get_username(self):
        return self._get_user_field("username")

    def get_userid(self):
        return self._get_user_field("userid")

    def _get_user_field(self, field):
        try:
            for item in SiteOper().get_userdata_latest():
                if item.domain == self.domain:
                    return getattr(item, field, None)
        except Exception as e:
            logger.error(f"获取站点 {self.site_name} 用户信息失败：{e}")
        return None
