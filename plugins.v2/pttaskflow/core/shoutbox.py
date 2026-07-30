"""声明式喊话区快照与反馈关联。"""
import re
from dataclasses import dataclass
from enum import Enum
from typing import Callable, List, Optional

from lxml import etree


class Direction(str, Enum):
    BEFORE = "before"
    AFTER = "after"
    BOTH = "both"
    EXTERNAL = "external"


@dataclass(frozen=True)
class ChatRow:
    index: int
    text: str
    age_seconds: Optional[int]
    source: str = "row"


@dataclass(frozen=True)
class ShoutboxProfile:
    path: str = "/shoutbox.php?type=shoutbox"
    row_xpath: str = "//td[contains(@class, 'shoutrow')]"
    external_feedback_xpath: str = ""
    direction: Direction = Direction.BEFORE
    window_size: int = 5
    message_terms: Optional[Callable[[str], List[str]]] = None
    is_feedback: Optional[Callable[[ChatRow, str], bool]] = None
    confirmation_wait_seconds: int = 2
    retry_on_unconfirmed: bool = True
    max_row_age_seconds: int = 600


@dataclass
class Observation:
    valid: bool
    sent: bool
    feedback: Optional[ChatRow] = None
    reason: str = ""
    retry_allowed: bool = True


def _normalize(text: str) -> str:
    return re.sub(r"[\s，,。.!！?？、\[\]【】（）()]", "", text or "")


def _age(text: str):
    minute = re.search(r"(\d+)\s*分钟前", text)
    hour = re.search(r"(\d+)\s*小时前", text)
    if hour:
        return int(hour.group(1)) * 3600
    if minute:
        return int(minute.group(1)) * 60
    if "刚刚" in text or "现在" in text:
        return 0
    return None


def parse_snapshot(html: str, profile: ShoutboxProfile):
    root = etree.HTML(html or "")
    if root is None:
        return [], "喊话区页面无法解析"
    nodes = root.xpath(profile.row_xpath)
    if not nodes:
        return [], "未找到 Profile 指定的喊话行"
    rows = []
    for index, node in enumerate(nodes):
        text = " ".join(part.strip() for part in node.xpath(".//text()") if part.strip())
        rows.append(ChatRow(index, text, _age(text), "row"))
    if profile.external_feedback_xpath:
        for node in root.xpath(profile.external_feedback_xpath):
            text = " ".join(part.strip() for part in node.xpath(".//text()") if part.strip())
            rows.append(ChatRow(len(rows), text, _age(text), "external"))
    return rows, ""


def observe(rows: List[ChatRow], profile: ShoutboxProfile, username: str,
            message: str, configured_messages: List[str]) -> Observation:
    if not rows:
        return Observation(False, False, reason="喊话区快照无有效行", retry_allowed=False)
    terms = profile.message_terms(message) if profile.message_terms else [message]
    terms = [_normalize(term) for term in terms if term]
    target = next((row for row in rows
                   if row.source == "row"
                   and (row.age_seconds is None or row.age_seconds <= profile.max_row_age_seconds)
                   and username in row.text
                   and all(term in _normalize(row.text) for term in terms)), None)
    if profile.direction == Direction.EXTERNAL:
        candidates = [row for row in rows if row.source == "external"]
        for row in candidates:
            if row.age_seconds is not None and row.age_seconds > profile.max_row_age_seconds:
                continue
            matched = profile.is_feedback(row, username) if profile.is_feedback else username in row.text
            if matched:
                return Observation(True, True, feedback=row)
    if not target:
        return Observation(True, False, reason="喊话区未出现当前用户消息",
                           retry_allowed=profile.retry_on_unconfirmed)
    if profile.direction == Direction.EXTERNAL:
        candidates = []
    else:
        before = list(reversed(rows[max(0, target.index - profile.window_size):target.index]))
        after = rows[target.index + 1:target.index + 1 + profile.window_size]
        candidates = before if profile.direction == Direction.BEFORE else after
        if profile.direction == Direction.BOTH:
            candidates = before + after
    configured = [_normalize(item) for item in configured_messages if item]
    for row in candidates:
        if (row.age_seconds is None and row.source != "external") or (
                row.age_seconds is not None and row.age_seconds > profile.max_row_age_seconds):
            continue
        normalized = _normalize(row.text)
        if username in row.text and any(msg in normalized for msg in configured):
            break
        matched = profile.is_feedback(row, username) if profile.is_feedback else username in row.text
        if matched:
            return Observation(True, True, feedback=row)
    return Observation(True, True, reason="未解析到反馈")
