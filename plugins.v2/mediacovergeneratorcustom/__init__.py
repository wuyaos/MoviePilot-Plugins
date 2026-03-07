import base64
import datetime
import hashlib
import json
import os
import re
import threading
import time
import shutil
import random
from pathlib import Path
from urllib.parse import urlparse
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict

import pytz
import yaml

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app import schemas
from app.chain.mediaserver import MediaServerChain
from app.core.config import settings
from app.core.event import eventmanager, Event
from app.helper.mediaserver import MediaServerHelper
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import MediaInfo
from app.schemas.types import EventType
from app.schemas import ServiceInfo
from app.utils.http import RequestUtils
from app.utils.url import UrlUtils
from app.plugins.mediacovergeneratorcustom.style_single_1 import create_style_single_1
from app.plugins.mediacovergeneratorcustom.style_single_2 import create_style_single_2
from app.plugins.mediacovergeneratorcustom.style_multi_1  import create_style_multi_1
from app.plugins.mediacovergeneratorcustom.style.style_animated_1 import create_style_animated_1
from app.plugins.mediacovergeneratorcustom.style.style_animated_2 import create_style_animated_2
from app.plugins.mediacovergeneratorcustom.style.style_animated_3 import create_style_animated_3
from app.plugins.mediacovergeneratorcustom.style.style_animated_4 import create_style_animated_4
from app.plugins.mediacovergeneratorcustom.static.single_1 import single_1
from app.plugins.mediacovergeneratorcustom.static.single_2 import single_2
from app.plugins.mediacovergeneratorcustom.static.multi_1  import multi_1


class MediaCoverGeneratorCustom(_PluginBase):
    # 插件名称
    plugin_name = "媒体库封面生成（自用版）"
    # 插件描述
    plugin_desc = "自动生成媒体库封面，支持库白名单、合集黑名单过滤、4种动画风格、Emby和Jellyfin"
    # 插件图标
    plugin_icon = "https://raw.githubusercontent.com/wuyaos/MoviePilot-Plugins/main/icons/emby.png"
    # 插件版本
    plugin_version = "0.9.1"
    # 插件作者
    plugin_author = "wuyaos,justzerock"
    # 作者主页
    author_url = "https://github.com/wuyaos"
    # 插件配置项ID前缀
    plugin_config_prefix = "mediacovergeneratorcustom_"
    # 加载顺序
    plugin_order = 2
    # 可使用的用户级别
    auth_level = 1

    # 退出事件
    _event = threading.Event()

    # 私有属性
    _scheduler = None
    mschain = None
    mediaserver_helper = None
    _enabled = False
    _onlyonce = False
    _transfer_monitor = True
    _cron = None
    _delay = 60
    _servers = None
    _selected_servers = []
    _all_libraries = []
    _exclude_libraries = []
    _all_users = []  # 新增：存储所有用户列表
    _selected_libraries = []     # 新增：库白名单
    _exclude_boxsets = []        # 新增：合集黑名单
    _sort_by = 'Random'
    _monitor_sort = ''
    _covers_output = ''
    _covers_input = ''
    _zh_font_url = ''
    _en_font_url = ''
    _zh_font_path = ''
    _en_font_path = ''
    _zh_font_path_local = ''
    _en_font_path_local = ''
    _zh_font_path_multi_1_local = ''
    _en_font_path_multi_1_local = ''
    _zh_font_url_multi_1 = ''
    _en_font_url_multi_1 = ''
    _zh_font_path_multi_1 = ''
    _en_font_path_multi_1 = ''
    _multi_1_use_main_font = False
    _title_config = ''
    _cover_style = 'single_1'
    _font_path = ''
    _covers_path = ''
    _tab = 'style-tab'
    _multi_1_blur = False
    _zh_font_size = 1
    _en_font_size = 1
    _zh_font_size_multi_1 = 1
    _en_font_size_multi_1 = 1
    _blur_size = 50
    _blur_size_multi_1 = 50
    _color_ratio = 0.8
    _color_ratio_multi_1 = 0.8
    _single_use_primary = False
    _multi_1_use_primary = True
    _selected_users = []  # 新增：选择的用户列表
    _font_download = True  # 新增：字体下载开关
    _animation_duration = 10  # 新增：动画时长（秒）
    _animation_fps = 15  # 新增：动画帧率
    _animation_format = 'apng'  # 新增：动画格式（apng/gif）
    _animation_scroll = 'down'  # 新增：动画滚动方向（down/up/alternate）
    _animation_resolution = '640x360'  # 新增：动画分辨率
    _animation_reduce_colors = 'medium'  # 新增：颜色减少（off/medium/strong）

    def __init__(self):
        super().__init__()

    def init_plugin(self, config: dict = None):
        self.mschain = MediaServerChain()
        self.mediaserver_helper = MediaServerHelper()   
        data_path = self.get_data_path()
        (data_path / 'fonts').mkdir(parents=True, exist_ok=True)
        (data_path / 'covers').mkdir(parents=True, exist_ok=True)
        self._covers_path = data_path / 'covers'
        self._font_path = data_path / 'fonts'
        if config:
            self._enabled = config.get("enabled")
            self._onlyonce = config.get("onlyonce")
            self._transfer_monitor = config.get("transfer_monitor")
            self._cron = config.get("cron")
            self._delay = config.get("delay")
            self._selected_servers = config.get("selected_servers")
            self._exclude_libraries = config.get("exclude_libraries")
            self._sort_by = config.get("sort_by")
            self._covers_output = config.get("covers_output")
            self._covers_input = config.get("covers_input")
            self._title_config = config.get("title_config")
            self._zh_font_url = config.get("zh_font_url")
            self._en_font_url = config.get("en_font_url")
            self._zh_font_path = config.get("zh_font_path")
            self._en_font_path = config.get("en_font_path")
            self._cover_style = config.get("cover_style")
            self._tab = config.get("tab")
            self._zh_font_url_multi_1 = config.get("zh_font_url_multi_1")
            self._en_font_url_multi_1 = config.get("en_font_url_multi_1")
            self._zh_font_path_multi_1 = config.get("zh_font_path_multi_1")
            self._en_font_path_multi_1 = config.get("en_font_path_multi_1")
            self._multi_1_blur = config.get("multi_1_blur")
            self._multi_1_use_main_font = config.get("multi_1_use_main_font")
            self._zh_font_path_local = config.get("zh_font_path_local")
            self._en_font_path_local = config.get("en_font_path_local")
            self._zh_font_path_multi_1_local = config.get("zh_font_path_multi_1_local")
            self._en_font_path_multi_1_local = config.get("en_font_path_multi_1_local")
            self._zh_font_size = config.get("zh_font_size")
            self._en_font_size = config.get("en_font_size")
            self._zh_font_size_multi_1 = config.get("zh_font_size_multi_1")
            self._en_font_size_multi_1 = config.get("en_font_size_multi_1")
            self._blur_size = config.get("blur_size")
            self._blur_size_multi_1 = config.get("blur_size_multi_1")
            self._color_ratio = config.get("color_ratio")
            self._color_ratio_multi_1 = config.get("color_ratio_multi_1")
            self._single_use_primary = config.get("single_use_primary")
            self._multi_1_use_primary = config.get("multi_1_use_primary")
            self._selected_users = config.get("selected_users", [])  # 新增：获取用户筛选配置
            self._font_download = config.get("font_download", True)  # 新增：获取字体下载配置
            self._selected_libraries = config.get("selected_libraries", [])  # 新增：库白名单
            self._exclude_boxsets = config.get("exclude_boxsets", [])  # 新增：合集黑名单
            self._animation_duration = config.get("animation_duration") or 10  # 新增：动画时长
            self._animation_fps = config.get("animation_fps") or 15  # 新增：动画帧率
            self._animation_format = config.get("animation_format") or "apng"  # 新增：动画格式
            self._animation_scroll = config.get("animation_scroll") or "down"  # 新增：动画滚动
            self._animation_resolution = config.get("animation_resolution") or "640x360"  # 新增：动画分辨率
            self._animation_reduce_colors = config.get("animation_reduce_colors") or "medium"  # 新增：颜色减少

        if self._selected_servers:
            self._servers = self.mediaserver_helper.get_services(
                name_filters=self._selected_servers
            )
            self._all_libraries = []
            self._all_users = []  # 初始化用户列表
            for server, service in self._servers.items():
                if not service.instance.is_inactive():
                    self._all_libraries.extend(self.__get_all_libraries(server, service))
                    # 同时获取用户列表
                    users = self.__get_server_users(service)
                    for user in users:
                        self._all_users.append({
                            "title": f"{server}: {user['name']}",
                            "value": f"{server}-{user['id']}"
                        })
                else:
                    logger.info(f"媒体服务器 {server} 未连接")
        else:
            logger.info("未选择媒体服务器")
        

        # 停止现有任务
        self.stop_service()

        # 启动服务
        if self._onlyonce:
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)
            self._scheduler.add_job(func=self.__update_all_libraries, trigger='date',
                                    run_date=datetime.datetime.now(
                                        tz=pytz.timezone(settings.TZ)) + datetime.timedelta(seconds=3)
                                    )
            logger.info(f"媒体库封面更新服务启动，立即运行一次")
            # 关闭一次性开关
            self._onlyonce = False
            # 保存配置
            self.__update_config()
            # 启动服务
            if self._scheduler.get_jobs():
                self._scheduler.print_jobs()
                self._scheduler.start()

    def __update_config(self):
        """
        更新配置
        """
        self.update_config({
            "enabled": self._enabled,
            "onlyonce": self._onlyonce,
            "transfer_monitor": self._transfer_monitor,
            "cron": self._cron,
            "delay": self._delay,
            "selected_servers": self._selected_servers,
            "exclude_libraries": self._exclude_libraries,
            "all_libraries": self._all_libraries,
            "sort_by": self._sort_by,
            "covers_output": self._covers_output,
            "covers_input": self._covers_input,
            "title_config": self._title_config,
            "zh_font_url": self._zh_font_url,
            "en_font_url": self._en_font_url,
            "zh_font_path": self._zh_font_path,
            "en_font_path": self._en_font_path,
            "cover_style": self._cover_style,
            "tab": self._tab,
            "multi_1_blur": self._multi_1_blur,
            "zh_font_url_multi_1": self._zh_font_url_multi_1,
            "en_font_url_multi_1": self._en_font_url_multi_1,
            "zh_font_path_multi_1": self._zh_font_path_multi_1,
            "en_font_path_multi_1": self._en_font_path_multi_1,
            "multi_1_use_main_font": self._multi_1_use_main_font,
            "zh_font_path_local": self._zh_font_path_local,
            "en_font_path_local": self._en_font_path_local,
            "zh_font_path_multi_1_local": self._zh_font_path_multi_1_local,
            "en_font_path_multi_1_local": self._en_font_path_multi_1_local,
            "zh_font_size": self._zh_font_size,
            "en_font_size": self._en_font_size,
            "zh_font_size_multi_1": self._zh_font_size_multi_1,
            "en_font_size_multi_1": self._en_font_size_multi_1,
            "blur_size": self._blur_size,
            "blur_size_multi_1": self._blur_size_multi_1,
            "color_ratio": self._color_ratio,
            "color_ratio_multi_1": self._color_ratio_multi_1,
            "single_use_primary": self._single_use_primary,
            "multi_1_use_primary": self._multi_1_use_primary,
            "selected_users": self._selected_users,  # 新增：保存用户筛选配置
            "font_download": self._font_download,  # 新增：保存字体下载配置
            "selected_libraries": self._selected_libraries,  # 新增：库白名单
            "exclude_boxsets": self._exclude_boxsets,  # 新增：合集黑名单
            "animation_duration": self._animation_duration,  # 新增：动画时长
            "animation_fps": self._animation_fps,  # 新增：动画帧率
            "animation_format": self._animation_format,  # 新增：动画格式
            "animation_scroll": self._animation_scroll,  # 新增：动画滚动
            "animation_resolution": self._animation_resolution,  # 新增：动画分辨率
            "animation_reduce_colors": self._animation_reduce_colors  # 新增：颜色减少
        })

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        """
        获取插件API
        [{
            "path": "/xx",
            "endpoint": self.xxx,
            "methods": ["GET", "POST"],
            "summary": "API说明"
        }]
        """
        pass

    def get_service(self) -> List[Dict[str, Any]]:
        """
        注册插件公共服务
        """
        if self._enabled and self._cron:
            return [{
                "id": "MediaCoverGenerator",
                "name": "媒体库封面更新服务",
                "trigger": CronTrigger.from_crontab(self._cron),
                "func": self.__update_all_libraries,
                "kwargs": {}
            }]

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        拼装插件配置页面
        """
        # 基础设置标签页 - 最常用的核心功能
        basic_tab = [
            {
                'component': 'VRow',
                'props': {
                    'dense': True
                },
                'content': [
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                        },
                        'content': [
                            {
                                'component': 'VAlert',
                                'props': {
                                    'type': 'info',
                                    'variant': 'tonal',
                                    'text': '媒体库封面生成插件 - 支持Emby/Jellyfin，'
                                           '自动为您的媒体库生成美观的封面图',
                                    'class': 'mb-2'
                                }
                            }
                        ]
                    }
                ]
            },
            {
                'component': 'VRow',
                'props': {
                    'dense': True
                },
                'content': [
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 6
                        },
                        'content': [
                            {
                                'component': 'VSwitch',
                                'props': {
                                    'model': 'enabled',
                                    'label': '启用插件',
                                    'hint': '开启后将自动为媒体库生成封面',
                                    'persistentHint': True,
                                    'color': 'primary'
                                }
                            }
                        ]
                    },
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 6
                        },
                        'content': [
                            {
                                'component': 'VSwitch',
                                'props': {
                                    'model': 'onlyonce',
                                    'label': '立即运行一次',
                                    'hint': '保存后立即更新所有媒体库封面',
                                    'persistentHint': True,
                                    'color': 'success'
                                }
                            }
                        ]
                    }
                ]
            },
            {
                'component': 'VRow',
                'props': {
                    'dense': True,
                    'class': 'mt-2'
                },
                'content': [
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                        },
                        'content': [
                            {
                                'component': 'VSelect',
                                'props': {
                                    'multiple': True,
                                    'chips': True,
                                    'clearable': True,
                                    'model': 'selected_servers',
                                    'label': '媒体服务器',
                                    'items': [{"title": config.name, "value": config.name}
                                             for config in
                                             self.mediaserver_helper.get_configs().values()
                                             if config.type in ("emby", "jellyfin")],
                                    'hint': '选择要管理封面的媒体服务器（支持多选）',
                                    'persistentHint': True,
                                    'prependInnerIcon': 'mdi-server',
                                    'variant': 'outlined'
                                }
                            }
                        ]
                    },
                ]
            },
            {
                'component': 'VRow',
                'props': {
                    'dense': True
                },
                'content': [
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 6
                        },
                        'content': [
                            {
                                'component': 'VSwitch',
                                'props': {
                                    'model': 'transfer_monitor',
                                    'label': '入库监控',
                                    'hint': '新媒体入库后自动更新所在库的封面',
                                    'persistentHint': True
                                }
                            }
                        ]
                    },
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 6
                        },
                        'content': [
                            {
                                'component': 'VTextField',
                                'props': {
                                    'model': 'delay',
                                    'label': '入库延迟（秒）',
                                    'placeholder': '60',
                                    'type': 'number',
                                    'hint': '等待媒体服务器扫描完成后再更新封面',
                                    'persistentHint': True,
                                    'variant': 'outlined',
                                    'disabled': '{{ !transfer_monitor }}'
                                }
                            }
                        ]
                    },
                ]
            },
            {
                'component': 'VRow',
                'props': {
                    'dense': True
                },
                'content': [
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 6
                        },
                        'content': [
                            {
                                'component': 'VCronField',
                                'props': {
                                    'model': 'cron',
                                    'label': '定时更新',
                                    'placeholder': '0 3 * * *',
                                    'hint': '使用Cron表达式定时更新所有封面',
                                    'persistentHint': True,
                                    'prependInnerIcon': 'mdi-clock-outline',
                                    'variant': 'outlined'
                                }
                            }
                        ]
                    },
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 6
                        },
                        'content': [
                            {
                                'component': 'VSelect',
                                'props': {
                                    'chips': True,
                                    'multiple': False,
                                    'model': 'sort_by',
                                    'label': '封面来源排序',
                                    'items': [
                                        {"title": "随机", "value": "Random"},
                                        {"title": "最新入库", "value": "DateCreated"},
                                        {"title": "最新发行", "value": "PremiereDate"}
                                    ],
                                    'hint': '选择媒体项的排序方式',
                                    'persistentHint': True,
                                    'prependInnerIcon': 'mdi-sort',
                                    'variant': 'outlined'
                                }
                            }
                        ]
                    },
                ]
            }
        ]

        # 封面风格选择卡片生成
        styles = [
            {
                "title": "单图 1",
                "value": "single_1",
                "src": single_1
            },
            {
                "title": "单图 2",
                "value": "single_2",
                "src": single_2
            },
            {
                "title": "多图 1",
                "value": "multi_1",
                "src": multi_1
            }
        ]

        style_content = []
        for style in styles:
            style_content.append(
                {
                    'component': 'VCol',
                    'props': {
                        'cols': 12,
                        'md': 4,
                    },
                    'content': [
                        {
                            "component": "VCard",
                            "props": {
                            },
                            "content": [
                                {
                                    "component": "VImg",
                                    "props": {
                                        "src": style.get("src"),
                                        "aspect-ratio": "16/9",
                                        "cover": True,
                                    }
                                },
                                {
                                    "component": "VCardTitle",
                                    "props": {
                                        "class": "text-secondary text-h6 "
                                                 "text-center bg-surface-light"
                                    },
                                    "content": [
                                        {
                                            "component": "VRadio",
                                            "props": {
                                                "color": "primary",
                                                "value": style.get("value"),
                                                "label": style.get("title"),
                                            },
                                        },
                                    ]
                                }
                            ]
                        }
                    ]
                }
            )

        # 封面风格标签页 - 样式选择和视觉设置
        style_tab = [
            {
                'component': 'VRow',
                'props': {
                    'dense': True
                },
                'content': [
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                        },
                        'content': [
                            {
                                'component': 'VRadioGroup',
                                'props': {
                                    'model': 'cover_style',
                                    'inline': True,
                                },
                                'content': [
                                    {
                                        'component': 'VRow',
                                        'content': style_content
                                    }
                                ]
                            }
                        ]
                    }
                ]
            },
            # 单图风格设置
            {
                'component': 'VRow',
                'props': {
                    'dense': True,
                    'class': 'single-style-settings mt-3'
                },
                'content': [
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                        },
                        'content': [
                            {
                                'component': 'VAlert',
                                'props': {
                                    'type': 'info',
                                    'variant': 'tonal',
                                    'text': '单图风格设置',
                                    'class': 'mb-2'
                                }
                            }
                        ]
                    },
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 4
                        },
                        'content': [
                            {
                                'component': 'VSwitch',
                                'props': {
                                    'model': 'single_use_primary',
                                    'label': '优先使用海报图',
                                    'hint': '否则优先使用背景图',
                                    'persistentHint': True
                                }
                            }
                        ]
                    },
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 4
                        },
                        'content': [
                            {
                                'component': 'VTextField',
                                'props': {
                                    'model': 'blur_size',
                                    'label': '背景模糊程度',
                                    'type': 'number',
                                    'placeholder': '50',
                                    'hint': '数值越大越模糊',
                                    'persistentHint': True,
                                    'variant': 'outlined'
                                }
                            }
                        ]
                    },
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 4
                        },
                        'content': [
                            {
                                'component': 'VTextField',
                                'props': {
                                    'model': 'color_ratio',
                                    'label': '背景颜色混合比',
                                    'type': 'number',
                                    'step': '0.1',
                                    'min': '0',
                                    'max': '1',
                                    'placeholder': '0.8',
                                    'hint': '0-1之间，控制颜色占比',
                                    'persistentHint': True,
                                    'variant': 'outlined'
                                }
                            }
                        ]
                    }
                ]
            },
            # 多图风格设置
            {
                'component': 'VRow',
                'props': {
                    'dense': True,
                    'class': 'multi-style-settings mt-3'
                },
                'content': [
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                        },
                        'content': [
                            {
                                'component': 'VAlert',
                                'props': {
                                    'type': 'info',
                                    'variant': 'tonal',
                                    'text': '多图风格设置',
                                    'class': 'mb-2'
                                }
                            }
                        ]
                    },
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 3
                        },
                        'content': [
                            {
                                'component': 'VSwitch',
                                'props': {
                                    'model': 'multi_1_use_primary',
                                    'label': '优先使用海报图',
                                    'hint': '多图模式建议开启',
                                    'persistentHint': True
                                }
                            }
                        ]
                    },
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 3
                        },
                        'content': [
                            {
                                'component': 'VSwitch',
                                'props': {
                                    'model': 'multi_1_blur',
                                    'label': '启用模糊背景',
                                    'hint': '否则使用纯色渐变',
                                    'persistentHint': True
                                }
                            }
                        ]
                    },
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 3
                        },
                        'content': [
                            {
                                'component': 'VTextField',
                                'props': {
                                    'model': 'blur_size_multi_1',
                                    'label': '背景模糊程度',
                                    'type': 'number',
                                    'placeholder': '50',
                                    'hint': '启用模糊时有效',
                                    'persistentHint': True,
                                    'variant': 'outlined',
                                    'disabled': '{{ !multi_1_blur }}'
                                }
                            }
                        ]
                    },
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 3
                        },
                        'content': [
                            {
                                'component': 'VTextField',
                                'props': {
                                    'model': 'color_ratio_multi_1',
                                    'label': '背景颜色混合比',
                                    'type': 'number',
                                    'step': '0.1',
                                    'min': '0',
                                    'max': '1',
                                    'placeholder': '0.8',
                                    'hint': '启用模糊时有效',
                                    'persistentHint': True,
                                    'variant': 'outlined',
                                    'disabled': '{{ !multi_1_blur }}'
                                }
                            }
                        ]
                    }
                ]
            },
            # 动画风格设置
            {
                'component': 'VRow',
                'props': {
                    'dense': True,
                    'class': 'animated-style-settings mt-3'
                },
                'content': [
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                        },
                        'content': [
                            {
                                'component': 'VAlert',
                                'props': {
                                    'type': 'info',
                                    'variant': 'tonal',
                                    'text': '动画风格设置',
                                    'class': 'mb-2'
                                }
                            }
                        ]
                    },
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 3
                        },
                        'content': [
                            {
                                'component': 'VTextField',
                                'props': {
                                    'model': 'animation_duration',
                                    'label': '动画时长（秒）',
                                    'type': 'number',
                                    'min': '1',
                                    'max': '60',
                                    'step': '1',
                                    'placeholder': '10',
                                    'hint': '每个循环的持续秒数',
                                    'persistentHint': True,
                                    'variant': 'outlined'
                                }
                            }
                        ]
                    },
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 3
                        },
                        'content': [
                            {
                                'component': 'VTextField',
                                'props': {
                                    'model': 'animation_fps',
                                    'label': '帧率（FPS）',
                                    'type': 'number',
                                    'min': '1',
                                    'max': '60',
                                    'step': '1',
                                    'placeholder': '15',
                                    'hint': '每秒帧数，值越大越流畅',
                                    'persistentHint': True,
                                    'variant': 'outlined'
                                }
                            }
                        ]
                    },
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 3
                        },
                        'content': [
                            {
                                'component': 'VSelect',
                                'props': {
                                    'model': 'animation_format',
                                    'label': '动画格式',
                                    'items': [
                                        {"title": "APNG", "value": "apng"},
                                        {"title": "GIF", "value": "gif"}
                                    ],
                                    'hint': '选择输出动画格式',
                                    'persistentHint': True,
                                    'variant': 'outlined'
                                }
                            }
                        ]
                    },
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 3
                        },
                        'content': [
                            {
                                'component': 'VSelect',
                                'props': {
                                    'model': 'animation_scroll',
                                    'label': '滚动方向',
                                    'items': [
                                        {"title": "向下", "value": "down"},
                                        {"title": "向上", "value": "up"},
                                        {"title": "交替", "value": "alternate"}
                                    ],
                                    'hint': '图片滚动方向',
                                    'persistentHint': True,
                                    'variant': 'outlined'
                                }
                            }
                        ]
                    },
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 6
                        },
                        'content': [
                            {
                                'component': 'VTextField',
                                'props': {
                                    'model': 'animation_resolution',
                                    'label': '动画分辨率',
                                    'placeholder': '640x360',
                                    'hint': '格式：宽度x高度，例如 1280x720',
                                    'persistentHint': True,
                                    'variant': 'outlined'
                                }
                            }
                        ]
                    },
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 6
                        },
                        'content': [
                            {
                                'component': 'VSelect',
                                'props': {
                                    'model': 'animation_reduce_colors',
                                    'label': '颜色压缩',
                                    'items': [
                                        {"title": "关闭", "value": "off"},
                                        {"title": "中等", "value": "medium"},
                                        {"title": "强力", "value": "strong"}
                                    ],
                                    'hint': '减少颜色数量以压缩文件大小',
                                    'persistentHint': True,
                                    'variant': 'outlined'
                                }
                            }
                        ]
                    }
                ]
            },
            # 合并字体设置到封面风格标签页
            {
                'component': 'VRow',
                'content': [
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                        },
                        'content': [
                            {
                                'component': 'VDivider',
                                'props': {
                                    'class': 'my-3'
                                }
                            }
                        ]
                    }
                ]
            },
            # 字体设置部分
            {
                'component': 'VRow',
                'props': {
                    'dense': True
                },
                'content': [
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                        },
                        'content': [
                            {
                                'component': 'VAlert',
                                'props': {
                                    'type': 'info',
                                    'variant': 'tonal',
                                    'text': '字体设置',
                                    'class': 'mb-2'
                                }
                            }
                        ]
                    }
                ]
            },
            # 字体下载开关
            {
                'component': 'VRow',
                'props': {
                    'dense': True
                },
                'content': [
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 6
                        },
                        'content': [
                            {
                                'component': 'VSwitch',
                                'props': {
                                    'model': 'font_download',
                                    'label': '自动下载字体',
                                    'hint': '启用后会自动从URL下载字体文件',
                                    'persistentHint': True,
                                    'color': 'primary'
                                }
                            }
                        ]
                    },
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 6
                        },
                        'content': [
                            {
                                'component': 'VAlert',
                                'props': {
                                    'type': 'warning',
                                    'variant': 'tonal',
                                    'text': '提示：本地路径优先级高于下载',
                                    'dense': True
                                }
                            }
                        ]
                    }
                ]
            },
            # 单图字体设置
            {
                'component': 'VRow',
                'props': {
                    'dense': True
                },
                'content': [
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 6
                        },
                        'content': [
                            {
                                'component': 'VTextField',
                                'props': {
                                    'model': 'zh_font_path_local',
                                    'label': '中文字体本地路径',
                                    'prependInnerIcon': 'mdi-ideogram-cjk',
                                    'placeholder': '/path/to/chinese.ttf',
                                    'hint': '优先使用本地字体文件',
                                    'persistentHint': True,
                                    'variant': 'outlined'
                                }
                            }
                        ]
                    },
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 6
                        },
                        'content': [
                            {
                                'component': 'VTextField',
                                'props': {
                                    'model': 'en_font_path_local',
                                    'label': '英文字体本地路径',
                                    'prependInnerIcon': 'mdi-format-font',
                                    'placeholder': '/path/to/english.ttf',
                                    'hint': '优先使用本地字体文件',
                                    'persistentHint': True,
                                    'variant': 'outlined'
                                }
                            }
                        ]
                    },
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 3
                        },
                        'content': [
                            {
                                'component': 'VTextField',
                                'props': {
                                    'model': 'zh_font_size',
                                    'label': '中文字体大小',
                                    'type': 'number',
                                    'step': '0.1',
                                    'placeholder': '1.0',
                                    'hint': '相对原尺寸的比例',
                                    'persistentHint': True,
                                    'variant': 'outlined'
                                }
                            }
                        ]
                    },
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 3
                        },
                        'content': [
                            {
                                'component': 'VTextField',
                                'props': {
                                    'model': 'en_font_size',
                                    'label': '英文字体大小',
                                    'type': 'number',
                                    'step': '0.1',
                                    'placeholder': '1.0',
                                    'hint': '相对原尺寸的比例',
                                    'persistentHint': True,
                                    'variant': 'outlined'
                                }
                            }
                        ]
                    }
                ]
            },
            # 多图字体设置
            {
                'component': 'VRow',
                'props': {
                    'dense': True,
                    'class': 'mt-2'
                },
                'content': [
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 6
                        },
                        'content': [
                            {
                                'component': 'VSwitch',
                                'props': {
                                    'model': 'multi_1_use_main_font',
                                    'label': '多图使用单图字体',
                                    'hint': '勾选后忽略多图专用字体',
                                    'persistentHint': True
                                }
                            }
                        ]
                    }
                ]
            }
        ]

        # 媒体库管理标签页 - 整合媒体库配置和用户筛选
        library_tab = [
            {
                'component': 'VRow',
                'props': {
                    'dense': True
                },
                'content': [
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                        },
                        'content': [
                            {
                                'component': 'VSelect',
                                'props': {
                                    'multiple': True,
                                    'chips': True,
                                    'clearable': True,
                                    'model': 'exclude_libraries',
                                    'label': '忽略媒体库',
                                    'items': [
                                        {"title": config['name'], "value": config['value']}
                                            for config in self._all_libraries
                                    ],
                                    'hint': '选择不需要自动更新封面的媒体库',
                                    'persistentHint': True,
                                    'prependInnerIcon': 'mdi-folder-off-outline',
                                    'variant': 'outlined'
                                }
                            }
                        ]
                    },
                ]
            },
            {
                'component': 'VRow',
                'props': {
                    'dense': True,
                    'class': 'mt-3'
                },
                'content': [
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                        },
                        'content': [
                            {
                                'component': 'VSelect',
                                'props': {
                                    'multiple': True,
                                    'chips': True,
                                    'clearable': True,
                                    'model': 'selected_libraries',
                                    'label': '库白名单',
                                    'items': [
                                        {"title": config['name'], "value": config['value']}
                                            for config in self._all_libraries
                                    ],
                                    'hint': '不选则处理所有媒体库，选择后仅处理指定媒体库',
                                    'persistentHint': True,
                                    'prependInnerIcon': 'mdi-folder-check-outline',
                                    'variant': 'outlined'
                                }
                            }
                        ]
                    },
                ]
            },
            {
                'component': 'VRow',
                'props': {
                    'dense': True,
                    'class': 'mt-3'
                },
                'content': [
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                        },
                        'content': [
                            {
                                'component': 'VAlert',
                                'props': {
                                    'type': 'info',
                                    'variant': 'tonal',
                                    'text': '合集源库黑名单：排除来自指定库的合集',
                                    'class': 'mb-2'
                                }
                            }
                        ]
                    },
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                        },
                        'content': [
                            {
                                'component': 'VSelect',
                                'props': {
                                    'multiple': True,
                                    'chips': True,
                                    'clearable': True,
                                    'model': 'exclude_boxsets',
                                    'label': '排除来源库',
                                    'items': [
                                        {"title": config['name'], "value": config['value']}
                                            for config in self._all_libraries
                                    ],
                                    'hint': '选择后，来自这些库的合集将被排除',
                                    'persistentHint': True,
                                    'prependInnerIcon': 'mdi-folder-remove-outline',
                                    'variant': 'outlined'
                                }
                            }
                        ]
                    },
                ]
            },
            {
                'component': 'VRow',
                'props': {
                    'dense': True,
                    'class': 'mt-3'
                },
                'content': [
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                        },
                        'content': [
                            {
                                'component': 'VDivider',
                                'props': {
                                    'class': 'my-4'
                                }
                            }
                        ]
                    }
                ]
            },
            {
                'component': 'VRow',
                'content': [
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                        },
                        'content': [
                            {
                                'component': 'VAlert',
                                'props': {
                                    'type': 'info',
                                    'variant': 'tonal',
                                    'text': '使用JSON格式配置媒体库标题。'
                                           '格式："库名": ["中文标题", "英文标题"]',
                                    'class': 'mb-2'
                                }
                            }
                        ]
                    },
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12
                        },
                        'content': [
                            {
                                'component': 'VAceEditor',
                                'props': {
                                    'modelvalue': 'title_config',
                                    'lang': 'json',
                                    'theme': 'monokai',
                                    'style': 'height: 15rem',
                                    'label': '媒体库标题配置',
                                    'placeholder': '''{
  "华语电影": ["华语电影", "Chinese Movies"],
  "欧美电影": ["欧美电影", "Western Movies"],
  "电视剧": ["电视剧", "TV Series"],
  "动漫": ["动漫", "Anime"],
  "纪录片": ["纪录片", "Documentary"]
}'''
                                }
                            }
                        ]
                    }
                ]
            },
            {
                'component': 'VRow',
                'props': {
                    'dense': True,
                    'class': 'mt-3'
                },
                'content': [
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                        },
                        'content': [
                            {
                                'component': 'VDivider',
                                'props': {
                                    'class': 'my-4'
                                }
                            }
                        ]
                    }
                ]
            },
            {
                'component': 'VRow',
                'content': [
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                        },
                        'content': [
                            {
                                'component': 'VAlert',
                                'props': {
                                    'type': 'info',
                                    'variant': 'tonal',
                                    'text': '用户筛选功能：选择特定用户后，合集将只显示该用户创建的内容',
                                    'class': 'mb-2'
                                }
                            }
                        ]
                    },
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                        },
                        'content': [
                            {
                                'component': 'VSelect',
                                'props': {
                                    'multiple': True,
                                    'chips': True,
                                    'clearable': True,
                                    'model': 'selected_users',
                                    'label': '合集用户筛选',
                                    'items': self._all_users,
                                    'hint': '不选择则显示所有用户的合集（先选择媒体服务器）',
                                    'persistentHint': True,
                                    'prependInnerIcon': 'mdi-account-filter',
                                    'variant': 'outlined'
                                }
                            }
                        ]
                    },
                ]
            }
        ]


        # 字体设置标签页 - 整合单图和多图字体
        font_tab = [
            # 通用字体设置提示
            {
                'component': 'VRow',
                'content': [
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                        },
                        'content': [
                            {
                                'component': 'VAlert',
                                'props': {
                                    'type': 'info',
                                    'variant': 'tonal',
                                    'text': '字体设置：优先使用本地路径，'
                                           '如未设置则从URL下载',
                                    'class': 'mb-4'
                                }
                            }
                        ]
                    },
                ]
            },
            # 单图字体设置部分
            {
                'component': 'VRow',
                'content': [
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                        },
                        'content': [
                            {
                                'component': 'VAlert',
                                'props': {
                                    'type': 'info',
                                    'variant': 'tonal',
                                    'text': '单图风格字体设置',
                                    'class': 'mb-2'
                                }
                            }
                        ]
                    }
                ]
            },
            {
                'component': 'VRow',
                'content': [
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 6
                        },
                        'content': [
                            {
                                'component': 'VTextField',
                                'props': {
                                    'model': 'zh_font_path_local',
                                    'label': '中文字体本地路径',
                                    'prependInnerIcon': 'mdi-ideogram-cjk',
                                    'placeholder': '/path/to/chinese.ttf',
                                    'hint': '优先使用本地字体文件',
                                    'persistentHint': True
                                }
                            }
                        ]
                    },
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 6
                        },
                        'content': [
                            {
                                'component': 'VTextField',
                                'props': {
                                    'model': 'en_font_path_local',
                                    'label': '英文字体本地路径',
                                    'prependInnerIcon': 'mdi-format-font',
                                    'placeholder': '/path/to/english.ttf',
                                    'hint': '优先使用本地字体文件',
                                    'persistentHint': True
                                }
                            }
                        ]
                    },
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 6
                        },
                        'content': [
                            {
                                'component': 'VTextField',
                                'props': {
                                    'model': 'zh_font_url',
                                    'label': '中文字体下载链接',
                                    'prependInnerIcon': 'mdi-link',
                                    'placeholder': 'https://example.com/font.ttf',
                                    'hint': '本地路径未设置时使用',
                                    'persistentHint': True
                                }
                            }
                        ]
                    },
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 6
                        },
                        'content': [
                            {
                                'component': 'VTextField',
                                'props': {
                                    'model': 'en_font_url',
                                    'label': '英文字体下载链接',
                                    'prependInnerIcon': 'mdi-link',
                                    'placeholder': 'https://example.com/font.ttf',
                                    'hint': '本地路径未设置时使用',
                                    'persistentHint': True
                                }
                            }
                        ]
                    },
                ]
            },
            {
                'component': 'VRow',
                'content': [
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                        },
                        'content': [
                            {
                                'component': 'VDivider',
                                'props': {
                                    'class': 'my-4'
                                }
                            }
                        ]
                    }
                ]
            },
            {
                'component': 'VRow',
                'content': [
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 4
                        },
                        'content': [
                            {
                                'component': 'VTextField',
                                'props': {
                                    'model': 'zh_font_size',
                                    'label': '中文字体大小',
                                    'prependInnerIcon': 'mdi-format-size',
                                    'type': 'number',
                                    'step': '0.1',
                                    'placeholder': '1.0',
                                    'hint': '相对原尺寸的比例',
                                    'persistentHint': True
                                }
                            }
                        ]
                    },
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 4
                        },
                        'content': [
                            {
                                'component': 'VTextField',
                                'props': {
                                    'model': 'en_font_size',
                                    'label': '英文字体大小',
                                    'prependInnerIcon': 'mdi-format-size',
                                    'type': 'number',
                                    'step': '0.1',
                                    'placeholder': '1.0',
                                    'hint': '相对原尺寸的比例',
                                    'persistentHint': True
                                }
                            }
                        ]
                    },
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 4
                        },
                        'content': [
                            {
                                'component': 'VSwitch',
                                'props': {
                                    'model': 'single_use_primary',
                                    'label': '优先使用海报图',
                                    'hint': '否则优先使用背景图',
                                    "persistent-hint": True,
                                }
                            }
                        ]
                    },
                ]
            },
            {
                'component': 'VRow',
                'content': [
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 6
                        },
                        'content': [
                            {
                                'component': 'VTextField',
                                'props': {
                                    'model': 'blur_size',
                                    'label': '背景模糊程度',
                                    'prependInnerIcon': 'mdi-blur',
                                    'type': 'number',
                                    'placeholder': '50',
                                    'hint': '数值越大越模糊',
                                    'persistentHint': True
                                }
                            }
                        ]
                    },
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 6
                        },
                        'content': [
                            {
                                'component': 'VTextField',
                                'props': {
                                    'model': 'color_ratio',
                                    'label': '背景颜色混合比',
                                    'prependInnerIcon': 'mdi-format-color-fill',
                                    'type': 'number',
                                    'step': '0.1',
                                    'min': '0',
                                    'max': '1',
                                    'placeholder': '0.8',
                                    'hint': '0-1之间，控制颜色占比',
                                    'persistentHint': True
                                }
                            }
                        ]
                    },
                ]
            },
            # 分隔线
            {
                'component': 'VRow',
                'content': [
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                        },
                        'content': [
                            {
                                'component': 'VDivider',
                                'props': {
                                    'class': 'my-4'
                                }
                            }
                        ]
                    }
                ]
            },
            # 多图字体设置部分
            {
                'component': 'VRow',
                'content': [
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                        },
                        'content': [
                            {
                                'component': 'VAlert',
                                'props': {
                                    'type': 'info',
                                    'variant': 'tonal',
                                    'text': '多图风格字体设置',
                                    'class': 'mb-2'
                                }
                            }
                        ]
                    }
                ]
            },
            {
                'component': 'VRow',
                'content': [
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 6
                        },
                        'content': [
                            {
                                'component': 'VSwitch',
                                'props': {
                                    'model': 'multi_1_use_main_font',
                                    'label': '使用单图字体',
                                    'hint': '勾选后忽略多图专用字体',
                                    "persistent-hint": True,
                                }
                            }
                        ]
                    },
                ]
            },
            {
                'component': 'VRow',
                'content': [
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 6
                        },
                        'content': [
                            {
                                'component': 'VTextField',
                                'props': {
                                    'model': 'zh_font_path_multi_1_local',
                                    'label': '中文字体本地路径',
                                    'prependInnerIcon': 'mdi-ideogram-cjk',
                                    'placeholder': '/path/to/chinese.ttf',
                                    'hint': '多图风格专用字体',
                                    'persistentHint': True,
                                    'disabled': '{{ multi_1_use_main_font }}'
                                }
                            }
                        ]
                    },
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 6
                        },
                        'content': [
                            {
                                'component': 'VTextField',
                                'props': {
                                    'model': 'en_font_path_multi_1_local',
                                    'label': '英文字体本地路径',
                                    'prependInnerIcon': 'mdi-format-font',
                                    'placeholder': '/path/to/english.ttf',
                                    'hint': '多图风格专用字体',
                                    'persistentHint': True,
                                    'disabled': '{{ multi_1_use_main_font }}'
                                }
                            }
                        ]
                    },
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 6
                        },
                        'content': [
                            {
                                'component': 'VTextField',
                                'props': {
                                    'model': 'zh_font_url_multi_1',
                                    'label': '中文字体下载链接',
                                    'prependInnerIcon': 'mdi-link',
                                    'placeholder': 'https://example.com/font.ttf',
                                    'hint': '本地路径未设置时使用',
                                    'persistentHint': True,
                                    'disabled': '{{ multi_1_use_main_font }}'
                                }
                            }
                        ]
                    },
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 6
                        },
                        'content': [
                            {
                                'component': 'VTextField',
                                'props': {
                                    'model': 'en_font_url_multi_1',
                                    'label': '英文字体下载链接',
                                    'prependInnerIcon': 'mdi-link',
                                    'placeholder': 'https://example.com/',
                                    'hint': '本地路径未设置时使用',
                                    'persistentHint': True,
                                    'disabled': '{{ multi_1_use_main_font }}'
                                }
                            }
                        ]
                    },
                ]
            },
            {
                'component': 'VRow',
                'content': [
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 6
                        },
                        'content': [
                            {
                                'component': 'VTextField',
                                'props': {
                                    'model': 'zh_font_size_multi_1',
                                    'label': '中文字体大小',
                                    'prependInnerIcon': 'mdi-format-size',
                                    'type': 'number',
                                    'step': '0.1',
                                    'placeholder': '1.0',
                                    'hint': '相对原尺寸的比例',
                                    'persistentHint': True
                                }
                            }
                        ]
                    },
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 6
                        },
                        'content': [
                            {
                                'component': 'VTextField',
                                'props': {
                                    'model': 'en_font_size_multi_1',
                                    'label': '英文字体大小',
                                    'prependInnerIcon': 'mdi-format-size',
                                    'type': 'number',
                                    'step': '0.1',
                                    'placeholder': '1.0',
                                    'hint': '相对原尺寸的比例',
                                    'persistentHint': True
                                }
                            }
                        ]
                    },
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 6
                        },
                        'content': [
                            {
                                'component': 'VTextField',
                                'props': {
                                    'model': 'blur_size_multi_1',
                                    'label': '背景模糊程度',
                                    'prependInnerIcon': 'mdi-blur',
                                    'type': 'number',
                                    'placeholder': '50',
                                    'hint': '启用模糊时有效',
                                    'persistentHint': True,
                                    'disabled': '{{ !multi_1_blur }}'
                                }
                            }
                        ]
                    },
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 6
                        },
                        'content': [
                            {
                                'component': 'VTextField',
                                'props': {
                                    'model': 'color_ratio_multi_1',
                                    'label': '背景颜色混合比',
                                    'prependInnerIcon': 'mdi-format-color-fill',
                                    'type': 'number',
                                    'step': '0.1',
                                    'min': '0',
                                    'max': '1',
                                    'placeholder': '0.8',
                                    'hint': '启用模糊时有效',
                                    'persistentHint': True,
                                    'disabled': '{{ !multi_1_blur }}'
                                }
                            }
                        ]
                    },
                ]
            },
        ]

        # 高级设置标签页
        advanced_tab = [
            {
                'component': 'VRow',
                'props': {
                    'dense': True
                },
                'content': [
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                        },
                        'content': [
                            {
                                'component': 'VAlert',
                                'props': {
                                    'type': 'info',
                                    'variant': 'tonal',
                                    'text': '自定义图片：将图片存于与媒体库同名的'
                                           '子目录下。多图模式需要1-9.jpg',
                                    'class': 'mb-2'
                                }
                            }
                        ]
                    },
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 6
                        },
                        'content': [
                            {
                                'component': 'VTextField',
                                'props': {
                                    'model': 'covers_input',
                                    'label': '自定义图片目录',
                                    'prependInnerIcon': 'mdi-folder-image',
                                    'hint': '使用自定义图片生成封面',
                                    'persistentHint': True,
                                    'placeholder': '/mnt/custom_images',
                                    'variant': 'outlined'
                                }
                            }
                        ]
                    },
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 6
                        },
                        'content': [
                            {
                                'component': 'VTextField',
                                'props': {
                                    'model': 'covers_output',
                                    'label': '封面另存目录',
                                    'prependInnerIcon': 'mdi-content-save-all',
                                    'hint': '生成的封面另存一份',
                                    'persistentHint': True,
                                    'placeholder': '/mnt/covers_backup',
                                    'variant': 'outlined'
                                }
                            }
                        ]
                    }
                ]
            }
        ]

        # 返回完整的表单结构
        return [
            {
                "component": "VTabs",
                "props": {
                    "model": "tab",
                    'style': {
                        'margin-top': '8px',
                        'margin-bottom': '16px'
                    },
                    "fixed-tabs": True,
                    "color": "primary"
                },
                "content": [
                    {
                        "component": "VTab",
                        "props": {"value": "basic"},
                        "content": [
                            {"component": "VIcon",
                             "props": {"icon": "mdi-cog", "start": True}},
                            {"component": "span", "text": "基础设置"},
                        ],
                    },
                    {
                        "component": "VTab",
                        "props": {"value": "style"},
                        "content": [
                            {"component": "VIcon",
                             "props": {"icon": "mdi-palette-swatch", "start": True}},
                            {"component": "span", "text": "封面风格"},
                        ],
                    },
                    {
                        "component": "VTab",
                        "props": {"value": "library"},
                        "content": [
                            {"component": "VIcon",
                             "props": {"icon": "mdi-folder-cog", "start": True}},
                            {"component": "span", "text": "媒体库配置"},
                        ],
                    },
                    {
                        "component": "VTab",
                        "props": {"value": "advanced"},
                        "content": [
                            {"component": "VIcon",
                             "props": {"icon": "mdi-cogs", "start": True}},
                            {"component": "span", "text": "高级设置"},
                        ],
                    },
                ]
            },
            {
                "component": "VWindow",
                "props": {"model": "tab"},
                "content": [
                    {
                        "component": "VWindowItem",
                        "props": {"value": "basic"},
                        "content": [
                            {"component": "VCardText", "content": basic_tab}
                        ],
                    },
                    {
                        "component": "VWindowItem",
                        "props": {"value": "style"},
                        "content": [
                            {"component": "VCardText", "content": style_tab}
                        ],
                    },
                    {
                        "component": "VWindowItem",
                        "props": {"value": "library"},
                        "content": [
                            {"component": "VCardText", "content": library_tab}
                        ],
                    },
                    {
                        "component": "VWindowItem",
                        "props": {"value": "advanced"},
                        "content": [
                            {"component": "VCardText", "content": advanced_tab}
                        ],
                    },
                ],
            }
        ], {
            "enabled": False,
            "onlyonce": False,
            "transfer_monitor": True,
            "cron": "",
            "delay": 60,
            "selected_servers": [],
            "exclude_libraries": [],
            "selected_libraries": [],
            "exclude_boxsets": [],
            "sort_by": "Random",
            "title_config": '''{
  "示例媒体库": ["中文标题", "English Title"]
}''',
            "tab": "basic",
            "cover_style": "single_1",
            "multi_1_blur": False,
            "multi_1_use_main_font": False,
            "zh_font_size": 1,
            "en_font_size": 1,
            "zh_font_size_multi_1": 1,
            "en_font_size_multi_1": 1,
            "blur_size": 50,
            "blur_size_multi_1": 50,
            "color_ratio": 0.8,
            "color_ratio_multi_1": 0.8,
            "single_use_primary": False,
            "multi_1_use_primary": True,
            "selected_users": [],  # 默认不筛选用户
            "font_download": True,  # 默认启用字体下载
            "animation_duration": 10,
            "animation_fps": 15,
            "animation_format": "apng",
            "animation_scroll": "down",
            "animation_resolution": "640x360",
            "animation_reduce_colors": "medium"
        }

    def get_page(self) -> List[dict]:
        pass

    @eventmanager.register(EventType.TransferComplete)
    def update_library_cover(self, event: Event):
        """
        媒体整理完成后，更新所在库封面
        """
        if not self._enabled:
            return
        if not self._transfer_monitor:
            return
        self.__get_fonts()     # Event data
        # Event data
        mediainfo: MediaInfo = event.event_data.get("mediainfo")
        # logger.info(f"监控到的媒体信息：{mediainfo}")
        if not mediainfo:
            return
            
        # Delay
        if self._delay:
            logger.info(f"延迟 {self._delay} 秒后开始更新封面")
            time.sleep(int(self._delay))
            
        # Query the item in media server
        existsinfo = self.mschain.media_exists(mediainfo=mediainfo)
        if not existsinfo or not existsinfo.itemid:
            logger.warning(f"{mediainfo.title_year} 不存在媒体库中，可能服务器还未扫描完成，建议设置合适的延迟时间")
            return
        
        # Get item details including backdrop
        iteminfo = self.mschain.iteminfo(server=existsinfo.server, item_id=existsinfo.itemid)
        # logger.info(f"获取到媒体项 {mediainfo.title_year} 详情：{iteminfo}")
        if not iteminfo:
            logger.warning(f"获取 {mediainfo.title_year} 详情失败")
            return
            
        # Try to get library ID
        library_id = None
        library = {}
        service = self._servers.get(existsinfo.server)
        if service:
            libraries = self.__get_server_libraries(service)
        if libraries and not library_id:
            library = next(
                (library
                 for library in libraries if library.get('Locations', []) 
                 and any(iteminfo.path.startswith(path) for path in library.get('Locations', []))),
                None
            )
        
        if not library:
            logger.warning(f"找不到 {mediainfo.title_year} 所在媒体库")
            return
        if service.type == 'emby':
            library_id = library.get("Id")
        else:
            library_id = library.get("ItemId")
        if f"{existsinfo.server}-{library_id}" in self._exclude_libraries:
            logger.info(f"{existsinfo.server}：{library['Name']} 已忽略，跳过更新封面")
            return
        # self.clean_cover_history(save=True)
        old_history = self.get_data('cover_history') or []
        # 新增去重判断逻辑
        latest_item = max(
            (item for item in old_history if str(item.get("library_id")) == str(library_id)),
            key=lambda x: x["timestamp"],
            default=None
        )
        if latest_item and str(latest_item.get("item_id")) == str(existsinfo.itemid):
            logger.info(f"媒体 {mediainfo.title_year} 在库中是最新记录，不更新封面图")
            return
        new_history = self.update_cover_history(
            server=existsinfo.server, 
            library_id=library_id, 
            item_id=existsinfo.itemid
        )
        # logger.info(f"最新数据： {new_history}")
        self._monitor_sort = 'DateCreated'
        if self._cover_style.startswith('single'):
            if self.__update_library(service, library):
                self._monitor_sort = ''
                logger.info(f"媒体库 {existsinfo.server}：{library['Name']} 封面更新成功")
        elif self._cover_style.startswith('multi'):
            if self.__update_library(service, library):
                self._monitor_sort = ''
                logger.info(f"媒体库 {existsinfo.server}：{library['Name']} 封面更新成功")
    
    def __update_all_libraries(self):
        """
        更新所有媒体库封面
        """
        if not self._enabled:
            return
        # 所有媒体服务器
        if not self._servers:
            return
        self.__get_fonts()  
        for server, service in self._servers.items():
            # 扫描所有媒体库
            logger.info(f"当前服务器 {server}")
            cover_style = {
                "single_1": "单图 1",
                "single_2": "单图 2",
                "multi_1": "多图 1"
            }[self._cover_style]
            logger.info(f"当前风格 {cover_style}")
            # 获取媒体库列表
            libraries = self.__get_server_libraries(service)
            if not libraries:
                logger.warning(f"服务器 {server} 的媒体库列表获取失败")
                continue
            for library in libraries:
                if self._event.is_set():
                    logger.info("媒体库封面更新服务停止")
                    return
                if service.type == 'emby':
                    library_id = library.get("Id")
                else:
                    library_id = library.get("ItemId")
                if f"{server}-{library_id}" in self._exclude_libraries:
                    logger.info(f"媒体库 {server}：{library['Name']} 已忽略，跳过更新封面")
                    continue
                if self.__update_library(service, library):
                    logger.info(f"媒体库 {server}：{library['Name']} 封面更新成功")
                else:
                    logger.warning(f"媒体库 {server}：{library['Name']} 封面更新失败")
        logger.info("所有媒体库封面更新完成")
                 

    def __update_library(self, service, library):
        library_name = library['Name']
        logger.info(f"媒体库 {service.name}：{library_name} 开始准备更新封面")

        # 新增：检查库白名单
        if self._selected_libraries:
            # 获取库ID（兼容Emby/Jellyfin）
            if service.type == 'emby':
                lib_id = library.get('Id')
            else:
                lib_id = library.get('ItemId')

            if lib_id:
                lib_key = f"{service.name}-{lib_id}"
                if lib_key not in self._selected_libraries:
                    logger.info(f"库 {library_name} 不在白名单中，跳过")
                    return False

        # 自定义图像路径
        image_path = self.__check_custom_image(library_name)
        # 从配置获取标题
        title = self.__get_library_title_from_config(library_name)
        if image_path:
            logger.info(f"媒体库 {service.name}：{library_name} 从自定义路径获取封面")
            image_data = self.__generate_image_from_path(service.name, library_name, title, image_path[0])
        else:
            image_data = self.__generate_from_server(service, library, title)

        if image_data:
            return self.__set_library_image(service, library, image_data)

    def __check_custom_image(self, library_name):
        if not self._covers_input:
            return None

        library_dir = os.path.join(self._covers_input, library_name)
        if not os.path.isdir(library_dir):
            return None

        images = sorted([
            os.path.join(library_dir, f)
            for f in os.listdir(library_dir)
            if f.lower().endswith((".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"))
        ])
        
        return images if images else None  # 或改为 return images if images else False

    def __generate_image_from_path(self, server, library_name, title, image_path=None):
        logger.info(f"媒体库 {server}：{library_name} 正在生成封面图...")
        font_path = (str(self._zh_font_path), str(self._en_font_path))

        zh_font_size = self._zh_font_size or 1
        en_font_size = self._en_font_size or 1
        blur_size = self._blur_size or 50
        color_ratio = self._color_ratio or 0.8
        zh_font_size_multi_1 = self._zh_font_size_multi_1 or 1
        en_font_size_multi_1 = self._en_font_size_multi_1 or 1
        blur_size_multi_1 = self._blur_size_multi_1 or 50
        color_ratio_multi_1 = self._color_ratio_multi_1 or 0.8
        font_size = (float(zh_font_size), float(en_font_size))

        if self._cover_style == 'single_1':
            image_data = create_style_single_1(image_path, title, font_path, 
                                               font_size=font_size, 
                                               blur_size=blur_size, 
                                               color_ratio=color_ratio)
        elif self._cover_style == 'single_2':
            image_data = create_style_single_2(image_path, title, font_path, 
                                               font_size=font_size, 
                                               blur_size=blur_size, 
                                               color_ratio=color_ratio)
        elif self._cover_style == 'multi_1':
            zh_font_path = self._zh_font_path if self._multi_1_use_main_font else self._zh_font_path_multi_1
            en_font_path = self._en_font_path if self._multi_1_use_main_font else self._en_font_path_multi_1
            font_path = (zh_font_path, en_font_path)
            font_size = (float(zh_font_size_multi_1), float(en_font_size_multi_1))
            if image_path:
                library_dir = Path(self._covers_input) / library_name
            else:
                library_dir = Path(self._covers_path) / library_name
            if self.prepare_library_images(library_dir):
                image_data = create_style_multi_1(library_dir, title, font_path,
                                                  font_size=font_size,
                                                  is_blur=self._multi_1_blur,
                                                  blur_size=blur_size_multi_1,
                                                  color_ratio=color_ratio_multi_1)
        elif self._cover_style == 'animated_1':
            if image_path:
                library_dir = Path(self._covers_input) / library_name
            else:
                library_dir = Path(self._covers_path) / library_name
            if self.prepare_library_images(library_dir):
                image_data = create_style_animated_1(library_dir, title, font_path,
                                                     font_size=font_size,
                                                     is_blur=self._multi_1_blur,
                                                     blur_size=blur_size_multi_1,
                                                     color_ratio=color_ratio_multi_1,
                                                     animation_duration=self._animation_duration,
                                                     animation_fps=self._animation_fps,
                                                     animation_format=self._animation_format,
                                                     animation_resolution=self._animation_resolution,
                                                     animation_reduce_colors=self._animation_reduce_colors)
        elif self._cover_style == 'animated_2':
            if image_path:
                library_dir = Path(self._covers_input) / library_name
            else:
                library_dir = Path(self._covers_path) / library_name
            if self.prepare_library_images(library_dir):
                image_data = create_style_animated_2(library_dir, title, font_path,
                                                     font_size=font_size,
                                                     is_blur=self._multi_1_blur,
                                                     blur_size=blur_size_multi_1,
                                                     color_ratio=color_ratio_multi_1,
                                                     animation_duration=self._animation_duration,
                                                     animation_fps=self._animation_fps,
                                                     animation_format=self._animation_format,
                                                     animation_resolution=self._animation_resolution,
                                                     animation_reduce_colors=self._animation_reduce_colors)
        elif self._cover_style == 'animated_3':
            if image_path:
                library_dir = Path(self._covers_input) / library_name
            else:
                library_dir = Path(self._covers_path) / library_name
            if self.prepare_library_images(library_dir):
                image_data = create_style_animated_3(library_dir, title, font_path,
                                                     font_size=font_size,
                                                     is_blur=self._multi_1_blur,
                                                     blur_size=blur_size_multi_1,
                                                     color_ratio=color_ratio_multi_1,
                                                     animation_duration=self._animation_duration,
                                                     animation_scroll=self._animation_scroll,
                                                     animation_fps=self._animation_fps,
                                                     animation_format=self._animation_format,
                                                     animation_resolution=self._animation_resolution,
                                                     animation_reduce_colors=self._animation_reduce_colors)
        elif self._cover_style == 'animated_4':
            if image_path:
                library_dir = Path(self._covers_input) / library_name
            else:
                library_dir = Path(self._covers_path) / library_name
            if self.prepare_library_images(library_dir):
                image_data = create_style_animated_4(library_dir, title, font_path,
                                                     font_size=font_size,
                                                     is_blur=self._multi_1_blur,
                                                     blur_size=blur_size_multi_1,
                                                     color_ratio=color_ratio_multi_1,
                                                     animation_duration=self._animation_duration,
                                                     animation_fps=self._animation_fps,
                                                     animation_format=self._animation_format,
                                                     animation_resolution=self._animation_resolution,
                                                     animation_reduce_colors=self._animation_reduce_colors)
        return image_data
    
    def __generate_from_server(self, service, library, title):

        logger.info(f"媒体库 {service.name}：{library['Name']} 开始筛选媒体项")
        required_items = 1 if self._cover_style.startswith('single') else 9
        
        # 获取项目集合
        items = []
        offset = 0
        batch_size = 20  # 每次获取的项目数量
        max_attempts = 5  # 最大尝试次数，防止无限循环
        
        library_type = library.get('CollectionType')
        if service.type == 'emby':
            library_id = library.get("Id")
        else:
            library_id = library.get("ItemId")
        parent_id = library_id
        
        # 获取当前服务器的选中用户ID（用于非合集库的情况）
        selected_user_ids = []
        if self._selected_users and library_type not in ["boxsets", "playlists"]:
            server_name = service.name
            # 从 selected_users 中提取当前服务器的用户ID
            for user_str in self._selected_users:
                if user_str.startswith(f"{server_name}-"):
                    user_id = user_str.replace(f"{server_name}-", "")
                    selected_user_ids.append(user_id)
        
        # 处理合集类型的特殊情况
        if library_type == "boxsets":
            return self.__handle_boxset_library(service, library, title)
        elif library_type == "playlists":
            return self.__handle_playlist_library(service, library, title)
        elif library_type == "music":
            include_types = 'MusicAlbum,Audio'
        else:
            date_created = 'Movie,Episode' if self._cover_style and self._cover_style.startswith('single') else 'Movie,Series'
            include_types = {
                "PremiereDate": "Movie,Series",
                "DateCreated": date_created,
                "Random": "Movie,Series"
            }[self._sort_by if self._sort_by else "Random"]
        for attempt in range(max_attempts):
            batch_items = self.__get_items_batch(service, parent_id,
                                              offset=offset, limit=batch_size,
                                              include_types=include_types)
            
            if not batch_items:
                break  # 没有更多项目可获取
                
            # 筛选有效项目（有所需图片的项目）
            valid_items = self.__filter_valid_items(batch_items)
            items.extend(valid_items)
            
            # 如果已经有足够的有效项目，则停止获取
            if len(items) >= required_items:
                break
                
            offset += batch_size
        
        # 使用获取到的有效项目更新封面
        if len(items) > 0:
            if self._cover_style.startswith('single'):
                return self.__update_single_image(service, library, title, items[0])
            else:
                return self.__update_grid_image(service, library, title, items[:9])
        else:
            print(f"媒体库 {service.name}：{library['Name']} 无法找到有效的图片项目")
            return False
        
    def __handle_boxset_library(self, service, library, title):

        include_types = 'BoxSet,Movie'
        if service.type == 'emby':
            library_id = library.get("Id")
        else:
            library_id = library.get("ItemId")
        parent_id = library_id
        
        # 获取当前服务器的选中用户ID
        selected_user_ids = []
        if self._selected_users:
            server_name = service.name
            # 从 selected_users 中提取当前服务器的用户ID
            for user_str in self._selected_users:
                if user_str.startswith(f"{server_name}-"):
                    user_id = user_str.replace(f"{server_name}-", "")
                    selected_user_ids.append(user_id)
        
        boxsets = self.__get_items_batch(service, parent_id,
                                      include_types=include_types,
                                      user_ids=selected_user_ids)
        
        required_items = 1 if self._cover_style.startswith('single') else 9
        valid_items = []
        
        # 首先检查BoxSet本身是否有合适的图片
        valid_boxsets = self.__filter_valid_items(boxsets)
        valid_items.extend(valid_boxsets)
        
        # 如果BoxSet本身没有足够的图片，则获取其中的电影
        if len(valid_items) < required_items:
            for boxset in boxsets:
                if len(valid_items) >= required_items:
                    break

                # 新增：检查合集来源库是否在黑名单中
                source_library_id = boxset.get('ParentId')
                if source_library_id:
                    boxset_key = f"{service.name}-{source_library_id}"
                    if boxset_key in self._exclude_boxsets:
                        logger.info(f"合集 {boxset.get('Name')} 来自黑名单库，跳过")
                        continue

                # 获取此BoxSet中的电影
                movies = self.__get_items_batch(service,
                                             parent_id=boxset['Id'],
                                             include_types=include_types,
                                             user_ids=selected_user_ids)
                
                valid_movies = self.__filter_valid_items(movies)
                valid_items.extend(valid_movies)
                
                if len(valid_items) >= required_items:
                    break
        
        # 使用获取到的有效项目更新封面
        if len(valid_items) > 0:
            if self._cover_style.startswith('single'):
                return self.__update_single_image(service, library, title, valid_items[0])
            else:
                return self.__update_grid_image(service, library, title, valid_items[:9])
        else:
            print(f"媒体库 {service.name}：{library['Name']} 无法找到有效的图片项目")
            return False
        
    def __handle_playlist_library(self, service, library, title):
        """
        播放列表图片获取
        """
        include_types = 'Playlist,Movie,Series,Episode,Audio'
        if service.type == 'emby':
            library_id = library.get("Id")
        else:
            library_id = library.get("ItemId")
        parent_id = library_id
        
        # 获取当前服务器的选中用户ID
        selected_user_ids = []
        if self._selected_users:
            server_name = service.name
            # 从 selected_users 中提取当前服务器的用户ID
            for user_str in self._selected_users:
                if user_str.startswith(f"{server_name}-"):
                    user_id = user_str.replace(f"{server_name}-", "")
                    selected_user_ids.append(user_id)
        
        playlists = self.__get_items_batch(service, parent_id,
                                      include_types=include_types,
                                      user_ids=selected_user_ids)
        
        required_items = 1 if self._cover_style.startswith('single') else 9
        valid_items = []
        
        # 首先检查 playlist 本身是否有合适的图片
        valid_playlists = self.__filter_valid_items(playlists)
        valid_items.extend(valid_playlists)
        
        # 如果 playlist 本身没有足够的图片，则获取其中的电影
        if len(valid_items) < required_items:
            for playlist in playlists:
                if len(valid_items) >= required_items:
                    break
                    
                # 获取此 playlist 中的电影
                movies = self.__get_items_batch(service,
                                             parent_id=playlist['Id'],
                                             include_types=include_types,
                                             user_ids=selected_user_ids)
                
                valid_movies = self.__filter_valid_items(movies)
                valid_items.extend(valid_movies)
                
                if len(valid_items) >= required_items:
                    break
        
        # 使用获取到的有效项目更新封面
        if len(valid_items) > 0:
            if self._cover_style.startswith('single'):
                return self.__update_single_image(service, library, title, valid_items[0])
            else:
                return self.__update_grid_image(service, library, title, valid_items[:9])
        else:
            print(f"警告: 无法为播放列表 {service.name}：{library['Name']} 找到有效的图片项目")
            return False
        
    def __get_items_batch(self, service, parent_id, offset=0, limit=20, include_types=None, user_ids=None):
        # 调用API获取项目，支持用户筛选
        try:
            if not service:
                return []
            
            try:
                if not self._sort_by:
                    sort_by = 'Random'
                else:
                    sort_by = self._sort_by
                if self._monitor_sort:
                    sort_by = 'DateCreated'
                if not include_types:
                    include_types = 'Movie,Series'

                url = f'[HOST]emby/Items/?api_key=[APIKEY]' \
                      f'&ParentId={parent_id}&SortBy={sort_by}&Limit={limit}' \
                      f'&StartIndex={offset}&IncludeItemTypes={include_types}' \
                      f'&Recursive=True&SortOrder=Descending'
                
                # 如果提供了用户ID列表，则逐个获取每个用户的合集
                if user_ids and include_types and 'BoxSet' in include_types:
                    all_items = []
                    for user_id in user_ids:
                        user_url = f'{url}&UserId={user_id}'
                        res = service.instance.get_data(url=user_url)
                        if res:
                            data = res.json()
                            all_items.extend(data.get("Items", []))
                    
                    # 去重（基于项目ID）
                    unique_items = {}
                    for item in all_items:
                        unique_items[item['Id']] = item
                    return list(unique_items.values())

                res = service.instance.get_data(url=url)
                if res:
                    data = res.json()
                    return data.get("Items", [])
            except Exception as err:
                logger.error(f"获取媒体项失败：{str(err)}")
            return []
                
        except Exception as err:
            logger.error(f"Failed to get latest items: {str(err)}")
            return []
        
    def __filter_valid_items(self, items):
        """筛选有效的项目（包含所需图片的项目），并按图片标签去重"""
        valid_items = []
        seen_tags = set()

        for item in items:
            tags = []

            # 统一收集所有可能的图片 tag 字符串作为唯一标识
            if item.get("PrimaryImageTag"):
                tags.append(f"Primary:{item['PrimaryImageTag']}")
            if item.get("AlbumPrimaryImageTag"):
                tags.append(f"AlbumPrimary:{item['AlbumPrimaryImageTag']}")
            if item.get("BackdropImageTags"):
                tags.extend([f"Backdrop:{t}" for t in item["BackdropImageTags"]])
            if item.get("ParentBackdropImageTags"):
                tags.extend([f"ParentBackdrop:{t}" for t in item["ParentBackdropImageTags"]])
            if item.get("ImageTags") and item["ImageTags"].get("Primary"):
                tags.append(f"ImagePrimary:{item['ImageTags']['Primary']}")

            # 判断是否重复（所有 tag 都未见过才添加）
            if any(tag in seen_tags for tag in tags):
                continue  # 跳过已有标签的 item

            # 决定是否为有效项目
            if item['Type'] in 'MusicAlbum,Audio':
                if item.get("ParentBackdropImageTags") or item.get("AlbumPrimaryImageTag") or item.get("PrimaryImageTag"):
                    valid_items.append(item)
                    seen_tags.update(tags)
            elif self._cover_style.startswith('multi'):
                if (item.get("ImageTags") and item["ImageTags"].get("Primary")) \
                    or item.get("BackdropImageTags") \
                    or item.get("ParentBackdropImageTags"):
                    valid_items.append(item)
                    seen_tags.update(tags)
            elif self._cover_style.startswith('single'):
                if item.get("BackdropImageTags") \
                    or item.get("ParentBackdropImageTags") \
                    or (item.get("ImageTags") and item["ImageTags"].get("Primary")):
                    valid_items.append(item)
                    seen_tags.update(tags)

        return valid_items

    
    def __update_single_image(self, service, library, title, item):
        """更新单图封面"""
        logger.info(f"媒体库 {service.name}：{library['Name']} 从媒体项获取图片")
        updated_item_id = ''
        image_url = self.__get_image_url(item)
        if not image_url:
            return False
            
        image_path = self.__download_image(service, image_url, library['Name'], count=1)
        if not image_path:
            return False
        updated_item_id = self.__get_item_id(item)
        image_data = self.__generate_image_from_path(service.name, library['Name'], title, image_path)
            
        if not image_data:
            return False
        if service.type == 'emby':
            library_id = library.get("Id")
        else:
            library_id = library.get("ItemId")
        # 更新id
        self.update_cover_history(
            server=service.name, 
            library_id=library_id, 
            item_id=updated_item_id
        )

        return image_data
    
    def __update_grid_image(self, service, library, title, items):
        """更新九宫格封面"""
        logger.info(f"媒体库 {service.name}：{library['Name']} 从媒体项获取图片")

        image_paths = []
        
        updated_item_ids = []
        for i, item in enumerate(items[:9]):
            image_url = self.__get_image_url(item)
            if image_url:
                image_path = self.__download_image(service, image_url, library['Name'], count=i+1)
                if image_path:
                    image_paths.append(image_path)
                    updated_item_ids.append(self.__get_item_id(item))
        
        if len(image_paths) < 1:
            return False
            
        # 生成九宫格图片
        image_data = self.__generate_image_from_path(service.name, library['Name'], title)
        if not image_data:
            return False
        if service.type == 'emby':
            library_id = library.get("Id")
        else:
            library_id = library.get("ItemId")
        # 更新ids
        for item_id in updated_item_ids:
            self.update_cover_history(
                server=service.name, 
                library_id=library_id, 
                item_id=item_id
            )
            
        return image_data
    
    def __get_library_title_from_config(self, library_name):
        """
        从 JSON 配置中获取媒体库的中英文标题
        """
        zh_title = library_name
        en_title = ''
        
        if not self._title_config:
            return (zh_title, en_title)
        
        try:
            # 解析 JSON 配置
            data = json.loads(self._title_config)
            if not isinstance(data, dict):
                raise ValueError("JSON 顶层结构必须是一个对象")
            
            logger.debug(f"JSON解析成功，共有 {len(data)} 个媒体库配置")
            
            # 获取指定媒体库的配置
            titles = data.get(library_name)
            if titles:
                if not isinstance(titles, list):
                    logger.warning(f"媒体库 '{library_name}' 的配置必须是数组格式，当前类型: {type(titles).__name__}")
                    return (zh_title, en_title)
                
                if len(titles) >= 2:
                    zh_title = titles[0]
                    en_title = titles[1]
                elif len(titles) == 1:
                    zh_title = titles[0]
                    en_title = ''
                    logger.info(f"媒体库 {library_name} 只配置了中文标题，英文标题留空")
                else:
                    logger.warning(f"媒体库 {library_name} 的标题配置为空数组")
            else:
                logger.debug(f"JSON 配置中未找到媒体库 {library_name} 的标题配置")
                
        except json.JSONDecodeError as e:
            # 提供详细的错误信息
            error_msg = f"JSON 解析错误在第 {e.lineno} 行，第 {e.colno} 列: {e.msg}"
            logger.error(f"标题配置解析失败: {error_msg}")
            logger.info(f"将使用库名作为标题: {library_name}")
        except Exception as e:
            logger.error(f"标题配置处理异常: {type(e).__name__}: {str(e)}")
            logger.info(f"将使用库名作为标题: {library_name}")
        
        return (zh_title, en_title)
    
    def __get_server_libraries(self, service):
        try:
            if not service:
                return []
            try:
                if service.type == 'emby':
                    url = f'[HOST]emby/Library/VirtualFolders/Query?api_key=[APIKEY]'
                else:
                    url = f'[HOST]emby/Library/VirtualFolders/?api_key=[APIKEY]'
                res = service.instance.get_data(url=url)
                if res:
                    data = res.json()
                    if service.type == 'emby':
                        return data.get("Items", [])
                    else:
                        return data
            except Exception as err:
                logger.error(f"获取媒体库列表失败：{str(err)}")
            return []
        except Exception as err:
            logger.error(f"获取媒体库列表失败：{str(err)}")
            return []
    
    def __get_all_libraries(self, server, service):
        try:
            lib_items = []
            libraries = self.__get_server_libraries(service)
            for library in libraries:
                if service.type == 'emby':
                    library_id = library.get("Id")
                else:
                    library_id = library.get("ItemId")
                if library['Name'] and library_id:
                    lib_item = {
                        "name": f"{server}: {library['Name']}",
                        "value": f"{server}-{library_id}"
                    }
                    lib_items.append(lib_item)
            return lib_items
        except Exception as err:
            logger.error(f"获取所有媒体库失败：{str(err)}")
            return []
    
    def __get_server_users(self, service):
        """
        获取媒体服务器的用户列表
        """
        try:
            if not service:
                return []
            
            # Emby/Jellyfin API for getting users
            url = f'[HOST]emby/Users?api_key=[APIKEY]'
            res = service.instance.get_data(url=url)
            
            if res and res.status_code == 200:
                users = res.json()
                user_list = []
                for user in users:
                    if user.get('Name') and user.get('Id'):
                        user_list.append({
                            'name': user['Name'],
                            'id': user['Id']
                        })
                return user_list
            else:
                logger.error(f"获取用户列表失败：状态码 {res.status_code if res else 'None'}")
                return []
        except Exception as err:
            logger.error(f"获取用户列表失败：{str(err)}")
            return []
    
    def __get_all_users(self):
        """
        获取所有选中服务器的用户列表，用于配置界面
        """
        try:
            all_users = []
            if self._servers:
                for server, service in self._servers.items():
                    if not service.instance.is_inactive():
                        users = self.__get_server_users(service)
                        for user in users:
                            all_users.append({
                                "title": f"{server}: {user['name']}",
                                "value": f"{server}-{user['id']}"
                            })
                    else:
                        logger.info(f"媒体服务器 {server} 未连接，无法获取用户列表")
            return all_users
        except Exception as err:
            logger.error(f"获取所有用户列表失败：{str(err)}")
            return []
        
    def __get_image_url(self, item):
        """
        从媒体项信息中获取图片URL
        """
        # Emby/Jellyfin
        if item['Type'] in 'MusicAlbum,Audio':
            if item.get("ParentBackdropImageTags") and len(item["ParentBackdropImageTags"]) > 0:
                item_id = item.get("ParentBackdropItemId")
                tag = item["ParentBackdropImageTags"][0]
                return f'[HOST]emby/Items/{item_id}/Images/Backdrop/0?tag={tag}&api_key=[APIKEY]'
            elif item.get("PrimaryImageTag"):
                item_id = item.get("PrimaryImageItemId")
                tag = item.get("PrimaryImageTag")
                return f'[HOST]emby/Items/{item_id}/Images/Primary?tag={tag}&api_key=[APIKEY]'
            elif item.get("AlbumPrimaryImageTag"):
                item_id = item.get("AlbumId")
                tag = item.get("AlbumPrimaryImageTag")
                return f'[HOST]emby/Items/{item_id}/Images/Primary?tag={tag}&api_key=[APIKEY]'

        elif self._cover_style.startswith('multi'):
            if self._multi_1_use_primary:
                if item.get("ImageTags") and item.get("ImageTags").get("Primary"):
                    item_id = item.get("Id")
                    tag = item.get("ImageTags").get("Primary")
                    return f'[HOST]emby/Items/{item_id}/Images/Primary?tag={tag}&api_key=[APIKEY]'
                elif item.get("ParentBackdropImageTags") and len(item["ParentBackdropImageTags"]) > 0:
                    item_id = item.get("ParentBackdropItemId")
                    tag = item["ParentBackdropImageTags"][0]
                    return f'[HOST]emby/Items/{item_id}/Images/Backdrop/0?tag={tag}&api_key=[APIKEY]'
                elif item.get("BackdropImageTags") and len(item["BackdropImageTags"]) > 0:
                    item_id = item.get("Id")
                    tag = item["BackdropImageTags"][0]
                    return f'[HOST]emby/Items/{item_id}/Images/Backdrop/0?tag={tag}&api_key=[APIKEY]'
            else:
                if item.get("ParentBackdropImageTags") and len(item["ParentBackdropImageTags"]) > 0:
                    item_id = item.get("ParentBackdropItemId")
                    tag = item["ParentBackdropImageTags"][0]
                    return f'[HOST]emby/Items/{item_id}/Images/Backdrop/0?tag={tag}&api_key=[APIKEY]'
                elif item.get("BackdropImageTags") and len(item["BackdropImageTags"]) > 0:
                    item_id = item.get("Id")
                    tag = item["BackdropImageTags"][0]
                    return f'[HOST]emby/Items/{item_id}/Images/Backdrop/0?tag={tag}&api_key=[APIKEY]'
                elif item.get("ImageTags") and item.get("ImageTags").get("Primary"):
                    item_id = item.get("Id")
                    tag = item.get("ImageTags").get("Primary")
                    return f'[HOST]emby/Items/{item_id}/Images/Primary?tag={tag}&api_key=[APIKEY]'

        elif self._cover_style.startswith('single'):
            if self._single_use_primary:
                if item.get("ImageTags") and item.get("ImageTags").get("Primary"):
                    item_id = item.get("Id")
                    tag = item.get("ImageTags").get("Primary")
                    return f'[HOST]emby/Items/{item_id}/Images/Primary?tag={tag}&api_key=[APIKEY]'
                elif item.get("ParentBackdropImageTags") and len(item["ParentBackdropImageTags"]) > 0:
                    item_id = item.get("ParentBackdropItemId")
                    tag = item["ParentBackdropImageTags"][0]
                    return f'[HOST]emby/Items/{item_id}/Images/Backdrop/0?tag={tag}&api_key=[APIKEY]'
                elif item.get("BackdropImageTags") and len(item["BackdropImageTags"]) > 0:
                    item_id = item.get("Id")
                    tag = item["BackdropImageTags"][0]
                    return f'[HOST]emby/Items/{item_id}/Images/Backdrop/0?tag={tag}&api_key=[APIKEY]'
            else:
                if item.get("ParentBackdropImageTags") and len(item["ParentBackdropImageTags"]) > 0:
                    item_id = item.get("ParentBackdropItemId")
                    tag = item["ParentBackdropImageTags"][0]
                    return f'[HOST]emby/Items/{item_id}/Images/Backdrop/0?tag={tag}&api_key=[APIKEY]'
                elif item.get("BackdropImageTags") and len(item["BackdropImageTags"]) > 0:
                    item_id = item.get("Id")
                    tag = item["BackdropImageTags"][0]
                    return f'[HOST]emby/Items/{item_id}/Images/Backdrop/0?tag={tag}&api_key=[APIKEY]'
                elif item.get("ImageTags") and item.get("ImageTags").get("Primary"):
                    item_id = item.get("Id")
                    tag = item.get("ImageTags").get("Primary")
                    return f'[HOST]emby/Items/{item_id}/Images/Primary?tag={tag}&api_key=[APIKEY]'
            
    def __get_item_id(self, item):
        """
        从媒体项信息中获取项目ID
        """
        # Emby/Jellyfin
        item_id = None  # 初始化变量
        if item['Type'] in 'MusicAlbum,Audio':
            if item.get("ParentBackdropImageTags") and len(item["ParentBackdropImageTags"]) > 0:
                item_id = item.get("ParentBackdropItemId")
            elif item.get("PrimaryImageTag"):
                item_id = item.get("PrimaryImageItemId")
            elif item.get("AlbumPrimaryImageTag"):
                item_id = item.get("AlbumId")

        elif self._cover_style and self._cover_style.startswith('multi'):
            if self._multi_1_use_primary:
                if (item.get("ImageTags") and item.get("ImageTags").get("Primary")) \
                    or (item.get("BackdropImageTags") and len(item["BackdropImageTags"]) > 0):
                    item_id = item.get("Id")
                elif item.get("ParentBackdropImageTags") and len(item["ParentBackdropImageTags"]) > 0:
                    item_id = item.get("ParentBackdropItemId")
            else:
                if item.get("ParentBackdropImageTags") and len(item["ParentBackdropImageTags"]) > 0:
                    item_id = item.get("ParentBackdropItemId")
                elif (item.get("ImageTags") and item.get("ImageTags").get("Primary")) \
                    or (item.get("BackdropImageTags") and len(item["BackdropImageTags"]) > 0):
                    item_id = item.get("Id")

        elif self._cover_style and self._cover_style.startswith('single'):
            if self._single_use_primary:
                if (item.get("BackdropImageTags") and len(item["BackdropImageTags"]) > 0) \
                    or (item.get("ImageTags") and item.get("ImageTags").get("Primary")):
                    item_id = item.get("Id")
                elif item.get("ParentBackdropImageTags") and len(item["ParentBackdropImageTags"]) > 0:
                    item_id = item.get("ParentBackdropItemId")
            else:
                if item.get("ParentBackdropImageTags") and len(item["ParentBackdropImageTags"]) > 0:
                    item_id = item.get("ParentBackdropItemId")
                elif (item.get("BackdropImageTags") and len(item["BackdropImageTags"]) > 0) \
                    or (item.get("ImageTags") and item.get("ImageTags").get("Primary")):
                    item_id = item.get("Id")

        return item_id

    def __download_image(self, service, imageurl, library_name, count=None, retries=3, delay=1):
        """
        下载图片，保存到本地目录 self._covers_path/library_name/ 下，文件名为 1-9.jpg
        若已存在则跳过下载，直接返回图片路径。
        下载失败时重试若干次。
        """
        try:
            # 创建目标子目录
            subdir = os.path.join(self._covers_path, library_name)
            os.makedirs(subdir, exist_ok=True)

            # 文件命名：item_id 为主，适合排序
            if count is not None:
                filename = f"{count}.jpg"
            else:
                filename = f"img_{int(time.time())}.jpg"

            filepath = os.path.join(subdir, filename)

            # 如果文件已存在，直接返回路径
            # if os.path.exists(filepath):
            #     return filepath

            # 重试机制
            for attempt in range(1, retries + 1):
                image_content = None

                if '[HOST]' in imageurl:
                    if not service:
                        return None

                    r = service.instance.get_data(url=imageurl)
                    if r and r.status_code == 200:
                        image_content = r.content
                else:
                    r = RequestUtils().get_res(url=imageurl)
                    if r and r.status_code == 200:
                        image_content = r.content

                # 如果成功，保存并返回
                if image_content:
                    with open(filepath, 'wb') as f:
                        f.write(image_content)
                    return filepath

                # 如果失败，记录并等待后重试
                logger.warning(f"第 {attempt} 次尝试下载失败：{imageurl}")
                if attempt < retries:
                    time.sleep(delay)

            logger.error(f"图片下载失败（重试 {retries} 次）：{imageurl}")
            return None

        except Exception as err:
            logger.error(f"下载图片异常：{str(err)}")
            return None


    def __save_image_to_local(self, image_content, filename):
        """
        保存图片到本地路径
        """
        try:
            # 确保目录存在
            local_path = self._covers_output
            if not local_path:
                return
            import os
            os.makedirs(local_path, exist_ok=True)
            
            # 保存文件
            file_path = os.path.join(local_path, filename)
            with open(file_path, "wb") as f:
                f.write(image_content)
            logger.info(f"图片已保存到本地: {file_path}")
        except Exception as err:
            logger.error(f"保存图片到本地失败: {str(err)}")
        

    def __set_library_image(self, service, library, image_base64):
        """
        设置媒体库封面
        """

        """设置Emby媒体库封面"""
        try:
            if service.type == 'emby':
                library_id = library.get("Id")
            else:
                library_id = library.get("ItemId")
            url = f'[HOST]emby/Items/{library_id}/Images/Primary?api_key=[APIKEY]'
            
            # 在发送前保存一份图片到本地
            if self._covers_output:
                try:
                    image_bytes = base64.b64decode(image_base64)
                    self.__save_image_to_local(image_bytes, f"{library['Name']}.jpg")
                except Exception as save_err:
                    logger.error(f"保存发送前图片失败: {str(save_err)}")
            
            res = service.instance.post_data(
                url=url,
                data=image_base64,
                headers={
                    "Content-Type": "image/png"
                }
            )
            
            if res and res.status_code in [200, 204]:
                return True
            else:
                logger.error(f"设置「{library['Name']}」封面失败，错误码：{res.status_code if res else 'No response'}")
                return False
        except Exception as err:
            logger.error(f"设置「{library['Name']}」封面失败：{str(err)}")
        return False

    def clean_cover_history(self, save=True):
        history = self.get_data('cover_history') or []
        cleaned = []

        for item in history:
            try:
                cleaned_item = {
                    "server": item["server"],
                    "library_id": str(item["library_id"]),
                    "item_id": str(item["item_id"]),
                    "timestamp": float(item["timestamp"])
                }
                cleaned.append(cleaned_item)
            except (KeyError, ValueError, TypeError):
                # 如果字段缺失或格式错误则跳过该项
                continue

        if save:
            self.save_data('cover_history', cleaned)

        return cleaned


    def update_cover_history(self, server, library_id, item_id):
        now = time.time()
        item_id = str(item_id)
        library_id = str(library_id)

        history_item = {
            "server": server,
            "library_id": library_id,
            "item_id": item_id,
            "timestamp": now
        }

        # 原始数据
        history = self.get_data('cover_history') or []

        # 用于分组管理：(server, library_id) => list of items
        grouped = defaultdict(list)
        for item in history:
            key = (item["server"], str(item["library_id"]))
            grouped[key].append(item)

        key = (server, library_id)
        items = grouped[key]

        # 查找是否已有该 item_id
        existing = next((i for i in items if str(i["item_id"]) == item_id), None)

        if existing:
            # 若已存在且是最新的，跳过
            if existing["timestamp"] >= max(i["timestamp"] for i in items):
                return
            else:
                existing["timestamp"] = now
        else:
            items.append(history_item)

        # 排序 + 截取前9
        grouped[key] = sorted(items, key=lambda x: x["timestamp"], reverse=True)[:9]

        # 重新整合所有分组的数据
        new_history = []
        for item_list in grouped.values():
            new_history.extend(item_list)

        self.save_data('cover_history', new_history)
        return [ 
            item for item in new_history
            if str(item.get("library_id")) == str(library_id)
        ]

    def prepare_library_images(self, library_dir: str):
        """
        准备目录下的1-9.jpg图片文件:
        1. 检查已有的1-9.jpg文件
        2. 保留已有的文件，只补足缺失的编号
        3. 补充文件时尽量避免连续使用相同的源图片
        """
        os.makedirs(library_dir, exist_ok=True)

        # 检查哪些编号的文件已存在，哪些缺失
        existing_numbers = []
        missing_numbers = []
        for i in range(1, 10):
            target_file_path = os.path.join(library_dir, f"{i}.jpg")
            if os.path.exists(target_file_path):
                existing_numbers.append(i)
            else:
                missing_numbers.append(i)

        # 如果已经存在所有文件，直接返回
        if not missing_numbers:
            # logger.info(f"信息: {library_dir} 中已存在所有 1-9.jpg，无需任何操作。")
            return True

        logger.info(f"信息: {library_dir} 中缺少以下编号的图片: {missing_numbers}，将进行补充。")

        # 获取所有可用作源的图片（排除已有的1-9.jpg）
        source_image_filenames = []
        for f in os.listdir(library_dir):
            # 排除1-9.jpg作为源
            if not re.match(r"^[1-9]\.jpg$", f, re.IGNORECASE):
                if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                    source_image_filenames.append(f)

        # 如果没有源图片可用
        if not source_image_filenames:
            # 如果已经有部分1-9.jpg，可以从这些现有文件中选择
            if existing_numbers:
                logger.info(f"信息: {library_dir} 中没有其他图片可用，将从现有的 1-9.jpg 中随机选择进行复制。")
                existing_file_paths = [os.path.join(library_dir, f"{i}.jpg") for i in existing_numbers]
                source_image_paths = existing_file_paths
            else:
                logger.info(f"警告: {library_dir} 中没有任何可用的图片来生成 1-9.jpg。")
                return False
        else:
            # 将文件名转换为完整路径
            source_image_paths = [os.path.join(library_dir, f) for f in sorted(source_image_filenames)]

        # 如果源图片数量不足，需要重复使用
        if len(source_image_paths) < len(missing_numbers):
            logger.info(f"信息: 源图片数量({len(source_image_paths)})小于缺失数量({len(missing_numbers)})，某些图片将被重复使用。")
        
        # 为每个缺失的编号选择一个源图片，尽量避免连续重复
        last_used_source = None
        for missing_num in missing_numbers:
            target_path = os.path.join(library_dir, f"{missing_num}.jpg")
            
            # 如果只有一个源文件，没有选择，直接使用
            if len(source_image_paths) == 1:
                selected_source = source_image_paths[0]
            else:
                # 尝试选择一个与上次不同的源文件
                available_sources = [s for s in source_image_paths if s != last_used_source]
                
                # 如果没有其他选择（可能上次用了唯一的源文件），则使用所有源
                if not available_sources:
                    available_sources = source_image_paths
                    
                # 随机选择一个源文件
                selected_source = random.choice(available_sources)
                
            # 记录本次使用的源文件，用于下次比较
            last_used_source = selected_source
            
            try:
                if not os.path.exists(selected_source):
                    logger.info(f"错误: 源文件 {selected_source} 在尝试复制前找不到了！")
                    return False
                    
                shutil.copy(selected_source, target_path)
                logger.info(f"信息: 已创建 {missing_num}.jpg (源自: {os.path.basename(selected_source)})")
                
            except Exception as e:
                logger.info(f"错误: 复制文件 {selected_source} 到 {target_path} 时发生错误: {e}")
                return False

        logger.info(f"信息: {library_dir} 已成功补充所有缺失的图片，现在包含完整的 1-9.jpg")
        return True

    def __get_fonts(self):
        font_dir_path = self._font_path
        
        # 如果未启用字体下载，直接返回
        if not self._font_download:
            logger.info("字体下载功能已禁用，跳过字体获取")
            # 设置默认字体路径为空，避免报错
            if self._cover_style == "multi_1" and not self._multi_1_use_main_font:
                self._zh_font_path_multi_1 = self._zh_font_path_multi_1_local or ""
                self._en_font_path_multi_1 = self._en_font_path_multi_1_local or ""
            else:
                self._zh_font_path = self._zh_font_path_local or ""
                self._en_font_path = self._en_font_path_local or ""
            return

        default_zh_url = "https://raw.githubusercontent.com/wuyaos/MoviePilot-Plugins/main/fonts/wendao.ttf"
        default_en_url = "https://raw.githubusercontent.com/wuyaos/MoviePilot-Plugins/main/fonts/EmblemaOne.woff2"
        
        default_zh_url_multi_1 = "https://raw.githubusercontent.com/wuyaos/MoviePilot-Plugins/main/fonts/multi_1_zh.ttf"
        default_en_url_multi_1 = "https://raw.githubusercontent.com/wuyaos/MoviePilot-Plugins/main/fonts/multi_1_en.otf"

        is_multi_1_style = self._cover_style == "multi_1"

        if is_multi_1_style and not self._multi_1_use_main_font:
            log_prefix = "多图风格1"
            current_zh_font_url = self._zh_font_url_multi_1 or default_zh_url_multi_1
            current_en_font_url = self._en_font_url_multi_1 or default_en_url_multi_1
            zh_local_path_config = self._zh_font_path_multi_1_local
            en_local_path_config = self._en_font_path_multi_1_local
            
            downloaded_zh_font_base = "zh_multi_1"
            downloaded_en_font_base = "en_multi_1"
            hash_zh_file_name = "zh_url_multi_1.hash"
            hash_en_file_name = "en_url_multi_1.hash"
            final_zh_font_path_attr = "_zh_font_path_multi_1"
            final_en_font_path_attr = "_en_font_path_multi_1"
        else:
            log_prefix = "默认"
            current_zh_font_url = self._zh_font_url or default_zh_url
            current_en_font_url = self._en_font_url or default_en_url
            zh_local_path_config = self._zh_font_path_local
            en_local_path_config = self._en_font_path_local
            
            downloaded_zh_font_base = "zh"
            downloaded_en_font_base = "en"
            hash_zh_file_name = "zh_url.hash"
            hash_en_file_name = "en_url.hash"
            final_zh_font_path_attr = "_zh_font_path"
            final_en_font_path_attr = "_en_font_path"

        active_fonts_to_process = [
            {
                "lang": "中文",
                "url": current_zh_font_url,
                "local_path_config": zh_local_path_config,
                "download_base_name": downloaded_zh_font_base,
                "hash_file_name": hash_zh_file_name,
                "final_attr_name": final_zh_font_path_attr,
                "fallback_ext": ".ttf"
            },
            {
                "lang": "英文",
                "url": current_en_font_url,
                "local_path_config": en_local_path_config,
                "download_base_name": downloaded_en_font_base,
                "hash_file_name": hash_en_file_name,
                "final_attr_name": final_en_font_path_attr,
                "fallback_ext": ".ttf"
            }
        ]


        for font_info in active_fonts_to_process:
            lang = font_info["lang"]
            url = font_info["url"]
            local_path_cfg = font_info["local_path_config"]
            download_base = font_info["download_base_name"]
            hash_filename = font_info["hash_file_name"]
            final_attr = font_info["final_attr_name"]
            fallback_ext = font_info["fallback_ext"]


            extension = self.get_file_extension_from_url(url, fallback_ext=fallback_ext)
            downloaded_font_file_path = Path(font_dir_path) / f"{download_base}{extension}"
            hash_file_path = Path(font_dir_path) / hash_filename
            
            current_font_path = None
            using_local_font = False
            if local_path_cfg:
                local_font_p = Path(local_path_cfg)
                if self._validate_font_file(local_font_p):
                    logger.info(f"{lang}字体: 使用本地指定路径 {local_font_p}")
                    current_font_path = local_font_p
                    using_local_font = True
                else:
                    logger.warning(f"{log_prefix}{lang}字体: 本地指定路径 {local_font_p} 无效或文件不存在。")

            if not using_local_font:
                url_hash = hashlib.md5(url.encode()).hexdigest()
                url_has_changed = True
                if hash_file_path.exists():
                    try:
                        if hash_file_path.read_text() == url_hash:
                            url_has_changed = False
                    except Exception as e:
                        logger.warning(f"读取哈希文件失败 {hash_file_path}: {e}。将重新下载。")
                
                font_file_is_valid = self._validate_font_file(downloaded_font_file_path)

                if url_has_changed or not font_file_is_valid:
                    if url_has_changed:
                        logger.info(f"{log_prefix}{lang}字体URL已更改或首次下载。")
                    if not font_file_is_valid and downloaded_font_file_path.exists():
                         logger.info(f"{log_prefix}{lang}字体文件 {downloaded_font_file_path} 无效或损坏，将重新下载。")
                    elif not downloaded_font_file_path.exists():
                         logger.info(f"{log_prefix}{lang}字体文件 {downloaded_font_file_path} 不存在，将下载。")

                    if self.download_font_safely(url, downloaded_font_file_path):
                        try:
                            hash_file_path.write_text(url_hash)
                        except Exception as e:
                            logger.error(f"写入哈希文件失败 {hash_file_path}: {e}")
                        current_font_path = downloaded_font_file_path
                    else:
                        logger.critical(f"无法获取必要的{log_prefix}{lang}支持字体: {url}")
                        if font_file_is_valid :
                             logger.warning(f"下载失败，但找到一个已存在的（可能旧版本）有效字体文件 {downloaded_font_file_path}，将尝试使用。")
                             current_font_path = downloaded_font_file_path
                        else:
                             current_font_path = None
                else:
                    logger.info(f"{log_prefix}{lang}字体: 使用已下载/缓存的有效字体 {downloaded_font_file_path}")
                    current_font_path = downloaded_font_file_path
            
            setattr(self, final_attr, current_font_path)
            status_log = '(本地路径)' if using_local_font else '(已下载/缓存)' if current_font_path and current_font_path.exists() else '(获取失败)'
            logger.info(f"{log_prefix}{lang}字体最终路径: {getattr(self,final_attr)} {status_log}")

    def download_font_safely(self, font_url: str, font_path: Path, retries: int = 3, delay: int = 2):
        """
        从链接下载字体文件到指定目录，支持多种下载策略（GitHub镜像、代理、直连）
        :param font_url: 字体文件URL
        :param font_path: 保存路径
        :param retries: 每种策略的最大重试次数
        :param delay: 重试间隔（秒）
        :return: 是否下载成功
        """
        logger.info(f"准备下载字体: {font_url} -> {font_path}")
        
        # 确保在开始下载前删除任何可能存在的损坏文件
        if font_path.exists():
            try:
                font_path.unlink()
                logger.info(f"删除之前的字体文件以便重新下载: {font_path}")
            except OSError as unlink_error:
                logger.error(f"无法删除现有字体文件 {font_path}: {unlink_error}")
                return False
        
        # 准备下载策略
        strategies = []
        
        # 判断是否为GitHub链接
        is_github_url = "github.com" in font_url or "raw.githubusercontent.com" in font_url
        
        # 对于GitHub链接，优先使用GitHub镜像站
        if is_github_url and settings.GITHUB_PROXY:
            github_proxy_url = f"{UrlUtils.standardize_base_url(settings.GITHUB_PROXY)}{font_url}"
            strategies.append(("GitHub镜像站", github_proxy_url))
        
        # 其次尝试使用代理
        if settings.PROXY_HOST:
            strategies.append(("代理", font_url, {"proxies": settings.PROXY}))
        
        # 最后尝试直连
        strategies.append(("直连", font_url, {}))
        
        # 遍历所有策略
        for strategy_name, target_url, *request_params in strategies:
            request_kwargs = request_params[0] if request_params else {}
            logger.info(f"尝试使用策略：{strategy_name} 下载字体: {target_url}")
            
            attempt = 0
            while attempt < retries:
                attempt += 1
                try:
                    logger.debug(f"使用策略 {strategy_name}，下载尝试 {attempt}/{retries} for {target_url}")
                    
                    # 创建目标目录
                    font_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # 使用对应策略下载内容
                    font_content = RequestUtils(**request_kwargs).get_res(url=target_url).content
                    
                    # 创建临时文件用于验证下载内容
                    temp_path = font_path.with_suffix('.temp')
                    with open(temp_path, "wb") as f:
                        f.write(font_content)
                    
                    # 验证下载的字体文件
                    if self._validate_font_file(temp_path):
                        # 验证通过后，将临时文件移动到正确位置
                        temp_path.replace(font_path)
                        logger.info(f"字体下载成功: 使用策略 {strategy_name}")
                        return True
                    else:
                        logger.warning(f"下载的字体文件验证失败，可能已损坏")
                        if temp_path.exists():
                            temp_path.unlink()
                    
                except Exception as e:
                    logger.warning(f"策略 {strategy_name} 下载尝试 {attempt}/{retries} 失败: {e}")
                    # 清理可能的临时文件
                    temp_path = font_path.with_suffix('.temp')
                    if temp_path.exists():
                        try:
                            temp_path.unlink()
                        except OSError:
                            pass
                    
                    if attempt < retries:
                        logger.info(f"将在 {delay} 秒后重试...")
                        time.sleep(delay)
                    else:
                        logger.error(f"使用策略 {strategy_name} 下载字体失败 (已达最大重试次数): {target_url}")
                        # 转到下一个策略，不返回False
                        break
        
        # 所有策略都失败
        logger.error(f"所有下载策略均失败，无法下载字体，建议手动下载字体: {font_url}")
        # 确保目标路径没有损坏的文件
        if font_path.exists():
            try:
                font_path.unlink()
                logger.info(f"已删除部分下载的文件: {font_path}")
            except OSError as unlink_error:
                logger.error(f"无法删除部分下载的文件 {font_path}: {unlink_error}")
        
        return False

    def get_file_extension_from_url(self, url: str, fallback_ext: str = ".ttf") -> str:
        """
        从链接获取字体扩展名扩展名
        """
        try:
            parsed_url = urlparse(url)
            path_part = parsed_url.path
            if path_part:
                filename = os.path.basename(path_part)
                _ , ext = os.path.splitext(filename)
                return ext if ext else fallback_ext
            else:
                logger.warning(f"无法从URL中提取路径部分: {url}. 使用备用扩展名: {fallback_ext}")
                return fallback_ext
        except Exception as e:
            logger.error(f"解析URL时出错 '{url}': {e}. 使用备用扩展名: {fallback_ext}")
            return fallback_ext
        
    def _validate_font_file(self, font_path: Path):
        if not font_path or not font_path.exists() or not font_path.is_file():
            return False
        
        try:
            with open(font_path, "rb") as f:
                header = f.read(4) 
                if (header.startswith(b'\x00\x01\x00\x00') or
                    header.startswith(b'OTTO') or
                    header.startswith(b'true') or
                    header.startswith(b'wOFF') or
                    header.startswith(b'wOF2')):
                    return True
                if font_path.suffix.lower() == ".svg":
                    f.seek(0)
                    sample = f.read(100).decode(errors='ignore').strip()
                    if sample.startswith('<svg') or sample.startswith('<?xml'):
                        return True
                if font_path.suffix.lower() == ".bdf":
                    f.seek(0)
                    sample = f.read(9).decode(errors='ignore')
                    if sample == "STARTFONT":
                        return True
            logger.warning(f"字体文件存在但可能已损坏或格式无法识别: {font_path}")
            return False
        except Exception as e:
            logger.warning(f"验证字体文件时出错 {font_path}: {e}")
            return False

    def stop_service(self):
        """
        停止服务
        """
        try:
            if self._scheduler:
                self._scheduler.remove_all_jobs()
                if self._scheduler.running:
                    self._event.set()
                    self._scheduler.shutdown()
                    self._event.clear()
                self._scheduler = None
        except Exception as e:
            logger.error(f"停止服务失败: {str(e)}")