"""PTNewsWatch 多来源隔离执行引擎。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from app.core.config import settings
from app.log import logger

from .auth.cookiecloud import resolve_invites_cookie
from .auth.mp_site_cookie import resolve_site_auth
from .config import PluginConfig
from .fetchers.feed import FeedFetcher
from .fetchers.nexus_topic import NexusTopicFetcher
from .models import DigestRunResult, SourceAuthMode, SourceFetchResult
from .notifier import build_digest_text
from .source_registry import SOURCES
from .state import add_recent_entries, apply_source_result, normalize_state, record_run


class DigestEngine:
    def __init__(
        self,
        *,
        config: PluginConfig,
        state: dict,
        save_state: Callable[[dict], None],
        save_config: Callable[[PluginConfig], None],
        notify: Callable[[str, str], None],
    ):
        self.config = config
        self.state = normalize_state(state)
        self.save_state = save_state
        self.save_config = save_config
        self.notify = notify

    def run(self, source_filter: str = "") -> DigestRunResult:
        started = datetime.now(timezone.utc)
        proxy_url = _proxy_url() if self.config.use_proxy else None
        feed_fetcher = FeedFetcher(proxy_url=proxy_url)
        topic_fetcher = NexusTopicFetcher(proxy_url=proxy_url, pages=2)
        results: list[SourceFetchResult] = []
        new_entries = []

        for source in SOURCES:
            if source_filter and source.source_id != source_filter:
                continue
            if not self.config.source_enabled(source.source_id):
                continue
            try:
                if source.auth_mode == SourceAuthMode.MP_SITE_COOKIE:
                    result = topic_fetcher.fetch(source, resolve_site_auth(source.site_domain))
                else:
                    cookie = ""
                    if source.auth_mode == SourceAuthMode.INVITES_COOKIE:
                        cookie, should_save = resolve_invites_cookie(self.config.invites_cookie)
                        if should_save:
                            self.config.invites_cookie = cookie
                            self.save_config(self.config)
                        if not cookie:
                            result = SourceFetchResult(
                                source.source_id, source.title, False,
                                error="药丸 Cookie 未配置且 CookieCloud 未匹配",
                                auth_status="cookie_missing",
                                fetched_at=datetime.now(timezone.utc),
                            )
                            results.append(result)
                            apply_source_result(
                                self.state, result,
                                first_run_push_recent=self.config.first_run_push_recent,
                            )
                            continue
                    result = feed_fetcher.fetch(source, cookie=cookie)
            except Exception as error:
                result = SourceFetchResult(
                    source.source_id, source.title, False,
                    error=str(error)[:300], auth_status="exception",
                fetched_at=datetime.now(timezone.utc),
                )
            results.append(result)
            source_new = apply_source_result(
                self.state,
                result,
                first_run_push_recent=self.config.first_run_push_recent,
            )
            new_entries.extend(source_new)

        add_recent_entries(self.state, new_entries, self.config.history_days)
        notification_entries = _notification_entries(
            new_entries, self.config.max_entries_per_source
        )
        notification_sent = False
        if self.config.notify and notification_entries:
            self.notify(
                "PT 论坛资讯动态",
                build_digest_text(
                    notification_entries,
                    timezone_name=settings.TZ,
                    failures=[f"{item.source_title}（{item.error}）" for item in results if not item.success],
                ),
            )
            notification_sent = True
        finished = datetime.now(timezone.utc)
        failures = [result for result in results if not result.success]
        record_run(self.state, {
            "time": finished.isoformat().replace("+00:00", "Z"),
            "enabled_sources": len(results),
            "success_sources": len(results) - len(failures),
            "failed_sources": len(failures),
            "new_count": len(new_entries),
            "notification_sent": notification_sent,
            "errors": [f"{item.source_title}: {item.error}" for item in failures],
        }, self.config.history_days)
        self.save_state(self.state)
        logger.info(
            "PTNewsWatch 完成：sources=%s success=%s failed=%s new=%s notified=%s",
            len(results), len(results) - len(failures), len(failures),
            len(new_entries), notification_sent,
        )
        return DigestRunResult(started, finished, results, new_entries, notification_sent)


def _notification_entries(entries, maximum_per_source):
    grouped = {}
    for entry in sorted(entries, key=lambda item: item.published_at):
        grouped.setdefault(entry.source_id, []).append(entry)
    selected = []
    for source_entries in grouped.values():
        selected.extend(source_entries[-maximum_per_source:])
    return sorted(selected, key=lambda item: item.published_at)


def _proxy_url() -> str | None:
    proxy = getattr(settings, "PROXY", None)
    if isinstance(proxy, str):
        return proxy or None
    if isinstance(proxy, dict):
        return proxy.get("http") or proxy.get("https")
    return None
