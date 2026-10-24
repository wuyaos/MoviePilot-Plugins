"""V2 风格的逐站签到与登录轮次通知。"""

FORMATS = ("plain", "markdown", "html")
PARSE_MODES = {"plain": "plain", "markdown": "MarkdownV2", "html": "HTML"}


def _bold(text: str, fmt: str) -> str:
    if fmt == "markdown":
        return f"**{text}**"
    if fmt == "html":
        return f"<b>{text}</b>"
    return text


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
        # pending 族：不冠「失败」，按未确认语义报告。
        return 3, "网络请求失败或超时，本轮未确认，稍后自动重试"
    if status == "maintenance":
        return 3, "站点维护中/已关闭，本轮跳过"
    if status == "unconfirmed":
        return 3, "签到结果未确认，请人工核验"
    if status == "protocol_pending":
        return 3, "验证码/协议未适配，未提交"
    if status == "failed":
        return 2, "签到失败" + (f"，{message}" if message else "")
    return 2, "签到失败" + (f"，{message}" if message else (f"，{reason}" if reason else ""))


def format_round_notifications(summary: dict, fmt: str = "plain") -> list[tuple[str, str]]:
    """返回分轨消息（标题、文本）；summary 按 action 提供计数与逐站 entries。"""
    fmt = fmt if fmt in FORMATS else "plain"
    result = []
    for track, title, verb in (("sign", "【站点自动签到】", "签到"),
                               ("login", "【站点自动登录】", "模拟登录")):
        data = summary.get(track) or {}
        entries = list(data.get("entries", []))
        if not data.get("total") and not entries:
            continue
        lines = [
            f"全部{verb}数量: {data.get('total', 0)}（启用且已勾选{verb}）",
            f"本次{verb}数量: {data.get('executed', 0)}（本轮实际执行）",
            f"下次{verb}数量: {data.get('next', 0)}（本轮后仍待办）",
        ]
        if track == "sign":
            rendered = []
            for site, entry in entries:
                bucket, text = _sign_text(entry)
                rendered.append((bucket, site, text))
            # 分组排序：成功(0) → 已签(1) → 未确认/待办(3) → 失败(2)
            rendered.sort(key=lambda item: (0 if item[0] == 0 else 2 if item[0] == 1 else 3 if item[0] == 3 else 4, item[1]))
            for bucket, site, text in rendered:
                if fmt == "html":
                    color = {0: "#28a745", 1: "#6c757d", 2: "#dc3545", 3: "#fd7e14"}.get(bucket, "#6c757d")
                    lines.append(f'<div style="color:{color}">【{site}】{text}</div>')
                else:
                    lines.append(f"【{site}】{text}")
        else:
            rendered = []
            for site, entry in entries:
                status = entry.get("status", "")
                message = (entry.get("message") or "").strip()
                if status == "login_ok":
                    rendered.append((0, site, "模拟登录成功" + (f"，{message}" if message else "")))
                elif status == "unconfirmed":
                    rendered.append((3, site, "模拟登录结果未确认，请人工核验"))
                else:
                    rendered.append((2, site, "模拟登录失败" + (f"，{message}" if message else "")))
            rendered.sort(key=lambda item: (item[0], item[1]))
            for bucket, site, text in rendered:
                if fmt == "html":
                    color = {0: "#28a745", 2: "#dc3545", 3: "#fd7e14"}.get(bucket, "#6c757d")
                    lines.append(f'<div style="color:{color}">【{site}】{text}</div>')
                else:
                    lines.append(f"【{site}】{text}")
        if fmt == "html":
            lines = [_bold_html(lines[i]) if i < 3 else lines[i] for i in range(len(lines))]
        elif fmt == "markdown":
            lines = [_bold(lines[i]) if i < 3 else lines[i] for i in range(len(lines))]
        result.append((title, "\n".join(lines)))
    return result


def _bold_html(text: str) -> str:
    import re
    return re.sub(r"^(\S+):", r"<b>\1</b>:", text)
