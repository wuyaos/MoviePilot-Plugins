"""推送消息渲染：单站结果与轮次摘要共用一套格式；/notify_preview 与真实推送走同一路径。

输出格式（notify_format，默认 plain）与渠道适配（MP V3 宿主实测口径）：
- Telegram：MarkdownV2 / HTML / plain 均支持（宿主 telegramify 标准化）；
- 飞书：默认 Markdown 卡片，显式 plain 才发纯文本；
- Discord：原生渲染 Markdown；Slack：mrkdwn 用单星号，`**` 会降级显示；
- 钉钉 / QQBot / SynologyChat / VoceChat / WebPush：纯文本，Markdown 符号原样露出。
"""
from .models import SignResult

SUCCESS_STATUSES = frozenset({"success", "signed", "already", "login_ok"})
FAILED_STATUSES = frozenset({"failed", "auth_failed"})
UNCONFIRMED_STATUSES = frozenset({"unconfirmed"})

# notify_format 合法值；parse_mode 透传宿主 Message（Telegram/飞书识别，其余渠道忽略）。
FORMATS = ("plain", "markdown", "html")
PARSE_MODES = {"plain": "plain", "markdown": "MarkdownV2", "html": "HTML"}


def format_notification(site: str, result: SignResult) -> str:
    """单站行；奖励仅在解析到时出现，不再输出「未知」兜底。"""
    parts = [f"{site}：{result.status.value}", (result.message or "").strip()]
    reward = (result.reward.reported if result.reward and result.reward.reported else "").strip()
    if reward:
        parts.append(f"奖励：{reward}")
    return "，".join(part for part in parts if part)


def _track_lines(summary: dict) -> list[tuple[str, dict]]:
    return [(label, summary.get(track) or {})
            for track, label in (("sign", "签到"), ("login", "登录"))
            if any((summary.get(track) or {}).values())]


def format_round_summary(summary: dict, fmt: str = "plain") -> str:
    """轮次/预览摘要。summary 形如：
    {"sign": {"success": 2, "failed": 1, "unconfirmed": 0, "other": 1},
     "login": {...}, "failures": ["13city（签到：站点不可达）", ...]}
    """
    fmt = fmt if fmt in FORMATS else "plain"

    def bold(text: str) -> str:
        return {"plain": text, "markdown": f"**{text}**", "html": f"<b>{text}</b>"}[fmt]

    track_lines = []
    for label, counts in _track_lines(summary):
        stats = (f"成功 {counts.get('success', 0)} · 失败 {counts.get('failed', 0)}"
                 f" · 未确认 {counts.get('unconfirmed', 0)} · 待办 {counts.get('other', 0)}")
        track_lines.append(f"{bold(label)} {stats}")
    body = "\n".join(track_lines) or "本轮无待执行站点"
    lines = [body]
    failures = summary.get("failures") or []
    if failures:
        shown = failures[:10]
        if fmt == "html":
            lines.append("<ul>" + "".join(f"<li>{item}</li>" for item in shown)
                         + ("<li>…</li>" if len(failures) > 10 else "") + "</ul>")
        elif fmt == "plain":
            lines.append("异常与失败：" + "、".join(shown) + ("…" if len(failures) > 10 else ""))
        else:
            lines.append("\n".join(f"- {item}" for item in shown)
                         + ("\n- …" if len(failures) > 10 else ""))
    return "\n\n".join(lines)
