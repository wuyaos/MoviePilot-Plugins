# input: 单张图片路径 + 标题 + 字体路径
# output: base64 编码的对角分割封面图片
# pos: style/ 风格 5，对角分割布局（左下标题 + 右侧主图），借鉴 a39908646/MediaCoverGenerator
"""
风格 5（对角分割）：主图右 65%，左下 35% 渐变背景，对角线 Gaussian feather 过渡。
标题左对齐，副标题多行宽度不超过主标题宽度。
"""
from __future__ import annotations

import base64
import io
import logging
from typing import Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ..utils.color_helper import ColorHelper
from ..utils.image_manager import (
    ResolutionConfig, align_image_right, create_diagonal_mask, create_shadow_mask,
    smart_center_crop,
)

logger = logging.getLogger(__name__)


def _add_film_grain(img: Image.Image, intensity: float = 0.03) -> Image.Image:
    """叠加胶片颗粒纹理。"""
    arr = np.array(img, dtype=np.float32)
    noise = np.random.normal(0, intensity * 255, arr.shape)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list:
    """按像素宽度折行。"""
    if not text:
        return []
    lines, current = [], ""
    for ch in text:
        test = current + ch
        if font.getlength(test) > max_width and current:
            lines.append(current)
            current = ch
        else:
            current = test
    if current:
        lines.append(current)
    return lines


def _fit_font_size(text: str, font_path: str, target_width: int,
                   start_size: int, min_size: int = 24) -> ImageFont.FreeTypeFont:
    """二分逼近：让单行文本宽度不超过 target_width；若仍超出则返回 min_size 字号。"""
    size = start_size
    while size > min_size:
        font = ImageFont.truetype(str(font_path), int(size))
        if font.getlength(text) <= target_width:
            return font
        size = int(size * 0.9)
    return ImageFont.truetype(str(font_path), min_size)


def create_style_static_5(
    image_path, title, font_path,
    font_size=(170, 75),
    font_offset=(0, 40, 40),
    blur_size=50,
    color_ratio=0.8,
    resolution_config=None,
    bg_color_config=None,
):
    """
    对角分割风格封面。
    - 右侧：主图（align_image_right 智能裁切右对齐）
    - 左侧：马卡龙背景 + 对角分割遮罩 + 羽化阴影
    - 左下：主标题 + 副标题
    """
    try:
        res = resolution_config or ResolutionConfig("1080p")
        width, height = res.width, res.height

        # ---- 加载图片 ----
        if isinstance(image_path, str):
            src_img = Image.open(image_path).convert("RGB")
        else:
            src_img = image_path if isinstance(image_path, Image.Image) else None
        if not src_img:
            logger.error("style_static_5: 无效的图片路径")
            return False

        # ---- 提色 ----
        colors = ColorHelper.find_dominant_vibrant_colors(src_img, num_colors=3)
        if not colors:
            colors = ColorHelper.MACARON_FALLBACK_COLORS[:3]
        bg_rgb = colors[0]

        # 自定义背景色覆盖
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

        # ---- 画布 ----
        canvas = Image.new("RGB", (width, height), bg_rgb)

        # 背景：纯色 90% + 模糊原图 10%
        blurred_bg = src_img.resize((width, height), Image.Resampling.LANCZOS)
        blurred_bg = blurred_bg.filter(ImageFilter.GaussianBlur(radius=blur_size))
        canvas = Image.blend(canvas, blurred_bg, 0.1)

        # ---- 主图右对齐 ----
        fg_img = align_image_right(src_img, (width, height))

        # ---- 对角遮罩合成 ----
        diag_mask = create_diagonal_mask((width, height), split_top=0.50, split_bottom=0.33)
        # 羽化遮罩边缘
        feathered_mask = diag_mask.filter(ImageFilter.GaussianBlur(radius=20))
        canvas.paste(fg_img, (0, 0), feathered_mask)

        # ---- 阴影 ----
        shadow = create_shadow_mask((width, height), split_top=0.50, split_bottom=0.33, feather=40)
        shadow_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        shadow_pixels = shadow_layer.load()
        shadow_data = shadow.load()
        for y in range(height):
            for x in range(width):
                a = min(int(shadow_data[x, y] * 0.5), 180)
                shadow_pixels[x, y] = (0, 0, 0, a)
        canvas = canvas.convert("RGBA")
        canvas = Image.alpha_composite(canvas, shadow_layer)
        canvas = canvas.convert("RGB")

        # ---- 胶片颗粒 ----
        canvas = _add_film_grain(canvas, intensity=0.02)

        # ---- 文字 ----
        zh_title, en_title = (title if isinstance(title, (list, tuple)) else (title, ""))
        zh_font_path, en_font_path = (font_path if isinstance(font_path, (list, tuple))
                                       else (font_path, font_path))
        zh_size, en_size = (font_size if isinstance(font_size, (list, tuple)) else (font_size, 75))
        zh_offset, title_spacing, en_spacing = (font_offset if isinstance(font_offset, (list, tuple))
                                                 else (0, 40, 40))

        zh_font = ImageFont.truetype(str(zh_font_path), int(zh_size))
        en_font = ImageFont.truetype(str(en_font_path), int(en_size))

        draw = ImageDraw.Draw(canvas)
        text_area_w = int(width * 0.30)  # 左侧 30% 区域，避免越过对角分割线
        text_x = int(width * 0.05)

        # 主标题：先尝试自动缩字到 1 行；如缩到 min 仍超出，则按字符折行
        zh_font = _fit_font_size(zh_title, zh_font_path, text_area_w, int(zh_size), min_size=int(zh_size * 0.5))
        zh_lines = _wrap_text(zh_title, zh_font, text_area_w) or [zh_title]
        zh_line_h = max((zh_font.getbbox(l)[3] - zh_font.getbbox(l)[1]) for l in zh_lines)
        zh_total_h = zh_line_h * len(zh_lines) + (len(zh_lines) - 1) * 6

        # 副标题：折行
        en_lines = _wrap_text(en_title, en_font, text_area_w) if en_title else []
        en_total_h = sum(en_font.getbbox(line)[3] - en_font.getbbox(line)[1] + en_spacing
                         for line in en_lines) if en_lines else 0

        total_text_h = zh_total_h + title_spacing + en_total_h
        # Y 边界保护：太高时上抬，确保不出画
        max_text_h = height - int(height * 0.05) - int(height * 0.12)
        if total_text_h > max_text_h:
            text_y = int(height * 0.05)
        else:
            text_y = height - total_text_h - int(height * 0.12)

        # 绘制主标题（多行）
        cur_y = text_y + zh_offset
        for line in zh_lines:
            draw.text((text_x, cur_y), line, font=zh_font, fill=(255, 255, 255))
            cur_y += zh_line_h + 6
        cur_y += title_spacing - 6

        # 绘制副标题
        for line in en_lines:
            draw.text((text_x, cur_y), line, font=en_font, fill=(230, 230, 230))
            bbox = en_font.getbbox(line)
            cur_y += (bbox[3] - bbox[1]) + en_spacing

        # ---- 输出 base64 ----
        buf = io.BytesIO()
        canvas.save(buf, format="JPEG", quality=92)
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    except Exception as e:
        logger.error(f"style_static_5 生成失败: {e}", exc_info=True)
        return False
