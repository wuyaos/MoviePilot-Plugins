# input: 媒体项 dict + PluginConfig + 风格名 + 字体路径
# output: 图片 URL 解析、标题 YAML 解析、风格函数分发结果（base64 图）
# pos: core/ 风格渲染辅助层（被 engine.py 调用）
"""图片 URL 解析、标题配置解析、风格函数分发。"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

import yaml

from app.plugins.covergen.style.style_static_1 import create_style_static_1
from app.plugins.covergen.style.style_static_2 import create_style_static_2
from app.plugins.covergen.style.style_static_3 import create_style_static_3
from app.plugins.covergen.style.style_static_4 import create_style_static_4
from app.plugins.covergen.style.style_static_5 import create_style_static_5
from app.plugins.covergen.style.style_animated_1 import create_style_animated_1
from app.plugins.covergen.style.style_animated_2 import create_style_animated_2
from app.plugins.covergen.style.style_animated_3 import create_style_animated_3
from app.plugins.covergen.style.style_animated_4 import create_style_animated_4

logger = logging.getLogger(__name__)
LOG_PREFIX = "【CoverGen】"

# 静态风格签名: (image_path, title, font_path, **common_kwargs)
# 动态风格签名: (library_dir, title, font_path, **common_kwargs, **anim_kwargs)
STATIC_STYLES = {"static_1", "static_2", "static_4", "static_5"}
GRID_STYLES = {"static_3"}  # 9 张图
ANIMATED_STYLES = {"animated_1", "animated_2", "animated_3", "animated_4"}

STYLE_FUNCS: Dict[str, Callable] = {
    "static_1": create_style_static_1,
    "static_2": create_style_static_2,
    "static_3": create_style_static_3,
    "static_4": create_style_static_4,
    "static_5": create_style_static_5,
    "animated_1": create_style_animated_1,
    "animated_2": create_style_animated_2,
    "animated_3": create_style_animated_3,
    "animated_4": create_style_animated_4,
}


# ---------- 图片 URL 解析 ----------

def _img(item_id: str, kind: str, tag: str, idx: int = 0) -> str:
    """构造 [HOST] 风格的图片 URL。"""
    if kind == "Backdrop":
        return f"[HOST]emby/Items/{item_id}/Images/Backdrop/{idx}?tag={tag}&api_key=[APIKEY]"
    return f"[HOST]emby/Items/{item_id}/Images/{kind}?tag={tag}&api_key=[APIKEY]"


def _backdrop(item: dict) -> Optional[Tuple[str, str]]:
    tags = item.get("ParentBackdropImageTags") or []
    if tags:
        return item.get("ParentBackdropItemId"), tags[0]
    return None


def _primary(item: dict) -> Optional[Tuple[str, str]]:
    tags = item.get("ImageTags", {}) if isinstance(item.get("ImageTags"), dict) else {}
    if tags.get("Primary"):
        return item.get("Id"), tags["Primary"]
    return None


def get_image_url(item: dict, cover_style: str, use_primary: bool) -> Optional[str]:
    """根据封面风格挑选最优图片 URL。"""
    item_type = item.get("Type", "")

    # 音乐类
    if item_type in ("MusicAlbum", "Audio"):
        if (b := _backdrop(item)):
            return _img(b[0], "Backdrop", b[1])
        if item.get("PrimaryImageTag"):
            return _img(item.get("PrimaryImageItemId"), "Primary", item["PrimaryImageTag"])
        if item.get("AlbumPrimaryImageTag"):
            return _img(item.get("AlbumId"), "Primary", item["AlbumPrimaryImageTag"])
        return None

    # 多图风格 (static_3 / animated_*) 与单图风格优先级不同
    is_multi = cover_style in (GRID_STYLES | ANIMATED_STYLES)
    sources = []
    if item_type == "Episode":
        if item.get("SeriesPrimaryImageTag"):
            sources.append(("Primary", item.get("SeriesId"), item["SeriesPrimaryImageTag"]))
        if (b := _backdrop(item)):
            sources.append(("Backdrop", b[0], b[1]))
    if (p := _primary(item)):
        sources.append(("Primary", p[0], p[1]))
    backdrop_self = item.get("BackdropImageTags") or []
    if backdrop_self:
        sources.append(("Backdrop", item.get("Id"), backdrop_self[0]))
    if (b := _backdrop(item)) and not any(s[1] == b[0] and s[0] == "Backdrop" for s in sources):
        sources.append(("Backdrop", b[0], b[1]))

    # use_primary 优先 Primary；否则多图风格优先 Backdrop
    if use_primary:
        sources.sort(key=lambda s: 0 if s[0] == "Primary" else 1)
    elif is_multi:
        sources.sort(key=lambda s: 0 if s[0] == "Backdrop" else 1)

    if sources:
        kind, iid, tag = sources[0]
        return _img(iid, kind, tag)
    return None


def get_item_id(item: dict, cover_style: str, use_primary: bool) -> Optional[str]:
    """根据规则返回项目 ID 用于历史记录。"""
    if item.get("Type") in ("MusicAlbum", "Audio"):
        return (item.get("ParentBackdropItemId") or item.get("PrimaryImageItemId")
                or item.get("AlbumId"))
    is_multi = cover_style in (GRID_STYLES | ANIMATED_STYLES)
    has_primary = (item.get("ImageTags") or {}).get("Primary") or item.get("BackdropImageTags")
    has_parent = item.get("ParentBackdropImageTags")
    if use_primary:
        return item.get("Id") if has_primary else (item.get("ParentBackdropItemId") if has_parent else None)
    if is_multi:
        return item.get("ParentBackdropItemId") if has_parent else (item.get("Id") if has_primary else None)
    return item.get("ParentBackdropItemId") if has_parent else (item.get("Id") if has_primary else None)


# ---------- 去重 key ----------

def build_content_key(item: dict) -> Optional[str]:
    """同来源内容只入选一次。"""
    t = item.get("Type")
    if t == "Episode":
        if item.get("SeriesId"):
            return f"series:{item['SeriesId']}"
        if item.get("ParentBackdropItemId"):
            return f"parent:{item['ParentBackdropItemId']}"
    if t in ("MusicAlbum", "Audio"):
        if item.get("AlbumId"):
            return f"album:{item['AlbumId']}"
    if item.get("Id"):
        return f"item:{item['Id']}"
    return None


def build_image_key(image_url: str) -> Optional[str]:
    """同图不同 api_key 视为同一图。"""
    if not image_url:
        return None
    try:
        from urllib.parse import urlparse
        normalized = re.sub(r"([?&])api_key=[^&]*", "", image_url).rstrip("?&")
        tag_match = re.search(r"[?&]tag=([^&]+)", image_url)
        tag = tag_match.group(1) if tag_match else ""
        path = urlparse(normalized).path or normalized
        return f"img:{path}|tag:{tag}"
    except Exception:
        return f"img:{image_url}"


# ---------- 标题 YAML 解析 ----------

def parse_title_config(yaml_str: str) -> Dict[str, list]:
    """解析 YAML 标题配置：{库名: [主标题, 副标题, 颜色?]}。"""
    if not yaml_str:
        return {}
    try:
        text = yaml_str.replace("：", ":").replace("\t", "  ")
        # 数字/特殊字符开头的键自动加引号
        out_lines = []
        for line in text.split("\n"):
            if ":" in line and not line.strip().startswith("#"):
                k, _, v = line.partition(":")
                k = k.strip()
                if k and not k.startswith(('"', "'")) and (k[0].isdigit() or any(
                        c in k for c in " -.()[]")):
                    out_lines.append(f'"{k}":{v}')
                else:
                    out_lines.append(line)
            else:
                out_lines.append(line)
        cfg = yaml.safe_load("\n".join(out_lines)) or {}
        if not isinstance(cfg, dict):
            return {}
        result = {}
        for k, v in cfg.items():
            if isinstance(v, list) and len(v) >= 2 and isinstance(v[0], str) and isinstance(v[1], str):
                if len(v) >= 3 and isinstance(v[2], str):
                    result[str(k)] = [v[0], v[1], v[2]]
                else:
                    result[str(k)] = [v[0], v[1]]
        return result
    except Exception as e:
        logger.warning(f"{LOG_PREFIX} YAML 解析失败: {e}")
        return {}


def lookup_title(library_name: str, config: dict) -> Tuple[str, str, Optional[str]]:
    """查找库标题配置（多策略匹配）。返回 (zh, en, bg_color)。"""
    for k, v in (config or {}).items():
        sk, sl = str(k).strip(), str(library_name).strip()
        if sk == sl or sk.lower() == sl.lower():
            return v[0], v[1] if len(v) > 1 else "", v[2] if len(v) > 2 else None
    return library_name, "", None


# ---------- 风格分发 ----------

def dispatch_style(cover_style: str, *, image_path=None, library_dir=None,
                   title=None, font_path=None, font_size=None, font_offset=None,
                   blur_size=50, color_ratio=0.8, resolution_config=None,
                   bg_color_config=None, multi_blur=True,
                   animation_duration=8, animation_scroll="alternate",
                   animation_fps=24, animation_format="apng",
                   animation_resolution="320x180", animation_reduce_colors="medium",
                   image_count=6, departure_type="fly", stop_event=None):
    """按风格分发到对应 create_style_* 函数。"""
    func = STYLE_FUNCS.get(cover_style)
    if not func:
        return False

    common = dict(font_size=font_size, font_offset=font_offset,
                  blur_size=blur_size, color_ratio=color_ratio,
                  resolution_config=resolution_config, bg_color_config=bg_color_config)

    if cover_style in STATIC_STYLES:
        return func(image_path, title, font_path, **common)

    if cover_style in GRID_STYLES:
        return func(library_dir, title, font_path, is_blur=multi_blur, **common)

    # animated
    anim = dict(animation_duration=animation_duration,
                animation_fps=animation_fps,
                animation_format=animation_format,
                animation_resolution=animation_resolution,
                animation_reduce_colors=animation_reduce_colors,
                stop_event=stop_event)
    if cover_style == "animated_3":
        return func(library_dir, title, font_path, is_blur=multi_blur,
                    animation_scroll=animation_scroll, **common, **anim)
    # animated_1/2/4
    extra = dict(image_count=image_count)
    if cover_style in ("animated_1", "animated_4"):
        extra["departure_type"] = departure_type if cover_style == "animated_1" else None
        extra = {k: v for k, v in extra.items() if v is not None}
    return func(library_dir, title, font_path, is_blur=multi_blur,
                **common, **anim, **extra)
