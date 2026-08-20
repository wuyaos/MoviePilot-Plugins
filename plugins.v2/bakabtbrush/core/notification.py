"""BakaBTBrush 聚合通知文本。"""

from __future__ import annotations

from .config import BrushConfig
from .presentation import format_elapsed, format_local_time
from .runner import RunResult


def build_notification(config: BrushConfig, result: RunResult) -> tuple[str, str] | None:
    if result.should_notify_success:
        lines = [
            "✅ **BakaBT 刷流任务完成**", "", f"**已推送**：{len(result.added)} 个", "**种子**：",
        ]
        for item in result.added:
            lines.extend([
                f"- [{_escape_title(item.title)}]({item.detail_url})",
                f"  体积：{item.size_mb:.2f} MB",
                f"  发种时间：{format_local_time(item.published_at)}",
                f"  发布间隔：{format_elapsed(item.published_at)}",
            ])
        slot_text = (
            "不限制" if result.max_downloading == 0
            else f"{result.downloading_count}/{result.max_downloading}"
        )
        lines.extend([
            "", f"**qB 下载槽位**：{slot_text}", f"**分类**：{config.qb_category}",
            f"**标签**：{', '.join(config.qb_tags)}",
        ])
        lines.extend(_deletion_lines(result))
        return "【BakaBT 刷流已加入 qB】", "\n".join(lines)

    if result.should_notify_dry_run and result.previewed:
        lines = [
            "🧪 **BakaBT 刷流试运行完成**", "",
            f"**候选**：{len(result.previewed)} 个（未推送 qB）", "**种子**：",
        ]
        for item in result.previewed:
            lines.extend([
                f"- {item.title}（{item.size_mb:.2f} MB）",
                f"  发种时间：{format_local_time(item.published_at)}",
                f"  发布间隔：{format_elapsed(item.published_at)}",
            ])
        lines.append(f"\n**详情**：{result.detail}")
        return "【BakaBT 刷流试运行】", "\n".join(lines)

    if result.should_notify_failure:
        titles = "、".join(result.failed_titles) or "-"
        lines = [
            "❌ **BakaBT 刷流添加失败**", "", f"**失败种子**：{titles}", f"**原因**：{result.detail}",
        ]
        lines.extend(_deletion_lines(result))
        return "【BakaBT 刷流任务异常】", "\n".join(lines)

    if result.should_notify_deletion:
        return "【BakaBT 自动删种】", "\n".join(_deletion_lines(result, include_heading=False))
    return None


def _deletion_lines(result: RunResult, *, include_heading: bool = True) -> list[str]:
    if not result.deleted:
        return []
    lines = ["", f"**自动删除**：{len(result.deleted)} 个"] if include_heading else [
        f"🧹 **已自动删除 {len(result.deleted)} 个 qB 任务**", ""
    ]
    for record in result.deleted:
        title = str(record.get("title") or "未知种子")
        url = str(record.get("detail_url") or "")
        display = f"[{_escape_title(title)}]({url})" if url else title
        lines.extend([
            f"- {display}",
            f"  原因：{record.get('reason') or '命中删除条件'}",
            f"  文件：{'已删除' if record.get('delete_files') else '保留'}",
        ])
    return lines


def _escape_title(title: str) -> str:
    return title.replace("[", "\\[").replace("]", "\\]")
