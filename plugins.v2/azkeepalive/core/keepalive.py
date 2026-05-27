# input: site_url, 下载器实例, 插件 state
# output: keepalive 结果 | pos: 核心运行器
from __future__ import annotations
import datetime as dt
import tempfile
from pathlib import Path
from typing import Any

from app.core.config import settings as app_settings
from app.log import logger
from .models import FeedItem, format_size
from .downloader import dl_add_torrent, dl_check_hnr, dl_has_hash, torrent_infohash
from .scraper import fetch_torrents, filter_eligible, visit_site

MAX_HISTORY = 50
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def run_keepalive(
    *, site_url: str, downloader_instance: Any,
    category: str, tags: str, keepalive_days: int, min_seeders: int,
    max_size_gb: float, require_free: bool, timeout: int,
    use_proxy: bool, cookie: str = "", state: dict[str, Any],
    force: bool = False, auto_delete_hnr: bool = False,
    skip_interval_check: bool = False,
) -> tuple[str, str, dict[str, Any]]:
    """执行一次保活检查"""
    now = dt.datetime.now(dt.UTC).replace(microsecond=0)
    proxies = app_settings.PROXY if use_proxy else None

    if not skip_interval_check:
        visit_due, _ = _should_run(
            state, "last_visit_at", keepalive_days, now, action="访问", force=force,
        )
        download_due, _ = _should_run(
            state, "last_download_at", keepalive_days, now, action="下载", force=force,
        )
        if not visit_due and not download_due:
            reason = "访问和下载均未到插件保活间隔"
            _append(state, "skipped", now, reason=reason, checked=False)
            return "skipped", _skip_msg(state, keepalive_days, now, reason), state

    visit_message = ""
    if not cookie:
        logger.warning("AZ保活: CookieCloud 未获取到 Cookie，用户信息无法抓取")
        visit_message = "CookieCloud 未获取到 AnimeZ Cookie，无法执行访问保活"
    else:
        vr = visit_site(site_url, cookie=cookie, timeout=timeout, proxies=proxies)
        found = False
        if vr.get("ok"):
            for k in ("upload", "download", "ratio", "buffer", "seeds",
                      "leeches", "bonus", "hnr", "reseed", "name"):
                if k in vr:
                    state[f"user_{k}"] = vr[k]
                    found = True
            if found:
                _append(state, "visit_success", now, reason="访问保活成功")
                visit_message = "访问保活成功"
            else:
                # P0 fix: HTTP 200 = 登录态有效，即使用户信息解析失败也推进 last_visit_at
                _append(state, "visit_ok", now, reason="访问成功但未解析到用户信息")
                visit_message = "访问成功但未解析到用户信息"
                logger.warning(f"AZ保活: {visit_message}")
        else:
            visit_message = "访问 AnimeZ 失败，未更新访问保活时间"
            logger.warning(f"AZ保活: {visit_message}")

    # H&R 检查：满足做种时限则移除标签，可选删除
    if downloader_instance:
        done = dl_check_hnr(downloader_instance, category, auto_delete=auto_delete_hnr)
        if done:
            logger.info(f"AZ保活: H&R完成 {len(done)} 个: {', '.join(done[:3])}")

    if not downloader_instance:
        msg = "下载器未配置或不可用，无法执行下载保活"
        msg = f"{visit_message or '站点访问已尝试执行'}；{msg}"
        _append(state, "failed", now, reason=msg)
        return "failed", msg, state
    if not cookie:
        msg = "CookieCloud 未获取到 AnimeZ Cookie，无法执行下载保活"
        _append(state, "failed", now, reason=msg)
        return "failed", msg, state

    try:
        submit_tags = f"{tags},H&R" if tags else "H&R"
        strategies = _build_strategies(max_size_gb, require_free)
        for label, free, size in strategies:
            r = _scan_pages(site_url, cookie, timeout, proxies, free, size,
                            min_seeders, downloader_instance, category, submit_tags,
                            state, now)
            if r:
                return r[0], r[1], state
            logger.info(f"AZ保活: 策略[{label}]无新种子，尝试下一策略")

        _append(state, "no_candidate", now, reason="所有策略均未找到可下载种子")
        return "no_candidate", ("⚠️ 未找到新种子\n━━━━━━━━━━━━━\n"
                                 "所有策略已扫描，候选种子均已存在于下载器\n"
                                 "建议: 删除部分旧种子或调整筛选条件"), state
    except Exception as e:
        logger.error(f"AZ保活失败: {e}")
        _append(state, "failed", now, reason=str(e))
        return "failed", f"执行失败: {e}", state


def _scan_pages(
    site_url: str, cookie: str, timeout: int, proxies: dict | None,
    freeleech: bool, max_size_gb: float, min_seeders: int,
    dl_inst: Any, category: str, tags: str,
    state: dict[str, Any], now: dt.datetime,
) -> tuple[str, str] | None:
    """逐页扫描，找到第一个可下载种子立即提交"""
    for page in range(1, 11):
        items = fetch_torrents(site_url, cookie=cookie, timeout=timeout,
                               proxies=proxies, freeleech=freeleech, page=page)
        if not items:
            break
        eligible = filter_eligible(items, min_seeders, max_size_gb, freeleech)
        logger.info(f"AZ保活: p{page} 解析={len(items)} 候选={len(eligible)}")

        # 逐个检查候选，找到即提交
        for item in eligible:
            result = _try_one(item, cookie, timeout, proxies, dl_inst,
                              category, tags, state, now)
            if result:
                return result
    return None


def _try_one(
    item: FeedItem, cookie: str, timeout: int, proxies: dict | None,
    dl_inst: Any, category: str, tags: str,
    state: dict[str, Any], now: dt.datetime,
) -> tuple[str, str] | None:
    """尝试下载并提交单个种子"""
    from app.utils.http import RequestUtils
    tmp_path: Path | None = None
    try:
        headers = {"User-Agent": UA, "Referer": "https://animez.to/"}
        if cookie:
            headers["Cookie"] = cookie
        res = RequestUtils(
            headers=headers, proxies=proxies, timeout=timeout,
        ).get_res(url=item.url)
        if not res or res.status_code != 200:
            logger.debug(f"种子下载失败: {item.title} [{res.status_code if res else '无响应'}]")
            return None
        body = res.content
        if not _looks_like_torrent(body, res.headers.get("Content-Type", "")):
            logger.debug(f"非种子文件: {item.title}")
            return None

        with tempfile.NamedTemporaryFile(suffix=".torrent", delete=False) as tmp:
            tmp.write(body)
            tmp_path = Path(tmp.name)

        infohash = torrent_infohash(tmp_path)
        if dl_has_hash(dl_inst, infohash):
            logger.debug(f"下载器已有: {item.title} ({infohash[:8]})")
            return None

        if dl_add_torrent(dl_inst, tmp_path, category=category, tags=tags):
            _append(state, "download_success", now, item=item, infohash=infohash)
            free_tag = "🆓 Free" if item.is_free else "付费"
            msg = (f"✅ 保活下载成功\n"
                   f"━━━━━━━━━━━━━\n"
                   f"📦 {item.title}\n"
                   f"💾 体积: {format_size(item.size_bytes)}\n"
                   f"🌱 做种: {item.seeders}  |  {free_tag}\n"
                   f"📁 分类: {category}")
            logger.info(f"AZ保活: 成功 {item.title}")
            return "download_success", msg

        logger.warning(f"提交失败: {item.title}")
    except Exception as e:
        logger.warning(f"候选异常: {item.title} - {e}")
    finally:
        if tmp_path:
            tmp_path.unlink(missing_ok=True)
    return None


def _build_strategies(max_size_gb: float, require_free: bool) -> list[tuple[str, bool, float]]:
    """构建扫描策略标签，避免关闭 Free 限制时日志仍显示 Free。"""
    if require_free:
        return [
            (f"Free<={max_size_gb}GB", True, max_size_gb),
            ("Free不限体积", True, 999999),
            (f"全部<={max_size_gb}GB", False, max_size_gb),
        ]
    return [
        (f"全部<={max_size_gb}GB", False, max_size_gb),
        ("全部不限体积", False, 999999),
    ]


def _looks_like_torrent(body: bytes, content_type: str) -> bool:
    if "text/html" in content_type.lower():
        return False
    return body.lstrip().startswith(b"d") and b"announce" in body[:4096]


def _should_run(state: dict[str, Any], field: str, days: int, now: dt.datetime,
                action: str, force: bool = False) -> tuple[bool, str]:
    if force:
        return True, f"强制{action}保活"
    last = _parse_ts(state.get(field))
    if last is None:
        return True, f"{action}首次运行"
    if now - last >= dt.timedelta(days=days):
        return True, f"{action}已到插件保活间隔"
    return False, f"{action}未到插件保活间隔"


def _append(
    state: dict[str, Any], status: str, now: dt.datetime,
    reason: str = "", item: FeedItem | None = None, infohash: str = "",
    checked: bool = True,
) -> None:
    ev: dict[str, Any] = {"time": _ts(now), "status": status}
    if reason:
        ev["reason"] = reason
    if item:
        ev.update(title=item.title, seeders=item.seeders,
                  size=format_size(item.size_bytes, item.size_text),
                  free=item.is_free)
    if infohash:
        ev["infohash"] = infohash
    history = state.setdefault("history", [])
    history.append(ev)
    del history[:-MAX_HISTORY]
    state["last_status"] = status
    if status in ("visit_success", "visit_ok"):
        state["last_visit_at"] = _ts(now)
    if status == "download_success":
        state["last_download_at"] = _ts(now)
        if item:
            state["last_title"] = item.title
    if checked:
        state["last_checked_at"] = _ts(now)


def _skip_msg(state: dict[str, Any], days: int, now: dt.datetime, reason: str) -> str:
    last_visit = _parse_ts(state.get("last_visit_at"))
    next_visit = _ts(last_visit + dt.timedelta(days=days)) if last_visit else "未知"
    last_download = _parse_ts(state.get("last_download_at"))
    next_download = _ts(last_download + dt.timedelta(days=days)) if last_download else "未知"
    return (f"⏭ 跳过本次执行\n━━━━━━━━━━━━━\n"
            f"📋 原因: {reason}\n"
            f"🌐 下次访问保活: {next_visit}\n"
            f"📥 下次下载保活: {next_download}")


def _ts(t: dt.datetime) -> str:
    return t.isoformat().replace("+00:00", "Z")


def _parse_ts(val: str | None) -> dt.datetime | None:
    if not val:
        return None
    try:
        p = dt.datetime.fromisoformat(val.replace("Z", "+00:00"))
        return p.replace(tzinfo=dt.UTC) if p.tzinfo is None else p.astimezone(dt.UTC)
    except ValueError:
        return None
