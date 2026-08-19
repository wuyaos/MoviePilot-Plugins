"""BakaBTBrush 单轮执行流程：先检查 qB 槽位，再访问 BakaBT。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from collections.abc import Callable
from typing import Any

from .config import BrushConfig
from .downloader import (
    DownloaderError,
    add_and_verify,
    available_slots,
    completed_infohashes,
    downloading_count,
    list_bakabt_torrents,
    transfer_totals_mb,
)
from .models import BakaBTTorrent
from .scraper import BakaBTClient, BakaBTError
from .state import (
    remember_added,
    remember_completed,
    record_run,
    update_account,
    update_qb,
    was_added,
)


@dataclass(frozen=True)
class RunResult:
    status: str
    added: tuple[BakaBTTorrent, ...]
    failed_titles: tuple[str, ...]
    detail: str
    downloading_count: int
    max_downloading: int

    @property
    def should_notify_success(self) -> bool:
        return bool(self.added)

    @property
    def should_notify_failure(self) -> bool:
        return self.status == "failed"


def run_once(
    config: BrushConfig,
    cookie: str | Callable[[], str],
    state: dict[str, Any],
    qb_instance: Any,
    *,
    now: datetime | None = None,
    client: BakaBTClient | None = None,
) -> RunResult:
    """执行一次刷流检查，始终把结果写入 state，调用方只需统一 save_data 一次。"""
    now = _utc(now)
    try:
        qb_torrents = _sync_qb_state(config, state, qb_instance)
    except DownloaderError as err:
        return _finish(
            state, "failed", (), (), "qBittorrent 查询失败", 0, config.max_bakabt_downloading, now,
        )

    current_downloading = downloading_count(qb_torrents)
    slots = available_slots(config.max_bakabt_downloading, current_downloading)
    if slots == 0:
        return _finish(
            state,
            "no_qb_slot",
            (),
            (),
            f"当前 BakaBT 下载流程：{current_downloading}/{config.max_bakabt_downloading}",
            current_downloading,
            config.max_bakabt_downloading,
            now,
        )

    resolved_cookie = (cookie() if callable(cookie) else cookie).strip()
    if not resolved_cookie:
        return _finish(
            state,
            "failed",
            (),
            (),
            "未配置 BakaBT Cookie，且 CookieCloud 未匹配到 bakabt.me",
            current_downloading,
            config.max_bakabt_downloading,
            now,
        )
    client = client or BakaBTClient(
        resolved_cookie,
        timeout=config.timeout,
        detail_retries=config.detail_request_retries,
    )
    try:
        page = client.fetch_browse()
    except BakaBTError as err:
        return _finish(
            state, "failed", (), (), str(err), current_downloading, config.max_bakabt_downloading, now,
        )

    account_note = ""
    if page.account_url:
        try:
            account = client.fetch_account(page.account_url)
            if account.uploaded_mb is not None or account.downloaded_mb is not None:
                update_account(state, account)
            else:
                account_note = "账户流量未识别"
        except BakaBTError:
            # 账户卡保留上一次成功快照，账户页失败不阻断本轮种子处理。
            account_note = "账户页读取失败"

    candidates = [
        item for item in prefilter_candidates(page.torrents, config, now)
        if not was_added(state, item.torrent_id)
    ]
    if not candidates:
        return _finish(
            state,
            "no_candidate",
            (),
            (),
            _append_note("未找到符合时间和体积的 Freeleech", account_note),
            current_downloading,
            config.max_bakabt_downloading,
            now,
        )

    existing_hashes = {item.infohash for item in qb_torrents}
    added: list[BakaBTTorrent] = []
    failures: list[str] = []
    processed_titles: list[str] = []
    candidate_limit = slots if slots is not None else len(candidates)

    for item in candidates:
        if len(added) >= candidate_limit:
            break
        processed_titles.append(item.title)
        try:
            detail = client.fetch_detail(item.detail_url)
            item.is_freeleech = detail.is_freeleech
            item.published_at = detail.published_at
            item.download_url = detail.download_url
            item.infohash = detail.infohash
            if not matches_final_filters(item, config, now):
                continue
            if not item.download_url or not item.infohash:
                failures.append(item.title)
                continue
            if item.infohash.lower() in existing_hashes:
                continue
            content = client.fetch_torrent(item.download_url)
            infohash = add_and_verify(
                qb_instance,
                content,
                item.infohash,
                config.qb_category,
                config.qb_tags,
                config.save_path,
            )
            remember_added(state, item, infohash)
            existing_hashes.add(infohash.lower())
            added.append(item)
        except (BakaBTError, DownloaderError):
            failures.append(item.title)
            # 单个候选失败时继续尝试后续候选，不中断整轮。
            continue

    # 刷新 qB 快照，让数据页和通知反映本轮提交后的实际状态。
    try:
        refreshed = _sync_qb_state(config, state, qb_instance)
        current_downloading = downloading_count(refreshed)
    except DownloaderError:
        # 添加已通过 qB 确认；刷新失败不回滚已记录成功。
        current_downloading += len(added)

    if added:
        detail = f"qB 下载槽位：{current_downloading}/{config.max_bakabt_downloading}" if config.max_bakabt_downloading else "qB 下载流程不限制"
        detail = _append_note(detail, account_note)
        return _finish(
            state,
            "success",
            tuple(added),
            tuple(failures),
            detail,
            current_downloading,
            config.max_bakabt_downloading,
            now,
        )
    if failures:
        return _finish(
            state,
            "failed",
            (),
            tuple(failures),
            _append_note("候选推送失败", account_note),
            current_downloading,
            config.max_bakabt_downloading,
            now,
            torrent_titles=processed_titles,
        )
    return _finish(
        state,
        "no_candidate",
        (),
        (),
        _append_note("候选已存在、已处理或未通过详情复核", account_note),
        current_downloading,
        config.max_bakabt_downloading,
        now,
        torrent_titles=processed_titles,
    )


def prefilter_candidates(
    torrents: list[BakaBTTorrent], config: BrushConfig, now: datetime | None = None,
) -> list[BakaBTTorrent]:
    """先用浏览页可知字段过滤，发布时间未知的近期条目留给详情页二次确认。"""
    now = _utc(now)
    candidates = [
        item for item in torrents
        if item.is_freeleech
        and _matches_size(item, config)
        and (item.published_at is None or _matches_time(item, config, now))
    ]
    return sorted(candidates, key=lambda item: _sort_key(item, now), reverse=True)


def matches_final_filters(
    item: BakaBTTorrent, config: BrushConfig, now: datetime | None = None,
) -> bool:
    """详情页复核后的最终判断；启用了时间限制却无法得到时间时安全跳过。"""
    now = _utc(now)
    if not item.is_freeleech or not _matches_size(item, config):
        return False
    if config.min_publish_age_minutes == 0 and config.max_publish_age_minutes == 0:
        return True
    if item.published_at is None:
        return False
    return _matches_time(item, config, now)


def _sync_qb_state(config: BrushConfig, state: dict[str, Any], qb_instance: Any):
    torrents = list_bakabt_torrents(qb_instance, config.qb_category)
    uploaded_mb, downloaded_mb = transfer_totals_mb(torrents)
    current_downloading = downloading_count(torrents)
    update_qb(
        state,
        uploaded_mb=uploaded_mb,
        downloaded_mb=downloaded_mb,
        downloading_count=current_downloading,
        max_downloading=config.max_bakabt_downloading,
    )
    remember_completed(state, completed_infohashes(torrents))
    return torrents


def _finish(
    state: dict[str, Any],
    status: str,
    added: tuple[BakaBTTorrent, ...],
    failures: tuple[str, ...],
    detail: str,
    downloading_count: int,
    max_downloading: int,
    now: datetime,
    torrent_titles: list[str] | None = None,
) -> RunResult:
    titles = [item.title for item in added] or (torrent_titles or list(failures))
    record_run(state, {
        "time": now.isoformat().replace("+00:00", "Z"),
        "status": status,
        "torrent": "、".join(titles) if titles else "-",
        "push": f"已推送 {len(added)} 个" if added else ("推送失败" if failures else "未推送"),
        "detail": detail,
    })
    return RunResult(
        status=status,
        added=added,
        failed_titles=failures,
        detail=detail,
        downloading_count=downloading_count,
        max_downloading=max_downloading,
    )


def _matches_size(item: BakaBTTorrent, config: BrushConfig) -> bool:
    if item.size_mb < 0:
        return False
    if config.min_size_mb > 0 and item.size_mb < config.min_size_mb:
        return False
    if config.max_size_mb > 0 and item.size_mb > config.max_size_mb:
        return False
    return True


def _matches_time(item: BakaBTTorrent, config: BrushConfig, now: datetime) -> bool:
    if item.published_at is None:
        return config.min_publish_age_minutes == 0 and config.max_publish_age_minutes == 0
    published_at = _utc(item.published_at)
    age_minutes = max(0, (now - published_at).total_seconds() / 60)
    if config.min_publish_age_minutes > 0 and age_minutes < config.min_publish_age_minutes:
        return False
    if config.max_publish_age_minutes > 0 and age_minutes > config.max_publish_age_minutes:
        return False
    return True


def _sort_key(item: BakaBTTorrent, now: datetime) -> tuple[float, float]:
    """发布时间新优先；同一时间使用较大体积打破平局。"""
    if item.published_at is not None:
        published_at = _utc(item.published_at).timestamp()
    elif item.added_text.lower() == "today":
        published_at = now.timestamp()
    elif item.added_text.lower() == "yesterday":
        published_at = now.timestamp() - 24 * 60 * 60
    else:
        published_at = 0
    return published_at, item.size_mb


def _append_note(primary: str, note: str) -> str:
    return f"{primary}；{note}" if note else primary


def _utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
