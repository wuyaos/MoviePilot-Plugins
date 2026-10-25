#!/usr/bin/env python3
"""不可躺(tangpt.top) 自动领红包独立脚本。

已实测契约：鉴权仅依赖 Cookie c_secure_pass；latest/detail 使用 GET；claim 使用
表单编码 POST packet_id=<id>。脚本单进程串行领取，红包需顺序抢，不做并发。
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

BASE = "https://www.tangpt.top"
LATEST = f"{BASE}/api/redpacket/latest"
CLAIM = f"{BASE}/api/redpacket/claim"
DETAIL = f"{BASE}/api/redpacket/detail"
DEFAULT_OUT = "/tmp/tangredpacket_claim.log.jsonl"
DEFAULT_SUMMARY = "/tmp/tangredpacket_claim.summary.json"
LOOP_INTERVAL = 60.0
MAX_RETRIES = 3

# Cookie 从环境变量 TANGPT_COOKIE 读取(避免凭证硬编码进脚本/仓库)。
# 形如: c_secure_pass=xxxx;也可含多个键值对以分号分隔。
# 仍可用 --cookie 命令行参数覆盖;两者都未设置时报错退出。
COOKIE = os.environ.get("TANGPT_COOKIE", "")

HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": f"{BASE}/index.php",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
    ),
}

LOG = logging.getLogger("tangredpacket_claim")


class CookieExpiredError(RuntimeError):
    """Cookie 失效或无权限访问红包接口。"""


class RateLimitState:
    """记录接口限流头，并在额度接近耗尽时延长等待。"""

    def __init__(self) -> None:
        self.limit: int | None = None
        self.remaining: int | None = None

    def update(self, headers: requests.structures.CaseInsensitiveDict[str]) -> None:
        """从响应头解析 x-ratelimit-limit / x-ratelimit-remaining。"""
        limit = _to_int(headers.get("x-ratelimit-limit"))
        remaining = _to_int(headers.get("x-ratelimit-remaining"))
        if limit is not None:
            self.limit = limit
        if remaining is not None:
            self.remaining = remaining
            LOG.debug("限流剩余额度: %s/%s", self.remaining, self.limit or "?")

    def sleep_seconds(self, normal_seconds: float, interval: float) -> float:
        """额度接近 0 时基于轮询间隔自动延长 sleep。"""
        if self.remaining is None:
            return normal_seconds
        if self.remaining <= 0:
            return max(normal_seconds, interval)
        if self.limit and self.remaining <= max(1, int(self.limit * 0.1)):
            return max(normal_seconds, min(interval, normal_seconds * 5))
        return normal_seconds


def _to_int(value: Any | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def setup_logging(verbose: bool) -> None:
    """初始化带时间戳和级别的日志。"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def cookie_dict(cookie: str) -> dict[str, str]:
    """把浏览器 Cookie 字符串解析为 requests 可用的 dict。"""
    out: dict[str, str] = {}
    for part in (cookie or "").split(";"):
        if "=" in part:
            key, value = part.split("=", 1)
            if key.strip():
                out[key.strip()] = value.strip()
    return out


def request_json(
    session: requests.Session,
    method: str,
    url: str,
    rate_limit: RateLimitState,
    **kwargs: Any,
) -> dict[str, Any]:
    """请求 JSON 接口；仅网络异常指数退避重试，业务失败不重试。"""
    last_error: requests.RequestException | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.request(method, url, timeout=15, **kwargs)
            rate_limit.update(response.headers)
            try:
                body: dict[str, Any] = response.json()
            except ValueError:
                body = {
                    "status": "error",
                    "message": f"非 JSON 响应 HTTP {response.status_code}: {response.text[:120]}",
                }
            body["_http"] = response.status_code
            return body
        except requests.RequestException as exc:
            last_error = exc
            if attempt >= MAX_RETRIES:
                break
            delay = 2 ** (attempt - 1)
            LOG.warning("网络异常，第 %s/%s 次重试，%ss 后重试: %s", attempt, MAX_RETRIES, delay, exc)
            time.sleep(delay)
    raise RuntimeError(f"网络请求失败，已重试 {MAX_RETRIES} 次: {last_error}")


def fetch_latest(session: requests.Session, rate_limit: RateLimitState) -> dict[str, Any]:
    return request_json(session, "GET", LATEST, rate_limit)


def fetch_detail(session: requests.Session, rate_limit: RateLimitState, packet_id: Any) -> dict[str, Any]:
    return request_json(session, "GET", f"{DETAIL}/{packet_id}", rate_limit)


def claim_one(session: requests.Session, rate_limit: RateLimitState, packet_id: Any) -> dict[str, Any]:
    # jQuery $.ajax 默认表单编码，POST body 即 packet_id=<id>。
    return request_json(session, "POST", CLAIM, rate_limit, data={"packet_id": str(packet_id)})


def is_fail(body: dict[str, Any]) -> bool:
    """严格按已实测契约判断失败；其余非失败即成功。"""
    if body.get("_http") in (401, 403):
        return True
    if body.get("status") == "error":
        return True
    if body.get("ok") is False:
        return True
    return False


def is_auth_fail(body: dict[str, Any]) -> bool:
    return body.get("_http") in (401, 403)


def is_terminal_message(message: str) -> bool:
    """已领取/抢完类失败不再重试当前红包。"""
    return "已领取" in message or "领取过" in message or "抢完" in message


def fmt_amount(body: dict[str, Any]) -> str:
    """从 detail 响应拼出“剩余总池 / 剩余个数 / 类型”的预览。"""
    packet = body.get("packet") or {}
    if not isinstance(packet, dict) or not packet:
        return "(无 packet 字段)"
    remain_magic = packet.get("remain_magic", "?")
    remain_count = packet.get("remain_count", "?")
    packet_type = "拼手气" if packet.get("type") == "random" else ("平均" if packet.get("type") else "?")
    return f"类型={packet_type} 剩余={remain_magic}魔力/{remain_count}个"


def load_claimed_ids(path: str) -> set[str]:
    """读取 jsonl 领取记录，重启后跳过已成功领取的 packet_id。"""
    claimed: set[str] = set()
    record_path = Path(path)
    if not record_path.exists():
        return claimed
    try:
        with record_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    LOG.warning("领取记录存在无效 JSON 行，已忽略: %s", line[:120])
                    continue
                if record.get("event") not in (None, "claim_ok"):
                    continue
                packet_id = record.get("packet_id")
                if packet_id is not None:
                    claimed.add(str(packet_id))
    except OSError as exc:
        LOG.warning("读取领取记录失败，将不使用历史跳过列表: %s", exc)
    return claimed


def migrate_legacy_records(path: str) -> None:
    """补齐旧版 jsonl 记录缺失的 event 字段。"""
    record_path = Path(path)
    if not record_path.exists():
        return
    try:
        lines = record_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        LOG.warning("读取领取记录用于迁移失败，已跳过: %s", exc)
        return

    migrated = 0
    out_lines: list[str] = []
    for line in lines:
        if not line.strip():
            out_lines.append(line)
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            out_lines.append(line)
            continue
        if "event" in record:
            out_lines.append(line)
            continue
        record["event"] = "claim_ok"
        out_lines.append(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
        migrated += 1

    if migrated == 0:
        return
    tmp_path = record_path.with_name(f".{record_path.name}.tmp")
    try:
        with tmp_path.open("w", encoding="utf-8") as handle:
            handle.write("\n".join(out_lines))
            if lines:
                handle.write("\n")
        tmp_path.replace(record_path)
    except OSError as exc:
        LOG.warning("迁移领取记录失败，已保留原文件: %s", exc)
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        return
    LOG.info("已迁移旧版领取记录 %s 条，补齐 event=claim_ok", migrated)


def local_time_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def append_event_record(path: str, record: dict[str, Any]) -> None:
    """追加写入红包事件 jsonl。"""
    record_path = Path(path)
    record_path.parent.mkdir(parents=True, exist_ok=True)
    with record_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def write_summary(out_path: str, summary_path: str) -> None:
    """从 jsonl 全量聚合并写入轻量汇总文件。"""
    record_path = Path(out_path)
    summary = {
        "updated_at": local_time_iso(),
        "total_claimed": 0,
        "total_failed": 0,
        "total_magic_gained": 0,
        "by_sender": {},
        "by_title": {},
        "by_date": {},
        "recent": [],
    }
    line_count = 0
    if record_path.exists():
        try:
            with record_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    line_count += 1
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        LOG.warning("领取记录存在无效 JSON 行，汇总时已忽略: %s", line[:120])
                        continue
                    event = record.get("event") or "claim_ok"
                    if event == "claim_fail":
                        summary["total_failed"] += 1
                        continue
                    if event != "claim_ok":
                        continue
                    magic = record.get("magic_amount")
                    try:
                        magic_value = float(magic)
                    except (TypeError, ValueError):
                        magic_value = 0.0
                    summary["total_claimed"] += 1
                    summary["total_magic_gained"] += magic_value
                    sender = str(record.get("sender") or "未知")
                    title = str(record["title_name"] or "无头衔") if "title_name" in record else "未知头衔"
                    date_key = str(record.get("time") or "")[:10] or "未知日期"
                    for bucket_name, key in (("by_sender", sender), ("by_title", title), ("by_date", date_key)):
                        bucket = summary[bucket_name].setdefault(key, {"claimed": 0, "magic": 0})
                        bucket["claimed"] += 1
                        bucket["magic"] += magic_value
                    summary["recent"].append(record)
        except OSError as exc:
            LOG.warning("读取领取记录生成汇总失败: %s", exc)
    if line_count > 5000:
        LOG.info("领取记录已超过 5000 行，当前 %s 行，汇总仍按全量重算", line_count)
    summary["recent"] = summary["recent"][-10:]
    for bucket_name in ("by_sender", "by_title", "by_date"):
        for item in summary[bucket_name].values():
            if isinstance(item.get("magic"), float) and item["magic"].is_integer():
                item["magic"] = int(item["magic"])
    if isinstance(summary["total_magic_gained"], float) and summary["total_magic_gained"].is_integer():
        summary["total_magic_gained"] = int(summary["total_magic_gained"])
    target = Path(summary_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, separators=(",", ":"))


def ensure_cookie_alive(latest_body: dict[str, Any]) -> None:
    """latest 401/403 时明确提示 Cookie 过期。"""
    if is_auth_fail(latest_body):
        raise CookieExpiredError("latest 返回 401/403，Cookie 可能已过期，请更新 c_secure_pass")


def run_once(
    session: requests.Session,
    rate_limit: RateLimitState,
    latest: dict[str, Any],
    do_claim: bool,
    fast: bool,
    claimed_ids: set[str],
    dead_ids: set[str],
    out_path: str,
    summary_path: str,
    interval: float,
) -> int:
    """执行一轮 latest -> detail/fast -> claim；单个红包异常不影响后续。"""
    ensure_cookie_alive(latest)
    claimed_count = 0
    failed_count = 0
    skipped_count = 0
    bonus_delta = 0.0
    auth_fail_count = 0
    total_seen = 0
    should_process = True
    if latest.get("enabled") is False:
        should_process = False
        LOG.warning("红包功能已被管理员全局关闭，停止本轮处理")

    items = latest.get("items") or []
    total = latest.get("total_packet_count", 0)
    claim_mode = "fast-claim" if fast else "detail-then-claim"
    if should_process and not items:
        should_process = False
        LOG.info("暂无可领红包(items 空,total_packet_count=%s)，当前为 %s 模式", total, claim_mode)

    if should_process:
        LOG.info("发现 %s 个可领红包(待领总数 %s)，当前为 %s 模式，--claim=%s，串行处理", len(items), total, claim_mode, "开" if do_claim else "关(dry-run)")

    for item in items if should_process else []:
        total_seen += 1
        try:
            packet_id = item.get("id")
            if packet_id is None:
                LOG.warning("红包缺少 id，跳过: %s", item)
                skipped_count += 1
                continue
            packet_key = str(packet_id)
            sender = item.get("sender", "?")
            title = item.get("title_name", "")
            title_class = item.get("title_class")
            message = item.get("message", "")
            packet_type = item.get("type")
            total_count = item.get("total_count")
            remain_count = _to_int(item.get("remain_count"))
            remain_magic = None
            label = f"#{packet_key} 来自 {sender}{(' [' + title + ']') if title else ''}"

            if packet_key in claimed_ids:
                skipped_count += 1
                LOG.info("CLAIM_SKIP packet_id=%s sender=%s reason=already_claimed", packet_key, sender)
                append_event_record(out_path, {
                    "event": "claim_skip",
                    "time": local_time_iso(),
                    "packet_id": packet_id,
                    "sender": sender,
                    "title_name": title,
                    "reason": "already_claimed",
                })
                continue
            if packet_key in dead_ids:
                skipped_count += 1
                LOG.info("CLAIM_SKIP packet_id=%s sender=%s reason=dead", packet_key, sender)
                append_event_record(out_path, {
                    "event": "claim_skip",
                    "time": local_time_iso(),
                    "packet_id": packet_id,
                    "sender": sender,
                    "title_name": title,
                    "reason": "dead",
                })
                continue

            if fast:
                LOG.info("%s 剩余%s个/共%s个%s", label, remain_count if remain_count is not None else "?", total_count if total_count is not None else "?", f' "{message}"' if message else "")
                if remain_count is not None and remain_count <= 0:
                    skipped_count += 1
                    LOG.info("CLAIM_SKIP packet_id=%s sender=%s reason=snatched_empty", packet_key, sender)
                    append_event_record(out_path, {
                        "event": "claim_skip",
                        "time": local_time_iso(),
                        "packet_id": packet_id,
                        "sender": sender,
                        "title_name": title,
                        "title_class": title_class,
                        "reason": "snatched_empty",
                    })
                    dead_ids.add(packet_key)
                    continue
            else:
                detail = fetch_detail(session, rate_limit, packet_key)
                if is_auth_fail(detail):
                    auth_fail_count += 1
                    LOG.error("%s detail 返回 401/403，疑似 Cookie 过期", label)
                    continue
                if is_fail(detail):
                    detail_message = str(detail.get("message") or detail)
                    skipped_count += 1
                    LOG.warning("CLAIM_SKIP packet_id=%s sender=%s reason=detail_error", packet_key, sender)
                    append_event_record(out_path, {
                        "event": "claim_skip",
                        "time": local_time_iso(),
                        "packet_id": packet_id,
                        "sender": sender,
                        "title_name": title,
                        "reason": "detail_error",
                        "message": detail_message,
                    })
                    if is_terminal_message(detail_message):
                        dead_ids.add(packet_key)
                    continue

                preview = fmt_amount(detail)
                LOG.info("%s %s%s", label, preview, f' "{message}"' if message else "")
                packet = detail.get("packet") or {}
                if isinstance(packet, dict):
                    sender = packet.get("sender") or sender
                    title = packet.get("title_name") or title
                    title_class = packet.get("title_class") or title_class
                    message = packet.get("message") or message
                    packet_type = packet.get("type")
                    total_count = packet.get("total_count")
                    remain_count = _to_int(packet.get("remain_count"))
                    remain_magic = _to_int(packet.get("remain_magic"))
                    if (remain_count is not None and remain_count <= 0) or remain_magic == 0:
                        skipped_count += 1
                        LOG.info("CLAIM_SKIP packet_id=%s sender=%s reason=snatched_empty", packet_key, sender)
                        append_event_record(out_path, {
                            "event": "claim_skip",
                            "time": local_time_iso(),
                            "packet_id": packet_id,
                            "sender": sender,
                            "title_name": title,
                            "title_class": title_class,
                            "reason": "snatched_empty",
                        })
                        dead_ids.add(packet_key)
                        continue
                else:
                    title_class = None
                    packet_type = None
                    total_count = None
                    remain_count = None
                    remain_magic = None
            if not do_claim:
                continue

            result = claim_one(session, rate_limit, packet_key)
            if is_auth_fail(result):
                auth_fail_count += 1
                LOG.error("%s claim 返回 401/403，疑似 Cookie 过期", label)
                continue
            if is_fail(result):
                fail_message = str(result.get("message") or result)
                failed_count += 1
                http_status = result.get("_http")
                LOG.warning("CLAIM_FAIL packet_id=%s sender=%s reason=%s http=%s", packet_key, sender, fail_message, http_status)
                append_event_record(out_path, {
                    "event": "claim_fail",
                    "time": local_time_iso(),
                    "packet_id": packet_id,
                    "sender": sender,
                    "title_name": title,
                    "title_class": title_class,
                    "reason": fail_message,
                    "http": http_status,
                })
                if is_terminal_message(fail_message):
                    dead_ids.add(packet_key)
                continue

            amount = result.get("magic_amount")
            after = result.get("user_bonus_after")
            record = {
                "event": "claim_ok",
                "time": local_time_iso(),
                "packet_id": packet_id,
                "sender": sender,
                "title_name": title,
                "title_class": title_class,
                "packet_type": packet_type,
                "message": message,
                "total_count": total_count,
                "remain_count": remain_count,
                "remain_magic": remain_magic,
                "magic_amount": amount,
                "user_bonus_after": after,
            }
            append_event_record(out_path, record)
            write_summary(out_path, summary_path)
            claimed_ids.add(packet_key)
            claimed_count += 1
            try:
                bonus_delta += float(amount)
            except (TypeError, ValueError):
                pass
            LOG.info(
                "CLAIM_OK packet_id=%s sender=%s title=%s type=%s amount=%s bonus_after=%s remain_count=%s remain_magic=%s",
                packet_key,
                sender,
                title or "",
                packet_type,
                amount if amount is not None else "?",
                after if after is not None else "?",
                remain_count if remain_count is not None else "?",
                remain_magic if remain_magic is not None else "?",
            )

            sleep_seconds = rate_limit.sleep_seconds(1.0, interval)
            LOG.debug("claim 后 sleep %.1fs 防风控/限流", sleep_seconds)
            time.sleep(sleep_seconds)
        except Exception as exc:
            LOG.exception("处理单个红包异常，已隔离并继续后续红包: %s", exc)

    if items and auth_fail_count == len(items):
        write_summary(out_path, summary_path)
        raise CookieExpiredError("latest 有红包但 detail/claim 全部返回 401/403，Cookie 可能已过期，请更新 c_secure_pass")

    if bonus_delta.is_integer():
        bonus_delta_value: int | float = int(bonus_delta)
    else:
        bonus_delta_value = bonus_delta
    LOG.info(
        "ROUND_END claimed=%s failed=%s skipped=%s total_seen=%s bonus_delta=%s ratelimit_remaining=%s",
        claimed_count,
        failed_count,
        skipped_count,
        total_seen,
        bonus_delta_value,
        rate_limit.remaining if rate_limit.remaining is not None else "?",
    )
    write_summary(out_path, summary_path)
    return claimed_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="不可躺自动领红包")
    parser.add_argument("--cookie", default=COOKIE, help="覆盖脚本顶部内嵌 Cookie")
    parser.add_argument("--claim", action="store_true", help="实际领取(默认 dry-run 仅列出)")
    parser.add_argument("--fast", action="store_true", help="跳过 detail，直接使用 latest 字段预览并 claim")
    parser.add_argument("--loop", action="store_true", help="持续轮询，有红包就领")
    parser.add_argument("--once", action="store_true", help="只执行一次，等价于不传 --loop")
    parser.add_argument("--interval", type=float, default=LOOP_INTERVAL, help="轮询间隔(秒)")
    parser.add_argument("--out", default=DEFAULT_OUT, help=f"红包事件记录 jsonl 路径(默认 {DEFAULT_OUT})")
    parser.add_argument("--summary", default=DEFAULT_SUMMARY, help=f"红包统计汇总 json 路径(默认 {DEFAULT_SUMMARY})")
    parser.add_argument("--verbose", action="store_true", help="输出 DEBUG 日志")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    setup_logging(args.verbose)

    if args.once and args.loop:
        LOG.warning("同时传入 --once 和 --loop，按 --once 只执行一次")
        args.loop = False
    if not args.cookie or "c_secure_pass=" not in args.cookie:
        LOG.error("未配置 Cookie，请编辑脚本顶部 COOKIE 常量或传入 --cookie")
        return 2

    session = requests.Session()
    session.headers.update(HEADERS)
    session.cookies.update(cookie_dict(args.cookie))
    rate_limit = RateLimitState()
    claimed_ids = load_claimed_ids(args.out)
    migrate_legacy_records(args.out)
    dead_ids: set[str] = set()

    LOG.info("单进程串行领取模式，不并发；记录文件: %s；历史已领 %s 个", args.out, len(claimed_ids))
    if not args.claim:
        LOG.info("当前为 dry-run，不会实际领取；加 --claim 才会提交领取")

    try:
        latest = fetch_latest(session, rate_limit)
        ensure_cookie_alive(latest)
    except CookieExpiredError as exc:
        LOG.error("%s", exc)
        return 1
    except Exception as exc:
        LOG.error("连接 latest 接口失败，请检查 Cookie/网络: %s", exc)
        return 1
    LOG.info("登录态自检通过: enabled=%s total_packet_count=%s items=%s", latest.get("enabled"), latest.get("total_packet_count"), len(latest.get("items") or []))
    write_summary(args.out, args.summary)

    if not args.loop:
        try:
            run_once(session, rate_limit, latest, args.claim, args.fast, claimed_ids, dead_ids, args.out, args.summary, args.interval)
        except CookieExpiredError as exc:
            LOG.error("%s", exc)
            return 1
        if not args.claim:
            LOG.info("以上为 dry-run；加 --claim 实际领取，加 --loop 持续轮询")
        return 0

    LOG.info("持续轮询启动，间隔 %.1fs，--claim=%s", args.interval, "开" if args.claim else "关(dry-run)")
    while True:
        try:
            run_once(session, rate_limit, latest, args.claim, args.fast, claimed_ids, dead_ids, args.out, args.summary, args.interval)
        except KeyboardInterrupt:
            LOG.info("用户中断，退出")
            return 0
        except CookieExpiredError as exc:
            LOG.error("%s", exc)
            return 1
        except Exception as exc:
            LOG.exception("主循环本轮异常，loop 模式继续下一轮: %s", exc)

        sleep_seconds = rate_limit.sleep_seconds(args.interval, args.interval)
        LOG.debug("下一轮 sleep %.1fs", sleep_seconds)
        try:
            time.sleep(sleep_seconds)
            latest = fetch_latest(session, rate_limit)
            ensure_cookie_alive(latest)
        except KeyboardInterrupt:
            LOG.info("用户中断，退出")
            return 0
        except CookieExpiredError as exc:
            LOG.error("%s", exc)
            return 1
        except Exception as exc:
            LOG.exception("刷新 latest 失败，loop 模式继续下一轮: %s", exc)
            latest = {"items": [], "total_packet_count": 0}


if __name__ == "__main__":
    sys.exit(main())
