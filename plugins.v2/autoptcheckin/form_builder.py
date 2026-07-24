"""AutoPtCheckin 配置页的无状态 Vuetify 表单构建工具。"""
from typing import Any, Dict, List, Tuple


def build_form(site_options: List[dict]) -> Tuple[List[dict], Dict[str, Any]]:
    """根据入口层准备的站点选项构造配置表单和默认配置。"""
    return [
        {
            'component': 'VForm',
            'content': [
                # ── 开关行 ──────────────────────────────────────────
                {
                    'component': 'VRow',
                    'content': [
                        {
                            'component': 'VCol',
                            'props': {'cols': 12, 'md': 3},
                            'content': [{'component': 'VSwitch', 'props': {'model': 'enabled', 'label': '启用插件'}}]
                        },
                        {
                            'component': 'VCol',
                            'props': {'cols': 12, 'md': 3},
                            'content': [{'component': 'VSwitch', 'props': {'model': 'notify', 'label': '发送通知'}}]
                        },
                        {
                            'component': 'VCol',
                            'props': {'cols': 12, 'md': 3},
                            'content': [{'component': 'VSwitch', 'props': {'model': 'onlyonce', 'label': '立即运行一次'}}]
                        },
                        {
                            'component': 'VCol',
                            'props': {'cols': 12, 'md': 3},
                            'content': [{'component': 'VSwitch', 'props': {'model': 'clean', 'label': '清理本日缓存'}}]
                        },
                    ]
                },
                # ── 调度 & 参数行 ────────────────────────────────────
                {
                    'component': 'VRow',
                    'content': [
                        {
                            'component': 'VCol',
                            'props': {'cols': 12, 'md': 3},
                            'content': [
                                {
                                    'component': 'VSelect',
                                    'props': {
                                        'model': 'cron_mode',
                                        'label': '调度模式',
                                        'items': [
                                            {'title': 'Cron表达式', 'value': 'cron'},
                                            {'title': '间隔随机', 'value': 'interval'},
                                        ]
                                    }
                                }
                            ]
                        },
                        {
                            'component': 'VCol',
                            'props': {'cols': 12, 'md': 3},
                            'content': [
                                {
                                    'component': 'VCronField',
                                    'props': {
                                        'model': 'cron',
                                        'label': 'Cron表达式',
                                        'placeholder': '0 9 * * *'
                                    }
                                }
                            ]
                        },
                        {
                            'component': 'VCol',
                            'props': {'cols': 12, 'md': 2},
                            'content': [
                                {
                                    'component': 'VTextField',
                                    'props': {'model': 'interval_hours', 'label': '间隔(小时)', 'placeholder': '2'}
                                }
                            ]
                        },
                        {
                            'component': 'VCol',
                            'props': {'cols': 12, 'md': 2},
                            'content': [
                                {
                                    'component': 'VTextField',
                                    'props': {'model': 'begin_hour', 'label': '开始时', 'placeholder': '9'}
                                }
                            ]
                        },
                        {
                            'component': 'VCol',
                            'props': {'cols': 12, 'md': 2},
                            'content': [
                                {
                                    'component': 'VTextField',
                                    'props': {'model': 'end_hour', 'label': '结束时', 'placeholder': '23'}
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
                            'props': {'cols': 12, 'md': 6},
                            'content': [
                                {
                                    'component': 'VTextField',
                                    'props': {
                                        'model': 'retry_keyword',
                                        'label': '重试关键词',
                                        'placeholder': '支持正则表达式，命中才重签'
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
                                        'model': 'auto_cf',
                                        'label': '自动优选',
                                        'placeholder': '命中重试关键词次数（0-关闭）'
                                    }
                                }
                            ]
                        },
                    ]
                },
                # ── 站点选择 ─────────────────────────────────────────
                {
                    'component': 'VRow',
                    'content': [
                        {
                            'component': 'VCol',
                            'content': [
                                {
                                    'component': 'VSelect',
                                    'props': {
                                        'chips': True,
                                        'multiple': True,
                                        'model': 'sign_sites',
                                        'label': '签到站点',
                                        'items': site_options
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
                            'content': [
                                {
                                    'component': 'VSelect',
                                    'props': {
                                        'chips': True,
                                        'multiple': True,
                                        'model': 'login_sites',
                                        'label': '登录站点',
                                        'items': site_options
                                    }
                                }
                            ]
                        }
                    ]
                },
                # ── 分割线 ───────────────────────────────────────────
                {
                    'component': 'VRow',
                    'content': [
                        {'component': 'VCol', 'props': {'cols': 12}, 'content': [{'component': 'VDivider'}]}
                    ]
                },
                # ── 自定义站点 ───────────────────────────────────────
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
                                        'text': '自定义站点：每行一个，格式：站点名称|站点地址|是否仿真(Y/N)。'
                                                'Cookie 通过 CookieCloud 自动同步。'
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
                                    'component': 'VTextarea',
                                    'props': {
                                        'model': 'custom_site_urls',
                                        'label': '自定义站点列表',
                                        'rows': 5,
                                        'placeholder': '每行一个站点，格式：\n'
                                                       '站点名称|站点地址|是否仿真(Y/N)\n'
                                                       '例如：思齐|https://si-qi.xyz/|N'
                                    }
                                }
                            ]
                        }
                    ]
                },
                # ── 说明 & 警告 ──────────────────────────────────────
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
                                        'text': '调度模式说明：'
                                                '1、Cron表达式：填写 5 位 cron（如 0 9 * * *），精确控制执行时间；'
                                                '2、间隔随机：在开始时~结束时范围内，按间隔小时数随机生成多个执行点；'
                                                '3、两种模式都不配置时默认 9-23 点随机执行 2 次。'
                                                '每天首次全量执行，后续仅重试命中关键词的站点。'
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
                                    'component': 'VAlert',
                                    'props': {
                                        'type': 'info',
                                        'variant': 'tonal',
                                        'text': '重试关键词：支持正则，命中签到结果才纳入下次重试。'
                                    }
                                }
                            ]
                        },
                        {
                            'component': 'VCol',
                            'props': {'cols': 12, 'md': 6},
                            'content': [
                                {
                                    'component': 'VAlert',
                                    'props': {
                                        'type': 'info',
                                        'variant': 'tonal',
                                        'text': '自动优选：命中重试关键词次数超过阈值时触发 Cloudflare IP 优选（需配置优选插件与自定义 Hosts 插件）。'
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
                            'props': {'cols': 12},
                            'content': [
                                {
                                    'component': 'VAlert',
                                    'props': {
                                        'type': 'warning',
                                        'variant': 'tonal',
                                        'text': '注意：部分站点（如馒头）不将程序签到/登录计为用户活跃，'
                                                '提示成功仍存在掉号风险，请结合站点公告自行判断。'
                                    }
                                }
                            ]
                        }
                    ]
                },
            ]
        }
    ], {
        "enabled": False,
        "notify": True,
        "cron": "",
        "cron_mode": "interval",
        "interval_hours": 2,
        "begin_hour": 9,
        "end_hour": 23,
        "auto_cf": 0,
        "onlyonce": False,
        "clean": False,
        "queue_cnt": 5,
        "sign_sites": [],
        "login_sites": [],
        "retry_keyword": "错误|失败",
        "custom_site_urls": "",
        "custom_sites_data": []
    }
