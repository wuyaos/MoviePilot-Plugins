"""声明式喊话区快照、确认与反馈关联。

本模块不发送消息；它只在一次已读取的页面快照中判断消息是否出现并寻找反馈，
避免不同站点把 DOM 过早压平为无方向的字符串。
"""
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


@dataclass(frozen=True)
class ShoutboxProfile:
    path: str = "/shoutbox.php?type=shoutbox"
    row_xpath: str = "//td[contains(@class, 'shoutrow')]"
    direction: FeedbackDirection = FeedbackDirection.BEFORE
    window_size: int = 5
    is_feedback: Optional[Callable[[ChatRow, str], bool]] = None
    external_feedback_xpath: str = ""


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
            return [ChatRow(i, " ".join(t.strip() for t in node.xpath(".//text()") if t.strip()), selector)
                    for i, node in enumerate(items)]
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


def observe(snapshot: ShoutboxSnapshot, profile: ShoutboxProfile, username: str,
            message: str, configured_messages: List[str]) -> ChatObservation:
    if not snapshot.valid:
        return ChatObservation(False, False, reason=snapshot.reason)
    target = next((row for row in snapshot.rows if username in row.text and message in row.text), None)
    if not target:
        return ChatObservation(True, False, reason="喊话区未出现当前用户消息")
    if profile.direction == FeedbackDirection.EXTERNAL:
        candidates = snapshot.external_rows
    else:
        before = list(reversed(snapshot.rows[max(0, target.index - profile.window_size):target.index]))
        after = snapshot.rows[target.index + 1:target.index + 1 + profile.window_size]
        candidates = before if profile.direction == FeedbackDirection.BEFORE else after
        if profile.direction == FeedbackDirection.BOTH:
            candidates = before + after
    for row in candidates:
        own_shout = username in row.text and any(item and item in row.text for item in configured_messages)
        if own_shout:
            break
        if profile.is_feedback and profile.is_feedback(row, username):
            return ChatObservation(True, True, feedback=row)
    return ChatObservation(True, True, reason="未解析到反馈")
