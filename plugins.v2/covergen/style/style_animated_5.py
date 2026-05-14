# input: 库图片目录 + 标题 + 字体路径 + 动画参数
# output: base64 编码的对角分割动画封面（APNG/GIF）
# pos: style/ 风格 5 动画版，多图在右侧 65% 区域交叉淡入淡出
"""
风格 5 动画版（对角分割）：左下标题固定，右侧 65% 区域多张图片交叉淡入淡出。
复用 static_5 的对角遮罩 + 阴影渲染，仅在动画帧之间切换右侧主图。
"""
from __future__ import annotations

import base64
import io
import math
import os
import threading
from pathlib import Path
from typing import List, Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from app.log import logger
from app.plugins.covergen.utils.color_helper import ColorHelper
from app.plugins.covergen.utils.image_manager import (
    ResolutionConfig, align_image_right, create_diagonal_mask, create_shadow_mask,
)


def _build_static_part(canvas_size, bg_rgb, title_zh, title_en, font_zh, font_en,
                       font_offset, blur_size, src_blur):
    """绘制不变的左侧背景 + 标题（动画各帧共享）。"""
    width, height = canvas_size
    base = Image.new("RGB", canvas_size, bg_rgb)
    base = Image.blend(base, src_blur, 0.1)

    draw = ImageDraw.Draw(base)
    text_x = int(width * 0.05)
    zh_bbox = draw.textbbox((0, 0), title_zh, font=font_zh)
    zh_h = zh_bbox[3] - zh_bbox[1]
    en_h = (font_en.getbbox(title_en)[3] - font_en.getbbox(title_en)[1]) if title_en else 0
    zh_offset, title_spacing, en_spacing = font_offset
    text_y = height - zh_h - title_spacing - en_h - int(height * 0.12)
    draw.text((text_x, text_y + zh_offset), title_zh, font=font_zh, fill=(255, 255, 255))
    if title_en:
        draw.text((text_x, text_y + zh_h + title_spacing), title_en, font=font_en, fill=(230, 230, 230))
    return base


def create_style_animated_5(
    library_dir, title, font_path,
    font_size=(170, 75), font_offset=(0, 40, 40),
    is_blur=True, blur_size=50, color_ratio=0.8,
    resolution_config=None, bg_color_config=None,
    animation_duration=8, animation_fps=12, animation_format="apng",
    animation_resolution="320x180", animation_reduce_colors="medium",
    image_count=4, stop_event=None,
):
    """对角分割动画。从 library_dir 取 image_count 张图，在右侧交叉淡入淡出。"""
    try:
        res = resolution_config or ResolutionConfig("1080p")
        width, height = res.width, res.height

        lib_path = Path(library_dir)
        if not lib_path.exists():
            logger.error(f"animated_5: 库目录不存在 {lib_path}")
            return False
        imgs_files = sorted([p for p in lib_path.iterdir()
                              if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")])
        if not imgs_files:
            return False
        imgs_files = imgs_files[:max(2, int(image_count))]

        # 加载所有图片到内存
        loaded: List[Image.Image] = []
        for fp in imgs_files:
            try:
                loaded.append(Image.open(fp).convert("RGB"))
            except Exception as e:
                logger.warning(f"animated_5: 跳过无效图 {fp}: {e}")
        if len(loaded) < 2:
            return False

        # 提色 + 背景
        colors = ColorHelper.find_dominant_vibrant_colors(loaded[0], num_colors=3)
        bg_rgb = colors[0] if colors else (100, 100, 100)
        if bg_color_config:
            mode = bg_color_config.get("mode", "auto")
            if mode == "custom" and bg_color_config.get("custom_color"):
                parsed = ColorHelper.parse_color_string(bg_color_config["custom_color"])
                if parsed:
                    bg_rgb = parsed
            elif mode == "config" and bg_color_config.get("config_color"):
                parsed = ColorHelper.parse_color_string(bg_color_config["config_color"])
                if parsed:
                    bg_rgb = parsed

        # 字体
        zh_title, en_title = (title if isinstance(title, (list, tuple)) else (title, ""))
        zh_font_path, en_font_path = (font_path if isinstance(font_path, (list, tuple))
                                       else (font_path, font_path))
        zh_sz, en_sz = (font_size if isinstance(font_size, (list, tuple)) else (font_size, 75))
        zh_font = ImageFont.truetype(str(zh_font_path), int(zh_sz))
        en_font = ImageFont.truetype(str(en_font_path), int(en_sz))

        # 共享背景模糊层
        src_blur = loaded[0].resize((width, height), Image.Resampling.LANCZOS)
        src_blur = src_blur.filter(ImageFilter.GaussianBlur(radius=blur_size))

        # 静态左侧 + 标题
        static_base = _build_static_part((width, height), bg_rgb, zh_title, en_title,
                                          zh_font, en_font, font_offset, blur_size, src_blur)

        # 预渲染每张图在右侧的位置
        diag_mask = create_diagonal_mask((width, height), split_top=0.50, split_bottom=0.33)
        feathered = diag_mask.filter(ImageFilter.GaussianBlur(radius=20))
        right_layers = [align_image_right(im, (width, height)) for im in loaded]

        # 帧数 = duration * fps，每张图占 N 帧（含交叉淡入淡出）
        total_frames = max(8, int(animation_duration * animation_fps))
        per_image = total_frames // len(right_layers)
        crossfade_frames = max(2, per_image // 3)

        frames = []
        for i in range(total_frames):
            if stop_event and stop_event.is_set():
                return False
            seg = i // per_image
            local = i % per_image
            cur = right_layers[seg % len(right_layers)]
            nxt = right_layers[(seg + 1) % len(right_layers)]
            if local >= per_image - crossfade_frames:
                # 交叉淡入淡出
                t = (local - (per_image - crossfade_frames)) / crossfade_frames
                blended = Image.blend(cur, nxt, t)
            else:
                blended = cur

            frame = static_base.copy()
            frame.paste(blended, (0, 0), feathered)
            frames.append(frame.convert("P", palette=Image.Palette.ADAPTIVE)
                          if animation_format == "gif" else frame)

        # 输出
        buf = io.BytesIO()
        if animation_format == "gif":
            frames[0].save(buf, format="GIF", save_all=True, append_images=frames[1:],
                          duration=int(1000 / animation_fps), loop=0, optimize=True)
        else:
            frames[0].save(buf, format="PNG", save_all=True, append_images=frames[1:],
                          duration=int(1000 / animation_fps), loop=0)
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    except Exception as e:
        logger.error(f"animated_5 生成失败: {e}", exc_info=True)
        return False
