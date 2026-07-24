"""AutoPtCheckin 详情页的无状态 Vuetify 组件构建工具。"""
from datetime import datetime
from typing import Dict, List, Tuple

from app.log import logger


def build_history_panels(records: List[dict]) -> Tuple[Dict[str, List[dict]], List[dict]]:
    """按原始追加顺序去重历史记录，分组排序后生成站点折叠面板。"""
    site_day_records = {}
    for record in records:
        site_name = record.get("site", "未知站点")
        date_str = record.get("date", "")
        # 不能在去重前排序：后追加的汇总状态必须覆盖详细执行文案。
        site_day_records[f"{site_name}_{date_str}"] = record

    site_data = {}
    for record in site_day_records.values():
        site_name = record.get("site", "未知站点")
        site_data.setdefault(site_name, []).append(record)

    panels = []
    for site_name, site_records in site_data.items():
        try:
            site_records.sort(key=lambda item: item.get("day_obj", datetime.now().date()), reverse=True)
        except Exception as e:
            logger.debug(f"{site_name} 历史记录排序失败: {e}")

        latest_status = site_records[0].get("status", "未知状态")
        status_color, status_icon = resolve_status_style(latest_status)
        panels.append(create_expansion_panel(
            site_name, site_records, status_color, status_icon, latest_status))

    return site_data, panels

def resolve_status_style(status: str) -> Tuple[str, str]:
    """根据状态文本返回 (颜色, 图标)"""
    if "失败" in status or "错误" in status:
        return "deep-orange-lighten-3", "mdi-emoticon-sad-outline"
    if "Cookie已失效" in status:
        return "pink-lighten-3", "mdi-cookie-off"
    if "重试" in status:
        return "amber-lighten-3", "mdi-emoticon-confused-outline"
    if "已签到" in status:
        return "light-blue-lighten-3", "mdi-emoticon-cool-outline"
    if "成功" in status:
        return "teal-lighten-3", "mdi-emoticon-happy-outline"
    return "teal-lighten-3", "mdi-emoticon-happy-outline"

def create_expansion_panel(site_name, records, status_color, status_icon, latest_status):
    """创建站点折叠面板"""
    # 生成站点图标（使用站点名的首字母）
    site_initial = site_name[0].upper() if site_name else "?"

    # 生成记录列表
    records_list = []
    for record in records:
        date_str = record.get("date", "")
        status_text = record.get("status", "未知状态")

        # 确定状态颜色和图标
        record_color = "success"
        record_icon = "mdi-check-circle"

        if "失败" in status_text or "错误" in status_text:
            record_color = "error"
            record_icon = "mdi-alert-circle"
        elif "Cookie已失效" in status_text:
            record_color = "error"
            record_icon = "mdi-cookie-off"
        elif "重试" in status_text:
            record_color = "warning"
            record_icon = "mdi-refresh"
        elif "已签到" in status_text:
            record_color = "info"
            record_icon = "mdi-check"
        elif "登录成功" in status_text:
            record_color = "success"
            record_icon = "mdi-login-variant"

        # 创建记录项
        records_list.append({
            'component': 'VListItem',
            'props': {
                'class': 'site-item px-2 py-1'
            },
            'content': [
                {
                    'component': 'div',
                    'props': {
                        'class': 'd-flex align-center w-100'
                    },
                    'content': [
                        {
                            'component': 'VChip',
                            'props': {
                                'color': 'grey-lighten-3',
                                'size': 'x-small',
                                'class': 'date-chip mr-2',
                                'variant': 'flat',
                                'prepend-icon': 'mdi-flower-tulip'
                            },
                            'text': date_str
                        },
                        {
                            'component': 'VSpacer'
                        },
                        {
                            'component': 'VChip',
                            'props': {
                                'color': record_color,
                                'size': 'x-small',
                                'class': 'ml-2 status-chip',
                                'variant': 'flat',
                                'prepend-icon': record_icon
                            },
                            'text': status_text
                        }
                    ]
                }
            ]
        })

    # 创建折叠面板
    return {
        'component': 'VExpansionPanel',
        'content': [
            {
                'component': 'VExpansionPanelTitle',
                'content': [{
                    'component': 'div',
                    'props': {
                        'class': 'd-flex align-center'
                    },
                    'content': [
                        {
                            'component': 'div',
                            'props': {
                                'class': 'site-icon'
                            },
                            'text': site_initial
                        },
                        {
                            'component': 'span',
                            'props': {
                                'class': 'font-weight-medium'
                            },
                            'text': site_name
                        },
                        {
                            'component': 'VSpacer'
                        },
                        {
                            'component': 'VIcon',
                            'props': {
                                'color': status_color,
                                'class': 'mr-2',
                                'size': 'small'
                            },
                            'text': status_icon
                        },
                        {
                            'component': 'span',
                            'props': {
                                'class': f'text-{status_color} text-caption'
                            },
                            'text': latest_status
                        }
                    ]
                }]
            },
            {
                'component': 'VExpansionPanelText',
                'content': [
                    {
                        'component': 'VList',
                        'props': {
                            'lines': 'one',
                            'density': 'compact'
                        },
                        'content': records_list
                    }
                ]
            }
        ]
    }


def record_to_row(record: dict) -> dict:
    """辅助函数：将记录转换为表格行"""
    status = record.get("status", "")

    # 确定状态图标和颜色
    icon = "mdi-check-circle"
    color = "success"

    if "失败" in status or "错误" in status:
        icon = "mdi-alert-circle"
        color = "error"
    elif "Cookie已失效" in status:
        icon = "mdi-cookie-off"
        color = "error"
    elif "已签到" in status:
        icon = "mdi-check"
        color = "grey"
    elif "成功" in status:
        icon = "mdi-check-circle"
        color = "success"

    return {
        'component': 'tr',
        'props': {
            'class': 'text-sm'
        },
        'content': [
            {
                'component': 'td',
                'props': {
                    'class': 'text-start'
                },
                'text': record.get("date", "")
            },
            {
                'component': 'td',
                'props': {
                    'class': 'text-start'
                },
                'text': status
            },
            {
                'component': 'td',
                'props': {
                    'class': 'text-center'
                },
                'content': [
                    {
                        'component': 'VIcon',
                        'props': {
                            'color': color,
                            'size': 'small'
                        },
                        'text': icon
                    }
                ]
            }
        ]
    }
