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
    parser_profile: str = ""
    enabled_by_default: bool = True


@dataclass(frozen=True)
class ForumEntry:
    source_id: str
    entry_id: str
    title: str
    author: str
    content: str
    link: str
    published_at: datetime


@dataclass
class SourceFetchResult:
    source_id: str
    source_title: str
    success: bool
    entries: list[ForumEntry] = field(default_factory=list)
    error: str = ""
    auth_status: str = ""
    fetched_at: datetime | None = None


@dataclass
class DigestRunResult:
    started_at: datetime
    finished_at: datetime
    source_results: list[SourceFetchResult]
    new_entries: list[ForumEntry]
    notification_sent: bool = False
