import random
import re
import time
from datetime import datetime
from http.cookies import SimpleCookie
from typing import Optional

from app.log import logger

from .http_client import ForumSigninHttpClient
from .models import ForumSigninConfig, PluginCallbacks
from .ui import format_money


class InvitesService:
    """药丸登录、Cookie 刷新、签到与拥塞退避业务。"""

    site_url = "https://invites.fun"
    user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0"
    )
    congestion_status_codes = {429, 502, 503, 504}

    def __init__(self, config: ForumSigninConfig, callbacks: PluginCallbacks):
        self.config = config
        self.callbacks = callbacks

    def signin(self, retry_count=0, max_retries=3):
        return self.__invites_signin(retry_count=retry_count, max_retries=max_retries)

    def __backoff_sleep(self, attempt: int, response=None, base_seconds: int = 3, max_seconds: int = 90):
        """
        对拥塞/限流响应进行指数退避，并添加随机抖动。
        """
        retry_after = None
        try:
            if response is not None:
                retry_after_header = response.headers.get('Retry-After')
                if retry_after_header and str(retry_after_header).isdigit():
                    retry_after = int(retry_after_header)
        except Exception:
            retry_after = None

        if retry_after is None:
            retry_after = min(max_seconds, base_seconds * (2 ** attempt))
        jitter = random.uniform(0.5, 3.0)
        sleep_seconds = retry_after + jitter
        logger.info(f"药丸站点拥塞或限流，退避 {sleep_seconds:.1f} 秒后重试")
        time.sleep(sleep_seconds)

    def __get_remember_value(self, cookie: str) -> Optional[str]:
        """从cookie字符串中提取flarum_remember值"""
        remember_match = re.search(r'flarum_remember=([^;]+)', cookie or "")
        if remember_match:
            return remember_match.group(1)
        return None

    def __parse_cookie_string(self, cookie_str: str) -> dict:
        """安全地解析cookie字符串，返回cookie字典"""
        try:
            cookie = SimpleCookie()
            cookie.load(cookie_str or "")
            cookies = {}
            if 'flarum_remember' in cookie:
                cookies['flarum_remember'] = cookie['flarum_remember'].value
            if 'flarum_session' in cookie:
                cookies['flarum_session'] = cookie['flarum_session'].value
            return cookies
        except Exception as e:
            logger.error(f"解析cookie字符串失败: {e}")
            return {}

    def __build_api_headers(self, csrf_token: str, referer: str = "https://invites.fun/") -> dict:
        """
        构建药丸 API 请求头，贴近前端真实签到请求。
        """
        return {
            'accept': '*/*',
            'accept-language': 'zh-CN,zh-Hans;q=0.9',
            'origin': self.site_url,
            'referer': referer,
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'x-csrf-token': csrf_token,
            'user-agent': self.user_agent
        }

    @staticmethod

    def __extract_checkin_state(payload: dict) -> dict:
        """
        从药丸 JSON:API 用户响应中提取签到状态字段。
        """
        if not isinstance(payload, dict):
            return {}

        data = payload.get('data')
        if not isinstance(data, dict):
            return {}

        attrs = data.get('attributes')
        if not isinstance(attrs, dict):
            return {}

        return {
            "user_id": str(data.get('id') or ""),
            "username": attrs.get('username') or "",
            "displayName": attrs.get('displayName') or attrs.get('username') or "",
            "avatarUrl": attrs.get('avatarUrl') or "",
            "discussionCount": attrs.get('discussionCount'),
            "commentCount": attrs.get('commentCount'),
            "joinTime": attrs.get('joinTime') or "",
            "lastSeenAt": attrs.get('lastSeenAt') or "",
            "unreadNotificationCount": attrs.get('unreadNotificationCount'),
            "followerCount": attrs.get('followerCount'),
            "canCheckin": attrs.get('canCheckin'),
            "lastCheckinTime": attrs.get('lastCheckinTime') or "",
            "totalContinuousCheckIn": attrs.get('totalContinuousCheckIn'),
            "lastCheckinMoney": attrs.get('lastCheckinMoney', 0),
            "money": attrs.get('money')
        }

    def __request_invites_with_backoff(self, method: str, url: str, **kwargs):
        """药丸请求统一退避包装，覆盖限流与拥塞状态码。"""
        max_attempts = kwargs.pop("max_attempts", 4)
        request_kwargs = kwargs.copy()
        for attempt in range(max_attempts):
            try:
                if attempt > 0:
                    logger.info(f"正在重试药丸请求 {method.upper()} ({attempt}/{max_attempts - 1})")
                call_kwargs = request_kwargs.copy()
                request = ForumSigninHttpClient(
                    proxy_url=call_kwargs.pop("proxies", self.callbacks.get_proxy_url()),
                    proxy_enabled=self.config.use_proxy,
                    timeout=call_kwargs.pop("timeout", 30),
                    **{key: call_kwargs.pop(key) for key in list(call_kwargs.keys()) if key in ("headers", "cookies")}
                )
                if method.lower() == "post":
                    response = request.post_res(url=url, **call_kwargs)
                else:
                    response = request.get_res(url=url, **call_kwargs)
            except Exception as e:
                logger.error(f"药丸请求 {method.upper()} {url} 异常: {e}")
                if attempt < max_attempts - 1:
                    self.__backoff_sleep(attempt)
                    continue
                return None

            if response is None:
                logger.error(f"药丸请求 {method.upper()} {url} 失败：无响应")
                if attempt < max_attempts - 1:
                    self.__backoff_sleep(attempt)
                    continue
                return None

            if response.status_code in self.congestion_status_codes and attempt < max_attempts - 1:
                logger.warning(f"药丸请求 {method.upper()} {url} 遇到拥塞状态码: {response.status_code}")
                self.__backoff_sleep(attempt, response=response)
                continue
            return response
        return None

    def __fetch_checkin_state(self, user_id: str, cookies: dict, csrf_token: str) -> dict:
        """
        查询用户当前签到状态，用于签到前判断和签到后复核。
        """
        try:
            response = self.__request_invites_with_backoff(
                "get",
                f'{self.site_url}/api/users/{user_id}',
                cookies=cookies,
                headers=self.__build_api_headers(csrf_token),
                timeout=30
            )
            if response is None:
                logger.error("查询药丸签到状态失败：无响应")
                return {}
            if response.status_code != 200:
                logger.error(f"查询药丸签到状态失败，状态码: {response.status_code}")
                return {}
            return self.__extract_checkin_state(response.json())
        except Exception as e:
            logger.error(f"查询药丸签到状态异常: {e}")
            return {}

    @staticmethod

    def __is_today_checkin(state: dict) -> bool:
        """
        判断签到状态是否已经落到当天。
        """
        last_checkin_time = str((state or {}).get("lastCheckinTime") or "")
        return bool(last_checkin_time and last_checkin_time.startswith(datetime.now().strftime('%Y-%m-%d')))

    @staticmethod

    def __get_response_error_message(response) -> str:
        """
        从药丸接口错误响应中提取可读提示。
        """
        if response is None:
            return "无响应"

        try:
            payload = response.json()
            errors = payload.get("errors") if isinstance(payload, dict) else None
            if errors:
                messages = []
                for error in errors:
                    if not isinstance(error, dict):
                        continue
                    message = error.get("detail") or error.get("title") or error.get("code")
                    if message:
                        messages.append(str(message))
                if messages:
                    return "；".join(messages)
        except Exception:
            pass

        text = getattr(response, "text", "") or ""
        return text[:200] if text else f"HTTP {response.status_code}"

    def __get_new_session(self, flarum_remember: str) -> Optional[dict]:
        """使用长期 flarum_remember 一次请求刷新 session 并解析首页状态。"""
        headers = {
            "Cookie": f"flarum_remember={flarum_remember}",
            "User-Agent": self.user_agent,
            "Upgrade-Insecure-Requests": "1",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
        }
        response = self.__request_invites_with_backoff(
            "get",
            self.site_url,
            headers=headers,
            timeout=30,
            allow_redirects=False
        )
        if response is None or response.status_code != 200:
            logger.error(f"刷新药丸 session 失败，状态码: {response.status_code if response else '无响应'}")
            return None

        flarum_session = response.cookies.get('flarum_session')
        if not flarum_session:
            cookies = response.headers.get('Set-Cookie', '') or response.headers.get('set-cookie', '')
            session_match = re.search(r'flarum_session=([^;]+)', cookies)
            flarum_session = session_match.group(1) if session_match else None

        csrf_match = re.search(r'"csrfToken":"(.*?)"', response.text or "")
        user_match = re.search(r'"userId":(\d+)', response.text or "")
        if not flarum_session or not csrf_match or not user_match or user_match.group(1) == "0":
            logger.error("刷新药丸 session 失败：remember 可能失效，未获取到有效 session/csrfToken/userId")
            return None

        return {"flarum_session": flarum_session, "csrf_token": csrf_match.group(1), "user_id": user_match.group(1)}

    def __get_homepage_state(self, cookie_str: str) -> Optional[dict]:
        """使用新 Cookie 获取首页中的 csrfToken 和 userId"""
        headers = {
            "Cookie": cookie_str,
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Upgrade-Insecure-Requests": "1"
        }
        response = self.__request_invites_with_backoff(
            "get",
            self.site_url,
            headers=headers,
            timeout=30
        )

        if not response or response.status_code != 200:
            logger.error(f"请求药丸首页失败，状态码: {response.status_code if response else '无响应'}")
            return None

        csrf_match = re.search(r'"csrfToken":"(.*?)"', response.text or "")
        if not csrf_match:
            logger.error("请求药丸 csrfToken 失败")
            return None

        user_match = re.search(r'"userId":(\d+)', response.text or "")
        if not user_match or user_match.group(1) == "0":
            logger.error("未找到有效的药丸 userId")
            return None

        csrf_token = csrf_match.group(1)
        user_id = user_match.group(1)
        logger.info(f"获取药丸 csrfToken 和 userId 成功，userId: {user_id}")
        return {"csrf_token": csrf_token, "user_id": user_id}

    def __login_with_credentials(self) -> dict:
        """使用用户名和密码登录药丸"""
        if not self.config.invites_username or not self.config.invites_password:
            return {"success": False, "error": "未配置用户名或密码"}

        headers_get = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'User-Agent': self.user_agent,
            'Upgrade-Insecure-Requests': '1'
        }
        proxies = self.callbacks.get_proxy_url()
        response_get = self.__request_invites_with_backoff(
            "get",
            f'{self.site_url}/',
            headers=headers_get,
            proxies=proxies,
            timeout=30
        )

        if not response_get or response_get.status_code != 200:
            return {"success": False, "error": "获取初始session失败"}

        flarum_session = response_get.cookies.get('flarum_session')
        csrf_token = response_get.headers.get('x-csrf-token') or (
            re.findall(r'"csrfToken":"(.*?)"', response_get.text or "") or [None]
        )[0]

        if not flarum_session:
            return {"success": False, "error": "未获取到flarum_session"}
        if not csrf_token:
            return {"success": False, "error": "未获取到csrf token"}

        cookies_login = {'flarum_session': flarum_session}
        headers_login = {
            'Accept': '*/*',
            'Content-Type': 'application/json; charset=UTF-8',
            'Origin': self.site_url,
            'Referer': f'{self.site_url}/',
            'x-csrf-token': csrf_token,
            'User-Agent': self.user_agent
        }
        json_data_login = {
            'identification': self.config.invites_username,
            'password': self.config.invites_password,
            'remember': True,
        }

        login_response = self.__request_invites_with_backoff(
            "post",
            f'{self.site_url}/login',
            cookies=cookies_login,
            headers=headers_login,
            proxies=proxies,
            timeout=30,
            json=json_data_login
        )

        if not login_response or login_response.status_code != 200:
            status = login_response.status_code if login_response else '无响应'
            reason = self.__get_response_error_message(login_response) if login_response else '无响应'
            return {"success": False, "error": f"登录失败：HTTP {status} {reason}"}

        flarum_remember = login_response.cookies.get('flarum_remember')
        flarum_session_new = login_response.cookies.get('flarum_session')
        csrf_token_new = login_response.headers.get('X-CSRF-Token') or login_response.headers.get('x-csrf-token') or csrf_token

        if not flarum_remember or not flarum_session_new:
            return {"success": False, "error": "登录后未获取到有效Cookie"}

        try:
            login_data = login_response.json()
            user_id = login_data.get('userId')
        except Exception as e:
            logger.error(f"解析药丸登录响应失败: {e}")
            user_id = None

        if not user_id:
            cookie_str = f"flarum_remember={flarum_remember}; flarum_session={flarum_session_new}"
            homepage_state = self.__get_homepage_state(cookie_str)
            user_id = homepage_state.get("user_id") if homepage_state else None
            csrf_token_new = homepage_state.get("csrf_token") if homepage_state else csrf_token_new

        if not user_id:
            return {"success": False, "error": "登录后未获取到用户ID"}

        logger.info(f"药丸登录成功，用户ID: {user_id}")
        return {
            "success": True,
            "flarum_remember": flarum_remember,
            "flarum_session": flarum_session_new,
            "csrf_token": csrf_token_new,
            "user_id": str(user_id)
        }

    def __update_cookie_if_changed(self, new_cookie_str: str):
        """
        检查Cookie是否发生变化，如果有变化则更新配置。
        """
        try:
            if not new_cookie_str:
                return

            new_cookies = self.__parse_cookie_string(new_cookie_str)
            new_remember = new_cookies.get('flarum_remember')
            new_session = new_cookies.get('flarum_session')
            if not new_remember or not new_session:
                return

            old_cookies = self.__parse_cookie_string(self.config.invites_cookie or "")
            old_remember = old_cookies.get('flarum_remember')
            old_session = old_cookies.get('flarum_session')

            if new_remember != old_remember or new_session != old_session:
                self.config.invites_cookie = f"flarum_remember={new_remember}; flarum_session={new_session}"
                logger.info("药丸 Cookie 已更新，保存新配置")
                self.callbacks.persist_config()
            else:
                logger.debug("药丸 Cookie 未发生变化，无需更新")
        except Exception as e:
            logger.error(f"更新药丸 Cookie 配置失败: {e}")

    def __save_success(self, state: dict, already_signed: bool = False):
        """保存成功签到状态并发送通知"""
        checkin_time = str((state or {}).get("lastCheckinTime") or "") or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        status_text = "已签到" if already_signed else "签到成功"
        record = {
            "site": "invites",
            "date": checkin_time,
            "status": status_text,
            "status_code": "success_already" if already_signed else "success_new",
            "money": (state or {}).get("money"),
            "totalContinuousCheckIn": (state or {}).get("totalContinuousCheckIn"),
            "lastCheckinMoney": (state or {}).get("lastCheckinMoney", 0),
            "failure_count": 0
        }
        self.callbacks.save_history(record)
        self.callbacks.save_data("invites_user_info", {"data": {"id": (state or {}).get("user_id"), "attributes": state or {}}})
        self.callbacks.save_data("invites_user_info_updated_at", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

        if self.config.notify:
            money = format_money(record.get("money"))
            reward = format_money(record.get("lastCheckinMoney"))
            reward_text = "今日已领取奖励" if already_signed else f"获得 {reward} 个药丸奖励"
            self.callbacks.send_notification(
                title=f"【✅ 药丸{status_text}】",
                text=(
                    f"📢 执行结果\n"
                    f"━━━━━━━━━━\n"
                    f"🕐 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"✨ 状态：{status_text}\n"
                    f"🎁 奖励：{reward_text}\n"
                    f"━━━━━━━━━━\n"
                    f"📊 积分统计\n"
                    f"💊 药丸：{money}\n"
                    f"📆 签到天数：{record.get('totalContinuousCheckIn')}\n"
                    f"━━━━━━━━━━"
                )
            )

    def __perform_checkin(self, user_id: str, cookie_str: str, csrf_token: str) -> bool:
        """执行实际的签到操作"""
        try:
            headers = self.__build_api_headers(csrf_token)
            cookies = self.__parse_cookie_string(cookie_str)
            if not cookies.get('flarum_remember') or not cookies.get('flarum_session'):
                logger.error("药丸 Cookie 中缺少 flarum_remember 或 flarum_session")
                return False

            before_state = self.__fetch_checkin_state(user_id, cookies, csrf_token)
            if before_state and before_state.get("canCheckin") is False and self.__is_today_checkin(before_state):
                logger.info("药丸今日已签到，跳过重复签到")
                self.__save_success(before_state, already_signed=True)
                return True

            checkin_url = f'{self.site_url}/api/checkin'
            response = self.__request_invites_with_backoff(
                "post",
                checkin_url,
                cookies=cookies,
                headers=headers,
                timeout=30
            )

            if response is None:
                return False

            if response.status_code != 200:
                error_message = self.__get_response_error_message(response)
                logger.error(f"药丸签到请求失败，状态码: {response.status_code}，原因: {error_message}")
                after_state = self.__fetch_checkin_state(user_id, cookies, csrf_token)
                if after_state and after_state.get("canCheckin") is False and self.__is_today_checkin(after_state):
                    logger.info("药丸站点状态显示今日已签到")
                    self.__save_success(after_state, already_signed=True)
                    return True
                return False

            try:
                checkin_data = response.json()
                checkin_state = self.__extract_checkin_state(checkin_data)
                if not checkin_state:
                    logger.error("药丸签到响应缺少用户状态数据")
                    return False
                if checkin_state.get("canCheckin") is not False or not self.__is_today_checkin(checkin_state):
                    logger.error(f"药丸签到响应未确认今日已签到: {checkin_state}")
                    after_state = self.__fetch_checkin_state(user_id, cookies, csrf_token)
                    if after_state and after_state.get("canCheckin") is False and self.__is_today_checkin(after_state):
                        self.__save_success(after_state, already_signed=True)
                        return True
                    return False

                logger.info("药丸签到成功")
                self.__save_success(checkin_state)
                return True
            except Exception as e:
                logger.error(f"解析药丸签到响应失败: {e}")
                logger.error(f"药丸签到响应内容: {response.text if response else 'None'}")
                after_state = self.__fetch_checkin_state(user_id, cookies, csrf_token)
                if after_state and after_state.get("canCheckin") is False and self.__is_today_checkin(after_state):
                    self.__save_success(after_state, already_signed=True)
                    return True
                return False
        except Exception as e:
            logger.error(f"执行药丸签到过程中发生异常: {e}")
            return False

    def __get_invites_auth_context(self) -> dict:
        """获取药丸统一认证上下文。"""
        if self.config.invites_cookie and self.config.invites_cookie.strip():
            flarum_remember = self.__get_remember_value(self.config.invites_cookie)
            if flarum_remember:
                session_state = self.__get_new_session(flarum_remember)
                if session_state:
                    cookie_str = f"flarum_remember={flarum_remember}; flarum_session={session_state['flarum_session']}"
                    cookies = self.__parse_cookie_string(cookie_str)
                    return {
                        "cookie_str": cookie_str,
                        "cookies": cookies,
                        "csrf_token": session_state["csrf_token"],
                        "user_id": session_state["user_id"],
                        "source": "remember_refresh",
                        "remember_valid": True,
                        "should_persist_cookie": True
                    }
                logger.warning("药丸 flarum_remember 已失效或无法刷新 session")
            else:
                cookies = self.__parse_cookie_string(self.config.invites_cookie)
                if cookies.get('flarum_session'):
                    homepage_state = self.__get_homepage_state(self.config.invites_cookie)
                    if homepage_state:
                        return {
                            "cookie_str": self.config.invites_cookie,
                            "cookies": cookies,
                            "csrf_token": homepage_state["csrf_token"],
                            "user_id": homepage_state["user_id"],
                            "source": "session_cookie",
                            "remember_valid": False,
                            "should_persist_cookie": False
                        }

        login_result = self.__login_with_credentials()
        if not login_result.get("success"):
            return {"success": False, "error": login_result.get("error", "登录失败"), "remember_valid": False}

        cookie_str = f"flarum_remember={login_result['flarum_remember']}; flarum_session={login_result['flarum_session']}"
        return {
            "cookie_str": cookie_str,
            "cookies": self.__parse_cookie_string(cookie_str),
            "csrf_token": login_result["csrf_token"],
            "user_id": login_result["user_id"],
            "source": "credentials",
            "remember_valid": True,
            "should_persist_cookie": True
        }

    def __invites_signin(self, retry_count=0, max_retries=3):
        """
        药丸签到
        """
        if hasattr(self, '_invites_signing_in') and self._invites_signing_in:
            logger.info("已有药丸签到任务在执行，跳过当前任务")
            return False

        self._invites_signing_in = True
        attempt = 0
        last_reason = "未知错误"
        try:
            if not self.config.invites_cookie and (not self.config.invites_username or not self.config.invites_password):
                last_reason = "未配置 Cookie，也未配置用户名密码"
                logger.error(last_reason)
                self.callbacks.send_signin_failure_notification(last_reason, 0, site='invites')
                return False

            for attempt in range(max_retries + 1):
                if attempt > 0:
                    wait_seconds = 3 + random.uniform(0, 2)
                    logger.info(f"正在进行第 {attempt}/{max_retries} 次快速重试，等待 {wait_seconds:.1f} 秒...")
                    time.sleep(wait_seconds)

                auth_context = self.__get_invites_auth_context()
                if not auth_context.get("user_id"):
                    last_reason = auth_context.get("error", "药丸认证失败")
                    if "未配置" in last_reason or "登录失败" in last_reason or "403" in last_reason:
                        break
                    continue

                if auth_context.get("should_persist_cookie"):
                    self.__update_cookie_if_changed(auth_context["cookie_str"])

                logger.info(f"开始执行药丸签到，认证来源: {auth_context.get('source')}")
                if self.__perform_checkin(auth_context["user_id"], auth_context["cookie_str"], auth_context["csrf_token"]):
                    if self.config.invites_current_retry > 0:
                        logger.info("药丸签到重试成功，重置重试计数")
                        self.config.invites_current_retry = 0
                    return True

                last_reason = "药丸签到失败"

            raise Exception(last_reason)
        except Exception as e:
            reason = str(e)
            logger.error(f"药丸签到过程发生异常: {reason}")

            failure_history_record = {
                "site": "invites",
                "date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "status": "签到失败",
                "status_code": "failed",
                "reason": reason,
                "failure_count": 1
            }
            self.callbacks.save_history(failure_history_record)
            self.callbacks.send_signin_failure_notification(reason, attempt, site='invites')

            if self.config.retry_count > 0 and self.config.invites_current_retry < self.config.retry_count:
                self.config.invites_current_retry += 1
                logger.info(f"安排第{self.config.invites_current_retry}次药丸定时重试，将在{self.config.retry_interval}分钟后重试")
                self.callbacks.schedule_retry(site='invites', minutes=self.config.retry_interval)
            else:
                if self.config.retry_count > 0:
                    logger.info("药丸签到已达到最大定时重试次数，不再重试")
                self.config.invites_current_retry = 0
            return False
        finally:
            self._invites_signing_in = False
