"""封面工坊渲染层。

只做本地图片合成，不访问网络。远程底图由 service 层下载后传入。
"""

from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from ...utils.pillow import pillow_available, PIL_IMAGE, PIL_IMAGE_DRAW, PIL_IMAGE_FONT

# 输出画布尺寸，保持 2:3 海报比例
POSTER_SIZE: Tuple[int, int] = (1000, 1500)

# 常见系统中文字体候选路径，命中即用
FONT_CANDIDATES: Sequence[str] = (
    "C:/Windows/Fonts/msyhbd.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Bold.otf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/PingFang.ttc",
)

STYLE_KEYS = ("poster", "clean", "gradient")


def font_path(configured: str = "") -> str:
    """解析可用字体文件路径。

    :param configured: 配置中显式指定的字体路径
    :return: 命中的字体路径，全部缺失时返回空串
    """
    if configured and Path(configured).is_file():
        return configured
    for candidate in FONT_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    return ""


def _load_font(configured: str, size: int):
    """加载指定字号的字体对象。

    :param configured: 配置中的字体路径
    :param size: 字号
    :return: 字体对象；失败时退回 Pillow 默认字体
    """
    path = font_path(configured)
    if path:
        try:
            return PIL_IMAGE_FONT.truetype(path, size)
        except Exception:  # noqa: BLE001 - 字体不可用时退回默认字体
            pass
    return PIL_IMAGE_FONT.load_default()


def _gradient(width: int, height: int, top: Tuple[int, int, int],
              bottom: Tuple[int, int, int]):
    """生成竖向线性渐变图层。

    :param width: 宽
    :param height: 高
    :param top: 顶部颜色
    :param bottom: 底部颜色
    :return: RGB 图像
    """
    layer = PIL_IMAGE.new("RGB", (1, height))
    pixels = layer.load()
    for y in range(height):
        ratio = y / max(1, height - 1)
        pixels[0, y] = (
            int(top[0] + (bottom[0] - top[0]) * ratio),
            int(top[1] + (bottom[1] - top[1]) * ratio),
            int(top[2] + (bottom[2] - top[2]) * ratio),
        )
    return layer.resize((width, height))


def _fit(text: str, font, max_width: int) -> List[str]:
    """按像素宽度折行。

    :param text: 原文
    :param font: 字体对象
    :param max_width: 单行最大宽度
    :return: 折行结果
    """
    if not text:
        return []
    lines: List[str] = []
    current = ""
    for char in text:
        trial = current + char
        try:
            width = font.getbbox(trial)[2]
        except Exception:  # noqa: BLE001 - 部分字体不支持 getbbox
            width = len(trial) * 20
        if width > max_width and current:
            lines.append(current)
            current = char
        else:
            current = trial
    if current:
        lines.append(current)
    return lines[:3]


def _cover_base(base: Optional[bytes]):
    """把底图裁切填满画布。

    :param base: 底图字节
    :return: RGB 图像；无底图时返回 None
    """
    if not base:
        return None
    try:
        image = PIL_IMAGE.open(BytesIO(base))
        image = image.convert("RGB")
    except Exception:  # noqa: BLE001 - 非法图片按无底图处理
        return None
    target_width, target_height = POSTER_SIZE
    src_width, src_height = image.size
    if not src_width or not src_height:
        return None
    scale = max(target_width / src_width, target_height / src_height)
    resized = image.resize(
        (max(1, int(src_width * scale + 0.5)), max(1, int(src_height * scale + 0.5)))
    )
    left = max(0, (resized.width - target_width) // 2)
    top = max(0, (resized.height - target_height) // 2)
    return resized.crop((left, top, left + target_width, top + target_height))


def _draw_text_block(draw, title: str, subtitle: str, font_path_conf: str,
                     top: int, max_width: int) -> None:
    """在指定纵向位置绘制标题与副标题。

    :param draw: Pillow 画布
    :param title: 主标题
    :param subtitle: 副标题
    :param font_path_conf: 配置的字体路径
    :param top: 起始纵坐标
    :param max_width: 可用宽度
    """
    title_font = _load_font(font_path_conf, 74)
    sub_font = _load_font(font_path_conf, 40)
    cursor = top
    for line in _fit(title, title_font, max_width):
        draw.text((60, cursor), line, font=title_font, fill=(255, 255, 255))
        cursor += 88
    if subtitle:
        for line in _fit(subtitle, sub_font, max_width):
            draw.text((60, cursor + 8), line, font=sub_font, fill=(220, 220, 220))
            cursor += 52


def render_cover(style: str, title: str, subtitle: str = "",
                 base_image: Optional[bytes] = None,
                 font_conf: str = "") -> Optional[bytes]:
    """按风格渲染一张海报封面。

    :param style: 风格键，见 ``STYLE_KEYS``
    :param title: 主标题
    :param subtitle: 副标题，通常是年份或季信息
    :param base_image: 底图字节，渐变风格可为空
    :param font_conf: 配置的字体文件路径
    :return: PNG 字节；Pillow 缺失或渲染失败时返回 None
    """
    if not pillow_available():
        return None
    style = style if style in STYLE_KEYS else "poster"
    width, height = POSTER_SIZE
    try:
        canvas = _cover_base(base_image)
        if canvas is None:
            palette = {
                "poster": ((24, 32, 56), (10, 12, 20)),
                "clean": ((38, 44, 60), (18, 20, 28)),
                "gradient": ((56, 32, 96), (12, 16, 40)),
            }
            top_color, bottom_color = palette.get(style, palette["poster"])
            canvas = _gradient(width, height, top_color, bottom_color)

        if style == "poster":
            overlay = _gradient(width, int(height * 0.55), (0, 0, 0), (0, 0, 0))
            mask = PIL_IMAGE.new("L", (width, int(height * 0.55)))
            mask_pixels = mask.load()
            for y in range(int(height * 0.55)):
                alpha = int(215 * (y / max(1, int(height * 0.55) - 1)))
                for x in range(width):
                    mask_pixels[x, y] = alpha
            canvas.paste(overlay, (0, height - int(height * 0.55)), mask)
            _draw_text_block(
                PIL_IMAGE_DRAW.Draw(canvas), title, subtitle, font_conf,
                top=int(height * 0.55), max_width=width - 120,
            )
        elif style == "clean":
            bar_height = int(height * 0.26)
            bar = PIL_IMAGE.new("RGB", (width, bar_height), (16, 18, 24))
            canvas.paste(bar, (0, height - bar_height))
            accent = PIL_IMAGE_DRAW.Draw(canvas)
            accent.rectangle([0, height - bar_height, width, height - bar_height + 6],
                            fill=(255, 178, 36))
            _draw_text_block(
                accent, title, subtitle, font_conf,
                top=height - bar_height + 32, max_width=width - 120,
            )
        else:
            draw = PIL_IMAGE_DRAW.Draw(canvas)
            draw.rectangle([56, 120, 64, height - 120], fill=(255, 178, 36))
            _draw_text_block(draw, title, subtitle, font_conf,
                             top=int(height * 0.42), max_width=width - 180)

        buffer = BytesIO()
        canvas.save(buffer, format="PNG", optimize=True)
        return buffer.getvalue()
    except Exception:  # noqa: BLE001 - 渲染失败由调用方记录为跳过
        return None


def save_cover(output_dir: str, filename: str, content: bytes) -> Optional[str]:
    """把封面写入本地目录。

    :param output_dir: 输出目录
    :param filename: 文件名
    :param content: PNG 字节
    :return: 写入成功时返回路径
    """
    try:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        path = os.path.join(output_dir, filename)
        Path(path).write_bytes(content)
        return path
    except OSError:
        return None


def mime_of(content: bytes) -> str:
    """按文件头判断图片 MIME。

    :param content: 图片字节
    :return: MIME 文本
    """
    if content[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if content[:4] == b"RIFF":
        return "image/webp"
    if content[:3] == b"GIF":
        return "image/gif"
    return "image/png"
