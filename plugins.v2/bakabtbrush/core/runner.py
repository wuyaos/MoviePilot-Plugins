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
from .filtering import matches_final_filters, matches_size, prefilter_candidates, sort_key
from .models import BakaBTTorrent
from .scraper import BakaBTClient, BakaBTError, BakaBTRssClient
from .state import (
    cache_rss_pending,
    initialize_rss_cache,
    remember_added,
    remember_completed,
    remember_detail,
    remember_rss_feed,
    remember_rss_promotion,
    record_run,
    remove_rss_pending,
    reset_detail_cache_for_day,
    restore_detail,
    rss_cache_initialized,
    rss_feed_signature,
    rss_pending_retry_count,
    rss_pending_torrents,
    rss_source_hash,
    set_rss_pending_status,
    unseen_rss_torrents,
    update_account,
    update_added_metadata,
    update_qb,
    was_added,
)


RSS_PENDING_MAX_ATTEMPTS = 3
RSS_ACCOUNT_REFRESH_SECONDS = 6 * 60 * 60


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
    if config.rss_url:
        return _run_rss_discovery(
            config=config,
            cookie=cookie,
            state=state,
            qb_instance=qb_instance,
            qb_torrents=qb_torrents,
            current_downloading=current_downloading,
            slots=slots,
            deleted_records=deleted_records,
            cleanup_notes=cleanup_notes,
            dry_run=dry_run,
            now=now,
            client=runtime_client,
        )
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
            processed_titles.append(item.title)
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


def _run_rss_discovery(
    config: BrushConfig,
    cookie: str | Callable[[], str],
    state: dict[str, Any],
    qb_instance: Any,
    qb_torrents: list[Any],
    current_downloading: int,
    slots: int | None,
    deleted_records: list[dict[str, Any]],
    cleanup_notes: list[str],
    dry_run: bool,
    now: datetime,
    client: BakaBTClient | None,
) -> RunResult:
    """RSS 只发现新种；仅合格且未完成首次判定的候选触发一次浏览页。"""
    cleanup_note = _append_cleanup_note("", deleted_records, cleanup_notes)
    try:
        feed = BakaBTRssClient(timeout=config.timeout).fetch_rss(config.rss_url)
    except BakaBTError as err:
        return _finish(
            state,
            "failed",
            (),
            (),
            _append_note(str(err), cleanup_note),
            current_downloading,
            config.max_bakabt_downloading,
            now,
            deleted=tuple(deleted_records),
        )

    source_hash = rss_source_hash(config.rss_url)
    for item in feed.torrents:
        update_added_metadata(state, item)
    if not rss_cache_initialized(state, source_hash):
        initialize_rss_cache(state, source_hash, feed.torrents, now)
        return _finish(
            state,
            "no_candidate",
            (),
            (),
            _append_note("RSS 基线已建立，等待后续新种", cleanup_note),
            current_downloading,
            config.max_bakabt_downloading,
            now,
            deleted=tuple(deleted_records),
        )

    previous_signature = str((state.get("rss") or {}).get("signature") or "")
    current_signature = rss_feed_signature(feed.torrents)
    new_items = (
        unseen_rss_torrents(state, feed.torrents)
        if current_signature != previous_signature else []
    )
    for item in new_items:
        if was_added(state, item.torrent_id) or not matches_size(item, config):
            continue
        age_state = _rss_age_state(item, config, now)
        if age_state == "expired":
            continue
        cache_rss_pending(
            state,
            item,
            "waiting_age" if age_state == "waiting" else "waiting_promotion",
            now,
        )
    remember_rss_feed(state, feed.torrents, now)

    promotion_candidates: list[BakaBTTorrent] = []
    for item in rss_pending_torrents(
        state, {"waiting_age", "waiting_slot", "waiting_promotion"}
    ):
        if was_added(state, item.torrent_id) or not matches_size(item, config):
            remove_rss_pending(state, item.torrent_id)
            continue
        age_state = _rss_age_state(item, config, now)
        if age_state == "expired":
            remove_rss_pending(state, item.torrent_id)
        elif age_state == "waiting":
            set_rss_pending_status(state, item.torrent_id, "waiting_age")
        else:
            set_rss_pending_status(state, item.torrent_id, "waiting_promotion")
            promotion_candidates.append(item)

    detail_candidates = rss_pending_torrents(state, {"waiting_detail"})
    if slots == 0:
        for item in promotion_candidates:
            set_rss_pending_status(state, item.torrent_id, "waiting_slot")
        return _finish(
            state,
            "no_qb_slot",
            (),
            (),
            _append_note(
                f"当前 BakaBT 下载流程：{current_downloading}/{config.max_bakabt_downloading}，"
                f"缓存候选 {len(promotion_candidates) + len(detail_candidates)} 个",
                cleanup_note,
            ),
            current_downloading,
            config.max_bakabt_downloading,
            now,
            deleted=tuple(deleted_records),
        )

    if not promotion_candidates and not detail_candidates:
        detail = "RSS 无符合时间和体积的新种" if new_items else "RSS 未发现新种"
        return _finish(
            state,
            "no_candidate",
            (),
            (),
            _append_note(detail, cleanup_note),
            current_downloading,
            config.max_bakabt_downloading,
            now,
            deleted=tuple(deleted_records),
        )

    resolved_cookie = (cookie() if callable(cookie) else cookie).strip()
    if not resolved_cookie:
        return _finish(
            state,
            "failed",
            (),
            (),
            _append_note("未配置 BakaBT Cookie，且 CookieCloud 未匹配到 bakabt.me", cleanup_note),
            current_downloading,
            config.max_bakabt_downloading,
            now,
            deleted=tuple(deleted_records),
        )
    client = client or BakaBTClient(
        resolved_cookie,
        timeout=config.timeout,
        detail_retries=config.detail_request_retries,
    )

    account_note = ""
    failed_titles: list[str] = []
    if promotion_candidates:
        try:
            page = client.fetch_browse()
        except BakaBTError as err:
            for item in promotion_candidates:
                _record_rss_attempt_failure(state, item.torrent_id, "waiting_promotion", now)
            return _finish(
                state,
                "failed",
                (),
                tuple(item.title for item in promotion_candidates),
                _append_note(str(err), cleanup_note),
                current_downloading,
                config.max_bakabt_downloading,
                now,
                deleted=tuple(deleted_records),
            )

        # 账户快照只搭乘本轮已被新候选触发的浏览页访问，不为展示数据单独增加网页请求。
        if page.account_url and _account_snapshot_due(state, now):
            try:
                account = client.fetch_account(page.account_url)
                if account.uploaded_mb is not None or account.downloaded_mb is not None:
                    update_account(state, account)
                else:
                    account_note = "账户流量未识别"
            except BakaBTError:
                account_note = "账户页读取失败"

        browse_by_id = {item.torrent_id: item for item in page.torrents}
        for item in promotion_candidates:
            browse_item = browse_by_id.get(str(item.torrent_id))
            if browse_item is None:
                failed_titles.append(item.title)
                _record_rss_attempt_failure(state, item.torrent_id, "waiting_promotion", now)
                continue
            remember_rss_promotion(state, item.torrent_id, browse_item.is_freeleech, now)
            if not browse_item.is_freeleech:
                remove_rss_pending(state, item.torrent_id)
                continue
            set_rss_pending_status(state, item.torrent_id, "waiting_detail", now)

    detail_candidates = rss_pending_torrents(state, {"waiting_detail"})
    detail_candidates.sort(key=lambda item: sort_key(item, now), reverse=True)
    existing_hashes = {item.infohash for item in qb_torrents}
    added: list[BakaBTTorrent] = []
    previewed: list[BakaBTTorrent] = []
    processed_titles: list[str] = []
    candidate_limit = slots if slots is not None else len(detail_candidates)

    for item in detail_candidates:
        selected_count = len(previewed) if dry_run else len(added)
        if selected_count >= candidate_limit:
            break
        processed_titles.append(item.title)
        cached_detail = restore_detail(state, item)
        try:
            if not cached_detail:
                detail = client.fetch_detail(item.detail_url)
                _apply_detail(item, detail)
                if item.published_at is not None and item.download_url and item.infohash:
                    remember_detail(state, item)
            if not matches_final_filters(item, config, now):
                remove_rss_pending(state, item.torrent_id)
                continue
            if not item.download_url or not item.infohash:
                raise BakaBTError("BakaBT 详情缺少下载信息")
            if item.infohash.lower() in existing_hashes:
                remove_rss_pending(state, item.torrent_id)
                continue
            if dry_run:
                previewed.append(item)
                existing_hashes.add(item.infohash.lower())
                continue

            try:
                content = client.fetch_torrent(item.download_url)
            except BakaBTError:
                if not cached_detail:
                    raise
                detail = client.fetch_detail(item.detail_url)
                _apply_detail(item, detail)
                if item.published_at is not None and item.download_url and item.infohash:
                    remember_detail(state, item)
                if (
                    not matches_final_filters(item, config, now)
                    or not item.download_url
                    or not item.infohash
                ):
                    remove_rss_pending(state, item.torrent_id)
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
            remove_rss_pending(state, item.torrent_id)
            existing_hashes.add(infohash.lower())
            added.append(item)
        except (BakaBTError, DownloaderError):
            failed_titles.append(item.title)
            _record_rss_attempt_failure(state, item.torrent_id, "waiting_detail", now)

    account_note = _append_cleanup_note(account_note, deleted_records, cleanup_notes)
    if dry_run:
        if previewed:
            detail = "RSS 试运行完成，候选未推送 qB"
        elif failed_titles:
            detail = f"RSS 试运行完成，{len(failed_titles)} 个候选处理失败"
        else:
            detail = "RSS 试运行完成，未找到可推送候选"
        return _finish(
            state,
            "dry_run",
            (),
            tuple(failed_titles),
            _append_note(detail, account_note),
            current_downloading,
            config.max_bakabt_downloading,
            now,
            torrent_titles=processed_titles,
            previewed=tuple(previewed),
            deleted=tuple(deleted_records),
        )

    try:
        refreshed = _sync_qb_state(config, state, qb_instance)
        current_downloading = downloading_count(refreshed)
    except DownloaderError:
        current_downloading += len(added)

    if added:
        slot_text = (
            f"qB 下载槽位：{current_downloading}/{config.max_bakabt_downloading}"
            if config.max_bakabt_downloading else "qB 下载流程不限制"
        )
        return _finish(
            state,
            "success",
            tuple(added),
            tuple(failed_titles),
            _append_note(slot_text, account_note),
            current_downloading,
            config.max_bakabt_downloading,
            now,
            deleted=tuple(deleted_records),
        )
    if failed_titles:
        return _finish(
            state,
            "failed",
            (),
            tuple(failed_titles),
            _append_note("RSS 候选处理失败", account_note),
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
        _append_note("RSS 新种未命中 Freeleech 或已存在", account_note),
        current_downloading,
        config.max_bakabt_downloading,
        now,
        torrent_titles=processed_titles,
        deleted=tuple(deleted_records),
    )


def _rss_age_state(item: BakaBTTorrent, config: BrushConfig, now: datetime) -> str:
    if item.published_at is None:
        return "expired"
    age_minutes = max(0.0, (_utc(now) - _utc(item.published_at)).total_seconds() / 60)
    if config.publish_age_maximum > 0 and age_minutes > config.publish_age_maximum:
        return "expired"
    if config.publish_age_minimum > 0 and age_minutes < config.publish_age_minimum:
        return "waiting"
    return "ready"


def _record_rss_attempt_failure(
    state: dict[str, Any], torrent_id: str, status: str, now: datetime,
) -> None:
    attempt = rss_pending_retry_count(state, torrent_id) + 1
    set_rss_pending_status(
        state,
        torrent_id,
        status,
        now,
        increment_retry=True,
    )
    if attempt >= RSS_PENDING_MAX_ATTEMPTS:
        remember_rss_promotion(state, torrent_id, None, now)
        remove_rss_pending(state, torrent_id)


def _account_snapshot_due(state: dict[str, Any], now: datetime) -> bool:
    updated_at = str((state.get("account") or {}).get("updated_at") or "")
    if not updated_at:
        return True
    try:
        updated = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
    except ValueError:
        return True
    return (_utc(now) - _utc(updated)).total_seconds() >= RSS_ACCOUNT_REFRESH_SECONDS


def _apply_detail(item: BakaBTTorrent, detail: Any) -> None:
    item.is_freeleech = bool(detail.is_freeleech)
    item.published_at = detail.published_at or item.published_at
    item.download_url = detail.download_url
    item.infohash = detail.infohash


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
    if not primary:
        return note
    return f"{primary}；{note}" if note else primary


def _utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
