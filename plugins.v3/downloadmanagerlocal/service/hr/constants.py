"""H&R 模块配置键、默认值、持久化键与调度注册常量。"""

from __future__ import annotations

HR_LOG_PREFIX = "【H&R】"

HR_TASKS_DATA_KEY = "hr_tasks"
"""H&R 任务集合的持久化 key。"""

HR_NOTIFY_EVENTS_DATA_KEY = "hr_notify_events"
"""H&R 待汇总通知事件的持久化 key。"""

HR_CHECK_SERVICE_ID = "HitAndRunCheck"
HR_CHECK_SERVICE_NAME = "H&R状态检查"
HR_DISCOVER_SERVICE_ID = "HitAndRunDiscover"
HR_DISCOVER_SERVICE_NAME = "H&R自动发现"
HR_SUMMARY_SERVICE_ID = "HitAndRunSummary"
HR_SUMMARY_SERVICE_NAME = "H&R通知汇总"

HR_NOTIFY_MODES = ("none", "on_error", "always")
"""通知模式：不发送 / 仅异常 / 全部。"""

HR_FORM_DEFAULTS = {
    "hr_enabled": False,
    "hr_protection_enabled": True,
    "hr_auto_discover": False,
    "hr_enable_site_config": False,
    "hr_downloader": [],
    "hr_sites": [],
    "hr_notify": "always",
    "hr_check_period": 10,
    "hr_hit_and_run_tag": "H&R",
    "hr_auto_cleanup_days": 15,
    "hr_notify_summary_cron": "0 8 * * *",
    "hr_exclude_tags": [],
    "hr_exclude_categories": [],
    "hr_duration": 48,
    "hr_deadline_days": 14,
    "hr_additional_seed_time": 24,
    "hr_ratio": None,
    "hr_upload_multiplier": None,
    "hr_upload_gte_download": None,
    "hr_active": False,
    "hr_size_tiers": None,
    "hr_brush_plugin": "BrushFlow",
    "hr_site_config_str": "",
}
"""pthitandrun 源码 get_form 的表单默认值（字段名加 hr_ 前缀，hr_* 字段不重复加前缀）。"""

HR_QNAP_CONFIG = {
    "hr_enabled": True,
    "hr_auto_discover": True,
    "hr_enable_site_config": True,
    "hr_downloader": ["QB1", "QB2"],
    "hr_sites": ["老师", "北洋园", "GGPT", "PTFans", "PTLGS", "1PTBA", "52pt"],
    "hr_additional_seed_time": 6.0,
    "hr_exclude_categories": ["seed"],
    "hr_auto_cleanup_days": 15.0,
    "hr_site_config_str": """- site_name: 'GGPT'
  hr_duration: 48.0
  hr_deadline_days: 30
  hr_ratio: 3.0
  hr_active: true

- site_name: '猪猪'
  hr_duration: 72.0
  hr_deadline_days: 20
  hr_active: true

- site_name: 'CARPT'
  hr_duration: 24.0
  hr_deadline_days: 10
  hr_upload_multiplier: 10.0
  hr_active: true

- site_name: '我堡'
  hr_duration: 48.0
  hr_deadline_days: 14
  hr_ratio: 1.0
  hr_active: true

- site_name: '学校'
  hr_duration: 20.0
  hr_deadline_days: 10
  hr_upload_gte_download: true
  hr_active: true

- site_name: '北洋园'
  hr_active: true
  hr_size_tiers:
    - max_size_gib: 10
      hr_duration: 24
      hr_deadline_days: 10
    - max_size_gib: 20
      hr_duration: 48
      hr_deadline_days: 20
    - max_size_gib: 30
      hr_duration: 72
      hr_deadline_days: 30
    - max_size_gib: 40
      hr_duration: 96
      hr_deadline_days: 40
    - max_size_gib: 50
      hr_duration: 120
      hr_deadline_days: 50
    - max_size_gib: 0
      hr_duration: 168
      hr_deadline_days: 70

- site_name: '老师'
  hr_duration: 99.0
  hr_deadline_days: 25
  hr_ratio: 2.0
  hr_active: true

- site_name: PTFans
  hr_duration: 168
  hr_deadline_days: 35

- site_name: PTLGS
  hr_duration: 72
  hr_deadline_days: 15

- site_name: 1PTBA
  hr_duration: 24
  hr_deadline_days: 5

- site_name: 52pt
  hr_duration: 24
  hr_deadline_days: 5
""",
}
"""qnap 现役 PtHitAndRun 配置中与表单默认不同的键；站点白名单 10 个 ID 与 11 个站名规则各自独立生效。"""

HR_CONFIG_DEFAULTS = dict(HR_FORM_DEFAULTS)
"""插件发布默认值：即 pthitandrun 表单默认值；qnap 私有覆盖（HR_QNAP_CONFIG）已移出，仅留作行为证据。"""


import copy


def build_hr_config_defaults() -> dict:
    """返回 H&R 配置默认值的独立副本，供插件配置默认值合并使用。"""
    return copy.deepcopy(HR_CONFIG_DEFAULTS)


__all__ = (
    "HR_CHECK_SERVICE_ID",
    "HR_CHECK_SERVICE_NAME",
    "HR_CONFIG_DEFAULTS",
    "HR_DISCOVER_SERVICE_ID",
    "HR_DISCOVER_SERVICE_NAME",
    "HR_FORM_DEFAULTS",
    "HR_LOG_PREFIX",
    "HR_NOTIFY_EVENTS_DATA_KEY",
    "HR_NOTIFY_MODES",
    "HR_QNAP_CONFIG",
    "HR_SUMMARY_SERVICE_ID",
    "HR_SUMMARY_SERVICE_NAME",
    "HR_TASKS_DATA_KEY",
    "build_hr_config_defaults",
)
