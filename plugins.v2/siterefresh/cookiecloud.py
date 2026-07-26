# input: MoviePilot CookieCloud 配置、站点 URL、刷新后的 Cookie 字符串
# output: 更新后的 CookieCloud 加密数据（远程 /update 或本地 json）
# pos: SiteRefresh 的 CookieCloud 写回适配层，避免主插件直接处理加密协议
from __future__ import annotations

import json
import os
import tempfile
from http.cookies import SimpleCookie
from typing import Any, Dict, Tuple
from urllib.parse import urlparse

from app.core.config import settings
from app.utils.crypto import CryptoJsUtils, HashUtils
from app.utils.http import RequestUtils
from app.utils.string import StringUtils
from app.utils.url import UrlUtils


def sync_cookie_to_cookiecloud(site_url: str, cookie: str) -> Tuple[bool, str]:
    try:
        return _sync_cookie_to_cookiecloud(site_url, cookie)
    except Exception as exc:
        return False, f"CookieCloud 同步异常：{exc}"


def _sync_cookie_to_cookiecloud(site_url: str, cookie: str) -> Tuple[bool, str]:
    key = StringUtils.safe_strip(settings.COOKIECLOUD_KEY)
    password = StringUtils.safe_strip(settings.COOKIECLOUD_PASSWORD)
    host = UrlUtils.standardize_base_url(settings.COOKIECLOUD_HOST)
    if not key or not password or (not host and not settings.COOKIECLOUD_ENABLE_LOCAL):
        return False, "CookieCloud 参数不完整"
    if not cookie:
        return False, "Cookie 为空"

    raw, msg = _load_raw_payload(host, key)
    if raw is None:
        return False, msg
    data, msg = _decrypt_payload(raw, key, password)
    if data is None:
        return False, msg

    has_wrapper = isinstance(data.get("cookie_data"), dict)
    cookie_data = data.get("cookie_data") if has_wrapper else data
    if not isinstance(cookie_data, dict):
        cookie_data = {}
    domain_key, cookie_items = _build_cookie_items(site_url, cookie)
    if not domain_key or not cookie_items:
        return False, "无法解析刷新后的 Cookie"
    target_key = _find_existing_key(cookie_data, domain_key)
    cookie_data[target_key] = _merge_cookie_items(cookie_data.get(target_key), cookie_items)

    if has_wrapper:
        data["cookie_data"] = cookie_data
    else:
        data = cookie_data
    encrypted = CryptoJsUtils.encrypt(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
        HashUtils.md5(f"{key}-{password}")[:16].encode("utf-8"),
    ).decode("utf-8")
    return _save_raw_payload(host, key, encrypted)


def _load_raw_payload(host: str, key: str) -> Tuple[Dict[str, Any] | None, str]:
    try:
        if settings.COOKIECLOUD_ENABLE_LOCAL:
            file_path = settings.COOKIE_PATH / f"{key}.json"
            if not file_path.exists():
                return None, "本地 CookieCloud 文件不存在"
            return json.loads(file_path.read_text(encoding="utf-8")), ""
        ret = RequestUtils(content_type="application/json").get_res(url=UrlUtils.combine_url(host=host, path=f"get/{key}"))
        if ret and ret.status_code == 200:
            return ret.json(), ""
        return None, f"CookieCloud 下载失败：{ret.status_code if ret else '无响应'}"
    except Exception as exc:
        return None, f"CookieCloud 读取失败：{exc}"


def _save_raw_payload(host: str, key: str, encrypted: str) -> Tuple[bool, str]:
    payload = {"uuid": key, "encrypted": encrypted}
    try:
        if settings.COOKIECLOUD_ENABLE_LOCAL:
            file_path = settings.COOKIE_PATH / f"{key}.json"
            file_path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(prefix=".cookiecloud-", suffix=".tmp", dir=str(file_path.parent))
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    fh.write(json.dumps(payload, ensure_ascii=False))
                    fh.flush()
                    os.fsync(fh.fileno())
                os.replace(tmp, file_path)
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)
            return True, "已写入本地 CookieCloud"
        ret = RequestUtils(content_type="application/x-www-form-urlencoded").post_res(
            url=UrlUtils.combine_url(host=host, path="update"), data=payload,
        )
        if ret and ret.status_code == 200:
            return True, "已同步 CookieCloud"
        return False, f"CookieCloud 上传失败：{ret.status_code if ret else '无响应'}"
    except Exception as exc:
        return False, f"CookieCloud 保存失败：{exc}"


def _decrypt_payload(raw: Dict[str, Any], key: str, password: str) -> Tuple[Dict[str, Any] | None, str]:
    encrypted = raw.get("encrypted") if isinstance(raw, dict) else None
    if not encrypted:
        return None, "未获取到 CookieCloud 密文"
    try:
        text = CryptoJsUtils.decrypt(encrypted, HashUtils.md5(f"{key}-{password}")[:16].encode("utf-8"))
        return json.loads(text.decode("utf-8")), ""
    except Exception as exc:
        return None, f"CookieCloud 解密失败：{exc}"


def _build_cookie_items(site_url: str, cookie: str) -> Tuple[str, list[dict]]:
    try:
        parsed = urlparse(site_url or "")
        host = (parsed.hostname or parsed.netloc or "").lower().strip()
        domain_key = StringUtils.get_url_domain(host) or host
        simple = SimpleCookie()
        simple.load(cookie)
        items = [{"domain": host, "hostOnly": True, "name": k, "path": "/", "value": m.value}
                 for k, m in simple.items() if k and m.value is not None]
        return domain_key, items
    except Exception:
        return "", []


def _merge_cookie_items(existing: Any, fresh: list[dict]) -> list[dict]:
    existing_items = existing if isinstance(existing, list) else []
    fresh_map = {(item.get("domain"), item.get("name"), item.get("path", "/")): item for item in fresh}
    merged = []
    for item in existing_items:
        key = (item.get("domain"), item.get("name"), item.get("path", "/"))
        if key in fresh_map:
            updated = dict(item)
            updated.update({k: v for k, v in fresh_map.pop(key).items() if v is not None})
            merged.append(updated)
        else:
            merged.append(item)
    return merged + list(fresh_map.values())


def _find_existing_key(cookie_data: Dict[str, Any], domain_key: str) -> str:
    for key, values in cookie_data.items():
        if key == domain_key:
            return key
        if isinstance(values, list):
            for item in values:
                domain = StringUtils.get_url_domain((item or {}).get("domain"))
                if domain == domain_key:
                    return key
    return domain_key
