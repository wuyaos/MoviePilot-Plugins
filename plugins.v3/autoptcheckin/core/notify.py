"""V2 风格的逐站签到与登录轮次通知（纯文本）。"""


# 锁忙/取消/门控禁用没有执行结论：不进明细，也不计入本轮三项（skipped 沿用停用色）。
_TRANSIENT_STATUSES = ("skipped", "cancelled")

# 三桶分类唯一入口：0 已完成 / 1 失败 / 2 待处理；_track_rows 与 _counts 共用，避免两套枚举。
_SUCCESS_STATUSES = frozenset({"success", "signed", "already", "login_ok"})
_FAILURE_STATUSES = frozenset({"failed", "auth_failed"})

# pending 族约定 reason 值：精确匹配，不做子串猜测；旧 status 值同表兼容。
_PENDING_REASON_TEXT = {
    "network_error": "网络请求失败或超时，本轮未确认，稍后自动重试",
    "maintenance": "站点维护中/已关闭，本轮跳过",
    "protocol_pending": "提交前置条件未满足，本轮未提交",
    "result_unknown": "结果未知，待下轮重试",
}


def _reportable(entry: dict) -> bool:
    status = entry.get("status", "")
    return status not in _TRANSIENT_STATUSES and entry.get("state") != "disabled"


def _bucket(entry: dict) -> int:
    status = entry.get("status", "")
    if status in _SUCCESS_STATUSES:
        return 0
    if status in _FAILURE_STATUSES:
        return 1
    # pending 族与未知状态一律待处理：不武断把未知值算成明确失败。
    return 2


def _pending_text(entry: dict) -> str:
    """pending 按 reason 精确细分网络/维护/协议/结果未知；未命中不编造原因，只回显原 message。"""
    message = (entry.get("message") or "").strip()
    base = _PENDING_REASON_TEXT.get(entry.get("reason", "")) or _PENDING_REASON_TEXT.get(entry.get("status", ""))
    if base is None:
        return message or "结果未知，待下轮重试"
    return base + (f"（{message}）" if message else "")


def _text(track: str, entry: dict) -> str:
    """单站状态文本；_reportable 已在 _track_rows 过滤，这里只管有结论的条目。"""
    status = entry.get("status", "")
    message = (entry.get("message") or "").strip()
    if status == "success":
        # 完整消息（可能含奖励信息），仅在重复前缀时去重。
        if message:
            return message if "签到成功" in message else f"签到成功，{message}"
        return "签到成功"
    if status == "signed":
        # 奖励/诊断都在 message 里，不能丢；already_signed 表示此前已签、非本轮新签。
        if entry.get("reason") == "already_signed":
            return "此前已签" + (f"，{message}" if message else "")
        # 与 success 同一套完整 message 去重；无 message 保留已签语义。
        if message:
            return message if "签到成功" in message else f"签到成功，{message}"
        return "今日已签到"
    if status == "already":
        return "今日已签到"
    if status == "login_ok":
        return "模拟登录成功" + (f"，{message}" if message else "")
    if status == "auth_failed":
        if track == "sign":
            cred = entry.get("credential", "cookie")
            return "签到失败，Cookie 已失效" if cred == "cookie" else "签到失败，认证失败"
        return "模拟登录认证失败" + (f"（{message}）" if message else "")
    if status == "failed":
        if track == "sign":
            reason = entry.get("reason", "")
            return "签到失败" + (f"，{message}" if message else (f"，{reason}" if reason else ""))
        return "模拟登录失败" + (f"，{message}" if message else "")
    if status == "unconfirmed":
        base = "签到结果未确认，请人工核验" if track == "sign" else "模拟登录结果未确认，请人工核验"
        return base + (f"（{message}）" if message else "")
    return _pending_text(entry)


def _track_rows(track: str, entries: list) -> list[tuple[int, str, str]]:
    """统一构造分轨逐站行：(bucket, 站名, 状态文本)，bucket 0已完成/1失败/2待处理。"""
    rendered = []
    for site, entry in entries:
        if not _reportable(entry):
            continue
        rendered.append((_bucket(entry), site, _text(track, entry)))
    rendered.sort(key=lambda item: (item[0], item[1]))
    return rendered


def _three_counts(entries: list) -> tuple[int, int, int]:
    """(成功, 失败, 待处理)，仅统计有执行结论的条目；分类与明细共用 _bucket。"""
    counts = [0, 0, 0]
    for _, entry in entries:
        if _reportable(entry):
            counts[_bucket(entry)] += 1
    return counts[0], counts[1], counts[2]


def _counts(data: dict, entries: list) -> tuple[int, int, int, int]:
    """(全部, 本次=成功+失败+待处理, 本轮成功, 下轮待执行)；明细与队列不可相互反推。"""
    success, failed, pending = _three_counts(entries)
    # 下一轮以实际待执行集合为准（data.next 直接复用）；历史失败明细不能反推队列长度。
    return data.get("total", 0), success + failed + pending, success, data.get("next", 0)


def format_round_notifications(summary: dict) -> list[tuple[str, str, str]]:
    """返回分轨纯文本消息（track, 标题, 文本）；summary 按 action 提供计数与逐站 entries。

    纯文本是唯一格式：Telegram 等渠道按 HTML 解析富文本会对 <div> 等标签返回
    400（can't parse entities），且宿主渠道能力差异大，统一降级为无标签文本。
    本轮计数只取 round_entries；entries 中的当日旧待办仅补明细，不补本轮数字。
    """
    result = []
    for track, title, all_label, this_label in (
            ("sign", "【PT 签到中心】", "全部签到", "本次签到"),
            ("login", "【PT 签到中心】", "全部登录", "本次登录")):
        data = summary.get(track) or {}
        entries = list(data.get("entries", []))
        # round_entries 键存在（即使为空）即为本轮口径；缺失时回退 entries 兼容直调。
        round_entries = data["round_entries"] if "round_entries" in data else entries
        total, executed, success, next_count = _counts(data, round_entries)
        _, failed, pending = _three_counts(round_entries)
        lines = [
            f"{all_label}: {total}",
            f"{this_label}: {executed}（成功 {success} · 失败 {failed} · 待处理 {pending}）",
            f"下轮待执行: {next_count}",
        ]
        rows = _track_rows(track, entries)
        for bucket, header in ((0, "—— ✅ 已完成 ——"), (1, "—— ❌ 失败 ——"), (2, "—— ⏳ 待处理 ——")):
            group = [f"【{site}】{text}" for b, site, text in rows if b == bucket]
            if group:
                lines.append(header)
                lines.extend(group)
        # 「全部签到/登录」是启用站点数，恒大于 0，不能当作“这一轨有没有话说”的判据。
        # 本轮没跑、也没有明细行和待执行队列时，整条全 0 消息纯噪音，跳过。
        if not executed and not rows and not next_count:
            continue
        result.append((track, title, "\n".join(lines)))
    return result
