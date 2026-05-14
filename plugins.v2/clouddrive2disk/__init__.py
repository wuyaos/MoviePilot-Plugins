# input: MoviePilot 存储模块调用、CloudDrive2 gRPC 地址与 API 令牌配置
# output: CloudDrive2Disk 插件类，注册 CloudDrive2 存储并暴露文件管理覆盖方法
# pos: clouddrive2disk 插件入口，负责 MoviePilot V2 插件生命周期与存储适配
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlsplit

from app.core.event import Event, eventmanager
from app.helper.storage import StorageHelper
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import FileItem, StorageOperSelectionEventData, StorageUsage
from app.schemas.types import ChainEventType

try:
    from .core.cd2_api import Cd2Api
except Exception as err:
    logger.error(f"【CloudDrive2Disk】加载 CloudDrive2 gRPC 模块失败: {err}")
    Cd2Api = None


class CloudDrive2Disk(_PluginBase):
    """CloudDrive2 存储插件。"""

    plugin_name = "CloudDrive2 存储"
    plugin_desc = "基于 clouddrivedisk/cd2disk 修改而成，通过 CloudDrive2 proto 1.0.7 / gRPC 直连与 API 令牌接入 CloudDrive2，提供 MoviePilot 存储模块能力。"
    plugin_icon = "https://raw.githubusercontent.com/wuyaos/MoviePilot-Plugins/main/icons/cloudcompanion.png"
    plugin_version = "0.2.0"
    plugin_author = "wuyaos"
    author_url = "https://github.com/wuyaos"
    plugin_config_prefix = "clouddrive2disk_"
    plugin_order = 99
    auth_level = 1

    _enabled = False
    _disk_name = "CloudDrive2"
    _cd2_url = "http://127.0.0.1:19798"
    _api_token = ""
    _upload_mode = "direct_write"
    _cd2_api: Optional[Cd2Api] = None if Cd2Api else None

    def init_plugin(self, config: dict = None):
        config = config or {}
        self.stop_service()

        self._enabled = bool(config.get("enabled", False))
        self._disk_name = (config.get("disk_name") or "CloudDrive2").strip() or "CloudDrive2"
        self._ensure_plugin_log_file()
        self._cd2_url = self._normalize_cd2_url(config.get("cd2_url") or "http://127.0.0.1:19798")
        if not self._cd2_url:
            logger.warning("【CloudDrive2Disk】CloudDrive2 gRPC 地址格式错误，必须为 http(s)://host:port")
            self._register_storage()
            return
        self._api_token = config.get("api_token") or config.get("cd2_api_key") or ""
        self._upload_mode = (config.get("upload_mode") or "direct_write").strip() or "direct_write"
        if self._upload_mode != "direct_write":
            logger.warning("【CloudDrive2Disk】当前仅支持 direct_write，已忽略 remote_upload 选择")
            self._upload_mode = "direct_write"

        self._register_storage()

        if not self._enabled:
            logger.info("【CloudDrive2Disk】插件未启用")
            return
        if not self._api_token:
            logger.warning("【CloudDrive2Disk】未配置 API 令牌，暂不初始化 CloudDrive2 连接")
            return
        if not Cd2Api:
            logger.error("【CloudDrive2Disk】gRPC API 模块不可用，请检查依赖与 proto 文件")
            return

        try:
            self._cd2_api = Cd2Api(
                cd2_url=self._cd2_url,
                api_key=self._api_token,
                disk_name=self._disk_name,
            )
            logger.info(f"【CloudDrive2Disk】初始化完成: url={self._cd2_url}, storage={self._disk_name}")
        except Exception as err:
            self._cd2_api = None
            logger.error(f"【CloudDrive2Disk】初始化 CloudDrive2 连接失败: {err}")

    @staticmethod
    def _normalize_cd2_url(value: str) -> Optional[str]:
        text = (value or "").strip()
        parsed = urlsplit(text)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return None
        host_part = parsed.netloc.rsplit("@", 1)[-1]
        if ":" not in host_part:
            return None
        return f"{parsed.scheme}://{parsed.netloc}"

    def get_state(self) -> bool:
        return bool(self._enabled)

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
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "enabled",
                                            "label": "启用插件",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "disk_name",
                                            "label": "存储名称",
                                            "placeholder": "CloudDrive2",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VSelect",
                                        "props": {
                                            "model": "upload_mode",
                                            "label": "上传模式",
                                            "items": [
                                                {"title": "直接上传", "value": "direct_write"},
                                                {"title": "远程上传", "value": "remote_upload"},
                                            ],
                                            "hint": "直接上传会通过 gRPC 写入远端文件；远程上传会由 CloudDrive2 拉取本地文件，当前仅保留选项未实现。",
                                            "persistent-hint": True,
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
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "cd2_url",
                                            "label": "CloudDrive2 gRPC 地址",
                                            "placeholder": "http://127.0.0.1:19798",
                                            "hint": "必须使用 http(s)://host:port，填写 gRPC 地址，不是 Web UI 端口",
                                            "persistent-hint": True,
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
                                        "props": {
                                            "model": "api_token",
                                            "label": "API 令牌",
                                            "placeholder": "粘贴 API 令牌",
                                            "type": "password",
                                            "hint": "API 令牌",
                                            "persistent-hint": True,
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
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VAlert",
                                        "props": {
                                            "type": "info",
                                            "variant": "tonal",
                                            "text": "直接上传：CreateFile → 3MB 分块 WriteToFile → CloseFile，并等待 CloudDrive2 云端上传完成；远程上传：CloudDrive2 通过本地 URL 拉取文件，当前仅预留未实现。",
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                ],
            }
        ], {
            "enabled": False,
            "disk_name": "CloudDrive2",
            "cd2_url": "http://127.0.0.1:19798",
            "api_token": "",
            "upload_mode": "direct_write",
        }

    def get_page(self) -> List[dict]:
        try:
            status = "已启用" if self._enabled else "未启用"
            api_status = "已连接" if self._cd2_api else "未连接"
            return [
                {
                    "component": "VCard",
                    "props": {"variant": "tonal"},
                    "content": [
                        {
                            "component": "VCardText",
                            "text": f"CloudDrive2Disk：{status}，存储：{self._disk_name}，gRPC：{self._cd2_url}，状态：{api_status}",
                        }
                    ],
                }
            ]
        except Exception as err:
            logger.error(f"【CloudDrive2Disk】渲染页面失败: {err}")
            return [{"component": "VAlert", "props": {"type": "error", "text": str(err)}}]

    def get_api(self) -> List[Dict[str, Any]]:
        return []

    def get_service(self) -> List[Dict[str, Any]]:
        return []

    def get_command(self) -> List[Dict[str, Any]]:
        return []

    def get_module(self) -> Dict[str, Any]:
        return {
            "list_files": self.list_files,
            "any_files": self.any_files,
            "download_file": self.download_file,
            "upload_file": self.upload_file,
            "delete_file": self.delete_file,
            "rename_file": self.rename_file,
            "get_file_item": self.get_file_item,
            "get_parent_item": self.get_parent_item,
            "snapshot_storage": self.snapshot_storage,
            "storage_usage": self.storage_usage,
            "support_transtype": self.support_transtype,
            "create_folder": self.create_folder,
            "exists": self.exists,
            "get_item": self.get_item,
        }

    @eventmanager.register(ChainEventType.StorageOperSelection)
    def storage_oper_selection(self, event: Event):
        if not self.get_state() or not self._cd2_api:
            return

        event_data: StorageOperSelectionEventData = event.event_data
        if event_data.storage == self._disk_name:
            event_data.storage_oper = self._cd2_api

    def list_files(self, fileitem: FileItem, recursion: bool = False) -> Optional[List[FileItem]]:
        if fileitem.storage != self._disk_name:
            return None
        if not self._cd2_api:
            return []
        return self._cd2_api.iter_files(fileitem) if recursion else self._cd2_api.list(fileitem)

    def any_files(self, fileitem: FileItem) -> Optional[bool]:
        files = self.list_files(fileitem)
        return None if files is None else bool(files)

    def download_file(self, fileitem: FileItem, path: Path = None) -> Optional[Path]:
        if fileitem.storage != self._disk_name:
            return None
        if not self._cd2_api:
            return None
        return self._cd2_api.download(fileitem, path)

    def upload_file(self, fileitem: FileItem, path: Path, new_name: str = None) -> Optional[FileItem]:
        if fileitem.storage != self._disk_name:
            return None
        if not self._cd2_api:
            return None
        return self._cd2_api.upload(fileitem, Path(path), new_name)

    def delete_file(self, fileitem: FileItem) -> Optional[bool]:
        if fileitem.storage != self._disk_name:
            return None
        if not self._cd2_api:
            return False
        return self._cd2_api.delete(fileitem)

    def rename_file(self, fileitem: FileItem, name: str) -> Optional[bool]:
        if fileitem.storage != self._disk_name:
            return None
        if not self._cd2_api:
            return False
        return self._cd2_api.rename(fileitem, name)

    def get_file_item(self, storage: str, path: Path) -> Optional[FileItem]:
        if storage != self._disk_name:
            return None
        if not self._cd2_api:
            return None
        return self._cd2_api.get_item(path)

    def get_parent_item(self, fileitem: FileItem) -> Optional[FileItem]:
        if fileitem.storage != self._disk_name:
            return None
        if not self._cd2_api:
            return None
        return self._cd2_api.get_parent(fileitem)

    def snapshot_storage(self, storage: str, fileitem: FileItem) -> Optional[List[FileItem]]:
        if storage != self._disk_name or fileitem.storage != self._disk_name:
            return None
        if not self._cd2_api:
            return []
        return self._cd2_api.iter_files(fileitem) or []

    def storage_usage(self, storage: str) -> Optional[StorageUsage]:
        if storage != self._disk_name:
            return None
        if not self._cd2_api:
            return None
        return self._cd2_api.usage()

    def support_transtype(self, storage: str, transtype: str) -> Optional[bool]:
        if storage != self._disk_name:
            return None
        if not self._cd2_api:
            return False
        return self._cd2_api.is_support_transtype(transtype)

    def create_folder(self, fileitem: FileItem, name: str) -> Optional[FileItem]:
        if fileitem.storage != self._disk_name:
            return None
        if not self._cd2_api:
            return None
        return self._cd2_api.create_folder(fileitem, name)

    def exists(self, fileitem: FileItem) -> Optional[bool]:
        if fileitem.storage != self._disk_name:
            return None
        if not self._cd2_api:
            return False
        return bool(self._cd2_api.get_item(Path(fileitem.path)))

    def get_item(self, storage: str, path: Path) -> Optional[FileItem]:
        return self.get_file_item(storage, path)

    def _register_storage(self):
        try:
            storage_helper = StorageHelper()
            storages = storage_helper.get_storagies()
            if not any(one.type == self._disk_name and one.name == self._disk_name for one in storages):
                storage_helper.add_storage(storage=self._disk_name, name=self._disk_name, conf={})
                logger.info(f"【CloudDrive2Disk】已注册存储: {self._disk_name}")
        except Exception as err:
            logger.error(f"【CloudDrive2Disk】注册存储失败: {err}")

    @staticmethod
    def _ensure_plugin_log_file():
        try:
            from app.core.config import settings

            path = settings.LOG_PATH / "plugins" / "clouddrive2disk.log"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch(exist_ok=True)
        except Exception:
            pass

    def stop_service(self):
        if self._cd2_api:
            self._cd2_api.close()
        self._cd2_api = None
