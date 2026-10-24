"""V2 风格的逐站签到与登录轮次通知（纯文本）。"""


def _sign_text(entry: dict) -> tuple[int, str]:
    status = entry.get("status", "")
    message = (entry.get("message") or "").strip()
    reason = entry.get("reason", "")
    if status in ("signed", "already"):
        return 1, "今日已签到"
    if status == "success":
        # 完整消息（可能含奖励信息），仅在重复前缀时去重。
        if message:
            return 0, message if "签到成功" in message else f"签到成功，{message}"
        return 0, "签到成功"
    if status == "auth_failed":
        cred = entry.get("credential", "cookie")
        return 2, "签到失败，Cookie 已失效" if cred == "cookie" else "签到失败，认证失败"
    if status == "network_error":
        # pending 族：不冠「失败」，按未确认语义报告；附带可达性诊断（HTTP 502/超时等）。
        return 3, "网络请求失败或超时，本轮未确认，稍后自动重试" + (f"（{message}）" if message else "")
    if status == "maintenance":
        return 3, "站点维护中/已关闭，本轮跳过" + (f"（{message}）" if message else "")
    if status == "unconfirmed":
        return 3, "签到结果未确认，请人工核验" + (f"（{message}）" if message else "")
    if status == "protocol_pending":
        return 3, "验证码/协议未适配，未提交" + (f"（{message}）" if message else "")
    return 2, "签到失败" + (f"，{message}" if message else (f"，{reason}" if reason else ""))


def _track_rows(track: str, entries: list) -> list[tuple[int, str, str]]:
    """统一构造分轨逐站行：(bucket, 站名, 状态文本)，bucket 0成功/1已签/3未确认/2失败。"""
    rendered = []
    if track == "sign":
        for site, entry in entries:
            bucket, text = _sign_text(entry)
            rendered.append((bucket, site, text))
        # 分组排序：成功(0) → 已签(1) → 未确认/待办(3) → 失败(2)
        rendered.sort(key=lambda item: (0 if item[0] == 0 else 2 if item[0] == 1 else 3 if item[0] == 3 else 4, item[1]))
    else:
        for site, entry in entries:
            status = entry.get("status", "")
            message = (entry.get("message") or "").strip()
            if status == "login_ok":
                rendered.append((0, site, "模拟登录成功" + (f"，{message}" if message else "")))
            elif status == "unconfirmed":
                rendered.append((3, site, "模拟登录结果未确认，请人工核验" + (f"（{message}）" if message else "")))
            else:
                rendered.append((2, site, "模拟登录失败" + (f"，{message}" if message else "")))
        rendered.sort(key=lambda item: (item[0], item[1]))
    return rendered


def _counts(data: dict, entries: list) -> tuple[int, int, int, int]:
    """(全部, 本次, 成功, 失败[下次])。"""
    success = sum(1 for _, e in entries if e.get("status") in ("success", "signed", "already", "login_ok"))
    failed_next = sum(1 for _, e in entries if e.get("status") not in ("success", "signed", "already", "login_ok"))
    return data.get("total", 0), data.get("executed", 0), success, max(data.get("next", 0), failed_next)


def format_round_notifications(summary: dict) -> list[tuple[str, str, str]]:
    """返回分轨纯文本消息（track, 标题, 文本）；summary 按 action 提供计数与逐站 entries。

    纯文本是唯一格式：Telegram 等渠道按 HTML 解析富文本会对 <div> 等标签返回
    400（can't parse entities），且宿主渠道能力差异大，统一降级为无标签文本。
    """
    result = []
    for track, title, verb in (("sign", "【PT 签到中心】", "签到"),
                               ("login", "【PT 签到中心】", "模拟登录")):
        data = summary.get(track) or {}
        entries = list(data.get("entries", []))
        if not data.get("total") and not entries:
            continue
        total, executed, success, failed_next = _counts(data, entries)
        lines = [
            f"全部{verb}: {total}",
            f"本次{verb}: {executed}",
            f"成功: {success}",
            f"失败（下次{verb}）: {failed_next}",
        ]
        ok_rows, bad_rows = [], []
        for bucket, site, text in _track_rows(track, entries):
            (ok_rows if bucket in (0, 1) else bad_rows).append(f"【{site}】{text}")
        if ok_rows:
            lines.append("—— ✅ 成功 ——")
            lines.extend(ok_rows)
        if bad_rows:
            lines.append("—— ❌ 失败（未确认）——")
            lines.extend(bad_rows)
        result.append((track, title, "\n".join(lines)))
    return result
