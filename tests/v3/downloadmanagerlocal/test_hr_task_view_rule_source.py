"""B01 H&R 任务详情规则来源离线测试。

覆盖：规则来源（全局/站点自定义/内置预设/未知）、任务详情返回考核要求/累计值/期限起点，
以及站点覆盖存在时不得把全局阈值当作任务要求。
宿主与下载器全部替身；不连接 MoviePilot。
"""
import importlib
import sys
from unittest.mock import Mock

import pytest


@pytest.fixture
def hr_view(mp_stubs):
    prefix = "app.plugins.downloadmanagerlocal."
    previous = {key: value for key, value in sys.modules.items() if key.startswith(prefix)}
    for key in previous:
        sys.modules.pop(key)
    try:
        module = mp_stubs("modules/hr/service.py", "modules.hr.service")
        models = importlib.import_module("app.plugins.downloadmanagerlocal.modules.hr.models")
        service = module.HrService(Mock())
        service._plugin.get_config = lambda: {}
        yield module, service, models
    finally:
        for key in list(sys.modules):
            if key.startswith(prefix):
                sys.modules.pop(key)
        sys.modules.update(previous)


def _task(module, models, site_name, hr_duration, additional_seed_time=0.0,
          seeding_time=3600, ratio=0.0, completed_on=None):
    return module.HrTask(
        downloader="qb", hash="abc", site_name=site_name, title="sample",
        hr_duration=hr_duration, additional_seed_time=additional_seed_time,
        seeding_time=seeding_time, ratio=ratio, completed_on=completed_on,
    )


def test_rule_source_global_when_no_site_rule(hr_view):
    """站点不在 site_rules：规则来源为 global。"""
    module, service, models = hr_view
    service._config = module.HrConfig(global_rule=models.HrSiteRule(hr_duration=48.0))
    assert service._rule_source("GGPT") == "global"
    assert service._rule_source(None) == "global"
    assert service._rule_source("") == "global"


def test_rule_source_builtin_for_52pt(hr_view):
    """站点在内置预设（52pt）且无自定义覆盖：规则来源为 builtin。"""
    module, service, models = hr_view
    service._config = module.HrConfig(
        global_rule=models.HrSiteRule(hr_duration=48.0),
        site_rules={"52pt": models.HrSiteRule(hr_duration=24.0)})
    service._plugin.get_config = lambda: {"hr_site_config_str": ""}
    assert service._rule_source("52pt") == "builtin"


def test_rule_source_site_for_custom_yaml(hr_view):
    """站点自定义 YAML 覆盖内置预设：规则来源为 site。"""
    module, service, models = hr_view
    service._config = module.HrConfig(
        global_rule=models.HrSiteRule(hr_duration=48.0),
        site_rules={"GGPT": models.HrSiteRule(hr_duration=12.0)})
    service._plugin.get_config = lambda: {
        "hr_site_config_str": "- site_name: 'GGPT'\n  hr_duration: 12.0\n"}
    assert service._rule_source("GGPT") == "site"


def test_rule_source_unknown_when_origin_ambiguous(hr_view):
    """站点在 site_rules 但既非内置也非自定义：规则来源标为 unknown，不猜测。"""
    module, service, models = hr_view
    service._config = module.HrConfig(
        global_rule=models.HrSiteRule(hr_duration=48.0),
        site_rules={"Mystery": models.HrSiteRule(hr_duration=9.0)})
    service._plugin.get_config = lambda: {"hr_site_config_str": ""}
    assert service._rule_source("Mystery") == "unknown"


def test_task_view_uses_site_rule_not_global(hr_view):
    """站点覆盖存在时：任务要求取站点阈值（24h），不得说成全局阈值（48h）。"""
    module, service, models = hr_view
    service._config = module.HrConfig(
        global_rule=models.HrSiteRule(hr_duration=48.0),
        site_rules={"52pt": models.HrSiteRule(hr_duration=24.0)})
    service._plugin.get_config = lambda: {"hr_site_config_str": ""}
    task = _task(module, models, "52pt", hr_duration=24.0)
    view = service._task_view(task)
    assert view["rule_source"] == "builtin"
    assert view["requirements"]["seeding_hours"] == 24.0
    assert view["requirements"]["hr_duration"] == 24.0
    # 累计值投影：做种 1 小时
    assert view["accumulated"]["seeding_hours"] == 1.0


def test_task_view_projects_requirements_accumulated_deadline_basis(hr_view):
    """任务详情返回考核要求、累计值、期限起点三类投影。"""
    module, service, models = hr_view
    service._config = module.HrConfig(global_rule=models.HrSiteRule(hr_duration=48.0))
    task = _task(module, models, "GGPT", hr_duration=48.0, additional_seed_time=6.0,
                 seeding_time=5400, ratio=1.5, completed_on=1000)
    view = service._task_view(task)
    assert view["requirements"]["seeding_hours"] == 54.0
    assert view["requirements"]["additional_seed_time"] == 6.0
    assert view["accumulated"]["ratio"] == 1.5
    assert view["deadline_basis"]["completed_on"] == 1000
    assert view["deadline_basis"]["added_on"] == task.added_on
    assert view["rule_source"] == "global"


def test_service_infos_reads_config_and_presets_once_for_many_tasks(hr_view):
    """任务列表逐任务投影：配置与内置预设各只读一次，IO 不随任务数放大。"""
    module, service, models = hr_view
    service._config = module.HrConfig(
        global_rule=models.HrSiteRule(hr_duration=48.0),
        site_rules={"GGPT": models.HrSiteRule(hr_duration=12.0),
                    "52pt": models.HrSiteRule(hr_duration=24.0),
                    "Mystery": models.HrSiteRule(hr_duration=9.0)})
    counts = {"config": 0}

    def counting_config():
        counts["config"] += 1
        return {"hr_site_config_str": "- site_name: 'GGPT'\n  hr_duration: 12.0\n"}

    service._plugin.get_config = counting_config
    rules = importlib.import_module("app.plugins.downloadmanagerlocal.modules.hr.rules")
    real_load = rules.load_preset_rules
    preset_calls = {"n": 0}

    def counting_presets():
        preset_calls["n"] += 1
        return real_load()

    rules.load_preset_rules = counting_presets
    try:
        service._tasks = {
            "k1": _task(module, models, "GGPT", hr_duration=12.0),
            "k2": _task(module, models, "52pt", hr_duration=24.0),
            "k3": _task(module, models, "Other", hr_duration=48.0),
            "k4": _task(module, models, "Mystery", hr_duration=9.0),
        }
        infos = service.get_service_infos()
    finally:
        rules.load_preset_rules = real_load

    assert counts["config"] == 1, "4 个任务不得读 4 次配置"
    assert preset_calls["n"] == 1, "4 个任务不得解析 4 次内置预设"
    assert [item["rule_source"] for item in infos["tasks"]] == [
        "site", "builtin", "global", "unknown"]
