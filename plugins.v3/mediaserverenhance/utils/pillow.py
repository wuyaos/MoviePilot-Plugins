"""媒体服务器增强 - Pillow 能力探测。

MoviePilot 宿主自带 Pillow，但插件仍按可选依赖处理：
缺少 Pillow 时封面工坊降级为不可用，其余模块不受影响。
"""

from __future__ import annotations

from typing import Any

try:  # pragma: no cover - 取决于宿主运行环境
    from PIL import Image as PIL_IMAGE
    from PIL import ImageDraw as PIL_IMAGE_DRAW
    from PIL import ImageFont as PIL_IMAGE_FONT
except ImportError:  # pragma: no cover - 宿主未安装 Pillow
    PIL_IMAGE: Any = None
    PIL_IMAGE_DRAW: Any = None
    PIL_IMAGE_FONT: Any = None


def pillow_available() -> bool:
    """判断当前环境是否可用 Pillow。

    :return: 三个子模块都导入成功时返回 True
    """
    return bool(PIL_IMAGE and PIL_IMAGE_DRAW and PIL_IMAGE_FONT)
