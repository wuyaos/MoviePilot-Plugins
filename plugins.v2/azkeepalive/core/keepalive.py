# input: RSS URL, 下载器实例, 插件 state
# output: keepalive 执行结果（成功/跳过/失败）
# pos: 核心运行器，编排 RSS → 筛选 → 下载 → 提交 → 记录

from __future__ import annotations

import datetime as dt
import tempfile
from pathlib import Path
from typing import Any

from app.core.config import settings as app_settings
from app.log import logger

from .models import FeedItem, format_size
from .qb_client import qb_add_torrent, qb_has_hash, torrent_infohash
from .rss import fetch_rss, filter_eligible, parse_feed, visit_site

MAX_HISTORY = 50


def run_keepalive(
    *,
    rss_url: str,
    downloader_instance: Any,
    category: str = "AnimeZ",
    tags: str = "keepalive",
    keepalive_days: int,
    min_seeders: int,
    max_items: int,
    timeout: int,
    use_proxy: bool,
    site_url: str = "",
    cookie: str = "",
    state: dict[str, Any],
) -> tuple[str, str, dict[str, Any]]:
    """
    执行一次保活检查。
    返回 (status, message, updated_state)
    """
    now = dt.datetime.now(dt.UTC).replace(microsecond=0)
    proxies = app_settings.PROXY if use_proxy else None

    # 每次都访问站点（模拟登录活跃 + 抓取用户信息）
    if site_url:
        visit_result = visit_site(site_url, cookie=cookie, timeout=timeout, proxies=proxies)
        state["last_visit_at"] = now.isoformat().replace("+00:00", "Z")
        if visit_result.get("ok"):
            for k in ("upload", "download", "ratio", "hnr", "bonus"):
                if k in visit_result:
                    state[f"user_{k}"] = visit_result[k]

    # 检查是否需要执行
    should, reason = _should_run(state, keepalive_days, now)
    if not should:
        _append(state, "skipped", now, reason=reason)
        return "skipped", _skip_msg(state, keepalive_days, now, reason), state

    try:
        xml = fetch_rss(rss_url, timeout=timeout, proxies=proxies)
        items = parse_feed(xml, max_items)
        eligible = filter_eligible(items, min_seeders)
        logger.info(f"AZ保活: 扫描={len(items)} 候选={len(eligible)}")

        if not eligible:
            _append(state, "no_candidate", now, reason="无符合条件的候选")
            return "no_candidate", f"扫描 {len(items)} 条，无候选 (seeders>={min_seeders})", state

        status, msg, _ = _try_candidates(
            eligible, downloader_instance, category, tags, timeout, proxies, state, now)
        return status, msg, state

    except Exception as e:
        logger.error(f"AZ保活失败: {e}")
        _append(state, "failed", now, reason=str(e))
        return "failed", f"执行失败: {e}", state


def _should_run(state: dict[str, Any], keepalive_days: int, now: dt.datetime) -> tuple[bool, str]:
    last_success = _parse_ts(state.get("last_success_at"))
    if last_success is None:
        return True, "无历史成功记录"
    if now - last_success >= dt.timedelta(days=keepalive_days):
        return True, "已到保活窗口"
    return False, "未到保活窗口"


def _try_candidates(
    eligible: list[FeedItem], dl_instance: Any,
    category: str, tags: str, timeout: int, proxies: dict | None,
    state: dict[str, Any], now: dt.datetime,
) -> tuple[str, str, FeedItem | None]:
    from app.utils.http import RequestUtils

    for i, item in enumerate(eligible, 1):
        logger.debug(f"检查候选 {i}/{len(eligible)}: {item.title}")
        try:
            res = RequestUtils(
                headers={"User-Agent": "AZ_KeepAlive/1.0", "Referer": "https://animez.to/"},
                proxies=proxies, timeout=timeout,
            ).get_res(url=item.url)
            if not res or res.status_code != 200:
                continue
            body = res.content
            if not _looks_like_torrent(body, res.headers.get("Content-Type", "")):
                continue

            with tempfile.NamedTemporaryFile(suffix=".torrent", delete=False) as tmp:
                tmp.write(body)
                tmp_path = Path(tmp.name)

            infohash = torrent_infohash(tmp_path)
            if qb_has_hash(dl_instance, infohash):
                logger.debug(f"qB 已存在: {item.title} ({infohash})")
                tmp_path.unlink(missing_ok=True)
                continue

            if qb_add_torrent(dl_instance, tmp_path, category=category, tags=tags):
                tmp_path.unlink(missing_ok=True)
                _append(state, "success", now, item=item, infohash=infohash)
                msg = f"成功提交: {item.title}\n体积: {format_size(item.size_bytes)} | 做种: {item.seeders}"
                return "success", msg, item

            tmp_path.unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"候选处理失败: {item.title} - {e}")
            continue

    _append(state, "no_candidate", now, reason="所有候选均已存在或不可用")
    return "no_candidate", "所有候选均已存在于 qBittorrent 或不可下载", None


def _looks_like_torrent(body: bytes, content_type: str) -> bool:
    if "text/html" in content_type.lower():
        return False
    stripped = body.lstrip()
    return stripped.startswith(b"d") and b"announce" in body[:4096]


def _append(
    state: dict[str, Any], status: str, now: dt.datetime,
    reason: str = "", item: FeedItem | None = None, infohash: str = "",
) -> None:
    ts = now.isoformat().replace("+00:00", "Z")
    event: dict[str, Any] = {"time": ts, "status": status}
    if reason:
        event["reason"] = reason
    if item:
        event.update(title=item.title, seeders=item.seeders,
                     size=format_size(item.size_bytes, item.size_text))
    if infohash:
        event["infohash"] = infohash
    history = state.setdefault("history", [])
    history.append(event)
    del history[:-MAX_HISTORY]
    state["last_status"] = status
    if status == "success":
        state["last_success_at"] = ts
        if item:
            state["last_title"] = item.title
    if status in {"success", "no_candidate", "skipped"}:
        state["last_checked_at"] = ts


def _skip_msg(state: dict[str, Any], keepalive_days: int, now: dt.datetime, reason: str) -> str:
    last_s = _parse_ts(state.get("last_success_at"))
    nxt = "未知"
    if last_s:
        nxt = (last_s + dt.timedelta(days=keepalive_days)).isoformat().replace("+00:00", "Z")
    return f"跳过: {reason}\n上次成功: {state.get('last_success_at', '无')}\n下次窗口: {nxt}"


def _parse_ts(val: str | None) -> dt.datetime | None:
    if not val:
        return None
    try:
        p = dt.datetime.fromisoformat(val.replace("Z", "+00:00"))
        if p.tzinfo is None:
            p = p.replace(tzinfo=dt.UTC)
        return p.astimezone(dt.UTC)
    except ValueError:
        return None
