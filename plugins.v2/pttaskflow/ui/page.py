"""数据页：运行统计概览 + 按站点任务状态卡片 + 最近三次趋势。"""

ICONS = {
    "上传量": "⬆️", "下载量": "⬇️", "魔力值": "✨",
    "VIP": "👑", "raw_feedback": "📝",
}


def _result_text(record):
    rewards = "；".join(
        f"{ICONS.get(item.get('type'), '📌')} {item.get('description', '')}".strip()
        for item in record.get("rewards") or [] if item.get("description")
    )
    return rewards or record.get("status") or "无反馈"


def _stat_cell(label, value, color="text-primary"):
    return {
        "component": "VCol", "props": {"cols": 6, "md": 3, "class": "d-flex"},
        "content": [{
            "component": "div", "props": {
                "class": "d-flex flex-column align-center justify-center pa-2 flex-grow-1",
                "style": "background-color: rgba(var(--v-theme-surface), 0.75);"
                         "border: 1px solid rgba(var(--v-theme-on-surface), 0.12);"
                         "border-radius: 8px;box-sizing: border-box;",
            }, "content": [
                {"component": "div", "props": {"class": f"text-h6 {color}"}, "text": str(value)},
                {"component": "div", "props": {
                    "class": "text-caption text-medium-emphasis text-center",
                }, "text": label},
            ],
        }],
    }


def _enabled_site_data(plugin):
    """以当前启用站点/任务为卡片基准，历史残留不反向创建卡片。"""
    selected = {str(value) for value in plugin.config.site_ids}
    data = {}
    order = []
    for option in plugin.available_site_options():
        if str(option["id"]) not in selected:
            continue
        site = plugin.build_site(option["site"])
        task_entries = {}
        for task in site.tasks:
            if not task.is_enabled(site, plugin.raw_config):
                continue
            base_key = f"{site.domain}:{task.name}"
            task_entries[base_key] = {
                "record": {
                    "site": site.site_name, "domain": site.domain,
                    "task_name": task.name, "task_type": task.task_type,
                    "unit_label": task.label(site), "status": "尚未执行",
                    "placeholder": True, "success": False,
                },
                "runs": [],
            }
        if not task_entries:
            continue
        data[site.site_name] = {
            "domain": site.domain, "url": site.url, "tasks": task_entries,
        }
        order.append(site.site_name)
    return data, order


def _merge_history(site_data, history):
    for run in history:  # latest() 已倒序，首个就是最近状态
        run_date = run.get("date", "")
        for record in run.get("records") or []:
            data = site_data.get(record.get("site") or "")
            if not data:
                continue
            base_key = f"{record.get('domain') or data['domain']}:{record.get('task_name') or ''}"
            parent = data["tasks"].get(base_key)
            if not parent:
                continue
            unit_key = record.get("execution_key") or base_key
            entry = data["tasks"].setdefault(unit_key, {"record": None, "runs": []})
            if entry["record"] is None or entry["record"].get("placeholder"):
                entry["record"] = record
            entry["runs"].append((run_date, bool(record.get("success"))))
            if unit_key != base_key and parent["record"].get("placeholder"):
                data["tasks"].pop(base_key, None)


def _site_card(site_name, data):
    entries = [entry for entry in data["tasks"].values() if entry.get("record")]
    records = [entry["record"] for entry in entries]
    success_count = sum(1 for record in records if record.get("success"))
    total = len(records)
    all_ok = success_count == total and total > 0
    title = {"component": "VBtn", "props": {
        "href": data["url"], "target": "_blank", "variant": "text", "color": "primary",
        "class": "text-subtitle-1 font-weight-medium pa-0 me-2",
        "append-icon": "mdi-open-in-new",
    }, "text": f"🌐 {site_name}"} if data["url"] else {
        "component": "span", "props": {
            "class": "text-subtitle-1 font-weight-medium me-2",
        }, "text": f"🌐 {site_name}",
    }
    rows = []
    for entry in entries:
        record = entry["record"]
        if record.get("placeholder"):
            icon, line = "⏳", f"{record.get('unit_label')} -> 尚未执行"
        else:
            icon = "✅" if record.get("success") else "❌"
            line = f"{record.get('unit_label') or record.get('task_name')} -> {_result_text(record)}"
        trend = " ".join("✅" if ok else "❌" for _date, ok in entry.get("runs", [])[:3])
        content = [{"component": "div", "text": line}]
        if trend:
            content.append({"component": "div", "props": {
                "class": "text-caption text-medium-emphasis",
            }, "text": f"最近{min(len(entry['runs']), 3)}次：{trend}"})
        rows.append({
            "component": "div", "props": {"class": "d-flex align-start py-1"},
            "content": [
                {"component": "span", "props": {"class": "me-2 text-body-2"}, "text": icon},
                {"component": "div", "props": {"class": "text-body-2 flex-grow-1"},
                 "content": content},
            ],
        })
    style = (
        "background-color: rgba(var(--v-theme-surface), 0.75);"
        "backdrop-filter: blur(5px);-webkit-backdrop-filter: blur(5px);"
        "border: 1px solid rgba(var(--v-theme-on-surface), 0.12);"
        "border-radius: 8px;box-sizing: border-box;"
    )
    return {
        "component": "VCol", "props": {"cols": 12, "md": 6, "class": "d-flex"},
        "content": [{
            "component": "VCard", "props": {
                "variant": "outlined", "class": "h-100 w-100 pa-0", "style": style,
            }, "content": [{
                "component": "VCardText", "props": {"class": "pa-3"}, "content": [
                    {"component": "div", "props": {"class": "d-flex align-center pb-2"},
                     "content": [title, {"component": "VSpacer"}, {
                         "component": "VChip", "props": {
                             "size": "small", "variant": "tonal",
                             "color": "success" if all_ok else (
                                 "warning" if success_count else "error"
                             ),
                         }, "text": f"{success_count}/{total}",
                     }]},
                    {"component": "VDivider", "props": {"class": "mb-2"}},
                    *(rows or [{"component": "div", "text": "暂无启用任务"}]),
                ],
            }],
        }],
    }


def build_page(plugin):
    history = plugin.history.latest(30)
    total = sum(len(run.get("records") or []) for run in history)
    successes = sum(
        1 for run in history for record in run.get("records") or [] if record.get("success")
    )
    last_records = history[0].get("records") or [] if history else []
    last_success = sum(1 for record in last_records if record.get("success"))
    last_date = history[0].get("date") or "无记录" if history else "无记录"
    overview = {
        "component": "VCard", "props": {"variant": "outlined", "class": "mb-3"},
        "content": [
            {"component": "VCardTitle", "props": {
                "class": "text-subtitle-1 py-2",
            }, "text": "运行统计概览"},
            {"component": "VDivider"},
            {"component": "VCardText", "content": [{
                "component": "VRow", "props": {"dense": True}, "content": [
                    _stat_cell(f"最近一次 {last_date}",
                               f"{last_success}/{len(last_records)}",
                               "text-success" if last_success == len(last_records) else "text-warning"),
                    _stat_cell("历史执行", total, "text-primary"),
                    _stat_cell("历史成功", successes, "text-success"),
                    _stat_cell("历史失败", total - successes,
                               "text-error" if total - successes else "text-medium-emphasis"),
                ],
            }]},
        ],
    }
    site_data, site_order = _enabled_site_data(plugin)
    _merge_history(site_data, history)
    cards = [_site_card(name, site_data[name]) for name in site_order]
    detail = {
        "component": "VCard", "props": {"variant": "outlined"}, "content": [
            {"component": "VCardTitle", "props": {
                "class": "text-subtitle-1 py-2",
            }, "content": [
                {"component": "span", "text": "站点任务执行情况"},
                {"component": "VSpacer"},
                {"component": "span", "props": {
                    "class": "text-caption text-medium-emphasis",
                }, "text": f"共 {len(site_order)} 个站点"},
            ]},
            {"component": "VDivider"},
            {"component": "VCardText", "content": [{
                "component": "VRow", "props": {"dense": True, "align": "stretch"},
                "content": cards or [{"component": "div", "props": {
                    "class": "text-medium-emphasis pa-2",
                }, "text": "暂无启用任务，配置后此处显示站点卡片"}],
            }]},
        ],
    }
    return [overview, detail]
