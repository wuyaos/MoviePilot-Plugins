"""BakaBTBrush 单轮执行流程：先检查 qB 槽位，再访问 BakaBT。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from collections.abc import Callable
from typing import Any

from .cleanup import execute_cleanup
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
from .filtering import matches_final_filters, prefilter_candidates, sort_key
from .models import BakaBTTorrent
from .scraper import BakaBTClient, BakaBTError
from .state import (
    remember_added,
    remember_completed,
    remember_detail,
    record_run,
    reset_detail_cache_for_day,
    restore_detail,
    update_account,
    update_added_metadata,
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
    previewed: tuple[BakaBTTorrent, ...] = ()
    deleted: tuple[dict[str, Any], ...] = ()

    @property
    def should_notify_success(self) -> bool:
        return bool(self.added)

    @property
    def should_notify_failure(self) -> bool:
        return self.status == "failed"

    @property
    def should_notify_dry_run(self) -> bool:
        return self.status == "dry_run"

    @property
    def should_notify_deletion(self) -> bool:
        return bool(self.deleted)


def run_once(
    config: BrushConfig,
    cookie: str | Callable[[], str],
    state: dict[str, Any],
    qb_instance: Any,
    *,
    dry_run: bool = False,
    now: datetime | None = None,
    client: BakaBTClient | None = None,
) -> RunResult:
    """执行一次刷流检查；dry_run 只筛选与记录，不请求 .torrent 或添加 qB。"""
    now = _utc(now)
    reset_detail_cache_for_day(state, now)
    try:
        qb_torrents = _sync_qb_state(config, state, qb_instance)
    except DownloaderError:
        return _finish(
            state, "failed", (), (), "qBittorrent 查询失败", 0, config.max_bakabt_downloading, now,
        )

    deleted_records: list[dict[str, Any]] = []
    cleanup_notes: list[str] = []
    resolved_cookie = ""
    runtime_client = client

    # 自动删种先于槽位判断执行，否则 2/2 时永远无法清理超时任务。
    if config.auto_delete and not dry_run:
        records, notes = execute_cleanup(
            config, state, qb_instance, qb_torrents, now, client=None,
        )
        deleted_records.extend(records)
        cleanup_notes.extend(notes)

        if config.delete_expired_freeleech_incomplete:
            resolved_cookie = (cookie() if callable(cookie) else cookie).strip()
            if resolved_cookie:
                runtime_client = runtime_client or BakaBTClient(
                    resolved_cookie,
                    timeout=config.timeout,
                    detail_retries=config.detail_request_retries,
                )
                records, notes = execute_cleanup(
                    config, state, qb_instance, qb_torrents, now, client=runtime_client,
                    freeleech_only=True,
                    excluded_hashes={item["infohash"] for item in deleted_records},
                )
                deleted_records.extend(records)
                cleanup_notes.extend(notes)
            else:
                cleanup_notes.append("促销过期检查跳过：未取得 BakaBT Cookie")

        if deleted_records:
            try:
                qb_torrents = _sync_qb_state(config, state, qb_instance)
            except DownloaderError:
                cleanup_notes.append("自动删除后刷新 qB 状态失败")

    current_downloading = downloading_count(qb_torrents)
    slots = available_slots(config.max_bakabt_downloading, current_downloading)
    if slots == 0:
        return _finish(
            state,
            "no_qb_slot",
            (),
            (),
            _append_cleanup_note(
                f"当前 BakaBT 下载流程：{current_downloading}/{config.max_bakabt_downloading}",
                deleted_records,
                cleanup_notes,
            ),
            current_downloading,
            config.max_bakabt_downloading,
            now,
            deleted=tuple(deleted_records),
        )

    if not resolved_cookie:
        resolved_cookie = (cookie() if callable(cookie) else cookie).strip()
    if not resolved_cookie:
        return _finish(
            state,
            "failed",
            (),
            (),
            _append_cleanup_note(
                "未配置 BakaBT Cookie，且 CookieCloud 未匹配到 bakabt.me",
                deleted_records,
                cleanup_notes,
            ),
            current_downloading,
            config.max_bakabt_downloading,
            now,
            deleted=tuple(deleted_records),
        )
    runtime_client = runtime_client or BakaBTClient(
        resolved_cookie,
        timeout=config.timeout,
        detail_retries=config.detail_request_retries,
    )
    client = runtime_client
    try:
        page = client.fetch_browse()
    except BakaBTError as err:
        return _finish(
            state,
            "failed",
            (),
            (),
            _append_cleanup_note(str(err), deleted_records, cleanup_notes),
            current_downloading,
            config.max_bakabt_downloading,
            now,
            deleted=tuple(deleted_records),
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
    account_note = _append_cleanup_note(account_note, deleted_records, cleanup_notes)
    for item in page.torrents:
        update_added_metadata(state, item)

    candidates = [
        item for item in prefilter_candidates(page.torrents, config)
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
            deleted=tuple(deleted_records),
        )

    existing_hashes = {item.infohash for item in qb_torrents}
    added: list[BakaBTTorrent] = []
    previewed: list[BakaBTTorrent] = []
    failures: list[str] = []
    processed_titles: list[str] = []

    # 浏览页的 Today 只是粗筛；必须先读取全部详情页取得精确发布时间，
    # 再按发布间隔过滤并排序，确保下载槽位优先分配给最新发布的种子。
    detail_candidates: list[BakaBTTorrent] = []
    cached_detail_ids: set[str] = set()
    for item in candidates:
        processed_titles.append(item.title)
        try:
            if restore_detail(state, item):
                cached_detail_ids.add(str(item.torrent_id))
            else:
                detail = client.fetch_detail(item.detail_url)
                item.is_freeleech = detail.is_freeleech
                item.published_at = detail.published_at
                item.download_url = detail.download_url
                item.infohash = detail.infohash
                # 只缓存可用于后续下载的完整详情；不完整详情下轮重新请求。
                if item.published_at is not None and item.download_url and item.infohash:
                    remember_detail(state, item)
            if not matches_final_filters(item, config, now):
                continue
            if not item.download_url or not item.infohash:
                failures.append(item.title)
                continue
            if item.infohash.lower() in existing_hashes:
                continue
            detail_candidates.append(item)
        except BakaBTError:
            failures.append(item.title)
            # 单个详情页失败不阻断后续 Today 候选。
            continue

    # 详情页时间是筛选和排序的唯一来源：发布时间最新（发布间隔最短）优先。
    detail_candidates.sort(key=lambda item: sort_key(item, now), reverse=True)
    candidate_limit = slots if slots is not None else len(detail_candidates)
    for item in detail_candidates:
        selected_count = len(previewed) if dry_run else len(added)
        if selected_count >= candidate_limit:
            break
        try:
            if dry_run:
                # 试运行仍复核详情页，但不请求 .torrent，也绝不调用 qB 添加接口。
                previewed.append(item)
                existing_hashes.add(item.infohash.lower())
                continue
            try:
                content = client.fetch_torrent(item.download_url)
            except BakaBTError:
                # 下载链接可能带短期 token；仅缓存链接失效时补一次详情刷新。
                if str(item.torrent_id) not in cached_detail_ids:
                    raise
                detail = client.fetch_detail(item.detail_url)
                item.is_freeleech = detail.is_freeleech
                item.published_at = detail.published_at
                item.download_url = detail.download_url
                item.infohash = detail.infohash
                if item.published_at is not None and item.download_url and item.infohash:
                    remember_detail(state, item)
                if not matches_final_filters(item, config, now) or not item.download_url or not item.infohash:
                    raise BakaBTError("缓存详情刷新后未通过最终过滤")
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
            # 单个候选添加失败时继续尝试下一个发布时间较早的候选。
            continue

    if dry_run:
        slot_text = (
            "qB 下载流程不限制" if config.max_bakabt_downloading == 0
            else f"qB 下载槽位：{current_downloading}/{config.max_bakabt_downloading}"
        )
        if previewed:
            detail = _append_note(f"试运行完成，候选未推送 qB；{slot_text}", account_note)
        elif failures:
            detail = _append_note(f"试运行完成，{len(failures)} 个候选详情复核失败", account_note)
        else:
            detail = _append_note("试运行完成，未找到可推送候选", account_note)
        return _finish(
            state,
            "dry_run",
            (),
            tuple(failures),
            detail,
            current_downloading,
            config.max_bakabt_downloading,
            now,
            torrent_titles=processed_titles,
            previewed=tuple(previewed),
            deleted=tuple(deleted_records),
        )

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
            deleted=tuple(deleted_records),
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
            deleted=tuple(deleted_records),
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
        deleted=tuple(deleted_records),
    )


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
        torrents=torrents,
    )
    remember_completed(state, completed_infohashes(torrents))
    return torrents


def _append_cleanup_note(
    primary: str,
    deleted: list[dict[str, Any]],
    notes: list[str],
) -> str:
    extras = []
    if deleted:
        extras.append(f"自动删除 {len(deleted)} 个 qB 任务")
    extras.extend(notes)
    result = primary
    for note in extras:
        result = _append_note(result, note)
    return result


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
    previewed: tuple[BakaBTTorrent, ...] = (),
    deleted: tuple[dict[str, Any], ...] = (),
) -> RunResult:
    titles = (
        [item.title for item in added]
        or [item.title for item in previewed]
        or (torrent_titles or list(failures))
    )
    push = (
        f"已推送 {len(added)} 个" if added
        else f"试运行，未推送 {len(previewed)} 个" if status == "dry_run"
        else "推送失败" if failures
        else "未推送"
    )
    linked_items = added or previewed
    record_run(state, {
        "time": now.isoformat().replace("+00:00", "Z"),
        "status": status,
        "torrent": "、".join(titles) if titles else "-",
        "torrent_links": [
            {
                "title": item.title,
                "url": item.detail_url,
                "published_at": (
                    item.published_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
                    if item.published_at else ""
                ),
                "size_mb": round(max(0.0, item.size_mb), 2),
            }
            for item in linked_items
        ],
        "push": push,
        "detail": detail,
    })
    return RunResult(
        status=status,
        added=added,
        failed_titles=failures,
        detail=detail,
        downloading_count=downloading_count,
        max_downloading=max_downloading,
        previewed=previewed,
        deleted=deleted,
    )


def _append_note(primary: str, note: str) -> str:
    return f"{primary}；{note}" if note else primary


def _utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
