# input: 媒体服务器 service 实例 + 图片 base64/URL
# output: 下载/上传图片到媒体服务器的方法
# pos: core/ 图片传输专用模块（与 server.py 元数据查询解耦）
"""图片 IO：下载远程图片、上传 base64 封面到媒体服务器。"""
from __future__ import annotations

import logging
import os
import re
import time
from pathlib import Path
from typing import Optional, Tuple

from app.utils.http import RequestUtils

from .server import get_library_id

logger = logging.getLogger(__name__)
_shared_request = RequestUtils()  # 单例，避免重试循环重复构造
LOG_PREFIX = "【CoverGen】"


def detect_content_type(image_base64: str) -> Tuple[str, str]:
    """根据 base64 前缀判断 mime + 扩展名。"""
    if image_base64.startswith("R0lG"): return "image/gif", "gif"
    if image_base64.startswith("UklG"): return "image/webp", "webp"
    if image_base64.startswith("/9j/"): return "image/jpeg", "jpg"
    return "image/png", "png"


def download_image(service, imageurl: str, covers_path: str, library_name: str,
                   count: Optional[int] = None, *, retries: int = 3, delay: int = 1,
                   sanitize_fn=None) -> Optional[str]:
    """下载图片到本地，返回路径。"""
    try:
        safe = sanitize_fn(library_name) if sanitize_fn else re.sub(r'[^\w\-.]', '_', library_name)
        subdir = os.path.join(covers_path, safe)
        os.makedirs(subdir, exist_ok=True)
        filename = f"{count}.jpg" if count is not None else f"img_{int(time.time())}.jpg"
        filepath = os.path.join(subdir, filename)

        for attempt in range(1, retries + 1):
            content = None
            if "[HOST]" in imageurl:
                if not service:
                    return None
                r = service.instance.get_data(url=imageurl)
            else:
                r = _shared_request.get_res(url=imageurl)
            if r and r.status_code == 200:
                content = r.content
            if content:
                Path(filepath).write_bytes(content)
                return filepath
            logger.warning(f"{LOG_PREFIX} 第 {attempt} 次下载失败：{imageurl}")
            if attempt < retries:
                time.sleep(delay)
        logger.error(f"{LOG_PREFIX} 图片下载失败（重试 {retries}）：{imageurl}")
    except Exception as err:
        logger.error(f"{LOG_PREFIX} 下载异常：{err}")
    return None


def upload_library_image(service, library: dict, image_base64: str,
                         *, retries: int = 3, delay: int = 2,
                         on_save_local=None) -> bool:
    """上传 base64 封面到媒体服务器。"""
    try:
        lib_id = get_library_id(service, library)
        url = f"[HOST]emby/Items/{lib_id}/Images/Primary?api_key=[APIKEY]"
        content_type, ext = detect_content_type(image_base64)
        size_kb = len(image_base64) * 3 // 4 // 1024
        name = library.get("Name", "")
        logger.info(f"{LOG_PREFIX} 上传封面: {name} | {ext} | ~{size_kb} KB")
        if on_save_local:
            try:
                on_save_local(image_base64, ext)
            except Exception as e:
                logger.error(f"{LOG_PREFIX} 保存本地副本失败: {e}")

        for attempt in range(1, retries + 1):
            try:
                res = service.instance.post_data(
                    url=url, data=image_base64, headers={"Content-Type": content_type})
                if res and res.status_code in (200, 204):
                    return True
                logger.warning(f"{LOG_PREFIX} 上传失败（{attempt}/{retries}），"
                               f"status={res.status_code if res else 'None'}")
            except Exception as err:
                logger.warning(f"{LOG_PREFIX} 上传异常（{attempt}/{retries}）：{err}")
            if attempt < retries:
                time.sleep(delay)
        logger.error(f"{LOG_PREFIX} 设置「{name}」封面失败，已重试 {retries} 次")
    except Exception as err:
        logger.error(f"{LOG_PREFIX} 设置封面失败：{err}")
    return False
