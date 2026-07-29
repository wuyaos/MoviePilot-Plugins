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

    def shoutbox_profile(self):
        """返回站点喊话区 Profile；子类仅覆写此声明，不覆写确认流程。"""
        from .shoutbox import ShoutboxProfile
        return ShoutboxProfile(
            path="/shoutbox.php?type=shoutbox",
            row_xpath="//td[contains(@class, 'shoutrow')]",
        )

    def read_shoutbox_snapshot(self):
        """按 Profile 读取并缓存一份喊话区原始快照。"""
        profile = self.shoutbox_profile()
        response = send_get(self, f"{self.site_url}{profile.path}")
        self._last_shoutbox_snapshot = response
        return response

    def _structured_shoutbox_snapshot(self, response=None):
        from .shoutbox import ShoutboxSnapshot
        response = response or getattr(self, "_last_shoutbox_snapshot", None)
        return ShoutboxSnapshot.parse(getattr(response, "text", ""), self.shoutbox_profile())

    def message_confirmation_snapshot(self, message: str):
        """发送前记录有效快照中的本人同文消息数量。"""
        response = self.read_shoutbox_snapshot()
        snapshot = self._structured_shoutbox_snapshot(response)
        username = (self.get_username() or "").strip()
        count = sum(username in row.text and message in row.text for row in snapshot.rows)
        return {"valid": snapshot.valid, "count": count, "reason": snapshot.reason}

    def observe_chat_message(self, message: str, baseline):
        """从发送后同一快照确认消息并给出结构化有效性结果。"""
        from .shoutbox import observe
        snapshot = self._structured_shoutbox_snapshot()
        username = (self.get_username() or "").strip()
        configured = [message]
        messages_getter = getattr(self, "shotbox_messages", None)
        if callable(messages_getter):
            configured.extend(str(item) for item in messages_getter() if item)
        result = observe(snapshot, self.shoutbox_profile(), username, message, configured)
        current_count = sum(username in row.text and message in row.text for row in snapshot.rows)
        if result.snapshot_valid and current_count <= int((baseline or {}).get("count", 0)):
            from .shoutbox import ChatObservation
            return ChatObservation(True, False, reason="喊话区未出现新增当前用户消息")
        return result

    @staticmethod
    def _is_shoutbox_url(url: str) -> bool:
        return str(url or "").split("?", 1)[0].rstrip("/").endswith("/shoutbox.php")

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

        默认页面按最新到最旧排列，因此查目标消息上方；个别站点可通过
        ``FEEDBACK_ROWS_BOTH=True`` 同时检查上下两侧（Moment 的反馈位置不稳定）。
        其他用户的普通聊天允许插入；遇到另一条自己的已配置喊话即终止。
        """
        response = getattr(self, "_last_shoutbox_snapshot", None) or self.read_shoutbox_snapshot()
        username = (self.get_username() or "").strip()
        target = (message or "").strip()
        if not username or not target:
            return []
        rows = self._shoutbox_rows(response)
        configured_messages = [target]
        messages_getter = getattr(self, "shotbox_messages", None)
        if callable(messages_getter):
            configured_messages.extend(str(item) for item in messages_getter() if item)
        for index, text in enumerate(rows):
            if username not in text or target not in text:
                continue
            candidates = list(reversed(rows[max(0, index - max_rows):index]))
            if getattr(type(self), "FEEDBACK_ROWS_BOTH", False):
                candidates.extend(rows[index + 1:index + 1 + max_rows])
            nearby = []
            for candidate in candidates:
                # 不能仅凭用户名判断：如「【用户名的女友】」这类系统反馈也会带用户名。
                # 只有包含本站实际喊话文本的行，才是另一条自己的喊话并构成边界。
                is_own_shout = username in candidate and any(
                    sent_message in candidate for sent_message in configured_messages
                )
                if is_own_shout:
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
