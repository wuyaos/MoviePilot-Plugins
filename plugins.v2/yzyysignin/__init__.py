import json
import re
import time
from datetime import datetime, timedelta
from typing import Any, List, Dict, Tuple, Optional
from urllib.parse import urlparse

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from lxml import etree

from app.core.config import settings
from app.plugins import _PluginBase
from app.log import logger
from app.schemas import NotificationType
from app.utils.http import RequestUtils


class YzyySignin(_PluginBase):
    # 插件基本信息
    plugin_name = "yzyy论坛签到"
    plugin_desc = "yzyy论坛每日签到，自动获取签到码完成签到"
    plugin_icon = "https://raw.githubusercontent.com/wuyaos/MoviePilot-Plugins/main/icons/signin.png"
    plugin_version = "1.2.9"
    plugin_author = "bfjy, wuyaos"
    author_url = "https://github.com/wuyaos"
    plugin_config_prefix = "yzyysignin_"
    plugin_order = 25
    auth_level = 2

    # 常量配置
    DEFAULT_SITE_URL = "https://yzyy.org"
    MAX_HISTORY = 100
    REQUEST_TIMEOUT = 30

    # 私有属性
    _enabled = False
    _cron = None
    _cookie = None
    _site_url = DEFAULT_SITE_URL
    _onlyonce = False
    _notify = False
    _history_days = 30
    _scheduler: Optional[BackgroundScheduler] = None

    def init_plugin(self, config: dict = None):
        """初始化插件"""
        self.stop_service()
        config = config or {}

        self._enabled = config.get("enabled", False)
        self._cron = config.get("cron", "0 9 * * *")
        self._cookie = config.get("cookie", "")
        self._site_url = self.__normalize_site_url(config.get("site_url", self.DEFAULT_SITE_URL))
        self._notify = config.get("notify", False)
        self._onlyonce = config.get("onlyonce", False)
        try:
            self._history_days = int(config.get("history_days", 30))
            if self._history_days < 0:
                self._history_days = 30
        except (TypeError, ValueError):
            self._history_days = 30

        if self._onlyonce:
            self._onlyonce = False
            self.update_config({
                "onlyonce": False,
                "cron": self._cron,
                "enabled": self._enabled,
                "cookie": self._cookie,
                "site_url": self._site_url,
                "notify": self._notify,
                "history_days": self._history_days,
            })

            self._scheduler = BackgroundScheduler(timezone=settings.TZ)
            logger.info("yzyy论坛签到服务启动，立即运行一次")
            self._scheduler.add_job(
                func=self.__signin,
                trigger='date',
                run_date=datetime.now(tz=pytz.timezone(settings.TZ)) + timedelta(seconds=3),
                name="yzyy论坛签到_立即执行"
            )
            self._scheduler.start()
            logger.info("yzyy论坛签到任务已启动")

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return [
            {
                "cmd": "/yzyy_sign",
                "event": "PluginAction",
                "desc": "立即执行 yzyy 论坛签到",
                "category": "站点",
                "data": {
                    "action": "yzyy_signin_run"
                }
            }
        ]

    def get_api(self) -> List[Dict[str, Any]]:
        return [
            {
                "path": "/sign",
                "endpoint": self.__signin_api,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "立即执行 yzyy 论坛签到",
            },
            {
                "path": "/history",
                "endpoint": self.__get_history_api,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取签到历史",
            }
        ]

    def __signin_api(self) -> Dict[str, Any]:
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}
        logger.info("收到API签到请求，后台启动签到任务")
        self.__signin()
        return {"success": True, "message": "签到任务已执行"}

    def __get_history_api(self) -> Dict[str, Any]:
        history = self.get_data('history') or []
        return {
            "success": True,
            "data": history[:50]
        }

    def get_service(self) -> List[Dict[str, Any]]:
        if self._enabled and self._cron:
            try:
                return [{
                    "id": "YzyySignin",
                    "name": "yzyy论坛签到服务",
                    "trigger": CronTrigger.from_crontab(self._cron),
                    "func": self.__signin,
                    "kwargs": {}
                }]
            except Exception as e:
                logger.error(f"yzyy论坛签到 Cron 配置无效: {e}")
        return []

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        return [
            {
                'component': 'VForm',
                'content': [
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {'cols': 12, 'md': 4},
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'enabled',
                                            'label': '启用插件',
                                            'color': 'success'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {'cols': 12, 'md': 4},
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'notify',
                                            'label': '开启通知',
                                            'color': 'info'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {'cols': 12, 'md': 4},
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'onlyonce',
                                            'label': '立即运行一次',
                                            'color': 'warning',
                                            'hint': '保存配置后立即执行一次签到'
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
                                'props': {'cols': 12, 'md': 6},
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'cron',
                                            'label': '签到周期',
                                            'placeholder': '0 9 * * * (每天9点)',
                                            'hint': 'Cron表达式，建议每天固定时间签到'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {'cols': 12, 'md': 6},
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'history_days',
                                            'label': '保留历史天数',
                                            'placeholder': '30',
                                            'type': 'number',
                                            'hint': '签到历史记录保留天数'
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
                                'props': {'cols': 12},
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'site_url',
                                            'label': '站点地址',
                                            'placeholder': 'https://yzyy.org',
                                            'hint': '默认 https://yzyy.org，请勿填写结尾斜杠'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {'cols': 12},
                                'content': [
                                    {
                                        'component': 'VTextarea',
                                        'props': {
                                            'model': 'cookie',
                                            'label': '🔑 yzyy Cookie',
                                            'rows': 2,
                                            'placeholder': 'Chn7_2132_auth=xxxxxx; Chn7_2132_saltkey=xxxxxx;',
                                            'hint': '留空则自动从 CookieCloud 按域名获取'
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
                                'props': {'cols': 12},
                                'content': [
                                    {
                                        'component': 'VAlert',
                                        'props': {
                                            'type': 'info',
                                            'variant': 'tonal',
                                            'text': '💡 插件会自动从签到页面提取签到链接并完成签到。'
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ], {
            "enabled": False,
            "onlyonce": False,
            "notify": False,
            "cookie": "",
            "site_url": self.DEFAULT_SITE_URL,
            "history_days": 30,
            "cron": "0 9 * * *"
        }

    def get_page(self) -> List[dict]:
        histories = self.get_data('history') or []
        if not histories:
            return [
                {
                    'component': 'div',
                    'props': {
                        'class': 'text-center text-medium-emphasis pa-4'
                    },
                    'text': '📭 暂无签到数据'
                }
            ]

        if not isinstance(histories, list):
            histories = [histories]

        histories = sorted(histories, key=lambda x: x.get("date") or "0", reverse=True)

        total = len(histories)
        success_count = sum(1 for h in histories if h.get("result") == "成功")
        fail_count = total - success_count
        success_rate = round(success_count / total * 100, 1) if total > 0 else 0

        sign_msgs = []
        for history in histories[:30]:
            result = history.get("result", "")
            is_success = result == "成功"
            
            sign_msgs.append({
                'component': 'tr',
                'props': {
                    'style': 'border-bottom: 1px solid #f0f0f0;'
                },
                'content': [
                    {
                        'component': 'td',
                        'props': {'class': 'text-caption py-2 px-3'},
                        'text': history.get("date", "-")
                    },
                    {
                        'component': 'td',
                        'props': {
                            'class': f'text-caption py-2 px-3 font-weight-medium',
                            'style': f'color: {"#2E7D32" if is_success else "#C62828"};'
                        },
                        'text': f'{"✅" if is_success else "❌"} {result}'
                    },
                    {
                        'component': 'td',
                        'props': {
                            'class': 'text-caption py-2 px-3',
                            'style': 'max-width: 300px; word-break: break-word;'
                        },
                        'text': history.get("info", "-")
                    }
                ]
            })

        return [
            {
                'component': 'VCard',
                'props': {'class': 'mb-3', 'variant': 'tonal'},
                'content': [
                    {
                        'component': 'VCardText',
                        'props': {'class': 'pa-3'},
                        'content': [
                            {
                                'component': 'VRow',
                                'props': {'dense': True},
                                'content': [
                                    {
                                        'component': 'VCol',
                                        'props': {'cols': 6, 'md': 3},
                                        'content': [
                                            {
                                                'component': 'div',
                                                'props': {'class': 'text-center'},
                                                'content': [
                                                    {
                                                        'component': 'div',
                                                        'props': {'class': 'text-h6 font-weight-bold text-primary'},
                                                        'text': str(total)
                                                    },
                                                    {
                                                        'component': 'div',
                                                        'props': {'class': 'text-caption text-medium-emphasis'},
                                                        'text': '📊 总签到次数'
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                    {
                                        'component': 'VCol',
                                        'props': {'cols': 6, 'md': 3},
                                        'content': [
                                            {
                                                'component': 'div',
                                                'props': {'class': 'text-center'},
                                                'content': [
                                                    {
                                                        'component': 'div',
                                                        'props': {'class': 'text-h6 font-weight-bold text-success'},
                                                        'text': str(success_count)
                                                    },
                                                    {
                                                        'component': 'div',
                                                        'props': {'class': 'text-caption text-medium-emphasis'},
                                                        'text': '✅ 签到成功'
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                    {
                                        'component': 'VCol',
                                        'props': {'cols': 6, 'md': 3},
                                        'content': [
                                            {
                                                'component': 'div',
                                                'props': {'class': 'text-center'},
                                                'content': [
                                                    {
                                                        'component': 'div',
                                                        'props': {'class': 'text-h6 font-weight-bold text-error'},
                                                        'text': str(fail_count)
                                                    },
                                                    {
                                                        'component': 'div',
                                                        'props': {'class': 'text-caption text-medium-emphasis'},
                                                        'text': '❌ 签到失败'
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                    {
                                        'component': 'VCol',
                                        'props': {'cols': 6, 'md': 3},
                                        'content': [
                                            {
                                                'component': 'div',
                                                'props': {'class': 'text-center'},
                                                'content': [
                                                    {
                                                        'component': 'div',
                                                        'props': {'class': 'text-h6 font-weight-bold text-info'},
                                                        'text': f"{success_rate}%"
                                                    },
                                                    {
                                                        'component': 'div',
                                                        'props': {'class': 'text-caption text-medium-emphasis'},
                                                        'text': '📈 成功率'
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                ]
            },
            {
                'component': 'VCard',
                'props': {'variant': 'elevated', 'elevation': 1},
                'content': [
                    {
                        'component': 'VCardItem',
                        'props': {'class': 'pa-2'},
                        'content': [
                            {
                                'component': 'VCardTitle',
                                'props': {'class': 'text-subtitle-1 font-weight-medium'},
                                'text': '📜 签到历史'
                            },
                            {
                                'component': 'VCardSubtitle',
                                'props': {'class': 'text-caption'},
                                'text': f'显示最近 {min(30, len(histories))} 条（共 {total} 条）'
                            }
                        ]
                    },
                    {
                        'component': 'VCardText',
                        'props': {'class': 'pt-0 pb-2 px-3'},
                        'content': [
                            {
                                'component': 'VSimpleTable',
                                'props': {
                                    'dense': True,
                                    'class': 'elevation-0',
                                    'style': 'width: 100%;'
                                },
                                'content': [
                                    {
                                        'component': 'thead',
                                        'content': [
                                            {
                                                'component': 'tr',
                                                'props': {'style': 'border-bottom: 2px solid #e0e0e0;'},
                                                'content': [
                                                    {
                                                        'component': 'th',
                                                        'props': {'class': 'text-left text-caption font-weight-medium py-1 px-3'},
                                                        'text': '签到时间'
                                                    },
                                                    {
                                                        'component': 'th',
                                                        'props': {'class': 'text-left text-caption font-weight-medium py-1 px-3'},
                                                        'text': '签到结果'
                                                    },
                                                    {
                                                        'component': 'th',
                                                        'props': {'class': 'text-left text-caption font-weight-medium py-1 px-3'},
                                                        'text': '详细信息'
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                    {
                                        'component': 'tbody',
                                        'content': sign_msgs
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ]

    def stop_service(self):
        try:
            if self._scheduler:
                self._scheduler.remove_all_jobs()
                if self._scheduler.running:
                    self._scheduler.shutdown()
                self._scheduler = None
                logger.info("yzyy论坛签到服务已停止")
        except Exception as e:
            logger.error(f"停止插件服务失败：{str(e)}")

    # ========== 核心签到逻辑（修复版） ==========

    def __signin(self):
        """执行签到任务"""
        configured_cookie = self._cookie
        if not configured_cookie:
            self._cookie = self.__fetch_site_cookie()
            if self._cookie:
                self.__persist_cookie(self._cookie)
        if not self._cookie:
            error_msg = "Cookie未配置且 CookieCloud 未匹配到该域名 Cookie"
            logger.error(error_msg)
            self.__save_history(success=False, info=error_msg)
            self.__send_notification("签到失败", error_msg)
            return

        try:
            logger.info("🔄 开始执行 yzyy 论坛签到任务")

            # 获取签到页面HTML
            page_html = self.__fetch_sign_page()
            if page_html is None:
                error_msg = "获取签到页面失败"
                logger.error(f"❌ {error_msg}")
                self.__save_history(success=False, info=error_msg)
                self.__send_notification("签到失败", error_msg)
                return

            # 检查登录状态
            if self.__is_not_logged_in(page_html):
                logger.warning("Cookie 失效，尝试从 CookieCloud 重新获取")
                new_cookie = self.__fetch_site_cookie()
                if new_cookie and new_cookie != self._cookie:
                    self._cookie = new_cookie
                    self.__persist_cookie(self._cookie)
                    page_html = self.__fetch_sign_page()
                    if page_html is None or self.__is_not_logged_in(page_html):
                        error_msg = "Cookie已失效，CookieCloud 重新获取后仍无效"
                        logger.error(f"❌ {error_msg}")
                        self.__save_history(success=False, info=error_msg)
                        self.__send_notification("签到失败", error_msg)
                        return
                else:
                    error_msg = "Cookie已失效，CookieCloud 未匹配到新 Cookie"
                    logger.error(f"❌ {error_msg}")
                    self.__save_history(success=False, info=error_msg)
                    self.__send_notification("签到失败", error_msg)
                    return

            # 【关键修复】先检查签到按钮文本，判断是否已签到
            button_status = self.__check_sign_button_status(page_html)
            if button_status == "already_signed":
                logger.info("✅ 今日已签到（按钮显示今日已打卡）")
                # 提取签到信息
                info = self.__extract_reward_info(page_html)
                self.__save_history(success=True, info=f"今日已签到 | {info}" if info else "今日已签到")
                self.__send_notification("签到完成", f"今日已签到 | {info}" if info else "今日已签到")
                return
            elif button_status == "need_sign":
                logger.info("📝 发现签到按钮，准备执行签到")
            else:
                # 按钮状态未知，继续尝试提取链接
                logger.info("⚠️ 无法确定按钮状态，尝试提取签到链接")

            # 提取签到链接
            sign_url = self.__extract_sign_url(page_html)
            if not sign_url:
                error_msg = "未找到签到链接，可能签到按钮不可用"
                logger.error(f"❌ {error_msg}")
                self.__save_history(success=False, info=error_msg)
                self.__send_notification("签到失败", error_msg)
                return

            logger.info(f"📝 提取到签到链接: {sign_url}")

            # 执行签到请求
            result_html = self.__execute_sign_request(sign_url)
            if result_html is None:
                error_msg = "签到请求失败"
                logger.error(f"❌ {error_msg}")
                self.__save_history(success=False, info=error_msg)
                self.__send_notification("签到失败", error_msg)
                return

            # 签到后重新获取页面，只根据当前用户 .signbtn 区域验证结果
            verify_html = self.__fetch_sign_page()
            if verify_html is None:
                error_msg = "签到后验证页面获取失败"
                logger.error(f"❌ {error_msg}")
                self.__save_history(success=False, info=error_msg)
                self.__send_notification("签到失败", error_msg)
                return

            success, info = self.__parse_sign_result(verify_html)

            if success:
                logger.info(f"✅ 签到成功: {info}")
                self.__save_history(success=True, info=info)
                self.__send_notification("签到成功", info)
            else:
                logger.error(f"❌ 签到失败: {info}")
                self.__save_history(success=False, info=info)
                self.__send_notification("签到失败", info)

        except Exception as e:
            error_msg = f"签到发生异常: {str(e)}"
            logger.error(f"❌ {error_msg}")
            try:
                self.__save_history(success=False, info=error_msg)
            except Exception as history_error:
                logger.error(f"保存签到异常历史失败: {history_error}")
            self.__send_notification("签到异常", error_msg)
        finally:
            if not configured_cookie:
                self._cookie = ""

    def __fetch_sign_page(self) -> Optional[str]:
        """获取签到页面HTML"""
        try:
            headers = self.__build_headers()
            sign_page_url = self.__sign_page_url()
            logger.info(f"🌐 访问签到页面: {sign_page_url}")

            res = RequestUtils(
                headers=headers,
                cookies=self._cookie,
                timeout=self.REQUEST_TIMEOUT
            ).get_res(url=sign_page_url)

            if not res or res.status_code != 200:
                logger.error(f"访问签到页面失败，状态码: {res.status_code if res else '无响应'}")
                return None

            logger.info(f"签到页面访问成功，状态码: {res.status_code}")
            return res.text

        except Exception as e:
            logger.error(f"获取签到页面异常: {str(e)}")
            return None

    def __is_not_logged_in(self, html: str) -> bool:
        """检查是否未登录"""
        keywords = ["请登录", "需要先登录", "请先登录", "未登录", "您还没有登录"]
        return any(keyword in html for keyword in keywords)

    def __check_sign_button_status(self, html: str) -> str:
        """
        检查签到按钮状态

        Returns:
            "already_signed": 已签到（按钮显示"今日已打卡"）
            "need_sign": 需要签到（按钮显示"点击打卡"）
            "unknown": 无法确定
        """
        button_area = self.__extract_sign_button_area(html)
        if not button_area:
            logger.warning("未找到 .signbtn 签到按钮区域，无法判断当前用户签到状态")
            return "unknown"

        if "今日已打卡" in button_area:
            logger.info("🔍 检测到当前用户签到按钮显示'今日已打卡'")
            return "already_signed"
        if "点击打卡" in button_area:
            logger.info("🔍 检测到当前用户签到按钮显示'点击打卡'")
            return "need_sign"
        return "unknown"

    def __extract_sign_url(self, html: str) -> Optional[str]:
        """
        从当前用户签到按钮区域提取签到链接
        """
        button_area = self.__extract_sign_button_area(html)
        if not button_area:
            logger.error("无法从 .signbtn 区域提取签到链接")
            return None

        match = re.search(
            r'<a[^>]*href=["\']([^"\']*plugin\.php\?id=zqlj_sign&(?:amp;)?sign=[a-f0-9]{8}[^"\']*)["\']',
            button_area,
            re.I | re.S
        )
        if not match:
            logger.error("当前用户签到按钮区域未找到签到链接")
            return None

        sign_url = match.group(1).replace("&amp;", "&")
        if sign_url.startswith('plugin.php'):
            sign_url = f"{self._site_url}/{sign_url}"
        elif sign_url.startswith('/'):
            sign_url = f"{self._site_url}{sign_url}"
        elif not sign_url.startswith('http'):
            sign_url = f"{self._site_url}/{sign_url}"
        logger.info(f"提取到签到链接: {sign_url}")
        return sign_url

    def __execute_sign_request(self, sign_url: str) -> Optional[str]:
        """
        执行签到请求 - 移除allow_redirects参数
        """
        try:
            headers = self.__build_headers()
            headers['referer'] = self.__sign_page_url()

            if not sign_url.startswith('http'):
                sign_url = f"{self._site_url}/{sign_url.lstrip('/')}"

            logger.info(f"🌐 执行签到请求: {sign_url}")

            res = RequestUtils(
                headers=headers,
                cookies=self._cookie,
                timeout=self.REQUEST_TIMEOUT
            ).get_res(url=sign_url)

            if not res:
                logger.error("签到请求无响应")
                return None

            if res.status_code != 200:
                logger.error(f"签到请求失败，状态码: {res.status_code}")
                return None

            # 检查响应内容是否包含登录提示
            if res.text and ("请登录" in res.text or "需要先登录" in res.text):
                logger.error("签到响应包含登录提示，Cookie可能已失效")
                return None

            return res.text

        except Exception as e:
            logger.error(f"签到请求异常: {str(e)}")
            return None

    def __parse_sign_result(self, html: str) -> Tuple[bool, str]:
        """
        解析签到结果：只根据当前用户 .signbtn 区域判断，不全局搜索排行榜状态。
        """
        try:
            button_status = self.__check_sign_button_status(html)
            if button_status == "already_signed":
                info = self.__extract_reward_info(html)
                return True, info or "今日已打卡"
            if button_status == "need_sign":
                return False, "签到后按钮仍显示点击打卡"
            return False, "无法识别当前用户签到按钮状态"

        except Exception as e:
            return False, f"解析签到结果异常: {str(e)}"

    def __extract_reward_info(self, html: str) -> str:
        """提取当前用户签到奖励信息 - 优先限定在我的记录区域"""
        try:
            import html as html_module
            html = html_module.unescape(html)
            my_area = self.__extract_my_record_area(html)
            if my_area:
                html = my_area
            info_parts = []

            # 1. 提取"最近奖励"（本次签到获得的影币）
            recent_match = re.search(r'最近奖励[：:]\s*([\d.]+)\s*影币', html)
            if recent_match:
                value = recent_match.group(1).strip()
                info_parts.append(f"获得 {value} 影币")
            else:
                # 备用：提取"累计奖励"（如果最近奖励没有）
                total_match = re.search(r'累计奖励[：:]\s*([\d.]+)\s*影币', html)
                if total_match:
                    value = total_match.group(1).strip()
                    info_parts.append(f"累计 {value} 影币")

            # 2. 提取连续打卡天数
            continuous_match = re.search(r'连续打卡[：:]\s*([\d.]+)\s*天', html)
            if continuous_match:
                value = continuous_match.group(1).strip()
                info_parts.append(f"连续 {value} 天")

            # 3. 提取累计打卡天数
            total_days_match = re.search(r'累计打卡[：:]\s*([\d.]+)\s*天', html)
            if total_days_match:
                value = total_days_match.group(1).strip()
                info_parts.append(f"累计 {value} 天")

            # 4. 提取本月打卡天数
            month_match = re.search(r'本月打卡[：:]\s*([\d.]+)\s*天', html)
            if month_match:
                value = month_match.group(1).strip()
                info_parts.append(f"本月 {value} 天")

            # 5. 提取打卡等级
            level_match = re.search(r'当前打卡等级[：:]\s*([^\s<]+)', html)
            if level_match:
                level = level_match.group(1).strip()
                info_parts.append(f"等级: {level}")

            # 6. 提取"最近打卡"时间
            time_match = re.search(r'最近打卡[：:]\s*([\d\-:\s]+)', html)
            if time_match:
                # 不加入奖励信息，只作为日志
                logger.debug(f"最近打卡时间: {time_match.group(1).strip()}")

            # 如果没有提取到任何信息
            if not info_parts:
                # 尝试检查是否有影币关键词
                if "影币" in html:
                    info_parts.append("签到成功")
                else:
                    return ""

            return " | ".join(info_parts)

        except Exception as e:
            logger.error(f"提取奖励信息异常: {e}")
            return ""

    def __extract_sign_button_area(self, html: str) -> str:
        """提取当前用户签到按钮 .signbtn 区域。"""
        try:
            tree = etree.HTML(html or "")
            nodes = tree.xpath('//div[contains(concat(" ", normalize-space(@class), " "), " signbtn ")]')
            if nodes:
                return etree.tostring(nodes[0], encoding="unicode", method="html")
        except Exception as e:
            logger.warning(f"解析签到按钮区域失败: {e}")
        return ""

    def __extract_my_record_area(self, html: str) -> str:
        """提取我的记录区域，避免从排行榜提取其他用户奖励。"""
        match = re.search(r'<tbody[^>]*id=["\']tb_my["\'][^>]*>(.*?)</tbody>', html or "", re.I | re.S)
        if match:
            return match.group(1)
        match = re.search(r'<div[^>]*id=["\']ct_mine["\'][^>]*>(.*?)</div>', html or "", re.I | re.S)
        if match:
            return match.group(1)
        return ""

    def __fetch_site_cookie(self) -> str:
        """Cookie 留空时从 CookieCloud 按 site_url 域名获取"""
        try:
            from app.helper.cookiecloud import CookieCloudHelper
            cookies, _ = CookieCloudHelper().download()
            if not cookies:
                logger.info(f"CookieCloud 未配置或无数据，跳过补取（{self._site_url}）")
                return ""
            site_domain = urlparse(self._site_url).hostname or ""
            for domain, cookie in cookies.items():
                if not cookie:
                    continue
                if site_domain and (domain == site_domain or site_domain.endswith(domain) or domain.endswith(site_domain)):
                    logger.info(f"CookieCloud 匹配到 {site_domain} 的 Cookie")
                    return cookie
            logger.info(f"CookieCloud 未匹配到 {site_domain} 的 Cookie")
            return ""
        except Exception as e:
            logger.warning(f"从 CookieCloud 获取 Cookie 失败: {e}")
            return ""

    def __persist_cookie(self, cookie: str):
        """将 CookieCloud 匹配到的 Cookie 保存到插件配置，下次直接复用"""
        try:
            cur = self.get_config() or {}
            if cur.get("cookie") == cookie:
                return
            cur["cookie"] = cookie
            self.update_config(cur)
            self._cookie = cookie
            logger.info("已将 CookieCloud 匹配到的 Cookie 保存到插件配置")
        except Exception as e:
            logger.warning(f"保存 Cookie 到配置失败: {e}")

    def __normalize_site_url(self, site_url: str) -> str:
        """规范化站点地址。"""
        site_url = (site_url or self.DEFAULT_SITE_URL).strip().rstrip('/')
        if not site_url:
            return self.DEFAULT_SITE_URL
        if not site_url.startswith(("http://", "https://")):
            site_url = f"https://{site_url}"
        if site_url.startswith("http://"):
            site_url = "https://" + site_url[len("http://"):]
        return site_url

    def __sign_page_url(self) -> str:
        """签到页地址。"""
        return f"{self._site_url}/plugin.php?id=zqlj_sign"

    def __build_headers(self) -> Dict[str, str]:
        """构建请求头"""
        return {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'cache-control': 'no-cache',
            'pragma': 'no-cache',
            'referer': self.__sign_page_url(),
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36'
        }

    def __save_history(self, success: bool, info: str = ""):
        """保存签到历史"""
        history = self.get_data('history') or []
        if not isinstance(history, list):
            history = []

        history.append({
            "date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "result": "成功" if success else "失败",
            "info": info or ("签到成功" if success else "签到失败")
        })

        if self._history_days > 0:
            cutoff = time.time() - int(self._history_days) * 24 * 60 * 60
            kept_history = []
            for h in history:
                try:
                    if datetime.strptime(h["date"], '%Y-%m-%d %H:%M:%S').timestamp() >= cutoff:
                        kept_history.append(h)
                except (KeyError, TypeError, ValueError):
                    kept_history.append(h)
            history = kept_history

        if len(history) > self.MAX_HISTORY:
            history = history[-self.MAX_HISTORY:]

        self.save_data("history", history)
        logger.info(f"签到历史已保存，当前共 {len(history)} 条记录")

    def __send_notification(self, title: str, text: str):
        """发送通知"""
        if self._notify:
            try:
                self.post_message(
                    mtype=NotificationType.SiteMessage,
                    title=f"【yzyy论坛签到】{title}",
                    text=text
                )
                logger.info(f"通知已发送: {title}")
            except Exception as e:
                logger.error(f"发送通知失败: {e}")