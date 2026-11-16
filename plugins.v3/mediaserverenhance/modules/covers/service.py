"""封面工坊模块。

用媒体条目已有的主图作为底图，本地合成风格化海报，可选上传回媒体服务器。
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from app.sdk.logging import logger

from ...adapter import mediaserver
from ...utils import store
from ...utils.config import as_bool, as_list, parse_scope, safe_int, scope_allows
from ...utils.runtime import observe_only
from ...utils.pillow import pillow_available
from ..refresh.service import history_limit, plugin_active
from . import render

MODULE = "covers"


def cover_dir(plugin) -> str:
    """返回封面输出目录。

    :param plugin: 插件实例
    :return: 目录绝对路径
    """
    base = getattr(plugin, "_cover_output_dir", "") or ""
    if base:
        return base
    try:
        root = Path(plugin.get_data_path()) / "covers"
    except Exception:  # noqa: BLE001 - 数据目录不可用时退回临时目录
        root = Path("covers")
    return str(root)


def _selected_servers(plugin, override: Optional[Sequence[str]] = None) -> List[str]:
    """解析封面任务涉及的服务器。"""
    explicit = as_list(override)
    if explicit:
        return explicit
    configured = as_list(getattr(plugin, "_cover_servers", None))
    if configured:
        return configured
    return [row["name"] for row in mediaserver.list_server_configs() if row.get("enabled")]


def _selected_libraries(plugin, override: Optional[Sequence[str]] = None) -> List[Tuple[str, str]]:
    """解析封面的媒体库范围（``server|library_id``），空列表表示不限。"""
    explicit = as_list(override)
    raw = explicit if explicit else as_list(getattr(plugin, "_cover_libraries", None))
    return parse_scope(raw)


def _subtitle(item: Any) -> str:
    """构造副标题文本。

    :param item: 媒体条目
    :return: 年份与类型组合文本
    """
    year = getattr(item, "year", None)
    item_type = getattr(item, "item_type", None)
    type_text = str(getattr(item_type, "value", item_type) or "")
    parts = [str(year)] if year else []
    if type_text:
        parts.append(type_text)
    return " · ".join(parts)


def run_cover(plugin, servers: Optional[Sequence[str]] = None,
              libraries: Optional[Sequence[str]] = None,
              style: Optional[str] = None,
              limit: Optional[int] = None,
              upload: bool = False,
              trigger: str = "手动") -> Dict[str, Any]:
    """生成一批风格化封面。

    :param plugin: 插件实例
    :param servers: 指定服务器
    :param libraries: 指定媒体库
    :param style: 风格键，缺省用配置
    :param limit: 本次最多生成数量，缺省用配置
    :param upload: 是否上传回服务器
    :param trigger: 触发来源说明
    :return: 封面任务结果字典
    """
    started = time.time()
    result: Dict[str, Any] = {
        "generated": 0,
        "uploaded": 0,
        "skipped": 0,
        "failed": 0,
        "items": [],
        "message": "",
    }
    if not pillow_available():
        result["message"] = "当前环境缺少 Pillow，无法生成封面"
        return result

    style_key = style or str(getattr(plugin, "_cover_style", "poster") or "poster")
    if style_key not in render.STYLE_KEYS:
        style_key = "poster"
    quota = safe_int(limit or getattr(plugin, "_cover_limit", 20), 20, 1, 500)
    upload_enabled = upload and as_bool(getattr(plugin, "_cover_upload", False))
    font_conf = str(getattr(plugin, "_cover_font", "") or "")
    server_names = _selected_servers(plugin, servers)
    library_filter = _selected_libraries(plugin, libraries)
    output_dir = cover_dir(plugin)

    job = store.build_job(MODULE, "generate", trigger=trigger, total=quota,
                          detail={"style": style_key, "upload": upload_enabled})
    if not server_names:
        store.finish_job(job, "skipped", "没有可用的媒体服务器")
        store.append_job(plugin, job, history_limit(plugin))
        result["message"] = "没有可用的媒体服务器"
        return result

    if upload_enabled:
        # 运行期互斥复查：初始化时的静态检测可能因插件启动时序漏检 CoverGen
        try:
            from ...adapter.host import installed_plugin_state

            cover_conflict = bool(installed_plugin_state("CoverGen").get("enabled"))
        except Exception:  # noqa: BLE001 - 探测失败按无冲突处理，由初始化兜底
            cover_conflict = False
        if cover_conflict:
            store.finish_job(job, "skipped", "检测到 CoverGen 已启用，封面上传与其互斥，已跳过")
            store.append_job(plugin, job, history_limit(plugin))
            result["message"] = "检测到 CoverGen（封面生成）已启用，两者都会覆盖媒体库封面，本次上传已跳过"
            return result

    for name in server_names:
        if result["generated"] >= quota:
            break
        for library in mediaserver.list_libraries(name) or []:
            if not scope_allows(library_filter, name, str(library.get("id") or "")):
                continue
            library_id = str(library.get("id") or "")
            if not library_id:
                continue
            if result["generated"] >= quota:
                break
            remaining = quota - result["generated"]
            try:
                library_items = mediaserver.iter_library_items(name, library_id, remaining)
            except Exception as error:  # noqa: BLE001 - 单库读取失败不中断其它媒体库
                logger.warning(f"【媒体服务器增强】{name}/{library_id} 条目读取失败，跳过该库：{error}")
                continue
            for item in library_items or []:
                item_id = str(getattr(item, "item_id", "") or "")
                if not item_id:
                    result["skipped"] += 1
                    continue
                entry = _build_one(plugin, name, item, item_id, style_key, font_conf,
                                  output_dir, upload_enabled)
                if entry["status"] == "generated":
                    result["generated"] += 1
                    if entry.get("uploaded"):
                        result["uploaded"] += 1
                    result["items"].append(entry)
                elif entry["status"] == "failed":
                    result["failed"] += 1
                else:
                    result["skipped"] += 1
                if result["generated"] >= quota:
                    break

    result["message"] = (
        f"生成 {result['generated']} 张，上传 {result['uploaded']} 张，"
        f"跳过 {result['skipped']} 条，失败 {result['failed']} 条"
    )
    store.finish_job(
        job,
        "success" if result["failed"] == 0 else "failed",
        result["message"],
        success=result["generated"],
        failed=result["failed"],
        skipped=result["skipped"],
    )
    store.append_job(plugin, job, history_limit(plugin))
    _remember(plugin, result, style_key)
    return result


def _build_one(plugin, server: str, item: Any, item_id: str, style_key: str,
               font_conf: str, output_dir: str, upload_enabled: bool) -> Dict[str, Any]:
    """生成单个条目的封面。

    :param plugin: 插件实例
    :param server: 服务器名称
    :param item: 媒体条目
    :param item_id: 条目 ID
    :param style_key: 风格键
    :param font_conf: 字体路径
    :param output_dir: 输出目录
    :param upload_enabled: 是否上传
    :return: 单条结果字典
    """
    title = str(getattr(item, "title", "") or "")
    base = mediaserver.fetch_primary_image(server, item_id)
    # 无底图不再跳过：render_cover 对三种风格都有渐变兜底画布，
    # 缺封面的条目恰恰是本模块的目标场景。
    content = render.render_cover(style_key, title, _subtitle(item), base, font_conf)
    if not content:
        return {"status": "failed", "server": server, "item_id": item_id, "title": title,
                "reason": "渲染失败"}
    filename = f"{server}_{item_id}.png".replace("/", "_").replace("\\", "_")
    path = render.save_cover(output_dir, filename, content)
    if not path:
        return {"status": "failed", "server": server, "item_id": item_id, "title": title,
                "reason": "写入本地失败"}
    entry: Dict[str, Any] = {
        "status": "generated",
        "server": server,
        "item_id": item_id,
        "title": title,
        "style": style_key,
        "path": path,
        "uploaded": False,
        "time": store.now_text(),
    }
    if upload_enabled and observe_only(plugin):
        entry["upload_message"] = "观察模式：已生成本地文件，未上传服务器"
    if upload_enabled and not observe_only(plugin):
        ok, message = mediaserver.upload_primary_image(server, item_id, content)
        entry["uploaded"] = bool(ok)
        entry["upload_message"] = message
        if not ok:
            logger.warning(f"【媒体服务器增强】{server}/{item_id} 封面上传失败：{message}")
    return entry


def _remember(plugin, result: Dict[str, Any], style_key: str) -> None:
    """把本次生成的封面写入历史快照。

    :param plugin: 插件实例
    :param result: 任务结果
    :param style_key: 风格键
    """
    # 与 webhook/job 同模式：read-modify-write 全程持实例级锁
    with store._plugin_lock(plugin, "_cover_history_lock"):
        existing = store.read_list(plugin, store.COVER_HISTORY_KEY)
        entry = {
            "time": store.now_text(),
            "style": style_key,
            "generated": result["generated"],
            "uploaded": result["uploaded"],
            "failed": result["failed"],
            "items": result["items"][:50],
        }
        store.write_value(plugin, store.COVER_HISTORY_KEY, store.merge_history(existing, entry, 100))


def cover_history(plugin) -> List[Dict[str, Any]]:
    """读取封面生成历史。"""
    return store.read_list(plugin, store.COVER_HISTORY_KEY)


def run_scheduled(plugin) -> None:
    """定时封面任务入口。"""
    if not plugin_active(plugin, MODULE):
        return
    if not as_bool(getattr(plugin, "_cover_upload", False)):
        return
    try:
        run_cover(plugin, trigger="定时生成")
    except Exception as error:  # noqa: BLE001 - 定时任务异常只记录
        logger.error(f"【媒体服务器增强】定时封面任务失败：{error}")
