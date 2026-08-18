"""蜂巢签到业务（适配新版 pting.club Next.js）。

使用 pting.club 专用集成 API（/api/integrations/moviepilot/v1/*），
认证方式为 Bearer api_key，不再依赖账号密码登录或 Cookie。
"""
import random
import time
from datetime import datetime
from typing import Any

from app.log import logger
from app.core.config import settings

from .http_client import ForumSigninHttpClient
from .models import ForumSigninConfig, PluginCallbacks

MOVIEPILOT_API_BASE = "https://pting.club"


class FengchaoService:
    """蜂巢签到、用户信息与 PT 人生快照业务。"""

    congestion_status_codes = {429, 502, 503, 504}

    def __init__(self, config: ForumSigninConfig, callbacks: PluginCallbacks):
        self.config = config
        self.callbacks = callbacks

    def signin(self, retry_count=0, max_retries=3):
        return self.__signin(retry_count=retry_count, max_retries=max_retries)

    def update_user_info(self, is_scheduled_run: bool = False):
        return self.__update_user_info(is_scheduled_run=is_scheduled_run)

    def check_and_push_mp_stats(self):
        return self.__check_and_push_mp_stats()

    # ------------------------------------------------------------------
    # API 基础设施
    # ------------------------------------------------------------------

    def _api_base(self) -> str:
        return MOVIEPILOT_API_BASE

    def _api_headers(self) -> dict:
        api_key = (self.config.fengchao_api_key or "").strip()
        if not api_key:
            raise RuntimeError("未配置蜂巢 Bearer Key，请在 pting.club 个人设置页生成并粘贴")
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "MoviePilot-ForumSignin/1.0",
        }

    def _api_request(self, method: str, path: str, payload=None) -> dict:
        proxies = self.callbacks.get_proxy_url() if self.config.use_proxy else None
        client = ForumSigninHttpClient(
            headers=self._api_headers(),
            proxy_url=proxies,
            proxy_enabled=self.config.use_proxy,
            timeout=30,
        )
        url = f"{self._api_base()}{path}"
        if method == "GET":
            response = client.get_res(url, raise_exception=True)
        else:
            response = client.post_res(url, json=payload, raise_exception=True)
        if not response:
            raise RuntimeError("蜂巢 API 请求无响应")
        if response.status_code >= 400:
            detail = (response.text or "")[:200]
            raise RuntimeError(f"蜂巢 API 请求失败（HTTP {response.status_code}）：{detail}")
        try:
            result = response.json() or {}
        except Exception as exc:
            raise RuntimeError(f"蜂巢返回非 JSON 响应（HTTP {response.status_code}）") from exc
        if result.get("code") not in (None, 0):
            raise RuntimeError(result.get("message") or f"蜂巢 API 请求失败（HTTP {response.status_code}）")
        return result.get("data") or {}

    # ------------------------------------------------------------------
    # 签到
    # ------------------------------------------------------------------

    def __signin(self, retry_count=0, max_retries=3):
        """使用专用集成 API 完成蜂巢签到。"""
        if getattr(self, "_signing_in", False):
            logger.info("已有蜂巢签到任务在执行，跳过当前任务")
            return False
        self._signing_in = True
        started = datetime.now()
        last_error = None
        try:
            for attempt in range(retry_count, max_retries + 1):
                if attempt > retry_count:
                    backoff = min(60, 3 * (2 ** (attempt - retry_count - 1)))
                    logger.info(f"蜂巢签到第 {attempt - retry_count}/{max_retries - retry_count} 次重试，退避 {backoff} 秒")
                    time.sleep(backoff)
                try:
                    # 获取用户身份（可选，用于刷新缓存）
                    try:
                        identity = self._api_request("GET", "/api/integrations/moviepilot/v1/me")
                    except Exception as identity_error:
                        logger.warning(f"蜂巢获取用户身份失败（不影响签到）：{identity_error}")

                    # 签到
                    result = self._api_request("POST", "/api/integrations/moviepilot/v1/check-in", {})

                    already = bool(result.get("alreadyCheckedIn"))
                    status_text = "已签到" if already else "签到成功"
                    reward = result.get("reward", 0)
                    streak = result.get("currentStreak", 0)
                    points = result.get("points", 0)

                    # 保存用户信息（normalize 为旧格式供 UI 使用）
                    user_info = self._normalize_user_info(result, identity if "identity" in dir() else None, reward)
                    self.callbacks.save_data("fengchao_user_info", user_info)
                    self.callbacks.save_data("fengchao_user_info_updated_at", started.strftime("%Y-%m-%d %H:%M:%S"))

                    # 保存历史
                    self.callbacks.save_history({
                        "site": "fengchao",
                        "date": started.strftime("%Y-%m-%d %H:%M:%S"),
                        "status": status_text,
                        "status_code": "success_already" if already else "success_new",
                        "money": points,
                        "totalContinuousCheckIn": streak,
                        "lastCheckinMoney": reward,
                        "failure_count": 0,
                    })

                    # PT 人生快照同步（如果开启）
                    snapshot_line = ""
                    if self.config.mp_push_enabled:
                        try:
                            snapshot = self.__push_pt_life_snapshot()
                            snapshot_line = f"\n📊 PT 站点：{snapshot.get('siteCount', 0)} 个"
                        except Exception as snap_error:
                            logger.warning(f"蜂巢签到成功，但 PT 人生快照同步失败：{snap_error}")
                            snapshot_line = "\n📊 PT 同步：本次失败"

                    # 通知
                    if self.config.notify:
                        self.callbacks.send_notification(
                            title=f"【✅ 蜂巢{status_text}】",
                            text=(f"状态：{status_text}\n奖励：{reward} 积分\n"
                                  f"当前积分：{points}\n连续签到：{streak} 天{snapshot_line}\n"
                                  f"时间：{started.strftime('%Y-%m-%d %H:%M:%S')}"),
                        )

                    self.config.fengchao_current_retry = 0
                    logger.info(f"蜂巢{status_text}，奖励 {reward}，连续 {streak} 天，积分 {points}")
                    return True
                except Exception as exc:
                    last_error = exc
                    logger.error(f"蜂巢签到第 {attempt - retry_count + 1} 次尝试失败: {exc}")
                    if attempt >= max_retries:
                        raise
            return False
        except Exception as exc:
            logger.error(f"蜂巢签到失败: {last_error or exc}")
            self.callbacks.save_history({
                "site": "fengchao",
                "date": started.strftime("%Y-%m-%d %H:%M:%S"),
                "status": "签到失败", "status_code": "failed",
                "reason": str(last_error or exc), "failure_count": 1,
            })
            self.callbacks.send_signin_failure_notification(str(last_error or exc), attempt, site="fengchao")
            if self.config.retry_count > 0 and self.config.fengchao_current_retry < self.config.retry_count:
                self.config.fengchao_current_retry += 1
                self.callbacks.schedule_retry(site="fengchao", minutes=self.config.retry_interval)
            else:
                self.config.fengchao_current_retry = 0
            return False
        finally:
            self._signing_in = False

    # ------------------------------------------------------------------
    # 用户信息更新
    # ------------------------------------------------------------------

    def __update_user_info(self, is_scheduled_run: bool = False):
        """仅更新蜂巢用户信息，不执行签到。"""
        logger.info("开始执行蜂巢用户信息更新任务...")
        try:
            identity = self._api_request("GET", "/api/integrations/moviepilot/v1/me")
            try:
                status = self._api_request("GET", "/api/integrations/moviepilot/v1/status")
            except Exception as status_error:
                logger.warning(f"蜂巢获取状态失败（不影响用户信息）：{status_error}")
                status = {}

            user_info = self._normalize_user_info({}, identity, None, status)
            self.callbacks.save_data("fengchao_user_info", user_info)
            self.callbacks.save_data("fengchao_user_info_updated_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

            unread = int(identity.get("user", {}).get("unreadNotificationCount", 0) if isinstance(identity.get("user"), dict) else 0)
            if unread > 0:
                self.callbacks.send_notification(
                    title="【📢 蜂巢论坛消息提醒】",
                    text=f"您有 {unread} 条未读消息待处理，请及时访问蜂巢论坛查看。",
                )

            if is_scheduled_run:
                self.config.timed_update_current_retry = 0
            self.callbacks.send_notification(
                title="【✅ 蜂巢信息更新成功】",
                text=(f"用户：{identity.get('user', {}).get('displayName', '—')}\n"
                      f"积分：{identity.get('user', {}).get('points', '—')}\n"
                      f"连续签到：{status.get('currentStreak', '—')} 天\n"
                      f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"),
            )
            return True
        except Exception as exc:
            logger.error(f"更新蜂巢用户信息失败: {exc}")
            if is_scheduled_run:
                self.callbacks.send_info_update_failure_notification(reason=str(exc))
                if (self.config.timed_update_retry_count > 0
                        and self.config.timed_update_current_retry < self.config.timed_update_retry_count):
                    self.config.timed_update_current_retry += 1
                    self.callbacks.schedule_info_update_retry()
                else:
                    self.config.timed_update_current_retry = 0
            else:
                self.callbacks.send_notification(
                    title="【❌ 蜂巢信息更新失败】",
                    text=f"原因：{exc}\n时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                )
            return False
        finally:
            if not is_scheduled_run:
                self.config.update_info_now = False
                self.callbacks.persist_config()

    # ------------------------------------------------------------------
    # PT 人生快照同步
    # ------------------------------------------------------------------

    def __check_and_push_mp_stats(self):
        """独立触发 PT 人生快照同步。"""
        if not self.config.mp_push_enabled:
            logger.info("蜂巢 PT 人生快照推送未开启，跳过")
            return None
        try:
            snapshot = self.__push_pt_life_snapshot()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.config.last_push_time = now
            self.callbacks.save_data("last_push_time", now)
            if self.config.notify:
                self.callbacks.send_notification(
                    title="【✅ 蜂巢 PT 人生快照同步成功】",
                    text=(f"📊 PT 站点：{snapshot.get('siteCount', 0)} 个\n"
                          f"🕐 时间：{now}"),
                )
            return snapshot
        except Exception as exc:
            logger.error(f"蜂巢 PT 人生快照同步失败: {exc}")
            if self.config.notify:
                self.callbacks.send_notification(
                    title="【❌ 蜂巢 PT 人生快照同步失败】",
                    text=f"原因：{exc}\n时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                )
            return None

    def __push_pt_life_snapshot(self) -> dict:
        """上传 PT 站点统计快照到蜂巢论坛。"""
        sites = self._get_site_statistics() or []
        normalized = []
        for site in sites:
            if not site.get("name") or site.get("error"):
                continue
            upload = float(site.get("upload", 0) or 0)
            download = float(site.get("download", 0) or 0)
            normalized.append({
                "name": site.get("name"),
                "username": site.get("username", ""),
                "userLevel": site.get("user_level", ""),
                "upload": upload,
                "download": download,
                "ratio": round(upload / download, 2) if download > 0 else 0,
                "bonus": float(site.get("bonus", 0) or 0),
                "seeding": int(site.get("seeding", 0) or 0),
                "seedingSize": float(site.get("seeding_size", 0) or 0),
            })
        payload = {
            "schemaVersion": 1,
            "collectedAt": datetime.now().isoformat(),
            "sites": normalized,
        }
        return self._api_request("PUT", "/api/integrations/moviepilot/v1/pt-life/snapshot", payload)

    # ------------------------------------------------------------------
    # 站点统计（复用 MoviePilot 站点数据）
    # ------------------------------------------------------------------

    def _get_site_statistics(self) -> list:
        """通过 MP API 获取站点统计数据。"""
        try:
            from app.helper.sites import SitesHelper
            sites_helper = SitesHelper()
            managed_sites = sites_helper.get_indexers()
            managed_site_names = [s.get("name") for s in managed_sites if s.get("name")]
            api_url = f"{settings.HOST}/api/v1/site/statistics"
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {settings.API_TOKEN}"}
            client = ForumSigninHttpClient(headers=headers, proxy_enabled=False, timeout=30)
            res = client.get_res(url=api_url)
            if res and res.status_code == 200:
                data = res.json()
                all_sites = data.get("sites", [])
                return [s for s in all_sites if s.get("name") in managed_site_names]
            logger.error(f"获取站点统计数据失败：{res.status_code if res else '连接失败'}")
            return []
        except Exception as e:
            logger.error(f"获取站点统计数据出错: {e}")
            return []

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    def _normalize_user_info(self, checkin_result: dict, identity: dict = None,
                             reward=None, status: dict = None) -> dict:
        """将新版 API 返回 normalize 为旧 {data:{attributes:{}}} 格式供 UI 使用。"""
        identity = identity or {}
        user = identity.get("user") or {}
        status = status or {}
        points = checkin_result.get("points") or user.get("points") or status.get("points", 0)
        streak = checkin_result.get("currentStreak") or status.get("currentStreak", 0)
        attrs = {
            "displayName": user.get("displayName") or user.get("username", ""),
            "username": user.get("username", ""),
            "nickname": user.get("nickname") or user.get("username", ""),
            "avatarUrl": user.get("avatarPath") or "",
            "money": points,
            "totalContinuousCheckIn": streak,
            "maxCheckInStreak": status.get("maxCheckInStreak", 0),
            "lastCheckinMoney": reward,
            "unreadNotificationCount": user.get("unreadNotificationCount", 0),
            "discussionCount": user.get("postCount", 0),
            "followerCount": user.get("followerCount", 0),
            "canCheckin": not bool(checkin_result or status.get("checkedInToday", False)),
            "level": user.get("level", 0),
            "levelName": user.get("levelName", ""),
        }
        return {"data": {"id": str(user.get("id") or ""), "attributes": attrs}}

    @staticmethod
    def _format_pollen(value: Any) -> str:
        """格式化花粉/积分值。"""
        if value is None:
            return "—"
        try:
            num = float(value)
            return str(int(num)) if num == int(num) else f"{round(num, 3):g}"
        except (ValueError, TypeError):
            return str(value)

    def __backoff_sleep(self, attempt: int, response=None, base_seconds: int = 3, max_seconds: int = 90):
        """对拥塞/限流响应进行指数退避。"""
        retry_after = None
        try:
            if response is not None:
                retry_after_header = response.headers.get("Retry-After")
                if retry_after_header and str(retry_after_header).isdigit():
                    retry_after = int(retry_after_header)
        except Exception:
            retry_after = None
        if retry_after is None:
            retry_after = min(max_seconds, base_seconds * (2 ** attempt))
        jitter = random.uniform(0.5, 3.0)
        sleep_seconds = retry_after + jitter
        logger.info(f"蜂巢站点拥塞或限流，退避 {sleep_seconds:.1f} 秒后重试")
        time.sleep(sleep_seconds)
