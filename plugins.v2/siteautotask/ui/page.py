"""运行数据页：按站点卡片展示，每站独立显示任务执行情况和趋势。"""
try:
    from ..utils.feedback import NotificationIcons
    from ..utils.display import display_record_lines, format_record_line
except ImportError:  # 便于脱离 MoviePilot 包环境做单元测试
    from siteautotask_feedback import NotificationIcons

    def display_record_lines(record):
        return [{
            "task": str(record.get("task_label") or record.get("task_id") or ""),
            "status": str(record.get("status") or ""),
            "rewards": (record.get("feedback") or {}).get("rewards") or record.get("rewards") or [],
        }]

    def format_record_line(item, icon_lookup):
        rewards = "；".join(
            f"{icon_lookup.get(reward.get('type', ''))} {reward.get('description', '')}".strip()
            for reward in item.get("rewards") or []
            if reward.get("description")
        )
        return f"{item['task']} -> {rewards or item['status'] or '无反馈'}"


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
    history = plugin.history.latest(30)

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

    # 按站点聚合最近记录，每站保留最近3次运行和各任务的最新状态。
    site_data = {}  # site -> {records: [...], runs: [(date, success_count, total)]}
    site_order = []
    for run in history:
        run_date = run.get("date", "")
        run_records = run.get("records", []) or []
        run_by_site = {}
        for r in run_records:
            site = r.get("site") or r.get("domain") or "未知站点"
            if site not in site_data:
                site_data[site] = {"latest_records": [], "runs": []}
                site_order.append(site)
            run_by_site.setdefault(site, []).append(r)
        # 记录每站本轮运行趋势
        for site, recs in run_by_site.items():
            s = sum(1 for r in recs if r.get("success"))
            site_data[site]["runs"].append((run_date, s, len(recs)))
        # 更新每站最新任务记录（只保留最近一次运行的任务）
        for site, recs in run_by_site.items():
            site_data[site]["latest_records"] = recs

    def _site_card(site, data):
        records = data["latest_records"]
        runs = list(reversed(data["runs"]))[:3]  # 最近3次，最新在前
        site_success = sum(1 for r in records if r.get("success"))
        site_total = len(records)
        all_ok = site_success == site_total and site_total > 0

        # 标题行
        title_row = {
            "component": "div",
            "props": {"class": "d-flex align-center pb-2"},
            "content": [
                {"component": "span", "props": {"class": "text-subtitle-1 font-weight-medium me-2"}, "text": f"🌐 {site}"},
                {"component": "VSpacer"},
                {"component": "VChip", "props": {
                    "size": "small", "variant": "tonal",
                    "color": "success" if all_ok else ("warning" if site_success > 0 else "error"),
                }, "text": f"{site_success}/{site_total}"},
            ],
        }

        # 任务行
        task_rows = []
        for r in records:
            icon = "✅" if r.get("success") else "❌"
            for item in display_record_lines(r):
                line_text = format_record_line(item, NotificationIcons)
                task_rows.append({
                    "component": "div",
                    "props": {"class": "d-flex align-start py-1"},
                    "content": [
                        {"component": "span", "props": {"class": "me-2 text-body-2"}, "text": icon},
                        {"component": "div", "props": {"class": "text-body-2 flex-grow-1"}, "text": line_text},
                    ],
                })

        # 趋势行
        trend_chips = []
        for run_date, s, t in runs:
            ok = s == t and t > 0
            label = run_date[-8:] if len(run_date) >= 8 else run_date  # HH:MM:SS
            trend_chips.append({
                "component": "VChip",
                "props": {
                    "size": "x-small", "variant": "flat",
                    "color": "success" if ok else "error",
                    "class": "me-1",
                },
                "text": f"{'✅' if ok else '❌'} {label}",
            })

        trend_row = {
            "component": "div",
            "props": {"class": "d-flex align-center pt-2 mt-1"},
            "content": [
                {"component": "span", "props": {"class": "text-caption text-medium-emphasis me-2"}, "text": "趋势"},
                *trend_chips,
            ],
        } if trend_chips else {"component": "div", "props": {"class": "pt-2"}, "text": ""}

        return {
            "component": "VCol",
            "props": {"cols": 12, "md": 6},
            "content": [{
                "component": "VCard",
                "props": {"variant": "outlined", "class": "h-100"},
                "content": [
                    {"component": "VCardText", "props": {"class": "pa-3"}, "content": [
                        title_row,
                        {"component": "VDivider", "props": {"class": "mb-2"}},
                        *(task_rows or [{"component": "div", "props": {"class": "text-medium-emphasis py-2"}, "text": "暂无记录"}]),
                        {"component": "VDivider", "props": {"class": "mt-2"}},
                        trend_row,
                    ]},
                ],
            }],
        }

    site_cards = [_site_card(site, site_data[site]) for site in site_order]

    history_card = {
        "component": "VCard",
        "props": {"variant": "outlined"},
        "content": [
            {"component": "VCardTitle", "props": {"class": "text-subtitle-1 py-2"}, "content": [
                {"component": "span", "text": "站点任务执行情况"},
                {"component": "VSpacer"},
                {"component": "span", "props": {"class": "text-caption text-medium-emphasis"}, "text": f"共 {len(site_order)} 个站点"},
            ]},
            {"component": "VDivider"},
            {"component": "VCardText", "content": [{
                "component": "VRow",
                "props": {"dense": True},
                "content": site_cards or [{"component": "div", "props": {"class": "text-medium-emphasis pa-2"}, "text": "暂无运行记录，执行任务后此处显示站点卡片"}],
            }]},
        ],
    }

    return [overview_card, history_card]
