"""PTNewsWatch 多来源、多 URL 隔离执行引擎。"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Callable

from app.core.config import settings
from app.log import logger

from .auth.cookiecloud import resolve_invites_cookie
from .auth.mp_site_cookie import resolve_site_auth
from .config import PluginConfig
from .fetchers.feed import FeedFetcher
from .fetchers.nexus_topic import NexusTopicFetcher
from .models import SourceAuthMode, SourceFetchResult
from .notifier import build_digest_text
from .source_instances import build_source_instances
from .state import add_recent_entries, apply_source_result, normalize_state, record_run


class DigestEngine:
    def __init__(
        self, *, config: PluginConfig, state: dict,
        save_state: Callable[[dict], None],
        save_config: Callable[[PluginConfig], None],
        notify: Callable[[str, str], None],
    ):
        self.config = config
        self.state = normalize_state(state)
        self.save_state = save_state
        self.save_config = save_config
        self.notify = notify

    def run(self, source_filter: str = "") -> None:
        proxy_url = _proxy_url() if self.config.use_proxy else None
        feed_fetcher = FeedFetcher(proxy_url=proxy_url)
        topic_fetcher = NexusTopicFetcher(proxy_url=proxy_url, pages=2)
        instances = build_source_instances(self.config, source_filter)
        results: list[SourceFetchResult] = []
        new_entries = []
        observed_entries = []
        site_auth_cache = {}
        invites_cookie: str | None = None
        instance_totals = Counter(source.base_id for source in instances)
        instance_positions: Counter = Counter()

        for source in instances:
            instance_positions[source.base_id] += 1
            source_label = source.title
            if instance_totals[source.base_id] > 1:
                source_label = f"{source.title} #{instance_positions[source.base_id]}"
            try:
                if source.auth_mode == SourceAuthMode.MP_SITE_COOKIE:
                    if source.base_id not in site_auth_cache:
                        site_auth_cache[source.base_id] = resolve_site_auth(source.site_domain)
                    result = topic_fetcher.fetch(source, site_auth_cache[source.base_id])
                else:
                    cookie = ""
                    if source.auth_mode == SourceAuthMode.INVITES_COOKIE:
                        if invites_cookie is None:
                            invites_cookie, should_save = resolve_invites_cookie(self.config.invites_cookie)
                            if should_save:
                                self.config.invites_cookie = invites_cookie
                                self.save_config(self.config)
                        cookie = invites_cookie or ""
                        if not cookie:
                            result = _failure(source, "药丸 Cookie 未配置且 CookieCloud 未匹配")
                        else:
                            result = feed_fetcher.fetch(source, cookie=cookie)
                    else:
                        result = feed_fetcher.fetch(source)
            except Exception as error:
                result = _failure(source, str(error)[:300])

            result.source_title = source_label
            results.append(result)
            # 首次运行固定返回最近条目；通知数量由单来源上限统一约束。
            source_new = apply_source_result(self.state, result)
            new_entries.extend(source_new)
            if result.success:
                observed_entries.extend(result.entries)

        # 数据页保存成功抓取的完整快照；通知仍只使用真正未见条目。
        add_recent_entries(self.state, observed_entries, self.config.history_days)
        notification_entries = _notification_entries(new_entries, self.config.max_entries_per_source)
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
        })
        self.save_state(self.state)
        logger.info(
            "PTNewsWatch 完成：sources=%s success=%s failed=%s new=%s notified=%s",
            len(results), len(results) - len(failures), len(failures),
            len(new_entries), notification_sent,
        )


def _failure(source, message: str) -> SourceFetchResult:
    return SourceFetchResult(
        source.source_id, source.title, False,
        error=message, fetched_at=datetime.now(timezone.utc),
    )


def _notification_entries(entries, maximum_per_source):
    grouped = {}
    for entry in sorted(entries, key=lambda item: item.published_at):
        grouped.setdefault(entry.base_source_id or entry.source_id, []).append(entry)
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
