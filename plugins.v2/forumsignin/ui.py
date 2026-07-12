from datetime import datetime
from typing import Any, Dict, List, Tuple

from app.core.config import settings

from .models import ForumSigninConfig


def format_money(value: Any) -> str:
    """格式化积分数量"""
    if value is None:
        return '—'
    try:
        num = float(value)
        if num == int(num):
            return str(int(num))
        return f'{round(num, 3):g}'
    except (ValueError, TypeError):
        return str(value)

def get_status_meta(record: dict) -> dict:
    """获取统一状态元数据，兼容旧版中文状态文本。"""
    status_code = (record or {}).get("status_code")
    status_text = (record or {}).get("status", "")
    if not status_code:
        if "失败" in status_text:
            status_code = "failed"
        elif "已签到" in status_text:
            status_code = "success_already"
        elif "成功" in status_text:
            status_code = "success_new"
        else:
            status_code = "unknown"
    metas = {
        "success_new": {"label": "签到成功", "color": "#4CAF50", "icon": "mdi-check-circle"},
        "success_already": {"label": "今日已签", "color": "#2196F3", "icon": "mdi-check-decagram"},
        "failed": {"label": "签到失败", "color": "#F44336", "icon": "mdi-close-circle"},
        "unknown": {"label": "未知", "color": "#9E9E9E", "icon": "mdi-help-circle"}
    }
    meta = metas.get(status_code, metas["unknown"]).copy()
    meta["code"] = status_code if status_code in metas else "unknown"
    return meta


def build_form() -> Tuple[List[dict], Dict[str, Any]]:
    """拼装插件配置页面。"""
    version = getattr(settings, "VERSION_FLAG", "v1")
    cron_field_component = "VCronField" if version == "v2" else "VTextField"
    return [
        {
            'component': 'VForm',
            'content': [
                {'component': 'VCard', 'props': {'variant': 'outlined', 'class': 'mt-3'}, 'content': [
                    {'component': 'VCardTitle', 'props': {'class': 'd-flex align-center'}, 'content': [
                        {'component': 'VIcon', 'props': {'style': 'color: #1976D2;', 'class': 'mr-2'}, 'text': 'mdi-clipboard-check'},
                        {'component': 'span', 'text': '通用设置'}
                    ]},
                    {'component': 'VDivider'},
                    {'component': 'VCardText', 'content': [
                        {'component': 'VRow', 'content': [
                            {'component': 'VCol', 'props': {'cols': 12, 'md': 3}, 'content': [{'component': 'VSwitch', 'props': {'model': 'enabled', 'label': '启用插件', 'color': 'primary'}}]},
                            {'component': 'VCol', 'props': {'cols': 12, 'md': 3}, 'content': [{'component': 'VSwitch', 'props': {'model': 'notify', 'label': '开启通知', 'color': 'info'}}]},
                            {'component': 'VCol', 'props': {'cols': 12, 'md': 3}, 'content': [{'component': 'VSwitch', 'props': {'model': 'use_proxy', 'label': '使用代理', 'color': 'primary'}}]},
                            {'component': 'VCol', 'props': {'cols': 12, 'md': 3}, 'content': [{'component': 'VSwitch', 'props': {'model': 'onlyonce', 'label': '立即运行一次', 'color': 'warning'}}]}
                        ]},
                        {'component': 'VRow', 'content': [
                            {'component': 'VCol', 'props': {'cols': 12, 'md': 3}, 'content': [{'component': cron_field_component, 'props': {'model': 'cron', 'label': '签到周期', 'placeholder': '7 9 * * *', 'hint': '默认每天09:07执行，建议避开整点以降低拥塞/429概率'}}]},
                            {'component': 'VCol', 'props': {'cols': 12, 'md': 3}, 'content': [{'component': 'VTextField', 'props': {'model': 'history_days', 'label': '历史保留天数', 'type': 'number', 'placeholder': '30'}}]},
                            {'component': 'VCol', 'props': {'cols': 12, 'md': 3}, 'content': [{'component': 'VTextField', 'props': {'model': 'retry_count', 'label': '失败重试次数', 'type': 'number', 'placeholder': '0'}}]},
                            {'component': 'VCol', 'props': {'cols': 12, 'md': 3}, 'content': [{'component': 'VTextField', 'props': {'model': 'retry_interval', 'label': '重试间隔(分钟)', 'type': 'number', 'placeholder': '10', 'hint': '分钟级重试并自动加入随机抖动'}}]}
                        ]},
                        {'component': 'VRow', 'content': [
                            {'component': 'VCol', 'props': {'cols': 12, 'md': 3}, 'content': [{'component': 'VSwitch', 'props': {'model': '_update_info_now', 'label': '立即更新蜂巢个人信息', 'color': 'info'}}]}
                        ]}
                    ]}
                ]},
                {'component': 'VCard', 'props': {'variant': 'outlined', 'class': 'mt-3'}, 'content': [
                    {'component': 'VCardTitle', 'props': {'class': 'd-flex align-center'}, 'content': [
                        {'component': 'VIcon', 'props': {'style': 'color: #FF9800;', 'class': 'mr-2'}, 'text': 'mdi-flower'},
                        {'component': 'span', 'text': '蜂巢账号设置'},
                        {'component': 'VSpacer'},
                        {'component': 'VSwitch', 'props': {'model': 'fengchao_enabled', 'label': '启用蜂巢签到', 'color': 'warning', 'hide-details': True}}
                    ]},
                    {'component': 'VDivider'},
                    {'component': 'VCardText', 'content': [
                        {'component': 'VRow', 'content': [
                            {'component': 'VCol', 'props': {'cols': 12, 'md': 4}, 'content': [{'component': 'VTextField', 'props': {'model': 'fengchao_username', 'label': '蜂巢用户名', 'placeholder': 'pting.club 用户名', 'autocomplete': 'new-username', 'clearable': True}}]},
                            {'component': 'VCol', 'props': {'cols': 12, 'md': 4}, 'content': [{'component': 'VTextField', 'props': {'model': 'fengchao_password', 'label': '蜂巢密码', 'type': 'password', 'autocomplete': 'new-password', 'clearable': True}}]},
                            {'component': 'VCol', 'props': {'cols': 12, 'md': 4}, 'content': [{'component': 'VTextField', 'props': {'model': 'fengchao_cookie', 'label': '蜂巢Cookie(可选)', 'type': 'password', 'clearable': True}}]}
                        ]}
                    ]}
                ]},
                {'component': 'VCard', 'props': {'variant': 'outlined', 'class': 'mt-3'}, 'content': [
                    {'component': 'VCardTitle', 'props': {'class': 'd-flex align-center'}, 'content': [
                        {'component': 'VIcon', 'props': {'style': 'color: #9C27B0;', 'class': 'mr-2'}, 'text': 'mdi-pill'},
                        {'component': 'span', 'text': '药丸账号设置'},
                        {'component': 'VSpacer'},
                        {'component': 'VSwitch', 'props': {'model': 'invites_enabled', 'label': '启用药丸签到', 'color': '#9C27B0', 'hide-details': True}}
                    ]},
                    {'component': 'VDivider'},
                    {'component': 'VCardText', 'content': [
                        {'component': 'VRow', 'content': [
                            {'component': 'VCol', 'props': {'cols': 12, 'md': 4}, 'content': [{'component': 'VTextField', 'props': {'model': 'invites_username', 'label': '药丸用户名', 'autocomplete': 'new-username', 'clearable': True}}]},
                            {'component': 'VCol', 'props': {'cols': 12, 'md': 4}, 'content': [{'component': 'VTextField', 'props': {'model': 'invites_password', 'label': '药丸密码', 'type': 'password', 'autocomplete': 'new-password', 'clearable': True}}]},
                            {'component': 'VCol', 'props': {'cols': 12, 'md': 4}, 'content': [{'component': 'VTextField', 'props': {'model': 'invites_cookie', 'label': '药丸Cookie', 'placeholder': '需要包含 flarum_remember，可自动刷新 flarum_session', 'type': 'password', 'autocomplete': 'new-cookie', 'clearable': True}}]}
                        ]}
                    ]}
                ]},
                {'component': 'VCard', 'props': {'variant': 'outlined', 'class': 'mt-3'}, 'content': [
                    {'component': 'VCardTitle', 'props': {'class': 'd-flex align-center'}, 'content': [
                        {'component': 'VIcon', 'props': {'style': 'color: #1976D2;', 'class': 'mr-2'}, 'text': 'mdi-chart-box'},
                        {'component': 'span', 'text': '蜂巢高级功能'}
                    ]},
                    {'component': 'VDivider'},
                    {'component': 'VCardText', 'content': [
                        {'component': 'VRow', 'content': [
                            {'component': 'VCol', 'props': {'cols': 12, 'md': 3}, 'content': [{'component': 'VSwitch', 'props': {'model': 'mp_push_enabled', 'label': '启用PT人生数据更新', 'color': 'primary'}}]},
                            {'component': 'VCol', 'props': {'cols': 12, 'md': 3}, 'content': [{'component': 'VTextField', 'props': {'model': 'mp_push_interval', 'label': 'PT人生推送间隔(天)', 'type': 'number', 'placeholder': '1'}}]},
                            {'component': 'VCol', 'props': {'cols': 12, 'md': 3}, 'content': [{'component': 'VSwitch', 'props': {'model': 'timed_update_enabled', 'label': '启用定时更新个人信息', 'color': 'primary'}}]},
                            {'component': 'VCol', 'props': {'cols': 12, 'md': 3}, 'content': [{'component': cron_field_component, 'props': {'model': 'timed_update_cron', 'label': '蜂巢信息更新周期', 'placeholder': '0 */2 * * *'}}]}
                        ]},
                        {'component': 'VRow', 'content': [
                            {'component': 'VCol', 'props': {'cols': 12, 'md': 6}, 'content': [{'component': 'VTextField', 'props': {'model': 'timed_update_retry_count', 'label': '信息更新失败重试次数', 'type': 'number', 'placeholder': '0'}}]},
                            {'component': 'VCol', 'props': {'cols': 12, 'md': 6}, 'content': [{'component': 'VTextField', 'props': {'model': 'timed_update_retry_interval', 'label': '信息更新重试间隔(小时)', 'type': 'number', 'placeholder': '0'}}]}
                        ]}
                    ]}
                ]},
                {'component': 'VCard', 'props': {'variant': 'outlined', 'class': 'mt-3'}, 'content': [
                    {'component': 'VCardTitle', 'props': {'class': 'd-flex align-center'}, 'content': [
                        {'component': 'VIcon', 'props': {'style': 'color: #1976D2;', 'class': 'mr-2'}, 'text': 'mdi-information-outline'},
                        {'component': 'span', 'text': '使用说明'}
                    ]},
                    {'component': 'VDivider'},
                    {'component': 'VCardText', 'content': [
                        {'component': 'VList', 'props': {'density': 'comfortable', 'lines': 'two'}, 'content': [
                            {'component': 'VListItem', 'content': [
                                {'component': 'template', 'props': {'v-slot:prepend': ''}, 'content': [{'component': 'VIcon', 'props': {'color': 'primary'}, 'text': 'mdi-clock-check-outline'}]},
                                {'component': 'VListItemTitle', 'text': '签到周期'},
                                {'component': 'VListItemSubtitle', 'text': '支持标准cron表达式，建议避开整点（如 7 9 * * *）以降低药丸站点整点拥塞与429限流概率。默认09:07执行。'}
                            ]},
                            {'component': 'VListItem', 'content': [
                                {'component': 'template', 'props': {'v-slot:prepend': ''}, 'content': [{'component': 'VIcon', 'props': {'color': 'info'}, 'text': 'mdi-sync'}]},
                                {'component': 'VListItemTitle', 'text': '双站调度'},
                                {'component': 'VListItemSubtitle', 'text': '一次定时触发依次执行蜂巢与药丸签到，两站异常隔离互不影响，各自独立重试与历史记录。'}
                            ]},
                            {'component': 'VListItem', 'content': [
                                {'component': 'template', 'props': {'v-slot:prepend': ''}, 'content': [{'component': 'VIcon', 'props': {'color': 'warning'}, 'text': 'mdi-flower'}]},
                                {'component': 'VListItemTitle', 'text': '蜂巢账号'},
                                {'component': 'VListItemSubtitle', 'text': '填写 pting.club 用户名和密码，登录后自动获取Cookie；可选填Cookie优先复用。'}
                            ]},
                            {'component': 'VListItem', 'content': [
                                {'component': 'template', 'props': {'v-slot:prepend': ''}, 'content': [{'component': 'VIcon', 'props': {'style': 'color: #9C27B0;'}, 'text': 'mdi-pill'}]},
                                {'component': 'VListItemTitle', 'text': '药丸账号'},
                                {'component': 'VListItemSubtitle', 'text': '填写 invites.fun 用户名和密码；Cookie选填（需含 flarum_remember，会自动刷新 flarum_session 并持久化）。Cookie优先，失败回退账号登录。'}
                            ]},
                            {'component': 'VListItem', 'content': [
                                {'component': 'template', 'props': {'v-slot:prepend': ''}, 'content': [{'component': 'VIcon', 'props': {'color': 'success'}, 'text': 'mdi-refresh'}]},
                                {'component': 'VListItemTitle', 'text': '失败重试'},
                                {'component': 'VListItemSubtitle', 'text': '重试间隔为分钟级并自动加入随机抖动，避免重试集中在整点；药丸站点对429/拥塞状态码单独指数退避。'}
                            ]},
                            {'component': 'VListItem', 'content': [
                                {'component': 'template', 'props': {'v-slot:prepend': ''}, 'content': [{'component': 'VIcon', 'props': {'color': 'primary'}, 'text': 'mdi-chart-box'}]},
                                {'component': 'VListItemTitle', 'text': '蜂巢高级功能'},
                                {'component': 'VListItemSubtitle', 'text': 'PT人生数据推送与定时更新个人信息仅服务蜂巢站；药丸站无对应接口。'}
                            ]}
                        ]}
                    ]}
                ]}
            ]
        }
    ], {
        "enabled": False,
        "notify": True,
        "cron": "7 9 * * *",
        "onlyonce": False,
        "history_days": 30,
        "retry_count": 0,
        "retry_interval": 10,
        "use_proxy": True,
        "_update_info_now": False,
        "fengchao_enabled": True,
        "invites_enabled": True,
        "fengchao_username": "",
        "fengchao_password": "",
        "fengchao_cookie": "",
        "invites_username": "",
        "invites_password": "",
        "invites_cookie": "",
        "mp_push_enabled": False,
        "mp_push_interval": 1,
        "timed_update_enabled": False,
        "timed_update_cron": "0 */2 * * *",
        "timed_update_retry_count": 0,
        "timed_update_retry_interval": 0
    }

def build_page(get_data, config: ForumSigninConfig) -> List[dict]:
    """构建插件详情页面，展示双站概览与签到历史。"""
    history = get_data('history') or []
    if not isinstance(history, list):
        history = [history]
    history = sorted(history, key=lambda x: x.get("date", ""), reverse=True)[:int(config.history_days or 30)]

    fengchao_user_info = get_data("fengchao_user_info") or {}
    invites_user_info = get_data("invites_user_info") or get_data("user_info") or {}
    updated_at = {
        "fengchao": get_data("fengchao_user_info_updated_at") or "—",
        "invites": get_data("invites_user_info_updated_at") or "—"
    }
    site_names = {"fengchao": "蜂巢", "invites": "药丸"}
    site_icons = {"fengchao": "mdi-flower", "invites": "mdi-pill"}
    site_colors = {"fengchao": "#FF9800", "invites": "#9C27B0"}
    site_points = {"fengchao": "花粉", "invites": "药丸"}
    site_history = {
        "fengchao": [item for item in history if item.get("site", "fengchao") == "fengchao"],
        "invites": [item for item in history if item.get("site") == "invites"]
    }
    today_str = datetime.now().strftime('%Y-%m-%d')
    frost_style = 'background-color: rgba(var(--v-theme-surface), 0.75); backdrop-filter: blur(5px); -webkit-backdrop-filter: blur(5px); border: 1px solid rgba(var(--v-theme-on-surface), 0.12); border-radius: 8px; box-sizing: border-box;'

    def user_attrs(user_info: dict) -> dict:
        if not isinstance(user_info, dict):
            return {}
        attrs = user_info.get("data", {}).get("attributes", {}) or {}
        return attrs if isinstance(attrs, dict) and attrs else user_info

    def user_id(user_info: dict) -> str:
        if not isinstance(user_info, dict):
            return "—"
        return str(user_info.get("data", {}).get("id") or user_info.get("user_id") or user_info.get("id") or "—")

    def stat_block(icon: str, color: str, value: Any, label: str) -> dict:
        value_text = str(value) if value not in (None, "") else "—"
        # 用 outline 替代 border，outline 不占盒模型空间，彻底避免溢出
        stat_style = 'background-color: rgba(var(--v-theme-surface), 0.75); backdrop-filter: blur(5px); -webkit-backdrop-filter: blur(5px); outline: 1px solid rgba(var(--v-theme-on-surface), 0.12); border-radius: 8px; box-sizing: border-box;'
        return {'component': 'VCol', 'props': {'cols': 6, 'md': 6, 'class': 'pa-2'}, 'content': [
            {'component': 'div', 'props': {'class': 'text-center pa-1 d-flex flex-column justify-center', 'style': stat_style}, 'content': [
                {'component': 'div', 'props': {'class': 'd-flex justify-center align-center mb-1'}, 'content': [
                    {'component': 'VIcon', 'props': {'size': 'large', 'style': f'color: {color};', 'class': 'mr-1'}, 'text': icon},
                    {'component': 'span', 'props': {'class': 'text-h5 font-weight-bold'}, 'text': value_text}
                ]},
                {'component': 'div', 'props': {'class': 'text-caption text-medium-emphasis'}, 'text': label}
            ]}
        ]}

    def overview_card(site: str, title: str, user_info: dict) -> dict:
        attrs = user_attrs(user_info)
        records = site_history.get(site, [])
        latest_record = records[0] if records else {}
        today_record = next((item for item in records if item.get("date", "").startswith(today_str)), {})
        status_meta = get_status_meta(today_record) if today_record else {"code": "unknown", "label": "今日未签", "color": "#9E9E9E", "icon": "mdi-help-circle"}
        last_reward = latest_record.get("lastCheckinMoney", attrs.get("lastCheckinMoney")) if latest_record else attrs.get("lastCheckinMoney")
        display_name = attrs.get('displayName') or attrs.get('username') or attrs.get('nickname') or '—'
        avatar_url = attrs.get('avatarUrl') or ""
        unread_count = attrs.get('unreadNotificationCount') or 0
        try:
            unread_count = int(unread_count)
        except (TypeError, ValueError):
            unread_count = 0
        can_checkin = attrs.get('canCheckin')
        if can_checkin is False:
            checkin_chip = {"label": "今日已签", "color": "#4CAF50", "icon": "mdi-check-circle"}
        elif can_checkin is True:
            checkin_chip = {"label": "待签到", "color": "#FB8C00", "icon": "mdi-calendar-clock"}
        else:
            checkin_chip = {"label": "签到状态 —", "color": "#9E9E9E", "icon": "mdi-help-circle"}
        follower_count = attrs.get('followerCount') or 0
        try:
            follower_count = int(follower_count)
        except (TypeError, ValueError):
            follower_count = 0
        return {'component': 'VCol', 'props': {'cols': 12, 'md': 4, 'class': 'd-flex'}, 'content': [
            {'component': 'VCard', 'props': {'variant': 'outlined', 'class': 'h-100 w-100 pa-0', 'style': frost_style}, 'content': [
                {'component': 'VCardTitle', 'props': {'class': 'd-flex align-center py-1 px-2'}, 'content': [
                    {'component': 'VIcon', 'props': {'style': f'color: {site_colors[site]};', 'class': 'mr-2'}, 'text': site_icons[site]},
                    {'component': 'span', 'props': {'class': 'text-subtitle-1 font-weight-bold'}, 'text': title},
                    {'component': 'VSpacer'},
                    {'component': 'VChip', 'props': {'style': f"background-color: {status_meta['color']}; color: white;", 'size': 'small', 'variant': 'elevated'}, 'content': [
                        {'component': 'VIcon', 'props': {'start': True, 'style': 'color: white;', 'size': 'small'}, 'text': status_meta['icon']},
                        {'component': 'span', 'text': status_meta['label']}
                    ]}
                ]},
                {'component': 'VDivider'},
                {'component': 'VCardText', 'props': {'class': 'pa-1', 'style': 'box-sizing: border-box;'}, 'content': [
                    {'component': 'div', 'props': {'class': 'd-flex align-center pa-2', 'style': frost_style}, 'content': [
                        {'component': 'VAvatar', 'props': {'size': 40, 'class': 'mr-2'}, 'content': [
                            {'component': 'VImg', 'props': {'src': avatar_url, 'alt': display_name}}
                        ]} if avatar_url else {'component': 'VAvatar', 'props': {'size': 40, 'color': '#ECEFF1', 'class': 'mr-2'}, 'content': [
                            {'component': 'VIcon', 'props': {'color': '#90A4AE', 'size': 'small'}, 'text': 'mdi-account'}
                        ]},
                        {'component': 'div', 'props': {'class': 'flex-grow-1'}, 'content': [
                            {'component': 'div', 'props': {'class': 'd-flex align-center'}, 'content': [
                                {'component': 'span', 'props': {'class': 'text-h6 font-weight-bold'}, 'text': display_name},
                                {'component': 'VBadge', 'props': {'content': unread_count, 'color': 'error', 'inline': True, 'class': 'ml-2'}, 'content': [
                                    {'component': 'VIcon', 'props': {'size': 'small', 'color': 'error'}, 'text': 'mdi-bell'}
                                ]} if unread_count > 0 else {'component': 'span', 'text': ''}
                            ]},
                            {'component': 'div', 'props': {'class': 'text-body-1 text-medium-emphasis'}, 'text': f"UID：{user_id(user_info)} · 更新：{updated_at.get(site, '—')}"}
                        ]}
                    ]},
                    {'component': 'VRow', 'props': {'no-gutters': True}, 'content': [
                        stat_block(site_icons[site], site_colors[site], format_money(attrs.get('money', latest_record.get('money'))), f"当前{site_points[site]}"),
                        stat_block('mdi-clipboard-check', '#1976D2', attrs.get('totalContinuousCheckIn', latest_record.get('totalContinuousCheckIn', '—')), '连续签到'),
                        stat_block('mdi-gift', '#FF8F00', format_money(last_reward), '最近奖励'),
                        stat_block('mdi-comment-text-outline', '#26A69A', attrs.get('discussionCount', '—'), '主题数')
                    ]}
                ]}
            ]}
        ]}

    def day_status(day_str: str) -> dict:
        """返回某天双站签到状态 {fengchao: code, invites: code}，code 取 success_new/success_already/failed/None。"""
        result = {"fengchao": None, "invites": None}
        for item in history:
            if not item.get("date", "").startswith(day_str):
                continue
            site = item.get("site", "fengchao")
            if site in result and result[site] is None:
                meta = get_status_meta(item)
                # 失败记录不覆盖当天已有成功记录
                if meta["code"] != "failed" or result[site] is None:
                    if meta["code"] != "failed":
                        result[site] = meta["code"]
                    elif result[site] is None:
                        result[site] = "failed"
        return result

    def day_rewards(day_str: str) -> List[dict]:
        rewards = []
        for site in ("fengchao", "invites"):
            site_reward = None
            for item in history:
                if item.get("site", "fengchao") != site or not item.get("date", "").startswith(day_str):
                    continue
                reward = item.get("lastCheckinMoney")
                if reward is None or reward == "":
                    continue
                try:
                    if float(reward) <= 0:
                        if site_reward is None:
                            site_reward = ""
                        continue
                except (ValueError, TypeError):
                    continue
                meta = get_status_meta(item)
                if meta["code"] in ("success_new", "success_already"):
                    site_reward = reward
                    break
                if site_reward is None:
                    site_reward = reward
            if site_reward not in (None, "", 0, "0", 0.0):
                rewards.append({'component': 'div', 'props': {'class': 'd-flex align-center justify-center', 'style': 'line-height: 11px;'}, 'content': [
                    {'component': 'VIcon', 'props': {'size': 9, 'style': f"color: {site_colors[site]};", 'class': 'mr-1'}, 'text': site_icons[site]},
                    {'component': 'span', 'props': {'class': 'font-weight-bold'}, 'text': format_money(site_reward)}
                ]})
        return rewards

    def day_color(statuses: dict) -> str:
        fc, iv = statuses["fengchao"], statuses["invites"]
        fc_ok = fc in ("success_new", "success_already")
        iv_ok = iv in ("success_new", "success_already")
        fc_fail = fc == "failed"
        iv_fail = iv == "failed"
        if fc_ok and iv_ok:
            return "#2E7D32"  # 双站都成功 深绿
        if fc_ok and iv is None:
            return "#FF9800"  # 仅蜂巢 橙
        if iv_ok and fc is None:
            return "#9C27B0"  # 仅药丸 紫
        if fc_ok and iv_fail:
            return "#FF8F00"  # 蜂巢成药丸败 琥珀
        if iv_ok and fc_fail:
            return "#7E57C2"  # 药丸成蜂巢败 浅紫
        if fc_fail and iv_fail:
            return "#F44336"  # 双站失败 红
        if fc_fail or iv_fail:
            return "#EF5350"  # 单站失败 浅红
        return "transparent"  # 无数据

    today = datetime.now()
    year, month = today.year, today.month
    import calendar as _calendar
    cal_days = _calendar.monthcalendar(year, month)
    weekdays = ["一", "二", "三", "四", "五", "六", "日"]
    cal_rows = [{'component': 'tr', 'content': [{'component': 'th', 'props': {'class': 'text-center text-caption font-weight-bold pa-1'}, 'text': w} for w in weekdays]}]
    for week in cal_days:
        cells = []
        for idx, day in enumerate(week):
            if day == 0:
                cells.append({'component': 'td', 'props': {'class': 'text-center pa-0', 'style': 'height: 40px;'}, 'text': ''})
            else:
                day_str = f"{year:04d}-{month:02d}-{day:02d}"
                statuses = day_status(day_str)
                fc_ok = statuses["fengchao"] in ("success_new", "success_already")
                iv_ok = statuses["invites"] in ("success_new", "success_already")
                fc_fail = statuses["fengchao"] == "failed"
                iv_fail = statuses["invites"] == "failed"
                color = day_color(statuses)
                rewards = day_rewards(day_str)
                is_today = day_str == today.strftime("%Y-%m-%d")
                border = "border: 2px solid #1976D2;" if is_today else f"border: 1px solid {color if color != 'transparent' else 'rgba(var(--v-theme-on-surface), 0.08)'};"
                background = f"background-color: {color}22;" if color != "transparent" else "background-color: rgba(var(--v-theme-surface), 0.45);"
                day_icons = []
                if fc_ok:
                    day_icons.append({'component': 'VIcon', 'props': {'size': 12, 'style': 'color: #FF9800;'}, 'text': 'mdi-flower'})
                elif fc_fail:
                    day_icons.append({'component': 'VIcon', 'props': {'size': 12, 'style': 'color: #F44336;'}, 'text': 'mdi-flower-off'})
                if iv_ok:
                    day_icons.append({'component': 'VIcon', 'props': {'size': 12, 'style': 'color: #9C27B0;'}, 'text': 'mdi-pill'})
                elif iv_fail:
                    day_icons.append({'component': 'VIcon', 'props': {'size': 12, 'style': 'color: #F44336;'}, 'text': 'mdi-close-circle'})
                cells.append({'component': 'td', 'props': {'class': 'text-center pa-0', 'style': f"height: 40px; {background} {border} border-radius: 4px;"}, 'content': [
                    {'component': 'div', 'props': {'class': 'text-caption font-weight-bold', 'style': 'line-height: 13px;'}, 'text': str(day)},
                    {'component': 'div', 'props': {'class': 'd-flex justify-center ga-1', 'style': 'height: 13px; margin-top: 1px;'}, 'content': day_icons},
                    {'component': 'div', 'props': {'class': 'text-caption', 'style': 'min-height: 11px; font-size: 10px;'}, 'content': rewards}
                ]})
        cal_rows.append({'component': 'tr', 'content': cells})

    calendar_card = {'component': 'VCard', 'props': {'variant': 'outlined', 'class': 'h-100 w-100 pa-0', 'style': frost_style}, 'content': [
        {'component': 'VCardTitle', 'props': {'class': 'd-flex align-center'}, 'content': [
            {'component': 'VIcon', 'props': {'color': 'primary', 'class': 'mr-2'}, 'text': 'mdi-calendar-month'},
            {'component': 'span', 'props': {'class': 'text-h6 font-weight-bold'}, 'text': f"签到日历（{year}/{month:02d}）"}
        ]},
        {'component': 'VDivider'},
        {'component': 'VCardText', 'props': {'class': 'pa-1'}, 'content': [
            {'component': 'VTable', 'props': {'density': 'compact', 'class': 'text-center'}, 'content': [
                {'component': 'tbody', 'content': cal_rows}
            ]},
            {'component': 'div', 'props': {'class': 'd-flex flex-wrap ga-2 mt-2 text-caption align-center'}, 'content': [
                {'component': 'span', 'props': {'class': 'd-flex align-center'}, 'content': [
                    {'component': 'VIcon', 'props': {'size': 12, 'style': 'color: #FF9800;', 'class': 'mr-1'}, 'text': 'mdi-flower'},
                    {'component': 'span', 'text': '蜂巢'}
                ]},
                {'component': 'span', 'props': {'class': 'd-flex align-center'}, 'content': [
                    {'component': 'VIcon', 'props': {'size': 12, 'style': 'color: #9C27B0;', 'class': 'mr-1'}, 'text': 'mdi-pill'},
                    {'component': 'span', 'text': '药丸'}
                ]}
            ]}
        ]}
    ]}

    components = [
        {'component': 'VRow', 'props': {'class': 'mb-4', 'align': 'stretch'}, 'content': [
            overview_card("fengchao", "蜂巢站", fengchao_user_info),
            overview_card("invites", "药丸站", invites_user_info),
            {'component': 'VCol', 'props': {'cols': 12, 'md': 4, 'class': 'd-flex'}, 'content': [
                calendar_card
            ]}
        ]}
    ]

    rows = []
    for record in history:
        site = record.get("site", "fengchao")
        status_meta = get_status_meta(record)
        failure_count = record.get('failure_count', 0)
        retry = record.get('retry', {})
        retry_text = ""
        if status_meta["code"] == "failed" and retry.get('enabled') and retry.get('current', 0) > 0:
            retry_text = f"将在{retry.get('interval', config.retry_interval)}{retry.get('unit', '分钟')}后重试 ({retry.get('current', 0)}/{retry.get('max', config.retry_count)})"
        point_name = site_points.get(site, "积分")
        point_icon = site_icons.get(site, "mdi-web")
        reward = record.get('lastCheckinMoney')
        reward_text = '—'
        try:
            has_reward = reward not in (None, "") and float(reward) > 0
        except (TypeError, ValueError):
            has_reward = False
        if status_meta["code"] in ("success_new", "success_already") and has_reward:
            reward_text = f"{format_money(reward)}{point_name}"
        elif status_meta["code"] == "success_already":
            reward_text = "已领取"
        rows.append({
            'component': 'tr',
            'content': [
                {'component': 'td', 'content': [{'component': 'VChip', 'props': {'size': 'small', 'variant': 'tonal'}, 'content': [
                    {'component': 'VIcon', 'props': {'start': True, 'size': 'small', 'style': f"color: {site_colors.get(site, '#607D8B')};"}, 'text': point_icon},
                    {'component': 'span', 'text': site_names.get(site, site)}
                ]}]},
                {'component': 'td', 'props': {'class': 'text-caption'}, 'text': record.get("date", "")},
                {'component': 'td', 'content': [{'component': 'VChip', 'props': {'style': f"background-color: {status_meta['color']}; color: white;", 'size': 'small', 'variant': 'elevated'}, 'content': [
                    {'component': 'VIcon', 'props': {'start': True, 'style': 'color: white;', 'size': 'small'}, 'text': status_meta['icon']},
                    {'component': 'span', 'text': status_meta['label']}
                ]}]},
                {'component': 'td', 'text': str(failure_count) if failure_count > 0 else '—'},
                {'component': 'td', 'content': [{'component': 'div', 'props': {'class': 'd-flex align-center'}, 'content': [
                    {'component': 'VIcon', 'props': {'style': f"color: {site_colors.get(site, '#607D8B')};", 'class': 'mr-1'}, 'text': point_icon},
                    {'component': 'span', 'text': format_money(record.get('money'))}
                ]}]},
                {'component': 'td', 'content': [{'component': 'div', 'props': {'class': 'd-flex align-center'}, 'content': [
                    {'component': 'VIcon', 'props': {'style': 'color: #1976D2;', 'class': 'mr-1'}, 'text': 'mdi-clipboard-check'},
                    {'component': 'span', 'text': record.get('totalContinuousCheckIn', '—')}
                ]}]},
                {'component': 'td', 'content': [{'component': 'div', 'props': {'class': 'd-flex align-center'}, 'content': [
                    {'component': 'VIcon', 'props': {'style': 'color: #FF8F00;', 'class': 'mr-1'}, 'text': 'mdi-gift'},
                    {'component': 'span', 'text': reward_text}
                ]}]},
                {'component': 'td', 'props': {'class': 'text-caption'}, 'text': record.get('reason') or retry_text or '—'}
            ]
        })

    if not rows:
        components.append({'component': 'VAlert', 'props': {'type': 'info', 'variant': 'tonal', 'text': '暂无双站签到记录，请先配置蜂巢/药丸账号并启用插件', 'class': 'mb-2', 'prepend-icon': 'mdi-information'}})
        return components

    components.extend([
        {'component': 'VCard', 'props': {'variant': 'outlined', 'class': 'mb-4'}, 'content': [
            {'component': 'VCardTitle', 'props': {'class': 'd-flex align-center'}, 'content': [
                {'component': 'VIcon', 'props': {'style': 'color: #9C27B0;', 'class': 'mr-2'}, 'text': 'mdi-history'},
                {'component': 'span', 'props': {'class': 'text-h6 font-weight-bold'}, 'text': '签到历史'}
            ]},
            {'component': 'VDivider'},
            {'component': 'VCardText', 'props': {'class': 'pa-0 pa-md-2'}, 'content': [
                {'component': 'VResponsive', 'content': [
                    {'component': 'VTable', 'props': {'hover': True, 'density': 'comfortable'}, 'content': [
                        {'component': 'thead', 'content': [{'component': 'tr', 'content': [
                            {'component': 'th', 'text': '站点'},
                            {'component': 'th', 'text': '时间'},
                            {'component': 'th', 'text': '状态'},
                            {'component': 'th', 'text': '失败次数'},
                            {'component': 'th', 'text': '当前积分'},
                            {'component': 'th', 'text': '签到天数'},
                            {'component': 'th', 'text': '奖励'},
                            {'component': 'th', 'text': '说明'}
                        ]}]},
                        {'component': 'tbody', 'content': rows}
                    ]}
                ]}
            ]}
        ]},
        {'component': 'style', 'text': ".v-table { border-radius: 8px; overflow: hidden; } .v-table th { background-color: rgba(var(--v-theme-primary), 0.05); color: rgb(var(--v-theme-primary)); font-weight: 600; }"}
    ])
    return components
