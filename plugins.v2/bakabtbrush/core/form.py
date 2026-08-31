"""BakaBTBrush Vuetify 配置页。"""

from __future__ import annotations

from typing import Any


def build_form(downloader_options: list[dict[str, str]]) -> tuple[list[dict], dict[str, Any]]:
    content = [
        {
            "component": "VRow",
            "content": [
                _col(3, _switch("enabled", "启用插件")),
                _col(3, _switch("notify", "发送通知")),
                _col(3, _switch("onlyonce", "立即运行一次")),
                _col(3, _switch("dry_run", "试运行一次")),
            ],
        },
        {
            "component": "VRow",
            "content": [
                _col(4, _cron_field()),
                _col(8, _alert(
                    "info",
                    "“立即运行一次”会直接推送；“试运行一次”仅扫描、复核与记录候选，绝不添加或删除 qB 任务。两者同时开启时试运行优先。",
                )),
            ],
        },
        _section("BakaBT 访问"),
        {
            "component": "VRow",
            "content": [
                _col(12, {
                    "component": "VTextField",
                    "props": {
                        "model": "rss_url", "label": "BakaBT RSS 地址", "type": "password",
                        "autocomplete": "off",
                        "hint": "新种发现的唯一来源；未配置时任务将直接失败。地址中的 uid/key 不会写入日志、状态、通知或数据页。",
                        "persistent-hint": True,
                    },
                }),
                _col(12, {
                    "component": "VTextField",
                    "props": {
                        "model": "cookie", "label": "BakaBT Cookie", "type": "password",
                        "autocomplete": "off", "hint": "仅在 RSS 新种通过时间和体积预筛后访问网页；留空时从 CookieCloud 获取。",
                        "persistent-hint": True,
                    },
                }),
                _col(3, _number("timeout", "请求超时（秒）")),
                _col(3, _number("detail_request_retries", "详情页重试次数")),
                _col(6, _alert(
                    "info",
                    "RSS 首次启用只建立当前 Feed 基线，之后仅对通过时间/体积筛选的新种访问网页；Cookie 仅用于优惠确认和下载。两类凭据均不会显示在数据页、日志或通知中。",
                )),
            ],
        },
        _section("候选过滤", "范围字段支持单值或“最小值-最大值”"),
        {
            "component": "VRow",
            "content": [
                _col(6, _range_field("size_range_mb", "种子大小（MB）", "10240")),
                _col(6, _range_field("publish_age_range_minutes", "发布时间（分钟）", "10")),
            ],
        },
        {
            "component": "VRow",
            "content": [_col(12, _alert(
                "info",
                "单个非零值表示最大上限；“最小值-最大值”表示完整区间；0 或留空表示不限制。不支持省略端点。每个新种只做一次优惠判定。",
            ))],
        },
        _section("qBittorrent"),
        {
            "component": "VRow",
            "content": [
                _col(4, {
                    "component": "VSelect",
                    "props": {
                        "model": "downloader", "label": "下载器", "items": downloader_options,
                        "hint": "仅显示 MoviePilot 已配置的 qBittorrent 下载器。", "persistent-hint": True,
                    },
                }),
                _col(8, _text("save_path", "保存路径（留空使用下载器默认路径）")),
            ],
        },
        {
            "component": "VRow",
            "content": [
                _col(3, _text("qb_category", "分类")),
                _col(4, _text("qb_tags", "标签（逗号分隔）")),
                _col(3, _number("max_bakabt_downloading", "最大下载流程数")),
                _col(2, _alert("info", "0 = 不限制；仅统计“刷流 + bakabt”任务。")),
            ],
        },
        _section("自动删种", "普通模式满足任一启用条件即删除"),
        {
            "component": "VRow",
            "content": [
                _col(4, _switch("auto_delete", "启用自动删种")),
                _col(4, _switch("delete_files", "同时删除文件")),
                _col(4, _switch("delete_expired_freeleech_incomplete", "删除促销过期的未完成下载")),
            ],
        },
        {
            "component": "VRow",
            "content": [
                _col(4, _number("delete_seed_hours", "做种时间（小时）")),
                _col(4, _number("delete_ratio", "分享率")),
                _col(4, _number("delete_uploaded_gb", "上传量（GB）")),
                _col(4, _number("delete_download_timeout_hours", "下载超时（小时）")),
                _col(4, _number("delete_inactive_minutes", "未活动时间（分钟）")),
                _col(4, _number("delete_avg_upload_kbps", "平均上传速度上限（KB/s）")),
                _col(4, _number("delete_protection_minutes", "删除保护期（分钟）")),
                _col(8, _text("delete_exclude_tags", "删除排除标签（逗号分隔）")),
            ],
        },
        {
            "component": "VRow",
            "content": [_col(12, _alert(
                "warning",
                "自动删种默认关闭；仅处理分类匹配、包含 bakabt 标签且由本插件登记的任务。删除文件默认关闭，排除标签优先级最高。",
            ))],
        },
    ]
    model = {
        "enabled": False,
        "notify": True,
        "onlyonce": False,
        "dry_run": False,
        "cron": "*/10 * * * *",
        "cookie": "",
        "rss_url": "",
        "timeout": 20,
        "detail_request_retries": 3,
        "publish_age_range_minutes": "0",
        "size_range_mb": "0",
        "downloader": "",
        "qb_category": "刷流",
        "qb_tags": "bakabt,刷流",
        "save_path": "",
        "max_bakabt_downloading": 2,
        "auto_delete": False,
        "delete_files": False,
        "delete_seed_hours": 0,
        "delete_ratio": 0,
        "delete_uploaded_gb": 0,
        "delete_download_timeout_hours": 0,
        "delete_inactive_minutes": 0,
        "delete_avg_upload_kbps": 0,
        "delete_protection_minutes": 60,
        "delete_exclude_tags": "H&R,保留",
        "delete_expired_freeleech_incomplete": False,
    }
    return [{"component": "VForm", "content": content}], model


def _section(title: str, subtitle: str = "") -> dict:
    return {
        "component": "VRow",
        "content": [{
            "component": "VCol",
            "props": {"cols": 12},
            "content": [
                {"component": "div", "props": {"class": "text-subtitle-1 font-weight-medium pt-2"}, "text": title},
                *([{"component": "div", "props": {"class": "text-body-2 text-medium-emphasis pb-1"}, "text": subtitle}] if subtitle else []),
            ],
        }],
    }


def _col(md: int, content: dict) -> dict:
    return {"component": "VCol", "props": {"cols": 12, "md": md}, "content": [content]}


def _switch(model: str, label: str) -> dict:
    return {"component": "VSwitch", "props": {"model": model, "label": label}}


def _alert(alert_type: str, text: str) -> dict:
    return {
        "component": "VAlert",
        "props": {
            "type": alert_type, "variant": "tonal", "density": "compact",
            "class": "text-caption h-100", "text": text,
        },
    }


def _text(model: str, label: str) -> dict:
    return {"component": "VTextField", "props": {"model": model, "label": label}}


def _number(model: str, label: str) -> dict:
    return {"component": "VTextField", "props": {"model": model, "label": label, "type": "number", "min": 0}}


def _range_field(model: str, label: str, placeholder: str) -> dict:
    return {
        "component": "VTextField",
        "props": {"model": model, "label": label, "placeholder": placeholder, "type": "text"},
    }


def _cron_field() -> dict:
    return {
        "component": "VCronField",
        "props": {"model": "cron", "label": "执行周期", "placeholder": "*/10 * * * *"},
    }
