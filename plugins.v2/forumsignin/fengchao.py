import json
import random
import re
import time
from datetime import datetime
from typing import Any

from app.core.config import settings
from app.log import logger

from .http_client import ForumSigninHttpClient
from .models import ForumSigninConfig, PluginCallbacks


class FengchaoService:
    """蜂巢签到、登录、个人信息与 PT 人生数据业务。"""

    congestion_status_codes = {429, 502, 503, 504}

    def __init__(self, config: ForumSigninConfig, callbacks: PluginCallbacks):
        self.config = config
        self.callbacks = callbacks

    def signin(self, retry_count=0, max_retries=3):
        return self.__fengchao_signin(retry_count=retry_count, max_retries=max_retries)

    def update_user_info(self, is_scheduled_run: bool = False):
        return self.__update_user_info(is_scheduled_run=is_scheduled_run)

    def check_and_push_mp_stats(self):
        return self.__check_and_push_mp_stats()

    def __update_user_info(self, is_scheduled_run: bool = False):
        """
        仅更新用户信息，不执行签到
        :param is_scheduled_run: 是否为定时任务调用，用于判断是否启用重试
        """
        logger.info("开始执行蜂巢用户信息更新任务...")
        try:
            if not self.config.fengchao_username or not self.config.fengchao_password:
                raise Exception("未配置用户名和密码")

            proxies = self.callbacks.get_proxy_url()
            cookie = self._get_fengchao_auth_cookie(proxies)
            if not cookie:
                raise Exception("登录失败，无法获取Cookie")

            res_main = None
            try:
                res_main = ForumSigninHttpClient(cookies=cookie, proxy_url=proxies, proxy_enabled=self.config.use_proxy, timeout=30).get_res(url="https://pting.club")
            except Exception as e:
                logger.error(f"访问主页时发生网络错误: {e}")
                raise Exception(f"访问主页失败: {e}")

            if not res_main or res_main.status_code != 200:
                raise Exception(f"访问主页失败，状态码: {res_main.status_code if res_main else 'N/A'}")

            match = re.search(r'"userId":(\d+)', res_main.text)
            if not match or match.group(1) == "0":
                raise Exception("无法从主页获取有效的用户ID")

            userId = match.group(1)

            res_api = None
            api_url = f"https://pting.club/api/users/{userId}"

            logger.info(f"正在使用API URL: {api_url}")
            try:
                res_api = ForumSigninHttpClient(cookies=cookie, proxy_url=proxies, proxy_enabled=self.config.use_proxy, timeout=30).get_res(url=api_url)
            except Exception as e:
                logger.error(f"请求API时发生网络错误: {e}")
                raise Exception(f"API请求失败: {e}")

            if not res_api or res_api.status_code != 200:
                raise Exception(f"API请求失败，状态码: {res_api.status_code if res_api else 'N/A'}")

            user_info = res_api.json()
            self.callbacks.save_data("fengchao_user_info", user_info)
            self.callbacks.save_data("fengchao_user_info_updated_at", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

            # --- 同步签到历史记录 START ---
            try:
                attrs = user_info.get('data', {}).get('attributes', {})
                last_checkin_time = attrs.get('lastCheckinTime')
                if last_checkin_time:
                    # API返回的时间格式例如 "2025-12-01 07:35:15"
                    today_str = datetime.now().strftime('%Y-%m-%d')
                    # 检查是否是今天的签到
                    if last_checkin_time.startswith(today_str):
                        # 获取现有历史记录
                        history = self.callbacks.get_data('history') or []
                        record_date = last_checkin_time.split(" ")[0]
                        skip_update = False

                        # 检查今天是否已有“成功”或“已签到”的记录
                        for item in history:
                            if item.get("site", "fengchao") == "fengchao" and item.get("date", "").startswith(record_date):
                                current_status = item.get("status", "")
                                # 核心修复：如果已经是“成功”或“已签到”状态，则跳过覆盖，防止丢失详细奖励信息
                                if "成功" in current_status or "已签到" in current_status:
                                    skip_update = True
                                    logger.info(f"今日已存在有效签到记录({current_status})，跳过从用户信息同步签到状态")
                                break

                        if not skip_update:
                            history_record = {
                                "site": "fengchao",
                                "date": last_checkin_time,
                                "status": "已签到",  # 标记为已签到
                                "status_code": "success_already",
                                "money": attrs.get('money', 0),
                                "totalContinuousCheckIn": attrs.get('totalContinuousCheckIn', 0),
                                "lastCheckinMoney": attrs.get('lastCheckinMoney', 0),
                                "failure_count": 0
                            }
                            # 保存到历史记录（_save_history 会处理覆盖逻辑）
                            self.callbacks.save_history(history_record)
                            logger.info(f"同步个人信息时检测到今日已签到，已更新本地记录。奖励: {attrs.get('lastCheckinMoney', 0)}")
            except Exception as e:
                logger.warning(f"同步签到历史记录失败: {e}")
            # --- 同步签到历史记录 END ---

            logger.info("成功更新并保存了蜂巢用户信息。")

            try:
                user_attrs = user_info.get('data', {}).get('attributes', {})
                unread_notifications = user_attrs.get('unreadNotificationCount', 0)
                if unread_notifications > 0:
                    logger.info(f"检测到 {unread_notifications} 条未读消息，发送通知。")
                    self.callbacks.send_notification(
                        title=f"【📢 蜂巢论坛消息提醒】",
                        text=f"您有 {unread_notifications} 条未读消息待处理，请及时访问蜂巢论坛查看。"
                    )
            except Exception as e:
                logger.warning(f"检查未读消息时发生错误: {e}")

            if is_scheduled_run:
                self.config.timed_update_current_retry = 0

            self.callbacks.send_notification(
                title="【✅ 蜂巢信息更新成功】",
                text=f"已成功获取并刷新您的蜂巢论坛个人信息。\n"
                     f"🕐 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

        except Exception as e:
            logger.error(f"更新蜂巢用户信息失败: {e}")
            if is_scheduled_run:
                self.callbacks.send_info_update_failure_notification(reason=str(e))
                if self.config.timed_update_retry_count > 0 and self.config.timed_update_current_retry < self.config.timed_update_retry_count:
                    self.config.timed_update_current_retry += 1
                    self.callbacks.schedule_info_update_retry()
                else:
                    if self.config.timed_update_retry_count > 0:
                        logger.info("用户信息更新已达到最大定时重试次数，不再重试")
                    self.config.timed_update_current_retry = 0
            else:
                self.callbacks.send_notification(
                    title="【❌ 蜂巢信息更新失败】",
                    text=f"在尝试刷新您的蜂巢论坛个人信息时发生错误。\n"
                         f"💬 原因：{e}\n"
                         f"🕐 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
        finally:
            if not is_scheduled_run:
                self.config.update_info_now = False
                self.callbacks.persist_config()

    def __fengchao_signin(self, retry_count=0, max_retries=3):
        """
        蜂巢签到
        """
        # 增加任务锁，防止重复执行
        if hasattr(self, '_fengchao_signing_in') and self._fengchao_signing_in:
            logger.info("已有签到任务在执行，跳过当前任务")
            return

        self._fengchao_signing_in = True
        attempt = 0
        try:
            # 检查用户名密码是否配置
            if not self.config.fengchao_username or not self.config.fengchao_password:
                logger.error("未配置用户名密码，无法进行签到")
                if self.config.notify:
                    self.callbacks.send_notification(
                        title="【❌ 蜂巢签到失败】",
                        text=(
                            f"📢 执行结果\n"
                            f"━━━━━━━━━━\n"
                            f"🕐 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                            f"❌ 状态：签到失败，未配置用户名密码\n"
                            f"━━━━━━━━━━\n"
                            f"💡 配置方法\n"
                            f"• 在插件设置中填写蜂巢论坛用户名和密码\n"
                            f"━━━━━━━━━━"
                        )
                    )
                return False

            # 使用循环而非递归实现重试
            for attempt in range(max_retries + 1):
                if attempt > 0:
                    backoff = min(60, 3 * (2 ** (attempt - 1)))
                    logger.info(f"正在进行第 {attempt}/{max_retries} 次重试，退避 {backoff} 秒...")
                    time.sleep(backoff)

                # 获取代理设置
                proxies = self.callbacks.get_proxy_url()

                # 优先复用已配置 Cookie，失效时再登录获取
                logger.info(f"开始获取蜂巢论坛认证cookie...")
                cookie = self._get_fengchao_auth_cookie(proxies)
                if not cookie:
                    logger.error(f"登录失败，无法获取cookie")
                    if attempt < max_retries:
                        continue
                    raise Exception("登录失败，无法获取cookie")

                logger.info(f"成功获取有效cookie")

                client = ForumSigninHttpClient(cookies=cookie, proxy_url=proxies, proxy_enabled=self.config.use_proxy, timeout=30)

                # 使用获取的cookie访问蜂巢
                try:
                    res = client.get_res(url="https://pting.club")
                except Exception as e:
                    logger.error(f"请求蜂巢出错: {str(e)}")
                    if attempt < max_retries:
                        continue
                    raise Exception("连接站点出错")

                if not res or res.status_code != 200:
                    logger.error(f"请求蜂巢返回错误状态码: {res.status_code if res else '无响应'}")
                    if attempt < max_retries:
                        continue
                    raise Exception("无法连接到站点")

                pre_money = None
                pre_days = None
                try:
                    pre_money_match = re.search(r'"money":\s*([\d.]+)', res.text)
                    if pre_money_match:
                        pre_money = float(pre_money_match.group(1))
                    pre_days_match = re.search(r'"totalContinuousCheckIn":\s*(\d+)', res.text)
                    if pre_days_match:
                        pre_days = int(pre_days_match.group(1))
                    logger.info(f"签到前状态检查：当前花粉 -> {pre_money}, 签到天数 -> {pre_days}")
                except Exception as e:
                    logger.warning(f"签到前解析用户状态失败，将依赖API原始判断: {e}")

                # 获取csrfToken
                csrfToken = res.headers.get("x-csrf-token") or (re.findall(r'"csrfToken":"(.*?)"', res.text) or [None])[0]
                if not csrfToken:
                    logger.error("请求csrfToken失败")
                    if attempt < max_retries:
                        continue
                    raise Exception("无法获取CSRF令牌")

                logger.info(f"获取csrfToken成功 {csrfToken}")

                # 获取userid
                pattern = r'"userId":(\d+)'
                match = re.search(pattern, res.text)

                if match and match.group(1) != "0":
                    userId = match.group(1)
                    logger.info(f"获取userid成功 {userId}")

                    # 如果开启了蜂巢论坛PT人生数据更新，尝试更新数据
                    if self.config.mp_push_enabled:
                        self.__push_mp_stats(user_id=userId, csrf_token=csrfToken, cookie=cookie, client=client)
                else:
                    logger.error("未找到userId")
                    if attempt < max_retries:
                        continue
                    raise Exception("无法获取用户ID")

                # 准备签到请求
                headers = {
                    "X-Csrf-Token": csrfToken,
                    "X-Http-Method-Override": "PATCH"
                }

                data = {
                    "data": {
                        "type": "users",
                        "attributes": {
                            "canCheckin": False,
                            "totalContinuousCheckIn": 2
                        },
                        "id": userId
                    }
                }

                # 开始签到
                try:
                    res = client.post_res(
                        url=f"https://pting.club/api/users/{userId}",
                        json=data,
                        headers=headers,
                        raise_exception=True
                    )
                except Exception as e:
                    import traceback
                    logger.error(f"签到请求出错: {str(e)}\n{traceback.format_exc()}")
                    if attempt < max_retries:
                        continue
                    raise Exception("签到请求异常")

                if not res or res.status_code != 200:
                    detail = ""
                    if res:
                        try:
                            detail = res.text[:200] if hasattr(res, "text") else ""
                        except Exception:
                            detail = ""
                    logger.error(
                        f"蜂巢签到失败，状态码: {res.status_code if res else '无响应(请求被吞)'} "
                        f"detail={detail or '无'}"
                    )
                    if attempt < max_retries:
                        continue
                    raise Exception("API请求错误")

                # 签到成功
                sign_dict = json.loads(res.text)

                # 直接保存签到后的用户信息
                self.callbacks.save_data("fengchao_user_info", sign_dict)
                self.callbacks.save_data("fengchao_user_info_updated_at", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                logger.info("成功获取并保存用户信息。")

                # 新增：检查未读消息并通知
                try:
                    user_attrs_for_msg = sign_dict.get('data', {}).get('attributes', {})
                    unread_notifications = user_attrs_for_msg.get('unreadNotificationCount', 0)
                    if unread_notifications > 0:
                        logger.info(f"检测到 {unread_notifications} 条未读消息，发送通知。")
                        self.callbacks.send_notification(
                            title=f"【📢 蜂巢论坛消息提醒】",
                            text=f"您有 {unread_notifications} 条未读消息待处理，请及时访问蜂巢论坛查看。"
                        )
                except Exception as e:
                    logger.warning(f"检查未读消息时发生错误: {e}")

                money = sign_dict['data']['attributes']['money']
                totalContinuousCheckIn = sign_dict['data']['attributes']['totalContinuousCheckIn']
                lastCheckinMoney = sign_dict['data']['attributes'].get('lastCheckinMoney', 0)

                formatted_money = self._format_pollen(money)
                formatted_last_checkin_money = self._format_pollen(lastCheckinMoney)

                is_successful_checkin = False
                if pre_money is not None and pre_days is not None:
                    if money > pre_money or totalContinuousCheckIn > pre_days:
                        is_successful_checkin = True
                else:
                    can_checkin_before = '"canCheckin":true' in res.text
                    logger.info(f"回退到API标志位判断: canCheckin -> {can_checkin_before}")
                    if can_checkin_before:
                        is_successful_checkin = True

                if is_successful_checkin:
                    status_text = "签到成功"
                    reward_text = f"获得{formatted_last_checkin_money}花粉奖励" if lastCheckinMoney > 0 else "获得奖励"
                    logger.info(
                        f"蜂巢签到成功，获得{formatted_last_checkin_money}花粉，当前花粉: {formatted_money}，累计签到: {totalContinuousCheckIn}")
                else:
                    status_text = "已签到"
                    reward_text = "今日已领取奖励"
                    logger.info(f"蜂巢已签到，当前花粉: {formatted_money}，累计签到: {totalContinuousCheckIn}")

                # 发送通知
                if self.config.notify:
                    self.callbacks.send_notification(
                        title=f"【✅ 蜂巢{status_text}】",
                        text=(
                            f"📢 执行结果\n"
                            f"━━━━━━━━━━\n"
                            f"🕐 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                            f"✨ 状态：{status_text}\n"
                            f"🎁 奖励：{reward_text}\n"
                            f"━━━━━━━━━━\n"
                            f"📊 积分统计\n"
                            f"🌸 花粉：{formatted_money}\n"
                            f"📆 签到天数：{totalContinuousCheckIn}\n"
                            f"━━━━━━━━━━"
                        )
                    )

                # 准备历史记录
                history_record = {
                    "site": "fengchao",
                    "date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "status": status_text,
                    "status_code": "success_new" if is_successful_checkin else "success_already",
                    "money": money,
                    "totalContinuousCheckIn": totalContinuousCheckIn,
                    "lastCheckinMoney": lastCheckinMoney,
                    "failure_count": 0
                }

                # 保存签到历史
                self.callbacks.save_history(history_record)

                # 如果是重试后成功，重置重试计数
                if self.config.fengchao_current_retry > 0:
                    logger.info(f"蜂巢签到重试成功，重置重试计数")
                    self.config.fengchao_current_retry = 0

                # 签到成功，退出循环
                return True

        except Exception as e:
            logger.error(f"签到过程发生异常: {str(e)}")
            import traceback
            logger.error(f"错误详情: {traceback.format_exc()}")

            # 保存失败记录
            failure_history_record = {
                "site": "fengchao",
                "date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "status": "签到失败",
                "status_code": "failed",
                "reason": str(e),
                "failure_count": 1  # 初始失败次数为1
            }
            self.callbacks.save_history(failure_history_record)

            # 所有重试失败，发送通知并退出
            self.callbacks.send_signin_failure_notification(str(e), attempt, site='fengchao')

            # 设置下次定时重试
            if self.config.retry_count > 0 and self.config.fengchao_current_retry < self.config.retry_count:
                self.config.fengchao_current_retry += 1
                logger.info(f"安排第{self.config.fengchao_current_retry}次蜂巢定时重试，将在{self.config.retry_interval}分钟后重试")
                self.callbacks.schedule_retry(site='fengchao', minutes=self.config.retry_interval)
            else:
                if self.config.retry_count > 0:
                    logger.info("已达到最大定时重试次数，不再重试")
                self.config.fengchao_current_retry = 0

            return False
        finally:
            # 释放锁
            self._fengchao_signing_in = False

    def _map_fa_to_mdi(self, icon_class: str) -> str:
        """
        Maps common Font Awesome icon names to MDI icon names.
        """
        if not icon_class or not isinstance(icon_class, str):
            return 'mdi-account-group'
        if icon_class.startswith('mdi-'):
            return icon_class

        mapping = {
            'fa-user-tie': 'mdi-account-tie', 'fa-crown': 'mdi-crown', 'fa-shield-alt': 'mdi-shield-outline',
            'fa-user-shield': 'mdi-account-shield', 'fa-user-cog': 'mdi-account-cog',
            'fa-user-check': 'mdi-account-check', 'fa-fan': 'mdi-fan', 'fa-user': 'mdi-account',
            'fa-users': 'mdi-account-group', 'fa-cogs': 'mdi-cog', 'fa-cog': 'mdi-cog', 'fa-star': 'mdi-star',
            'fa-gem': 'mdi-diamond'
        }
        match = re.search(r'fa-[\w-]+', icon_class)
        if match:
            core_icon = match.group(0)
            return mapping.get(core_icon, 'mdi-account-group')
        return 'mdi-account-group'

    def _format_pollen(self, value: Any) -> str:
        """
        Formats the pollen value.
        """
        if value is None:
            return '—'
        try:
            num = float(value)
            if num == int(num):
                return str(int(num))
            else:
                return f'{round(num, 3):g}'
        except (ValueError, TypeError):
            return str(value)

    def __check_and_push_mp_stats(self):
        """检查是否需要更新蜂巢论坛PT人生数据"""
        if hasattr(self, '_pushing_stats') and self._pushing_stats:
            logger.info("已有更新PT人生数据任务在执行，跳过当前任务")
            return
        self._pushing_stats = True
        try:
            if not self.config.mp_push_enabled: return
            if not self.config.fengchao_username or not self.config.fengchao_password:
                logger.error("未配置用户名密码，无法更新PT人生数据")
                return
            proxies = self.callbacks.get_proxy_url()
            now = datetime.now()
            if self.config.last_push_time:
                last_push = datetime.strptime(self.config.last_push_time, '%Y-%m-%d %H:%M:%S')
                if (now - last_push).days < self.config.mp_push_interval:
                    logger.info(f"距离上次更新PT人生数据时间不足{self.config.mp_push_interval}天，跳过更新")
                    return
            logger.info(f"开始更新蜂巢论坛PT人生数据...")
            cookie = self._get_fengchao_auth_cookie(proxies)
            if not cookie:
                logger.error("登录失败，无法获取cookie进行PT人生数据更新")
                return
            client = ForumSigninHttpClient(cookies=cookie, proxy_url=proxies, proxy_enabled=self.config.use_proxy, timeout=30)
            try:
                res = client.get_res(url="https://pting.club")
            except Exception as e:
                logger.error(f"请求蜂巢出错: {str(e)}")
                return
            if not res or res.status_code != 200:
                logger.error(f"请求蜂巢返回错误状态码: {res.status_code if res else '无响应'}")
                return
            csrf_token = res.headers.get("x-csrf-token") or (re.findall(r'"csrfToken":"(.*?)"', res.text) or [None])[0]
            if not csrf_token:
                logger.error("获取CSRF令牌失败，无法进行PT人生数据更新")
                return
            user_matches = re.search(r'"userId":(\d+)', res.text)
            if not user_matches:
                logger.error("获取用户ID失败，无法进行PT人生数据更新")
                return
            user_id = user_matches.group(1)
            self.__push_mp_stats(user_id=user_id, csrf_token=csrf_token, cookie=cookie, client=client)
        finally:
            self._pushing_stats = False

    def __push_mp_stats(self, user_id=None, csrf_token=None, cookie=None, client=None, retry_count=0, max_retries=3):
        """更新蜂巢论坛PT人生数据"""
        if not self.config.mp_push_enabled: return
        if not cookie and client:
            cookie = client.get_cookie_string()
        if not all([user_id, cookie]):
            logger.error("用户ID或Cookie为空，无法更新PT人生数据")
            return
        proxies = self.callbacks.get_proxy_url()
        if client is None:
            client = ForumSigninHttpClient(cookies=cookie, proxy_url=proxies, proxy_enabled=self.config.use_proxy, timeout=60)
            try:
                res = client.get_res(url="https://pting.club")
            except Exception as e:
                logger.error(f"请求蜂巢出错: {str(e)}")
                return
            if not res or res.status_code != 200:
                logger.error(f"请求蜂巢返回错误状态码: {res.status_code if res else '无响应'}")
                return
            csrf_token = res.headers.get("x-csrf-token") or (re.findall(r'"csrfToken":"(.*?)"', res.text) or [None])[0]
        if not csrf_token:
            logger.error("获取CSRF令牌失败，无法进行PT人生数据更新")
            return
        for attempt in range(retry_count, max_retries + 1):
            if attempt > retry_count:
                backoff = min(120, 5 * (2 ** (attempt - retry_count - 1)))
                logger.info(f"更新失败，正在进行第 {attempt - retry_count}/{max_retries - retry_count} 次重试，退避 {backoff} 秒...")
                time.sleep(backoff)
            try:
                now = datetime.now()
                logger.info(f"开始获取站点统计数据以更新蜂巢论坛PT人生数据 (用户ID: {user_id})")
                if not hasattr(self, '_cached_stats_data') or not self._cached_stats_data or not hasattr(self,
                                                                                                        '_cached_stats_time') or (
                        now - self._cached_stats_time).total_seconds() > 3600:
                    self._cached_stats_data = self._get_site_statistics()
                    self._cached_stats_time = now
                    logger.info("获取最新站点统计数据")
                else:
                    logger.info(f"使用缓存的站点统计数据（缓存时间：{self._cached_stats_time.strftime('%Y-%m-%d %H:%M:%S')}）")
                stats_data = self._cached_stats_data
                if not stats_data:
                    logger.error("获取站点统计数据失败，无法更新PT人生数据")
                    if attempt < max_retries: continue
                    return
                if not hasattr(self, '_cached_formatted_stats') or not self._cached_formatted_stats or not hasattr(
                        self,
                        '_cached_stats_time') or (
                        now - self._cached_stats_time).total_seconds() > 3600:
                    self._cached_formatted_stats = self._format_stats_data(stats_data)
                    logger.info("格式化最新站点统计数据")
                else:
                    logger.info("使用缓存的已格式化站点统计数据")
                formatted_stats = self._cached_formatted_stats
                if not formatted_stats:
                    logger.error("格式化站点统计数据失败，无法更新PT人生数据")
                    if attempt < max_retries: continue
                    return

                # 记录第一个站点的数据以便确认所有字段是否都被正确传递
                if formatted_stats.get("sites") and len(formatted_stats.get("sites")) > 0:
                    first_site = formatted_stats.get("sites")[0]
                    logger.info(f"推送数据示例：站点={first_site.get('name')}, 用户名={first_site.get('username')}, 等级={first_site.get('user_level')}, "
                                f"上传={first_site.get('upload')}, 下载={first_site.get('download')}, 分享率={first_site.get('ratio')}, "
                                f"魔力值={first_site.get('bonus')}, 做种数={first_site.get('seeding')}, 做种体积={first_site.get('seeding_size')}")

                sites = formatted_stats.get("sites", [])
                if len(sites) > 300:
                    logger.warning(f"站点数据过多({len(sites)}个)，将只推送做种数最多的前300个站点")
                    sites.sort(key=lambda x: x.get("seeding", 0), reverse=True)
                    formatted_stats["sites"] = sites[:300]
                headers = {"X-Csrf-Token": csrf_token, "X-Http-Method-Override": "PATCH",
                           "Content-Type": "application/json"}
                data = {"data": {"type": "users", "attributes": {
                    "mpStatsSummary": json.dumps(formatted_stats.get("summary", {})),
                    "mpStatsSites": json.dumps(formatted_stats.get("sites", []))}, "id": user_id}}

                # 输出JSON数据片段以便确认
                json_data = json.dumps(formatted_stats.get("sites", []))
                if len(json_data) > 500:
                    logger.info(f"推送的JSON数据片段: {json_data[:500]}...")
                    logger.info(f"推送数据大小约为: {len(json_data)/1024:.2f} KB")
                else:
                    logger.info(f"推送的JSON数据: {json_data}")
                    logger.info(f"推送数据大小约为: {len(json_data)/1024:.2f} KB")

                url = f"https://pting.club/api/users/{user_id}"
                logger.info(f"准备更新蜂巢论坛PT人生数据: {len(formatted_stats.get('sites', []))} 个站点")
                try:
                    res = client.post_res(url=url, json=data, headers=headers, raise_exception=True)
                except Exception as e:
                    import traceback
                    logger.error(f"更新请求出错: {str(e)}\n{traceback.format_exc()}")
                    if attempt < max_retries: continue
                    logger.error("所有重试都失败，放弃更新")
                    return
                if res and res.status_code == 200:
                    logger.info(
                        f"成功更新蜂巢论坛PT人生数据: 总上传 {round(formatted_stats['summary']['total_upload'] / (1024 ** 3), 2)} GB, 总下载 {round(formatted_stats['summary']['total_download'] / (1024 ** 3), 2)} GB")
                    self.config.last_push_time = now.strftime('%Y-%m-%d %H:%M:%S')
                    self.callbacks.save_data('last_push_time', self.config.last_push_time)
                    if hasattr(self, '_cached_stats_data'): self._cached_stats_data = None
                    if hasattr(self, '_cached_formatted_stats'): self._cached_formatted_stats = None
                    if hasattr(self, '_cached_stats_time'): delattr(self, '_cached_stats_time')
                    logger.info("已清除站点数据缓存，下次将获取最新数据")
                    if self.config.notify:
                        self.callbacks.send_notification(
                            title="【✅ 蜂巢论坛PT人生数据更新成功】",
                            text=(
                                f"📢 执行结果\n"
                                f"━━━━━━━━━━\n"
                                f"🕐 时间：{now.strftime('%Y-%m-%d %H:%M:%S')}\n"
                                f"✨ 状态：成功更新蜂巢论坛PT人生数据\n"
                                f"📊 站点数：{len(formatted_stats.get('sites', []))} 个\n"
                                f"━━━━━━━━━━"
                            )
                        )
                    return True
                else:
                    if res:
                        try:
                            detail = res.text[:100] if hasattr(res, "text") else "无响应内容"
                        except Exception:
                            detail = "无响应内容"
                        logger.error(f"更新蜂巢论坛PT人生数据失败：状态码 {res.status_code}, 响应: {detail}")
                    else:
                        logger.error("更新蜂巢论坛PT人生数据失败：无响应(请求异常被 ForumSigninHttpClient 吞掉，见上方 traceback)")
                    if attempt < max_retries:
                        continue

                    # 所有重试都失败，发送通知
                    if self.config.notify:
                        self.callbacks.send_notification(
                            title="【❌ 蜂巢论坛PT人生数据更新失败】",
                            text=(
                                f"📢 执行结果\n"
                                f"━━━━━━━━━━\n"
                                f"🕐 时间：{now.strftime('%Y-%m-%d %H:%M:%S')}\n"
                                f"❌ 状态：更新蜂巢论坛PT人生数据失败（已重试{attempt - retry_count}次）\n"
                                f"━━━━━━━━━━\n"
                                f"💡 可能的解决方法\n"
                                f"• 检查Cookie是否有效\n"
                                f"• 确认站点是否可访问\n"
                                f"• 尝试手动登录网站\n"
                                f"━━━━━━━━━━"
                            )
                        )
                    return False
            except Exception as e:
                logger.error(f"更新过程发生异常: {str(e)}")
                import traceback
                logger.error(f"错误详情: {traceback.format_exc()}")

                if attempt < max_retries:
                    continue

                # 所有重试都失败
                if self.config.notify:
                    self.callbacks.send_notification(
                        title="【❌ 蜂巢论坛PT人生数据更新失败】",
                        text=(
                            f"📢 执行结果\n"
                            f"━━━━━━━━━━\n"
                            f"🕐 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                            f"❌ 状态：更新蜂巢论坛PT人生数据失败（已重试{attempt - retry_count}次）\n"
                            f"━━━━━━━━━━\n"
                            f"💡 可能的解决方法\n"
                            f"• 检查系统网络连接\n"
                            f"• 确认站点是否可访问\n"
                            f"• 检查代码是否有错误\n"
                            f"━━━━━━━━━━"
                        )
                    )

    def _get_site_statistics(self):
        """获取站点统计数据（参考站点统计插件实现）"""
        try:
            # 导入SiteOper类和SitesHelper
            from app.db.site_oper import SiteOper
            from app.helper.sites import SitesHelper
            site_oper, sites_helper = SiteOper(), SitesHelper()
            managed_sites = sites_helper.get_indexers()
            managed_site_names = [s.get("name") for s in managed_sites if s.get("name")]
            raw_data_list = site_oper.get_userdata()
            if not raw_data_list:
                logger.error("未获取到站点数据")
                return None
            data_dict = {f"{d.updated_day}_{d.name}": d for d in raw_data_list}
            data_list = sorted(list(data_dict.values()), key=lambda x: x.updated_day, reverse=True)
            site_names = set()
            latest_site_data = []
            for data in data_list:
                if data.name not in site_names and data.name in managed_site_names:
                    site_names.add(data.name)
                    latest_site_data.append(data)
            sites = []
            for site_data in latest_site_data:
                site_dict = site_data.to_dict() if hasattr(site_data, "to_dict") else site_data.__dict__
                if "_sa_instance_state" in site_dict: site_dict.pop("_sa_instance_state")
                sites.append(site_dict)
            return {"sites": sites}
        except Exception as e:
            logger.error(f"获取站点统计数据出错: {str(e)}")
            return self._get_site_statistics_via_api()

    def _get_site_statistics_via_api(self):
        """通过API获取站点统计数据（备用）"""
        try:
            from app.helper.sites import SitesHelper
            sites_helper = SitesHelper()
            managed_sites = sites_helper.get_indexers()
            managed_site_names = [s.get("name") for s in managed_sites if s.get("name")]
            api_url = f"{settings.HOST}/api/v1/site/statistics"
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {settings.API_TOKEN}"}
            res = ForumSigninHttpClient(headers=headers, proxy_enabled=False).get_res(url=api_url)
            if res and res.status_code == 200:
                data = res.json()
                all_sites = data.get("sites", [])
                sites = [s for s in all_sites if s.get("name") in managed_site_names]
                data["sites"] = sites
                return data
            else:
                logger.error(f"获取站点统计数据失败: {res.status_code if res else '连接失败'}")
                return None
        except Exception as e:
            logger.error(f"获取站点统计数据出错: {str(e)}")
            return None

    def _format_stats_data(self, stats_data):
        """格式化站点统计数据"""
        try:
            if not stats_data or not stats_data.get("sites"): return None
            sites = stats_data.get("sites", [])
            summary = {"total_upload": 0, "total_download": 0, "total_seed": 0, "total_seed_size": 0}
            site_details = []
            for site in sites:
                if not site.get("name") or site.get("error"): continue
                upload = float(site.get("upload", 0))
                download = float(site.get("download", 0))
                summary["total_upload"] += upload
                summary["total_download"] += download
                summary["total_seed"] += int(site.get("seeding", 0))
                summary["total_seed_size"] += float(site.get("seeding_size", 0))
                site_details.append({
                    "name": site.get("name"), "username": site.get("username", ""),
                    "user_level": site.get("user_level", ""),
                    "upload": upload, "download": download,
                    "ratio": round(upload / download, 2) if download > 0 else float('inf'),
                    "bonus": site.get("bonus", 0), "seeding": site.get("seeding", 0),
                    "seeding_size": site.get("seeding_size", 0)
                })
            summary["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return {"summary": summary, "sites": site_details}
        except Exception as e:
            logger.error(f"格式化站点统计数据出错: {str(e)}")
            return None

    def _login_and_get_cookie(self, proxies=None):
        """使用用户名密码登录获取cookie"""
        try:
            logger.info(f"开始使用用户名'{self.config.fengchao_username}'登录蜂巢论坛...")
            cookie = self._login_postman_method(proxies=proxies)
            if cookie:
                self._update_fengchao_cookie_if_changed(cookie)
            return cookie
        except Exception as e:
            logger.error(f"登录过程出错: {str(e)}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
            return None

    def _update_fengchao_cookie_if_changed(self, cookie_str: str):
        """蜂巢登录成功后持久化 Cookie。"""
        if cookie_str and cookie_str != (self.config.fengchao_cookie or ""):
            self.config.fengchao_cookie = cookie_str
            logger.info("蜂巢 Cookie 已更新，保存新配置")
            self.callbacks.persist_config()

    def _get_fengchao_auth_cookie(self, proxies=None):
        """优先复用已配置蜂巢 Cookie，失效时再登录刷新。"""
        if self.config.fengchao_cookie:
            req = ForumSigninHttpClient(proxy_url=proxies, proxy_enabled=self.config.use_proxy, timeout=30)
            verified = self._verify_cookie(req, self.config.fengchao_cookie, "代理" if self.config.use_proxy else "直接连接")
            if verified:
                logger.info("蜂巢 Cookie 验证有效，直接复用")
                return verified
            logger.warning("蜂巢 Cookie 验证失效，回退账号密码登录")
        return self._login_and_get_cookie(proxies)

    def _login_postman_method(self, proxies=None):
        """使用Postman方式登录"""
        try:
            req = ForumSigninHttpClient(proxy_url=proxies, proxy_enabled=self.config.use_proxy, timeout=30)
            proxy_info = "代理" if self.config.use_proxy else "直接连接"
            logger.info(f"使用Postman方式登录 (使用{proxy_info})...")
            headers = {"Accept": "*/*",
                       "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
                       "Cache-Control": "no-cache"}
            try:
                res = req.get_res("https://pting.club", headers=headers, raise_exception=True)
                if not res or res.status_code != 200:
                    logger.error(f"GET请求失败，状态码: {res.status_code if res else '无响应'} (使用{proxy_info})")
                    return None
            except Exception as e:
                import traceback
                logger.error(f"GET请求异常 (使用{proxy_info}): {str(e)}\n{traceback.format_exc()}")
                return None
            csrf_token = res.headers.get('x-csrf-token') or (re.findall(r'"csrfToken":"(.*?)"', res.text) or [None])[
                0]
            if not csrf_token:
                logger.error(f"无法获取CSRF令牌 (使用{proxy_info})")
                return None
            login_data = {"identification": self.config.fengchao_username, "password": self.config.fengchao_password, "remember": True}
            login_headers = {"Content-Type": "application/json", "X-CSRF-Token": csrf_token, **headers}
            try:
                login_res = req.post_res(url="https://pting.club/login", json=login_data, headers=login_headers)
                if not login_res or login_res.status_code != 200:
                    logger.error(
                        f"登录请求失败，状态码: {login_res.status_code if login_res else '无响应'} (使用{proxy_info})")
                    return None
            except Exception as e:
                logger.error(f"登录请求异常 (使用{proxy_info}): {str(e)}")
                return None
            jar_cookies = req.get_cookies_dict()
            cookie_dict = {k: jar_cookies[k] for k in ("flarum_session", "flarum_remember") if k in jar_cookies}
            if set_cookie_header := login_res.headers.get('set-cookie'):
                if 'flarum_session' not in cookie_dict and (session_match := re.search(r'flarum_session=([^;]+)', set_cookie_header)):
                    cookie_dict['flarum_session'] = session_match.group(1)
                if 'flarum_remember' not in cookie_dict and (remember_match := re.search(r'flarum_remember=([^;]+)', set_cookie_header)):
                    cookie_dict['flarum_remember'] = remember_match.group(1)
            cookie_str = "; ".join([f"{k}={v}" for k, v in cookie_dict.items()])
            return self._verify_cookie(req, cookie_str, proxy_info)
        except Exception as e:
            logger.error(f"Postman方式登录失败 (使用{proxy_info if self.config.use_proxy else '直接连接'}): {str(e)}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
            return None

    def _verify_cookie(self, req, cookie_str, proxy_info):
        """验证cookie是否有效"""
        if not cookie_str: return None
        logger.info(f"验证cookie有效性 (使用{proxy_info})...")
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
                   "Accept": "*/*", "Cache-Control": "no-cache"}
        if cookie_str:
            req = ForumSigninHttpClient(cookies=cookie_str, proxy_url=getattr(req, "_proxy_url", None),
                                        proxy_enabled=getattr(req, "_proxy_enabled", False), timeout=getattr(req, "_timeout", 30))
        for attempt in range(3):
            try:
                if attempt > 0:
                    logger.info(f"验证Cookie重试 {attempt}/2...")
                    time.sleep(2)
                verify_res = req.get_res("https://pting.club", headers=headers)
                if verify_res and verify_res.status_code == 200:
                    if user_matches := re.search(r'"userId":(\d+)', verify_res.text):
                        if (user_id := user_matches.group(1)) != "0":
                            logger.info(f"登录成功！获取到有效cookie，用户ID: {user_id} (使用{proxy_info})")
                            return cookie_str
                if verify_res and verify_res.status_code in self.congestion_status_codes and attempt < 2:
                    self.__backoff_sleep(attempt, response=verify_res)
                    continue
                logger.warning(f"第{attempt + 1}次验证cookie失败 (使用{proxy_info})")
            except Exception as e:
                logger.warning(f"第{attempt + 1}次验证cookie请求异常 (使用{proxy_info}): {str(e)}")
        logger.error("所有 3 次cookie验证尝试均失败。")
        return None

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
