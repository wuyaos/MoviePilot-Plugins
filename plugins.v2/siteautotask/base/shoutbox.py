"""声明式喊话区快照、确认与反馈关联。

本模块不发送消息；它只在一次已读取的页面快照中判断消息是否出现并寻找反馈，
避免不同站点把 DOM 过早压平为无方向的字符串。
"""
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional


class FeedbackDirection(str, Enum):
    BEFORE = "before"
    AFTER = "after"
    BOTH = "both"
    EXTERNAL = "external"


@dataclass(frozen=True)
class ChatRow:
    index: int
    text: str
    selector: str = ""
    age_seconds: Optional[int] = None


@dataclass(frozen=True)
class ShoutboxProfile:
    path: str = "/shoutbox.php?type=shoutbox"
    row_xpath: str = "//td[contains(@class, 'shoutrow')]"
    direction: FeedbackDirection = FeedbackDirection.BEFORE
    window_size: int = 5
    is_feedback: Optional[Callable[[ChatRow, str], bool]] = None
    external_feedback_xpath: str = ""
    # 某些站点的确认入口与发送入口最终一致性较慢或需特殊认证；
    # 此时宁可单次失败，也不能因误判连续重复喊话。
    retry_on_unconfirmed: bool = True
    max_row_age_seconds: int = 600
    # None 表示使用当前完整消息；否则每个关键词都必须出现在本人喊话行中。
    # 用于兼容头衔、空格和标点变化，而不使用危险的任意模糊匹配。
    message_terms: Optional[Callable[[str], List[str]]] = None
    # 发送成功到喊话流可见的最短等待；只影响读快照，不增加发送次数。
    confirmation_wait_seconds: int = 0


@dataclass
class ShoutboxSnapshot:
    rows: List[ChatRow] = field(default_factory=list)
    external_rows: List[ChatRow] = field(default_factory=list)
    valid: bool = False
    reason: str = ""

    @classmethod
    def parse(cls, html: str, profile: ShoutboxProfile):
        from lxml import etree
        root = etree.HTML(html or "")
        if root is None:
            return cls(reason="喊话区页面无法解析")
        nodes = root.xpath(profile.row_xpath)
        if not nodes:
            return cls(reason="未找到 Profile 指定的喊话行")
        def convert(items, selector):
            return [ChatRow(
                i,
                " ".join(t.strip() for t in node.xpath(".//text()") if t.strip()),
                selector,
                _relative_age_seconds(" ".join(t.strip() for t in node.xpath(".//text()") if t.strip())),
            ) for i, node in enumerate(items)]
        rows = convert(nodes, profile.row_xpath)
        external = convert(root.xpath(profile.external_feedback_xpath), profile.external_feedback_xpath) \
            if profile.external_feedback_xpath else []
        return cls(rows=rows, external_rows=external, valid=True)


@dataclass(frozen=True)
class ChatObservation:
    snapshot_valid: bool
    sent: bool
    feedback: Optional[ChatRow] = None
    reason: str = ""
    retry_allowed: bool = True


def _relative_age_seconds(text: str) -> Optional[int]:
    """解析喊话区常见相对时间；无法确认时间的行不得用于近时反馈关联。"""
    minute = re.search(r"(?:<\s*)?(\d+)\s*分钟前", text)
    hour = re.search(r"(\d+)\s*时", text)
    if minute or hour:
        return (int(hour.group(1)) * 3600 if hour else 0) + (int(minute.group(1)) * 60 if minute else 0)
    if "刚刚" in text or "现在" in text:
        return 0
    return None


def _normalize_match_text(text: str) -> str:
    """放宽同文匹配的格式差异，但不使用危险的模糊相似度。"""
    return re.sub(r"[\s，,。.!！?？、\[\]【】（）()]", "", text or "")


def _is_recent(row: ChatRow, profile: ShoutboxProfile) -> bool:
    return row.age_seconds is not None and row.age_seconds <= profile.max_row_age_seconds


def observe(snapshot: ShoutboxSnapshot, profile: ShoutboxProfile, username: str,
            message: str, configured_messages: List[str]) -> ChatObservation:
    if not snapshot.valid:
        return ChatObservation(False, False, reason=snapshot.reason)
    terms = profile.message_terms(message) if profile.message_terms else [message]
    normalized_terms = [_normalize_match_text(term) for term in terms if term]
    target = next((row for row in snapshot.rows
                   if _is_recent(row, profile) and username in row.text
                   and all(term in _normalize_match_text(row.text) for term in normalized_terms)), None)
    if not target:
        return ChatObservation(True, False, reason="喊话区未出现当前用户消息",
                              retry_allowed=profile.retry_on_unconfirmed)
    if profile.direction == FeedbackDirection.EXTERNAL:
        candidates = snapshot.external_rows
    else:
        before = list(reversed(snapshot.rows[max(0, target.index - profile.window_size):target.index]))
        after = snapshot.rows[target.index + 1:target.index + 1 + profile.window_size]
        candidates = before if profile.direction == FeedbackDirection.BEFORE else after
        if profile.direction == FeedbackDirection.BOTH:
            candidates = before + after
    normalized_messages = [_normalize_match_text(item) for item in configured_messages if item]
    for row in candidates:
        if not _is_recent(row, profile):
            continue
        normalized_row = _normalize_match_text(row.text)
        own_shout = username in row.text and any(item in normalized_row for item in normalized_messages)
        if own_shout:
            break
        # 默认反馈规则：含用户名但不是本人喊话的行即为系统反馈；站点可声明更精确的 is_feedback。
        if profile.is_feedback is not None:
            if profile.is_feedback(row, username):
                return ChatObservation(True, True, feedback=row)
        elif username in row.text:
            return ChatObservation(True, True, feedback=row)
    return ChatObservation(True, True, reason="未解析到反馈")
