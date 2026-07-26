"""
图像资源管理工具类
用于管理PIL图像对象的生命周期，防止内存泄漏
"""
import gc
import threading
from contextlib import contextmanager
from typing import Optional, Tuple, Union, List
from PIL import Image
from app.log import logger


class ImageResourceManager:
    """图像资源管理器，确保PIL图像对象正确释放"""

    def __init__(self):
        self._images = []
        self._lock = threading.Lock()

    def register(self, image: Image.Image) -> Image.Image:
        """注册图像对象以便后续释放"""
        with self._lock:
            self._images.append(image)
        return image

    def cleanup(self):
        """清理所有注册的图像对象"""
        with self._lock:
            for img in self._images:
                try:
                    if hasattr(img, 'close'):
                        img.close()
                except Exception as e:
                    logger.warning(f"清理图像对象时出错: {e}")
            self._images.clear()
            # 强制垃圾回收
            gc.collect()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()


@contextmanager
def managed_image(image_path_or_obj: Union[str, Image.Image], mode: str = "RGB"):
    """
    上下文管理器，确保图像对象正确释放

    Args:
        image_path_or_obj: 图像路径或PIL图像对象
        mode: 图像模式

    Yields:
        PIL.Image对象
    """
    img = None
    try:
        if isinstance(image_path_or_obj, str):
            img = Image.open(image_path_or_obj)
            if mode and img.mode != mode:
                img = img.convert(mode)
        else:
            img = image_path_or_obj
        yield img
    finally:
        if img and hasattr(img, 'close'):
            try:
                img.close()
            except Exception as e:
                logger.warning(f"关闭图像对象时出错: {e}")


@contextmanager
def managed_images(*images: Image.Image):
    """
    管理多个图像对象的上下文管理器

    Args:
        *images: 多个PIL图像对象

    Yields:
        图像对象元组
    """
    try:
        yield images
    finally:
        for img in images:
            if img and hasattr(img, 'close'):
                try:
                    img.close()
                except Exception as e:
                    logger.warning(f"关闭图像对象时出错: {e}")


def safe_image_operation(func):
    """
    装饰器：确保图像操作的安全性
    自动管理临时图像对象的生命周期
    """
    def wrapper(*args, **kwargs):
        with ImageResourceManager() as manager:
            try:
                result = func(*args, **kwargs)
                # 如果返回的是PIL图像对象，确保它不会被意外释放
                if isinstance(result, Image.Image):
                    # 创建副本以避免原对象被释放
                    result_copy = result.copy()
                    return result_copy
                return result
            except Exception as e:
                logger.error(f"图像操作失败: {e}")
                raise
    return wrapper


class ResolutionConfig:
    """分辨率配置类"""

    # 预设分辨率选项
    PRESETS = {
        "1080p": (1920, 1080),
        "720p": (1280, 720),
        "480p": (854, 480),
        "360p": (640, 360),
        "4k": (3840, 2160),
        "1440p": (2560, 1440),
        "custom": None  # 自定义分辨率
    }

    def __init__(self, resolution: Union[str, Tuple[int, int]] = "1080p"):
        """
        初始化分辨率配置

        Args:
            resolution: 分辨率预设名称或(width, height)元组
        """
        if isinstance(resolution, str):
            if resolution in self.PRESETS:
                self._resolution = self.PRESETS[resolution] or (1920, 1080)
                self._preset_name = resolution
            else:
                self._resolution = (1920, 1080)
                self._preset_name = "1080p"
        elif isinstance(resolution, (tuple, list)) and len(resolution) == 2:
            self._resolution = tuple(resolution)
            self._preset_name = "custom"
        else:
            self._resolution = (1920, 1080)
            self._preset_name = "1080p"

    @property
    def width(self) -> int:
        return self._resolution[0]

    @property
    def height(self) -> int:
        return self._resolution[1]

    @property
    def size(self) -> Tuple[int, int]:
        return self._resolution

    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height

    @property
    def preset_name(self) -> str:
        return self._preset_name

    def scale_size(self, scale_factor: float) -> Tuple[int, int]:
        """按比例缩放尺寸"""
        return (int(self.width * scale_factor), int(self.height * scale_factor))

    def get_relative_size(self, width_ratio: float, height_ratio: float) -> Tuple[int, int]:
        """获取相对于当前分辨率的尺寸"""
        return (int(self.width * width_ratio), int(self.height * height_ratio))

    def get_font_size(self, base_size: int, scale_factor: float = 1.0) -> int:
        """根据分辨率计算字体大小"""
        # 基于高度的字体缩放
        height_scale = self.height / 1080.0  # 以1080p为基准
        return int(base_size * height_scale * scale_factor)

    def __str__(self):
        return f"{self.width}x{self.height}"

    def __repr__(self):
        return f"ResolutionConfig({self._preset_name}: {self.width}x{self.height})"


def optimize_image_for_processing(image: Image.Image, max_size: Tuple[int, int] = (800, 600)) -> Image.Image:
    """
    为处理优化图像尺寸，减少内存占用

    Args:
        image: 原始图像
        max_size: 最大尺寸限制

    Returns:
        优化后的图像
    """
    if image.width <= max_size[0] and image.height <= max_size[1]:
        return image

    # 计算缩放比例
    width_ratio = max_size[0] / image.width
    height_ratio = max_size[1] / image.height
    scale_ratio = min(width_ratio, height_ratio)

    new_size = (int(image.width * scale_ratio), int(image.height * scale_ratio))
    return image.resize(new_size, Image.Resampling.LANCZOS)


def align_image_right(img: Image.Image, canvas_size: Tuple[int, int],
                      target_ratio: float = 0.675) -> Image.Image:
    """
    将图片缩放后右对齐到画布；左侧 (1 - target_ratio) 留给标题文字。
    借鉴自 a39908646/MediaCoverGenerator.
    """
    canvas_w, canvas_h = canvas_size
    target_w = int(canvas_w * target_ratio)
    img_w, img_h = img.size

    scale = canvas_h / img_h
    new_w = int(img_w * scale)
    resized = img.resize((new_w, canvas_h), Image.Resampling.LANCZOS)

    if new_w < target_w:
        scale = target_w / img_w
        new_h = int(img_h * scale)
        resized = img.resize((target_w, new_h), Image.Resampling.LANCZOS)
        if new_h > canvas_h:
            top = (new_h - canvas_h) // 2
            resized = resized.crop((0, top, target_w, top + canvas_h))
        out = Image.new("RGB", canvas_size)
        out.paste(resized, (canvas_w - target_w, 0))
        return out

    center_x = new_w / 2
    crop_left = max(0, center_x - target_w / 2)
    if crop_left + target_w > new_w:
        crop_left = new_w - target_w
    cropped = resized.crop((int(crop_left), 0, int(crop_left + target_w), canvas_h))

    out = Image.new("RGB", canvas_size)
    out.paste(cropped, (canvas_w - cropped.width + int(canvas_w * 0.075), 0))
    return out


def smart_center_crop(img: Image.Image, target_size: Tuple[int, int]) -> Image.Image:
    """等比缩放至 cover 目标尺寸再从中心裁切（保留主体）。"""
    target_w, target_h = target_size
    img_w, img_h = img.size
    scale = (target_h / img_h) if (img_w / img_h) > (target_w / target_h) else (target_w / img_w)
    new_w, new_h = int(img_w * scale), int(img_h * scale)
    resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left, top = (new_w - target_w) // 2, (new_h - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def create_diagonal_mask(size: Tuple[int, int], split_top: float = 0.5,
                         split_bottom: float = 0.33) -> Image.Image:
    """对角分割遮罩：左侧 255 / 右侧 0。借鉴自 a39908646/MediaCoverGenerator."""
    from PIL import ImageDraw
    mask = Image.new('L', size, 255)
    draw = ImageDraw.Draw(mask)
    width, height = size
    top_x = int(width * split_top)
    bottom_x = int(width * split_bottom)
    draw.polygon([(top_x, 0), (width, 0), (width, height), (bottom_x, height)], fill=0)
    draw.polygon([(0, 0), (top_x, 0), (bottom_x, height), (0, height)], fill=255)
    return mask


def create_shadow_mask(size: Tuple[int, int], split_top: float = 0.5,
                       split_bottom: float = 0.33, feather: int = 40) -> Image.Image:
    """对角分割阴影遮罩（高斯模糊羽化边缘）。"""
    from PIL import ImageDraw, ImageFilter
    width, height = size
    top_x = int(width * split_top)
    bottom_x = int(width * split_bottom)
    shadow_w = feather // 3
    mask = Image.new('L', size, 0)
    draw = ImageDraw.Draw(mask)
    draw.polygon([
        (top_x - 5, 0), (top_x - 5 + shadow_w, 0),
        (bottom_x - 5 + shadow_w, height), (bottom_x - 5, height),
    ], fill=255)
    return mask.filter(ImageFilter.GaussianBlur(radius=feather // 3))