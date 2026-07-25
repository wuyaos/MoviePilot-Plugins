"""运行数据页：按运行批次折叠、站点分组、任务状态+反馈奖励一体。"""
try:
    from ..utils.feedback import NotificationIcons
    from ..utils.display import display_task
except ImportError:  # 便于脱离 MoviePilot 包环境做单元测试
    from siteautotask_feedback import NotificationIcons

    def display_task(site_name, task_label, task_type):
        return str(task_label or "")


def _text(value):
    return "" if value is None else str(value)


def _reward_line(rewards):
    parts = []
    for r in rewards or []:
        icon = NotificationIcons.get(r.get("type", ""))
        desc = _text(r.get("description"))
        parts.append(f"{icon} {desc}" if desc else icon)
    return "；".join(parts)


def build_page(plugin):
    history = plugin.history.latest(20)

    # 累计统计
    total = success = 0
    last_success = last_fail = 0
    last_date = "无记录"
    if history:
        last = history[0]
        last_date = last.get("date") or "无记录"
        for r in last.get("records", []):
            if r.get("success"):
                last_success += 1
            else:
                last_fail += 1
    for run in history:
        for r in run.get("records", []):
            total += 1
            if r.get("success"):
                success += 1
    fail = total - success
    cfg = plugin.config

    def stat_cell(label, value, color="text-primary"):
        return {
            "component": "VCol",
            "props": {"cols": 6, "md": 3},
            "content": [{
                "component": "div",
                "props": {"class": "d-flex flex-column align-center py-1"},
                "content": [
                    {"component": "div", "props": {"class": f"text-h6 {color}"}, "text": str(value)},
                    {"component": "div", "props": {"class": "text-caption text-medium-emphasis"}, "text": label},
                ],
            }],
        }

    overview_card = {
        "component": "VCard",
        "props": {"variant": "outlined", "class": "mb-3"},
        "content": [
            {"component": "VCardTitle", "props": {"class": "text-subtitle-1 py-2"}, "text": "运行统计概览"},
            {"component": "VDivider"},
            {"component": "VCardText", "content": [{
                "component": "VRow",
                "props": {"dense": True},
                "content": [
                    stat_cell(f"最近一次 {last_date}", f"{last_success}/{last_success + last_fail}", "text-success" if last_fail == 0 else "text-warning"),
                    stat_cell("历史成功", success, "text-success"),
                    stat_cell("历史失败", fail, "text-error" if fail else "text-medium-emphasis"),
                    stat_cell(f"重试 {cfg.retry_count}次/{cfg.retry_interval}分", "—", "text-medium-emphasis"),
                ],
            }]},
        ],
    }

    panels = []
    for run in history:
        run_date = run.get("date", "")
        records = run.get("records", []) or []
        run_success = sum(1 for r in records if r.get("success"))
        run_fail = len(records) - run_success

        # 按站点分组
        sites_map = {}
        site_order = []
        for r in records:
            site = r.get("site") or r.get("domain") or "未知站点"
            if site not in site_order:
                site_order.append(site)
            sites_map.setdefault(site, []).append(r)

        site_blocks = []
        for site in site_order:
            recs = sites_map[site]
            site_success = sum(1 for r in recs if r.get("success"))
            site_block = {
                "component": "div",
                "props": {"class": "mb-2"},
                "content": [{
                    "component": "div",
                    "props": {"class": "d-flex align-center text-subtitle-2 py-1"},
                    "content": [
                        {"component": "span", "text": f"🔔 {site}"},
                        {"component": "VSpacer"},
                        {"component": "VChip", "props": {"size": "x-small", "variant": "tonal", "color": "success" if site_success == len(recs) else "warning"}, "text": f"{site_success}/{len(recs)}"},
                    ],
                }, {"component": "VDivider", "props": {"class": "mb-1"}}],
            }
            # 任务行：紧凑列表
            for r in recs:
                icon = "✅" if r.get("success") else "❌"
                task_name = display_task(
                    site,
                    r.get("task_label") or r.get("task_id"),
                    r.get("task_type"),
                )
                status = _text(r.get("status"))
                rewards = (r.get("feedback") or {}).get("rewards") or r.get("rewards") or []
                reward_str = _reward_line(rewards)
                task_row = {
                    "component": "div",
                    "props": {"class": "d-flex align-start py-1"},
                    "content": [
                        {"component": "span", "props": {"class": "me-2"}, "text": icon},
                        {"component": "div", "props": {"class": "flex-grow-1"}, "content": [
                            {"component": "div", "props": {"class": "text-body-2"}, "text": f"{task_name}：{status}"},
                        ] + ([{"component": "div", "props": {"class": "text-caption text-medium-emphasis mt-1"}, "text": reward_str}] if reward_str else [])},
                    ],
                }
                site_block["content"].append(task_row)
            site_blocks.append(site_block)

        panels.append({
            "component": "VExpansionPanel",
            "content": [{
                "component": "VExpansionPanelTitle",
                "content": [{
                    "component": "div",
                    "props": {"class": "d-flex align-center w-100"},
                    "content": [
                        {"component": "span", "props": {"class": "font-weight-medium me-2"}, "text": run_date},
                        {"component": "VChip", "props": {"size": "x-small", "variant": "tonal", "color": "success", "class": "me-1"}, "text": f"成功 {run_success}"},
                        {"component": "VChip", "props": {"size": "x-small", "variant": "tonal", "color": "error", "class": "me-1"}, "text": f"失败 {run_fail}"} if run_fail else {"component": "span", "text": ""},
                    ],
                }],
            }, {
                "component": "VExpansionPanelText",
                "content": site_blocks or [{"component": "div", "props": {"class": "text-medium-emphasis pa-2"}, "text": "无详细记录"}],
            }],
        })

    history_card = {
        "component": "VCard",
        "props": {"variant": "outlined"},
        "content": [
            {"component": "VCardTitle", "props": {"class": "text-subtitle-1 py-2"}, "content": [
                {"component": "span", "text": "执行历史记录"},
                {"component": "VSpacer"},
                {"component": "span", "props": {"class": "text-caption text-medium-emphasis"}, "text": f"共 {len(history)} 次运行"},
            ]},
            {"component": "VDivider"},
            {"component": "VCardText", "content": [{
                "component": "VExpansionPanels",
                "props": {"variant": "accordion", "multiple": True},
                "content": panels if panels else [{"component": "div", "props": {"class": "text-medium-emphasis pa-2"}, "text": "暂无运行记录，执行任务后此处显示历史"}],
            }]},
        ],
    }

    return [overview_card, history_card]
