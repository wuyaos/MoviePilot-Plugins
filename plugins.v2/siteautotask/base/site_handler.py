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

    def read_shoutbox_snapshot(self):
        """读取并缓存一份喊话区快照，供发送确认和反馈解析共用。"""
        url = getattr(self, "shoutbox_url", None) or f"{self.site_url}/shoutbox.php?type=shoutbox"
        response = send_get(self, url)
        self._last_shoutbox_snapshot = response
        return response

    @staticmethod
    def _is_shoutbox_url(url: str) -> bool:
        return str(url or "").split("?", 1)[0].rstrip("/").endswith("/shoutbox.php")

    def message_confirmation_snapshot(self, message: str) -> int:
        """发送前记录当前用户同文喊话的数量。"""
        return len(self._find_sent_message_rows(message, self.read_shoutbox_snapshot()))

    def verify_message_sent(self, message: str, previous_count: int, response) -> bool:
        """在发送后的同一份快照中确认当前用户的本条消息已出现。"""
        return len(self._find_sent_message_rows(message, response)) > previous_count

    def _shoutbox_rows(self, response):
        """将常见喊话区 DOM 归一成按页面顺序排列的文本行。"""
        from lxml import etree

        if not response:
            return []
        root = etree.HTML(response.text or "")
        if root is None:
            return []
        rows = []
        for row in root.xpath("//tr[td] | //li | //div[contains(@class, 'shout') or contains(@class, 'chat-message')]"):
            text = " ".join(part.strip() for part in row.xpath(".//text()") if part.strip())
            if text:
                rows.append(text)
        return rows

    def _find_sent_message_rows(self, message: str, response):
        """从喊话区提取同时含当前用户名和指定消息的行。"""
        username = (self.get_username() or "").strip()
        target = (message or "").strip()
        if not username or not target:
            return []
        return [text for text in self._shoutbox_rows(response) if username in text and target in text]

    def nearby_shoutbox_rows(self, message: str, max_rows: int = 5):
        """返回本条喊话上方的附近行，不跨过另一条自己的喊话。

        页面默认按最新到最旧排列，目标消息上方（较小索引）才可能是其系统反馈。
        其他用户的普通聊天允许插入；遇到另一条自己的非 ``@用户名`` 喊话即终止。
        """
        response = getattr(self, "_last_shoutbox_snapshot", None) or self.read_shoutbox_snapshot()
        username = (self.get_username() or "").strip()
        target = (message or "").strip()
        if not username or not target:
            return []
        rows = self._shoutbox_rows(response)
        for index, text in enumerate(rows):
            if username not in text or target not in text:
                continue
            nearby = []
            for candidate in reversed(rows[max(0, index - max_rows):index]):
                if username in candidate and f"@{username}" not in candidate:
                    break
                nearby.append(candidate)
            return nearby
        return []

    def _send_get_request(self, url, params=None, rt_method=None):
        # 发送确认成功后，反馈解析复用同一次喊话区读取，避免确认与反馈错配。
        cached = getattr(self, "_last_shoutbox_snapshot", None)
        if (getattr(self, "_reuse_shoutbox_snapshot", False)
                and cached and not params and self._is_shoutbox_url(url)):
            return rt_method(cached) if rt_method else cached
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
