"""PTNewsWatch 领域模型。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class SourceKind(StrEnum):
    RSS = "rss"
    ATOM = "atom"
    NEXUS_TOPIC = "nexus_topic"


class SourceAuthMode(StrEnum):
    PUBLIC = "public"
    MP_SITE_COOKIE = "mp_site_cookie"
    INVITES_COOKIE = "invites_cookie"


@dataclass(frozen=True)
class SourceSpec:
    source_id: str
    site_id: str
    title: str
    kind: SourceKind
    url: str
    auth_mode: SourceAuthMode
    site_domain: str = ""
    timezone_name: str = "Asia/Shanghai"
    base_source_id: str = ""

    @property
    def base_id(self) -> str:
        return self.base_source_id or self.source_id


@dataclass(frozen=True)
class ForumEntry:
    source_id: str
    entry_id: str
    title: str
    author: str
    content: str
    link: str
    published_at: datetime
    source_title: str = ""
    base_source_id: str = ""


@dataclass
class SourceFetchResult:
    source_id: str
    source_title: str
    success: bool
    entries: list[ForumEntry] = field(default_factory=list)
    error: str = ""
    fetched_at: datetime | None = None
