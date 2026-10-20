# -*- coding: utf-8 -*-
import threading
from typing import Any, Optional
from urllib.parse import urlsplit

from app.runtime.log import logger
from app.sdk.plugin import _PluginBase

MARKER_ATTR = "_runtimepatchguard_wrapped"


class RuntimePatchGuard(_PluginBase):
    """
    运行时补丁守卫。

    MP V3 宿主部分网络调用缺少总时长守卫，慢站/黑洞响应会长期挂起
    工作线程并拖垮调度批次。本插件在内存中为
    SiteParserBase._get_page_content 包装一层总时长守卫：调用仍走原实现
    （保留官方 per-request timeout），但整体超过阈值时调用方立即返回空串，
    不再无限等待。不修改宿主文件，MP 镜像升级后无需重打。
    """

    plugin_name = "运行时补丁守卫"
    plugin_desc = "为站点解析网络请求增加总时长守卫，防止慢站挂起工作线程。内存补丁，升级免重打。"
    plugin_icon = "Moviepilot_A.png"
    plugin_version = "1.0.0"
    plugin_author = "wuyaos"
    author_url = "https://github.com/wuyaos"
    plugin_config_prefix = "runtimepatchguard_"
    plugin_order = 1
    auth_level = 1

    _enabled = False
    _timeout = 120
    _lock = threading.Lock()
    _applied = False
    _original = None

    def init_plugin(self, config: dict | None = None) -> None:
        config = config or {}
        self._enabled = bool(config.get("enabled", True))
        try:
            self._timeout = max(30, int(config.get("timeout") or 120))
        except (TypeError, ValueError):
            self._timeout = 120
        if not self._enabled:
            self._unpatch()
            return
        self._patch()

    def _patch(self) -> None:
        with self._lock:
            try:
                from app.modules.indexer.parser import SiteParserBase
            except Exception as e:
                logger.error(f"【RuntimePatchGuard】无法导入 SiteParserBase，补丁未应用：{e}")
                return
            current = SiteParserBase.__dict__.get("_get_page_content")
            if current is None:
                logger.error("【RuntimePatchGuard】SiteParserBase._get_page_content 不存在，补丁未应用")
                return
            if getattr(current, MARKER_ATTR, False):
                logger.info("【RuntimePatchGuard】补丁已应用，跳过重复包装")
                self._applied = True
                return
            self._original = current
            timeout = self._timeout
            plugin_label = "【RuntimePatchGuard】"

            def guarded_get_page_content(self_parser, *args, **kwargs):
                url = kwargs.get("url") or (args[0] if args else "")
                host = urlsplit(str(url)).netloc or str(url)
                result_box: dict[str, Any] = {}

                def worker():
                    try:
                        result_box["result"] = current(self_parser, *args, **kwargs)
                    except BaseException as e:
                        result_box["error"] = e

                worker_thread = threading.Thread(
                    target=worker, name="runtimepatchguard-page", daemon=True
                )
                worker_thread.start()
                worker_thread.join(timeout)
                if worker_thread.is_alive():
                    logger.error(
                        f"{plugin_label}站点 {self_parser._site_name} 页面请求超过总时长 "
                        f"{timeout}s（host={host}），已放行调用方；守护线程随请求失败自行退出"
                    )
                    return ""
                if "error" in result_box:
                    logger.error(f"{plugin_label}站点 {self_parser._site_name} 页面请求异常：{result_box['error']}")
                    return ""
                return result_box.get("result")

            guarded_get_page_content.__name__ = "_get_page_content"
            guarded_get_page_content.__qualname__ = "SiteParserBase._get_page_content"
            setattr(guarded_get_page_content, MARKER_ATTR, True)
            SiteParserBase._get_page_content = guarded_get_page_content
            self._applied = True
            logger.info(
                f"【RuntimePatchGuard】已为 SiteParserBase._get_page_content 应用 {timeout}s 总时长守卫"
            )

    def _unpatch(self) -> None:
        with self._lock:
            if not self._applied or self._original is None:
                return
            try:
                from app.modules.indexer.parser import SiteParserBase

                current = SiteParserBase.__dict__.get("_get_page_content")
                if getattr(current, MARKER_ATTR, False):
                    SiteParserBase._get_page_content = self._original
                    logger.info("【RuntimePatchGuard】已恢复原始 _get_page_content")
            except Exception as e:
                logger.error(f"【RuntimePatchGuard】恢复原始方法失败：{e}")
            self._applied = False
            self._original = None


    def get_state(self) -> bool:
        return self._enabled and self._applied

    @staticmethod
    def get_command() -> list[dict[str, Any]]:
        return []

    def get_api(self) -> list[dict[str, Any]]:
        return []

    def get_form(self) -> tuple[list[dict], dict[str, Any]]:
        return [
            {
                "component": "VForm",
                "content": [
                    {
                        "component": "VSwitch",
                        "props": {
                            "model": "enabled",
                            "label": "启用总时长守卫",
                        },
                    },
                    {
                        "component": "VTextField",
                        "props": {
                            "model": "timeout",
                            "label": "单次页面请求总时长上限（秒）",
                            "placeholder": "120",
                        },
                    },
                ],
            }
        ], {
            "enabled": True,
            "timeout": 120,
        }

    def get_page(self) -> list[dict]:
        status = "已应用" if self._applied else "未应用"
        return [
            {
                "component": "VAlert",
                "props": {
                    "type": "info",
                    "variant": "tonal",
                    "text": f"补丁状态：{status}；当前守卫阈值 {self._timeout} 秒。",
                },
            }
        ]

    def stop_service(self) -> None:
        self._unpatch()
        self._unpatch()
