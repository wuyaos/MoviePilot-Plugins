import os
import shutil
import threading
import traceback
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlsplit

import requests

from app.core.event import Event, eventmanager
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import EventType


class CloudStrmCompanionCustom(_PluginBase):
    plugin_name = "云盘Strm助手（CD2增强）"
    plugin_desc = "联动生成 strm，并支持通过 CloudDrive2 下载非视频文件。"
    plugin_icon = "https://raw.githubusercontent.com/thsrite/MoviePilot-Plugins/main/icons/cloudcompanion.png"
    plugin_version = "0.1.1"
    plugin_author = "wuyaos"
    author_url = "https://github.com/wuyaos"
    plugin_config_prefix = "cloudstrmcompanioncustom_"
    plugin_order = 25
    auth_level = 1

    _enabled = False
    _onlyonce = False
    _cover = False
    _uriencode = False
    _copy_nonmedia_local = False
    _monitor_confs = ""
    _rmt_mediaext = ".mp4, .mkv, .ts, .iso,.rmvb, .avi, .mov, .mpeg,.mpg, .wmv, .3gp, .asf, .m4v, .flv, .m2ts, .strm,.tp, .f4v"
    _other_mediaext = ".nfo, .jpg, .png, .json, .ass, .ssa, .srt, .sub"

    _cd2_enabled = False
    _cd2_origin = "http://127.0.0.1:19798"
    _cd2_username = ""
    _cd2_password = ""
    _cd2_timeout = 30
    _cd2_download_nonmedia = False
    _cd2_handle_mode = "download_url_path"
    _cd2_use_grpc_lookup = True

    _strm_dir_conf = {}
    _cloud_dir_conf = {}
    _format_conf = {}
    _event = threading.Event()
    _lock = threading.Lock()
    _last_stats: Dict[str, Any] = {}

    def init_plugin(self, config: dict = None):
        self._strm_dir_conf = {}
        self._cloud_dir_conf = {}
        self._format_conf = {}
        self._event.clear()
        self._last_stats = {}

        config = config or {}
        self._enabled = bool(config.get("enabled"))
        self._onlyonce = bool(config.get("onlyonce"))
        self._cover = bool(config.get("cover"))
        self._uriencode = bool(config.get("uriencode"))
        self._copy_nonmedia_local = bool(config.get("copy_nonmedia_local"))
        self._monitor_confs = (config.get("monitor_confs") or "").strip()
        self._rmt_mediaext = config.get("rmt_mediaext") or self._rmt_mediaext
        self._other_mediaext = config.get("other_mediaext") or self._other_mediaext

        self._cd2_enabled = bool(config.get("cd2_enabled"))
        self._cd2_origin = (config.get("cd2_origin") or self._cd2_origin).strip()
        self._cd2_username = (config.get("cd2_username") or "").strip()
        self._cd2_password = (config.get("cd2_password") or "").strip()
        try:
            self._cd2_timeout = int(config.get("cd2_timeout") or 30)
        except (TypeError, ValueError):
            self._cd2_timeout = 30
        self._cd2_download_nonmedia = bool(config.get("cd2_download_nonmedia"))
        self._cd2_handle_mode = self.__resolve_cd2_handle_mode(config)
        self._cd2_use_grpc_lookup = self._cd2_handle_mode != "static_url"

        self.__load_monitor_conf()

        if self._onlyonce and self._enabled:
            threading.Thread(target=self.scan, daemon=True, name="cloudstrmcompanioncustom_scan").start()
            self._onlyonce = False
            self.__update_config()

    def __load_monitor_conf(self):
        for row in self._monitor_confs.split("\n"):
            line = (row or "").strip()
            if not line or line.startswith("#"):
                continue
            if line.count("#") != 3:
                logger.error(f"目录配置格式错误: {line}")
                continue
            local_dir, strm_dir, cloud_dir, format_str = line.split("#")
            local_dir = local_dir.strip()
            strm_dir = strm_dir.strip()
            cloud_dir = cloud_dir.strip()
            format_str = format_str.strip()
            if not local_dir or not strm_dir or not cloud_dir or not format_str:
                logger.error(f"目录配置存在空字段: {line}")
                continue
            self._strm_dir_conf[local_dir] = strm_dir
            self._cloud_dir_conf[local_dir] = cloud_dir
            self._format_conf[local_dir] = format_str

    def __update_config(self):
        self.update_config(
            {
                "enabled": self._enabled,
                "onlyonce": self._onlyonce,
                "cover": self._cover,
                "uriencode": self._uriencode,
                "monitor_confs": self._monitor_confs,
                "rmt_mediaext": self._rmt_mediaext,
                "other_mediaext": self._other_mediaext,
                "copy_nonmedia_local": self._copy_nonmedia_local,
                "cd2_enabled": self._cd2_enabled,
                "cd2_origin": self._cd2_origin,
                "cd2_username": self._cd2_username,
                "cd2_password": self._cd2_password,
                "cd2_timeout": self._cd2_timeout,
                "cd2_download_nonmedia": self._cd2_download_nonmedia,
                "cd2_handle_mode": self._cd2_handle_mode,
                "cd2_use_grpc_lookup": self._cd2_use_grpc_lookup,
            }
        )

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return [
            {
                "cmd": "/cloud_strm_custom",
                "event": EventType.PluginAction,
                "desc": "云盘Strm助手（CD2增强）全量同步",
                "category": "",
                "data": {"action": "cloudstrm_scan_custom"},
            },
        ]

    def get_api(self) -> List[Dict[str, Any]]:
        return [
            {
                "path": "/scan",
                "endpoint": self.api_scan,
                "auth": "bear",
                "methods": ["POST", "GET"],
                "summary": "全量扫描生成 Strm 与下载非视频文件",
            },
            {
                "path": "scan",
                "endpoint": self.api_scan,
                "auth": "bear",
                "methods": ["POST", "GET"],
                "summary": "全量扫描生成 Strm 与下载非视频文件(兼容无前导斜杠)",
            },
            {
                "path": "/process_file",
                "endpoint": self.api_process_file,
                "auth": "bear",
                "methods": ["POST", "GET"],
                "summary": "处理单个文件",
            },
            {
                "path": "process_file",
                "endpoint": self.api_process_file,
                "auth": "bear",
                "methods": ["POST", "GET"],
                "summary": "处理单个文件(兼容无前导斜杠)",
            },
        ]

    def api_scan(self):
        if not self._enabled:
            return {"code": 1, "msg": "插件未启用"}
        threading.Thread(target=self.scan, daemon=True, name="cloudstrmcompanioncustom_api_scan").start()
        return {"code": 0, "msg": "扫描任务已启动"}

    def api_process_file(self, file_path: str = "", body: dict = None):
        if not self._enabled:
            return {"code": 1, "msg": "插件未启用"}
        if not file_path and body and isinstance(body, dict):
            file_path = str(body.get("file_path") or "").strip()
        if not file_path:
            return {"code": 1, "msg": "缺少 file_path"}
        mon_path = self.__resolve_mon_path(file_path)
        if not mon_path:
            return {"code": 1, "msg": "文件不在监控目录下"}
        ok = self.__handle_file(file_path, mon_path)
        return {"code": 0 if ok else 1, "msg": "处理完成" if ok else "处理失败"}

    @eventmanager.register(EventType.PluginAction)
    def on_plugin_action(self, event: Event = None):
        event_data = (event.event_data or {}) if event else {}
        action = event_data.get("action")
        if action == "cloudstrm_scan_custom":
            if not self._enabled:
                return
            threading.Thread(target=self.scan, daemon=True, name="cloudstrmcompanioncustom_cmd_scan").start()
            return
        if action != "cloudstrm_file":
            return
        if not self._enabled:
            return
        file_path = event_data.get("file_path")
        if not file_path:
            logger.error("cloudstrm_file 事件缺少 file_path")
            return
        mon_path = self.__resolve_mon_path(file_path)
        if not mon_path:
            logger.warning(f"未找到文件 {file_path} 对应监控目录")
            return
        self.__handle_file(file_path, mon_path)

    def __resolve_mon_path(self, file_path: str) -> Optional[str]:
        for mon in self._strm_dir_conf.keys():
            if str(file_path).startswith(mon):
                return mon
        return None

    def scan(self):
        if not self._enabled:
            return
        if not self._strm_dir_conf:
            logger.warning("未配置目录映射，跳过扫描")
            return
        stats = {"total": 0, "strm": 0, "nonmedia_downloaded": 0, "failed": 0}
        self._event.clear()
        logger.info("开始全量扫描处理 Strm/CD2")
        for mon_path in self._strm_dir_conf.keys():
            if self._event.is_set():
                break
            for root, dirs, files in os.walk(mon_path):
                if "extrafanart" in dirs:
                    dirs.remove("extrafanart")
                for name in files:
                    if self._event.is_set():
                        break
                    source_file = os.path.join(root, name)
                    if self.__skip_file(source_file):
                        continue
                    stats["total"] += 1
                    result = self.__handle_file(source_file, mon_path)
                    if result is True:
                        if self.__is_media_file(source_file):
                            stats["strm"] += 1
                        else:
                            stats["nonmedia_downloaded"] += 1
                    else:
                        stats["failed"] += 1
        self._last_stats = stats
        logger.info(
            f"Strm/CD2 扫描结束: total={stats['total']} strm={stats['strm']} "
            f"nonmedia_downloaded={stats['nonmedia_downloaded']} failed={stats['failed']}"
        )

    def __skip_file(self, source_file: str) -> bool:
        return (
            source_file.find("/@Recycle") != -1
            or source_file.find("/#recycle") != -1
            or source_file.find("/.") != -1
            or source_file.find("/@eaDir") != -1
        )

    def __is_media_file(self, source_file: str) -> bool:
        ext = Path(source_file).suffix.lower()
        allowed = [item.strip().lower() for item in str(self._rmt_mediaext).split(",") if item.strip()]
        return ext in allowed

    def __is_other_file(self, source_file: str) -> bool:
        ext = Path(source_file).suffix.lower()
        allowed = [item.strip().lower() for item in str(self._other_mediaext).split(",") if item.strip()]
        return ext in allowed

    def __handle_file(self, event_path: str, mon_path: str) -> bool:
        try:
            if not Path(event_path).exists() or not Path(event_path).is_file():
                return False
            with self._lock:
                strm_dir = self._strm_dir_conf.get(mon_path)
                cloud_dir = self._cloud_dir_conf.get(mon_path)
                format_str = self._format_conf.get(mon_path)
                if not strm_dir or not cloud_dir or not format_str:
                    logger.error(f"目录配置不完整: mon={mon_path}")
                    return False

                target_file = str(event_path).replace(mon_path, strm_dir)
                cloud_file = str(event_path).replace(mon_path, cloud_dir)

                if self.__is_media_file(event_path):
                    strm_content = self.__format_content(format_str, event_path, cloud_file, self._uriencode)
                    return self.__create_strm_file(target_file, strm_content)

                if self.__is_other_file(event_path):
                    if self._cd2_enabled and self._cd2_download_nonmedia:
                        ok = self.__download_nonmedia_via_cd2(cloud_file, target_file)
                        if ok:
                            return True
                    if self._copy_nonmedia_local:
                        os.makedirs(os.path.dirname(target_file), exist_ok=True)
                        shutil.copy2(event_path, target_file)
                        logger.info(f"本地复制非视频文件: {event_path} -> {target_file}")
                        return True
                    logger.info(f"非视频文件跳过(未启用 CD2 下载/本地复制): {event_path}")
                    return False
                return False
        except Exception:
            logger.error(f"处理文件异常: {event_path}\n{traceback.format_exc()}")
            return False

    @staticmethod
    def __format_content(format_str: str, local_file: str, cloud_file: str, uriencode: bool) -> Optional[str]:
        if "{local_file}" in format_str:
            return format_str.replace("{local_file}", local_file)
        if "{cloud_file}" in format_str:
            normalized = cloud_file
            if uriencode:
                normalized = urllib.parse.quote(normalized, safe="/")
            else:
                normalized = normalized.replace("\\", "/")
            return format_str.replace("{cloud_file}", normalized)
        return None

    def __create_strm_file(self, target_file: str, strm_content: Optional[str]) -> bool:
        if not strm_content:
            logger.error(f"strm 内容为空，跳过: {target_file}")
            return False
        try:
            strm_file = os.path.join(Path(target_file).parent, f"{Path(target_file).stem}.strm")
            if Path(strm_file).exists() and not self._cover:
                logger.info(f"Strm 已存在且未开启覆盖: {strm_file}")
                return True
            os.makedirs(Path(strm_file).parent, exist_ok=True)
            with open(strm_file, "w", encoding="utf-8") as f:
                f.write(strm_content)
            logger.info(f"写入 Strm 成功: {strm_file} -> {strm_content}")
            return True
        except Exception:
            logger.error(f"写入 Strm 失败: {target_file}\n{traceback.format_exc()}")
            return False

    def __normalize_cloud_path(self, cloud_file: str) -> str:
        normalized = str(cloud_file).replace("\\", "/").strip()
        if not normalized.startswith("/"):
            normalized = f"/{normalized}"
        return normalized

    @staticmethod
    def __pick_field(payload: Any, *field_names: str) -> Any:
        if payload is None:
            return None
        for field_name in field_names:
            if isinstance(payload, dict) and field_name in payload:
                return payload.get(field_name)
            if hasattr(payload, field_name):
                return getattr(payload, field_name)
        return None

    def __resolve_cd2_handle_mode(self, config: Dict[str, Any]) -> str:
        mode = str(config.get("cd2_handle_mode") or "").strip()
        allowed_modes = {"download_url_path", "find_file_path", "static_url"}
        if not mode:
            legacy_lookup = config.get("cd2_use_grpc_lookup")
            if legacy_lookup is None:
                return "download_url_path"
            return "find_file_path" if bool(legacy_lookup) else "static_url"
        if mode not in allowed_modes:
            logger.warning(f"未知 cd2_handle_mode={mode}，回退到 download_url_path")
            return "download_url_path"
        return mode

    def __resolve_cd2_origin(self) -> Tuple[str, str]:
        origin = self._cd2_origin.strip() or "http://127.0.0.1:19798"
        if "://" not in origin:
            origin = f"http://{origin}"
        url_info = urlsplit(origin)
        scheme = url_info.scheme or "http"
        netloc = url_info.netloc or "127.0.0.1:19798"
        return scheme, netloc

    def __build_static_download_url(self, cloud_file: str) -> str:
        cloud_path = self.__normalize_cloud_path(cloud_file)
        scheme, netloc = self.__resolve_cd2_origin()
        base_url = f"{scheme}://{netloc}/static/{scheme}/{netloc}/False"
        quoted_cloud_path = urllib.parse.quote(cloud_path, safe="/")
        return f"{base_url}{quoted_cloud_path}"

    @staticmethod
    def __call_cd2_api(api_func: Any, request_data: Dict[str, Any]) -> Any:
        try:
            return api_func(request_data)
        except TypeError:
            return api_func(**request_data)

    def __get_download_url_from_api(self, client: Any, cloud_path: str) -> Optional[Tuple[str, Dict[str, str]]]:
        api_func = getattr(client, "GetDownloadUrlPath", None)
        if not api_func:
            return None
        try:
            req = {
                "path": cloud_path,
                "preview": False,
                "lazyRead": False,
                "getDirectUrl": True,
            }
            result = self.__call_cd2_api(api_func, req)
            direct_url = self.__pick_field(result, "directUrl", "direct_url")
            extra_headers = self.__pick_field(result, "additionalHeaders", "additional_headers") or {}
            user_agent = self.__pick_field(result, "userAgent", "user_agent")
            headers = {}
            if isinstance(extra_headers, dict):
                headers = {str(k): str(v) for k, v in extra_headers.items() if k and v}
            if user_agent and "User-Agent" not in headers:
                headers["User-Agent"] = str(user_agent)
            if direct_url:
                return str(direct_url), headers

            raw_download_path = self.__pick_field(result, "downloadUrlPath", "download_url_path")
            if not raw_download_path:
                return None

            scheme, netloc = self.__resolve_cd2_origin()
            download_url = str(raw_download_path)
            download_url = download_url.replace("{SCHEME}", scheme)
            download_url = download_url.replace("{HOST}", netloc)
            download_url = download_url.replace("{PREVIEW}", "False")
            if download_url.startswith("/"):
                download_url = f"{scheme}://{netloc}{download_url}"
            return download_url, headers
        except Exception as e:
            logger.warning(f"CD2 GetDownloadUrlPath 获取下载地址失败: {e}")
            return None

    def __get_download_url_from_find_file(self, client: Any, cloud_path: str) -> Optional[Tuple[str, Dict[str, str]]]:
        api_func = getattr(client, "FindFileByPath", None)
        if not api_func:
            return None
        try:
            parent_path = str(Path(cloud_path).parent).replace("\\", "/")
            if not parent_path or parent_path == ".":
                parent_path = "/"
            file_name = Path(cloud_path).name
            cloud_file_obj = self.__call_cd2_api(api_func, {"parentPath": parent_path, "path": file_name})
            full_path = self.__pick_field(cloud_file_obj, "fullPathName", "full_path_name") or cloud_path
            base_url = str(getattr(client, "download_baseurl", "") or "").rstrip("/")
            if base_url:
                quoted_path = urllib.parse.quote(str(full_path).lstrip("/"), safe="/")
                return f"{base_url}/{quoted_path}", {}
            return self.__build_static_download_url(str(full_path)), {}
        except Exception as e:
            logger.warning(f"CD2 FindFileByPath 获取下载地址失败: {e}")
            return None

    def __build_cd2_download_target(self, cloud_file: str) -> Tuple[str, Dict[str, str]]:
        cloud_path = self.__normalize_cloud_path(cloud_file)
        if self._cd2_handle_mode == "static_url":
            return self.__build_static_download_url(cloud_path), {}

        try:
            import clouddrive  # type: ignore

            client = clouddrive.Client(
                origin=self._cd2_origin,
                username=self._cd2_username,
                password=self._cd2_password,
            )
            if self._cd2_handle_mode == "download_url_path":
                target = self.__get_download_url_from_api(client, cloud_path)
                if target:
                    return target
                logger.warning("CD2 处理方式 download_url_path 失败，回退 find_file_path")
            target = self.__get_download_url_from_find_file(client, cloud_path)
            if target:
                return target
        except Exception as e:
            logger.warning(f"CD2 gRPC 初始化失败，回退静态下载URL: {e}")

        return self.__build_static_download_url(cloud_path), {}

    def __download_nonmedia_via_cd2(self, cloud_file: str, target_file: str) -> bool:
        if not self._cd2_enabled:
            return False
        try:
            if Path(target_file).exists() and not self._cover:
                logger.info(f"非视频文件已存在且未开启覆盖: {target_file}")
                return True
            download_url, request_headers = self.__build_cd2_download_target(cloud_file)
            os.makedirs(Path(target_file).parent, exist_ok=True)
            logger.info(f"开始通过 CD2 下载非视频文件: {cloud_file} -> {target_file}")
            with requests.get(
                download_url,
                stream=True,
                headers=request_headers,
                timeout=self._cd2_timeout,
            ) as resp:
                if resp.status_code != 200:
                    logger.error(f"CD2 下载失败，状态码={resp.status_code}, url={download_url}")
                    return False
                with open(target_file, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=1024 * 128):
                        if chunk:
                            f.write(chunk)
            logger.info(f"CD2 下载非视频文件成功: {target_file}")
            return True
        except Exception:
            logger.error(f"CD2 下载非视频文件异常: {cloud_file}\n{traceback.format_exc()}")
            return False

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        return [
            {
                "component": "VForm",
                "content": [
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {"component": "VSwitch", "props": {"model": "enabled", "label": "启用插件"}}
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {"component": "VSwitch", "props": {"model": "onlyonce", "label": "立即扫描一次"}}
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {"component": "VSwitch", "props": {"model": "cover", "label": "覆盖已存在文件"}}
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {"component": "VSwitch", "props": {"model": "uriencode", "label": "strm URL编码"}}
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VTextarea",
                                        "props": {
                                            "model": "monitor_confs",
                                            "label": "目录配置",
                                            "rows": 5,
                                            "placeholder": "本地挂载路径#strm输出路径#云盘路径#strm格式模板",
                                        },
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VTextarea",
                                        "props": {
                                            "model": "rmt_mediaext",
                                            "label": "视频格式",
                                            "rows": 2,
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VTextarea",
                                        "props": {
                                            "model": "other_mediaext",
                                            "label": "非视频格式（下载目标）",
                                            "rows": 2,
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {"component": "VSwitch", "props": {"model": "cd2_enabled", "label": "启用 CD2 下载"}}
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {"model": "cd2_download_nonmedia", "label": "CD2 下载非视频文件"},
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VSelect",
                                        "props": {
                                            "model": "cd2_handle_mode",
                                            "label": "CD2 处理方式",
                                            "items": [
                                                {"title": "GetDownloadUrlPath（推荐）", "value": "download_url_path"},
                                                {"title": "FindFileByPath", "value": "find_file_path"},
                                                {"title": "静态URL拼接", "value": "static_url"},
                                            ],
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {"model": "copy_nonmedia_local", "label": "失败回退本地复制"},
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "cd2_origin",
                                            "label": "CD2 地址",
                                            "placeholder": "http://127.0.0.1:19798",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {"model": "cd2_timeout", "label": "CD2下载超时(秒)", "type": "number"},
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {"component": "VTextField", "props": {"model": "cd2_username", "label": "CD2 用户名"}}
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {"model": "cd2_password", "label": "CD2 密码", "type": "password"},
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VAlert",
                                        "props": {
                                            "type": "info",
                                            "variant": "tonal",
                                            "text": (
                                                "非视频下载流程：可选 CD2 处理方式。推荐使用 gRPC API 的 GetDownloadUrlPath，"
                                                "失败自动回退 FindFileByPath/静态URL；仍失败时可回退本地复制。"
                                            ),
                                        },
                                    }
                                ],
                            }
                        ],
                    },
                ],
            }
        ], {
            "enabled": False,
            "onlyonce": False,
            "cover": False,
            "uriencode": False,
            "monitor_confs": "",
            "rmt_mediaext": ".mp4, .mkv, .ts, .iso,.rmvb, .avi, .mov, .mpeg,.mpg, .wmv, .3gp, .asf, .m4v, .flv, .m2ts, .strm,.tp, .f4v",
            "other_mediaext": ".nfo, .jpg, .png, .json, .ass, .ssa, .srt, .sub",
            "copy_nonmedia_local": False,
            "cd2_enabled": False,
            "cd2_origin": "http://127.0.0.1:19798",
            "cd2_username": "",
            "cd2_password": "",
            "cd2_timeout": 30,
            "cd2_download_nonmedia": False,
            "cd2_handle_mode": "download_url_path",
            "cd2_use_grpc_lookup": True,
        }

    def get_page(self) -> List[dict]:
        stats = self._last_stats or {}
        text = (
            f"最近扫描统计: total={stats.get('total', 0)} "
            f"strm={stats.get('strm', 0)} "
            f"nonmedia_downloaded={stats.get('nonmedia_downloaded', 0)} "
            f"failed={stats.get('failed', 0)}"
        )
        return [
            {
                "component": "VAlert",
                "props": {"type": "info", "variant": "tonal", "text": text},
            }
        ]

    def stop_service(self):
        self._event.set()
