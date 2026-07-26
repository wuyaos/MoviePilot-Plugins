"""运行数据页：按站点卡片展示，每站独立显示任务执行情况和趋势。"""
try:
    from ..utils.feedback import NotificationIcons
    from ..utils.display import display_record_lines, format_record_line, display_task
    from ..core.task_keys import claim_task_key, site_task_key
except ImportError:  # 便于脱离 MoviePilot 包环境做单元测试
    from siteautotask_feedback import NotificationIcons

    def display_task(_site, label, _task_type, **_kwargs):
        return str(label)

    def site_task_key(site, task):
        return f"task_{site.get('id')}_{task.get('name') or task.get('id', '').split('_')[-1]}"

    def claim_task_key(site, task):
        return f"claim_{site.get('id')}_{task.get('name') or task.get('id', '').split('_')[-1]}"

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
            "props": {"cols": 6, "md": 3, "class": "d-flex"},
            "content": [{
                "component": "div",
                "props": {
                    "class": "d-flex flex-column align-center justify-center pa-2 flex-grow-1",
                    "style": "background-color: rgba(var(--v-theme-surface), 0.75);border: 1px solid rgba(var(--v-theme-on-surface), 0.12);border-radius: 8px;box-sizing: border-box;",
                },
                "content": [
                    {"component": "div", "props": {"class": f"text-h6 {color}"}, "text": str(value)},
                    {"component": "div", "props": {"class": "text-caption text-medium-emphasis text-center"}, "text": label},
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

    # 以当前“启用站点 + 启用任务”作为卡片基准；历史仅补充每个单元的最近状态和趋势。
    selected_ids = {str(site_id) for site_id in (getattr(cfg, "chat_sites", None) or [])}
    site_data = {}
    site_order = []
    for option in plugin.support_site_options():
        if str(option.get("id")) not in selected_ids:
            continue
        enabled_tasks = []
        for task in option.get("tasks") or []:
            key = claim_task_key(option, task) if task.get("claim_options") else site_task_key(option, task)
            value = plugin.claim_task_id(key) if task.get("claim_options") else plugin.task_enabled(key)
            if value:
                enabled_tasks.append(task)
        if not enabled_tasks:
            continue
        site_name = option.get("name") or option.get("domain") or "未知站点"
        site_data[site_name] = {
            "domain": option.get("domain") or "",
            "url": (option.get("url") or "").strip(),
            "tasks": {},
        }
        for task in enabled_tasks:
            task_id = task.get("id") or ""
            base_key = f"{option.get('domain') or ''}:{task_id}"
            site_data[site_name]["tasks"][base_key] = {
                "record": {
                    "site": site_name,
                    "domain": option.get("domain") or "",
                    "task_id": task_id,
                    "task_label": task.get("label") or task_id,
                    "task_type": task.get("task_type"),
                    "status": "尚未执行",
                    "placeholder": True,
                },
                "runs": [],
            }
        site_order.append(site_name)

    # history.latest() 已按时间倒序返回，因此首次命中的记录就是该执行单元最近状态。
    for run in history:
        run_date = run.get("date", "")
        for record in run.get("records", []) or []:
            site_name = record.get("site") or record.get("domain") or "未知站点"
            data = site_data.get(site_name)
            if not data:
                continue  # 已禁用站点或任务不在卡片中展示历史残留
            domain = record.get("domain") or data["domain"]
            task_id = record.get("task_id") or ""
            base_key = f"{domain}:{task_id}"
            parent = data["tasks"].get(base_key)
            if not parent and not task_id:
                # 兼容旧历史：旧记录可能只有 task_label，没有 task_id。
                parent = next(
                    (entry for entry in data["tasks"].values()
                     if entry["record"].get("task_label") == record.get("task_label")),
                    None,
                )
                if parent:
                    base_key = next(key for key, entry in data["tasks"].items() if entry is parent)
            if not parent:
                continue  # 已禁用任务不展示历史残留
            unit_key = record.get("execution_key") or base_key
            entry = data["tasks"].setdefault(unit_key, {"record": None, "runs": []})
            if entry["record"] is None or entry["record"].get("placeholder"):
                entry["record"] = record
            entry["runs"].append((run_date, bool(record.get("success"))))
            # 有拆分单元的任务不再显示父任务的“尚未执行”占位行。
            if unit_key != base_key and parent["record"].get("placeholder"):
                data["tasks"].pop(base_key, None)

    def _task_trend(runs):
        states = ["✅" if success else "❌" for _date, success in runs[:3]]
        return " ".join(states)

    # 与论坛签到数据页统一：主题变量保障深浅色可读，外层卡片才有边框。
    site_card_style = (
        "background-color: rgba(var(--v-theme-surface), 0.75);"
        "backdrop-filter: blur(5px);-webkit-backdrop-filter: blur(5px);"
        "border: 1px solid rgba(var(--v-theme-on-surface), 0.12);"
        "border-radius: 8px;box-sizing: border-box;"
    )

    def _site_card(site, data):
        entries = list(data["tasks"].values())
        records = [entry["record"] for entry in entries if entry.get("record")]
        site_success = sum(1 for r in records if r.get("success"))
        site_total = len(records)
        all_ok = site_success == site_total and site_total > 0

        site_title = {
            "component": "VBtn",
            "props": {
                "href": data["url"], "target": "_blank", "variant": "text", "color": "primary",
                "class": "text-subtitle-1 font-weight-medium pa-0 me-2", "append-icon": "mdi-open-in-new",
            },
            "text": f"🌐 {site}",
        } if data["url"] else {
            "component": "span", "props": {"class": "text-subtitle-1 font-weight-medium me-2"}, "text": f"🌐 {site}",
        }
        title_row = {
            "component": "div",
            "props": {"class": "d-flex align-center pb-2"},
            "content": [
                site_title,
                {"component": "VSpacer"},
                {"component": "VChip", "props": {
                    "size": "small", "variant": "tonal",
                    "color": "success" if all_ok else ("warning" if site_success > 0 else "error"),
                }, "text": f"{site_success}/{site_total}"},
            ],
        }

        task_rows = []
        for entry in entries:
            record = entry["record"]
            if record.get("placeholder"):
                icon = "⏳"
                line_text = display_task(site, record.get("task_label"), record.get("task_type")) + " -> 尚未执行"
            else:
                icon = "✅" if record.get("success") else "❌"
                rendered = display_record_lines(record)
                line_text = "；".join(format_record_line(item, NotificationIcons) for item in rendered)
            trend = _task_trend(entry.get("runs") or [])
            task_rows.append({
                "component": "div",
                "props": {"class": "d-flex align-start py-1"},
                "content": [
                    {"component": "span", "props": {"class": "me-2 text-body-2"}, "text": icon},
                    {"component": "div", "props": {"class": "text-body-2 flex-grow-1"}, "content": [
                        {"component": "div", "text": line_text},
                        {"component": "div", "props": {"class": "text-caption text-medium-emphasis"}, "text": f"最近{min(len(entry.get('runs') or []), 3)}次：{trend}"} if trend else None,
                    ]},
                ],
            })
            task_rows[-1]["content"][1]["content"] = [part for part in task_rows[-1]["content"][1]["content"] if part]

        return {
            "component": "VCol",
            "props": {"cols": 12, "md": 6, "class": "d-flex"},
            "content": [{
                "component": "VCard",
                "props": {
                    "variant": "outlined", "class": "h-100 w-100 pa-0",
                    "style": site_card_style,
                },
                "content": [
                    {"component": "VCardText", "props": {"class": "pa-3"}, "content": [
                        title_row,
                        {"component": "VDivider", "props": {"class": "mb-2"}},
                        *(task_rows or [{"component": "div", "props": {"class": "text-medium-emphasis py-2"}, "text": "暂无启用任务"}]),
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
                "props": {"dense": True, "align": "stretch"},
                "content": site_cards or [{"component": "div", "props": {"class": "text-medium-emphasis pa-2"}, "text": "暂无运行记录，执行任务后此处显示站点卡片"}],
            }]},
        ],
    }

    return [overview_card, history_card]
