# input: PluginConfig 字体配置 + 字体目录路径
# output: FontManager（字体发现/下载/缓存/校验）
# pos: core/ 字体管理层；启用 cache-skip 修复原 4526-4527 注释代码
"""字体管理：预设发现、URL 下载、本地校验。RequestUtils 单例复用。"""
from __future__ import annotations

import hashlib
from app.log import logger
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

from app.utils.http import RequestUtils

LOG_PREFIX = "【CoverGen】"

DEFAULT_FONT_BASE = "https://raw.githubusercontent.com/justzerock/MoviePilot-Plugins/main/fonts"
DEFAULT_FONT_URLS = {
    "chaohei": f"{DEFAULT_FONT_BASE}/chaohei.ttf",
    "yasong": f"{DEFAULT_FONT_BASE}/yasong.ttf",
    "EmblemaOne": f"{DEFAULT_FONT_BASE}/EmblemaOne.woff2",
    "Melete": f"{DEFAULT_FONT_BASE}/Melete.otf",
    "Phosphate": f"{DEFAULT_FONT_BASE}/phosphate.ttf",
    "JosefinSans": f"{DEFAULT_FONT_BASE}/josefinsans.woff2",
    "LilitaOne": f"{DEFAULT_FONT_BASE}/lilitaone.woff2",
    "Monoton": f"{DEFAULT_FONT_BASE}/Monoton.woff2",
    "Plaster": f"{DEFAULT_FONT_BASE}/Plaster.woff2",
}
ZH_PRESETS = [
    {"title": "潮黑", "value": "chaohei", "aliases": ["chaohei", "潮黑", "chao_hei"]},
    {"title": "粗雅宋", "value": "yasong", "aliases": ["yasong", "粗雅宋", "ya_song"]},
]
EN_PRESETS = [
    {"title": "EmblemaOne", "value": "EmblemaOne", "aliases": ["emblemaone", "emblema_one"]},
    {"title": "Melete", "value": "Melete", "aliases": ["melete"]},
    {"title": "Phosphate", "value": "Phosphate", "aliases": ["phosphate", "phosphat"]},
    {"title": "JosefinSans", "value": "JosefinSans", "aliases": ["josefinsans", "josefin_sans"]},
    {"title": "LilitaOne", "value": "LilitaOne", "aliases": ["lilitaone", "lilita_one"]},
    {"title": "Monoton", "value": "Monoton", "aliases": ["monoton"]},
    {"title": "Plaster", "value": "Plaster", "aliases": ["plaster"]},
]
FONT_EXTS = (".ttf", ".otf", ".woff2", ".woff")


def _is_url(s: str) -> bool:
    return bool(s) and bool(re.match(r"^https?://[^\s]+$", s.strip(), re.IGNORECASE))


def _is_path(s: str) -> bool:
    s = (s or "").strip()
    return bool(s) and (os.path.isabs(s) or s.startswith((".", "~", "/")) or "/" in s or "\\" in s)


def detect_string_type(s: str) -> Optional[str]:
    """识别字体配置字符串类型：url / path / None。"""
    if _is_url(s):
        return "url"
    if _is_path(s):
        return "path"
    return None


def validate_font_file(path: Path) -> bool:
    """校验字体文件是否可用。"""
    try:
        if not path or not path.exists() or path.stat().st_size == 0:
            return False
        from PIL import ImageFont
        ImageFont.truetype(str(path), 12)
        return True
    except Exception as err:
        logger.warning(f"{LOG_PREFIX} 字体校验失败 {path}: {err}")
        return False


def get_extension_from_url(url: str, fallback: str = ".ttf") -> str:
    """从 URL 推断字体文件扩展名。"""
    try:
        path = urlparse(url).path
        ext = Path(path).suffix.lower()
        return ext if ext in FONT_EXTS else fallback
    except Exception:
        return fallback


class FontManager:
    """字体生命周期管理器。"""

    def __init__(self, font_dir: Path):
        self.font_dir = Path(font_dir)
        self.font_dir.mkdir(parents=True, exist_ok=True)
        self._http = RequestUtils(timeout=30)  # 单例，避免重试循环重复构造

    # ---- 预设发现 ----

    def _find_local(self, aliases: List[str]) -> Optional[Path]:
        normalized = [a.lower() for a in aliases if a]
        compact = [re.sub(r"[\s_\-]+", "", a) for a in normalized]
        if not self.font_dir.exists():
            return None
        for f in sorted(self.font_dir.iterdir(), key=lambda p: p.name.lower()):
            if not f.is_file() or f.suffix.lower() not in FONT_EXTS:
                continue
            stem = f.stem.lower()
            stem_compact = re.sub(r"[\s_\-]+", "", stem)
            for alias, ca in zip(normalized, compact):
                if alias in stem or ca in stem_compact:
                    return f
        return None

    def get_presets(self) -> Tuple[List[Dict], List[Dict], Dict[str, Optional[str]], Dict[str, Optional[str]]]:
        """返回 (zh_items, en_items, zh_paths, en_paths)。"""
        all_specs = list({s["value"]: s for s in ZH_PRESETS + EN_PRESETS}.values())
        zh_paths = {s["value"]: (str(p) if (p := self._find_local(s["aliases"])) else None) for s in all_specs}
        en_paths = dict(zh_paths)
        zh_items = [{"title": s["title"], "value": s["value"]} for s in all_specs]
        return zh_items, list(zh_items), zh_paths, en_paths

    # ---- 下载 ----

    def _download(self, url: str, dest: Path) -> bool:
        """同步下载（带重试），成功返回 True。"""
        try:
            r = self._http.get_res(url=url)
            if r and r.status_code == 200 and r.content:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(r.content)
                return True
            logger.warning(f"{LOG_PREFIX} 下载字体 {url} 状态码: {r.status_code if r else 'None'}")
        except Exception as err:
            logger.error(f"{LOG_PREFIX} 下载字体异常 {url}: {err}")
        return False

    def resolve(self, preset: str, custom: str = "") -> Optional[Path]:
        """解析字体最终路径。custom 优先 path>url>预设 URL。
        cache-skip：URL hash 未变 + 本地有效 → 跳过下载（修复原 4526-4527 注释代码）。"""
        custom_type = detect_string_type(custom)
        if custom_type == "path":
            p = Path(custom.strip())
            if validate_font_file(p):
                return p
            logger.warning(f"{LOG_PREFIX} 自定义字体路径无效: {p}")
        url = custom.strip() if custom_type == "url" else DEFAULT_FONT_URLS.get(
            preset, DEFAULT_FONT_URLS["chaohei"])
        base = f"{preset}_custom" if custom_type == "url" else preset
        dest = self.font_dir / f"{base}{get_extension_from_url(url)}"
        hash_file = self.font_dir / f"{base}_url.hash"
        url_hash = hashlib.md5(url.encode()).hexdigest()
        if hash_file.exists():
            try:
                if hash_file.read_text().strip() == url_hash and validate_font_file(dest):
                    logger.info(f"{LOG_PREFIX} 字体缓存命中: {dest}")
                    return dest
            except Exception:
                pass
        if self._download(url, dest):
            try:
                hash_file.write_text(url_hash)
            except Exception as e:
                logger.warning(f"{LOG_PREFIX} 写入 hash 失败: {e}")
            return dest
        if validate_font_file(dest):
            logger.warning(f"{LOG_PREFIX} 下载失败，沿用现有字体: {dest}")
            return dest
        logger.error(f"{LOG_PREFIX} 字体获取失败: {url}")
        return None

    # ---- 清理 ----

    def cleanup(self) -> int:
        """清理字体目录，返回删除项数。"""
        removed = 0
        if not self.font_dir.exists():
            return 0
        for entry in self.font_dir.iterdir():
            if entry.name.startswith("."):
                continue
            try:
                entry.unlink(missing_ok=True) if entry.is_file() else None
                removed += 1
            except Exception as e:
                logger.warning(f"{LOG_PREFIX} 清理字体失败 {entry}: {e}")
        return removed
