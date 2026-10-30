"""H&R 判定引擎测试：真实加载 modules/hr 的 models / rules / evaluator。

只替身 MP 宿主边界（`app.sdk.config.settings` 提供 TZ）；hr 三个模块按真实文件加载，
被测对象是真实的 `evaluate_task` / `initialize_requirements` / `seeding_progress` /
`HrTask.meets_hr` / `match_size_tier`。

为什么走规则侧而不是端到端：常规 H&R `seeding_time` 由扫描器按 `now - completed_at` 计算；52pt 则读取下载器累计做种秒数。测试分别构造规则条件和下载器快照字段，覆盖两种语义。
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import Mock

import pytest

PLUGIN = Path(__file__).resolve().parents[3] / "plugins.v3/downloadmanagerlocal"
HR_DIR = PLUGIN / "modules/hr"
PREFIX = "app.plugins.downloadmanagerlocal"
GIB = 1024**3


def test_hr_presets_asset_present_and_loadable(hr):
    """随代码发布的 H&R 预设资源必须存在且可解析。

    回归背景：目录重组（v3.9.3，`94603c4c`）把 `modules/hr/presets.json` 整个丢掉了，
    直到端到端用例报 `/hr_presets` 返回 0 条才被发现——当时「部署镜像校验」只比 `.py` 的
    md5，非 .py 资源不在比对范围内，于是一整个版本都缺这个文件。
    """
    path = HR_DIR / "presets.json"
    assert path.is_file(), f"预设资源缺失（重组时丢过）：{path}"

    presets = hr.rules.load_preset_rules()
    assert isinstance(presets, dict) and presets, "预设资源存在但可解析不出任何条目"


def test_52pt_preset_tracks_all_downloads_and_either_requirement(hr):
    """52pt 自动纳入考核；5日内累计做种24小时或分享率1即达标。"""
    rule = hr.rules.load_preset_rules()["52pt"]
    assert rule.hr_active is True
    assert rule.hr_duration == 24
    assert rule.hr_deadline_days == 5
    assert rule.hr_ratio == 1
    assert rule.hr_deadline_from_completion is True
    assert rule.hr_use_downloader_seeding_time is True

    pending_task = _task(hr, added_on=NOW, seeding_time=0, ratio=1.0)
    assert hr.evaluator.evaluate_task(pending_task, rule, NOW + 20 * 86400) is hr.models.HrStatus.IN_PROGRESS

    # Once the downloader records completion, the five-day deadline starts from that timestamp.
    completed_on = NOW + 20 * 86400
    pending_task.completed_on = completed_on
    pending_task.ratio = 0.2
    assert pending_task.deadline_time == completed_on + 5 * 86400
    assert hr.evaluator.evaluate_task(pending_task, rule, completed_on + 4 * 86400) is None
    assert pending_task.hr_status is hr.models.HrStatus.IN_PROGRESS

    ratio_task = _task(hr, added_on=NOW, completed_on=NOW, seeding_time=0, ratio=1.0)
    assert hr.evaluator.evaluate_task(ratio_task, rule, NOW + 86400) is hr.models.HrStatus.COMPLIANT
    late_task = _task(hr, added_on=NOW, completed_on=NOW, seeding_time=0, ratio=1.0)
    assert hr.evaluator.evaluate_task(late_task, rule, NOW + 5 * 86400 + 1) is hr.models.HrStatus.OVERDUE

    duration_task = _task(
        hr, added_on=NOW, completed_on=NOW, seeding_time=0,
        downloader_seeding_time=24 * 3600, ratio=0.5,
    )
    assert hr.evaluator.evaluate_task(duration_task, rule, NOW + 4 * 86400) is hr.models.HrStatus.COMPLIANT

    missing_counter_task = _task(
        hr, added_on=NOW, completed_on=NOW, seeding_time=6 * 86400,
        downloader_seeding_time=None, ratio=0.5,
    )
    assert hr.evaluator.evaluate_task(missing_counter_task, rule, NOW + 4 * 86400) is hr.models.HrStatus.IN_PROGRESS
    assert missing_counter_task.seeding_time == 0

    unmet_task = _task(
        hr, added_on=NOW, completed_on=NOW, seeding_time=0,
        downloader_seeding_time=23 * 3600, ratio=0.99,
    )
    assert hr.evaluator.evaluate_task(unmet_task, rule, NOW + 5 * 86400 + 1) is hr.models.HrStatus.OVERDUE


def _pkg(monkeypatch, name, path: Path | None = None, **attrs) -> types.ModuleType:
    """带 __spec__ 的包/模块替身（pytest 断言重写要求 spec 非 None）。"""
    result = types.ModuleType(name)
    result.__spec__ = importlib.machinery.ModuleSpec(name, None, is_package=path is not None)
    if path is not None:
        result.__path__ = [str(path)]
    result.__dict__.update(attrs)
    monkeypatch.setitem(sys.modules, name, result)
    return result


def _load_hr_module(monkeypatch, name: str) -> types.ModuleType:
    full = f"{PREFIX}.modules.hr.{name}"
    spec = importlib.util.spec_from_file_location(full, HR_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, full, module)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def hr(monkeypatch):
    """返回 models / rules / evaluator 三个真实模块。"""
    _pkg(monkeypatch, "app")
    _pkg(monkeypatch, "app.sdk")
    _pkg(monkeypatch, "app.sdk.config", settings=Mock(TZ="Asia/Shanghai"))
    _pkg(monkeypatch, "app.sdk.logging", logger=Mock())
    _pkg(monkeypatch, "app.plugins", path=PLUGIN.parent)
    _pkg(monkeypatch, PREFIX)
    _pkg(monkeypatch, f"{PREFIX}.modules")
    _pkg(monkeypatch, f"{PREFIX}.modules.hr", path=HR_DIR)
    models = _load_hr_module(monkeypatch, "models")
    rules = _load_hr_module(monkeypatch, "rules")
    evaluator = _load_hr_module(monkeypatch, "evaluator")
    return types.SimpleNamespace(models=models, rules=rules, evaluator=evaluator)


def _task(hr, **overrides):
    """构造一条参与判定的 H&R 任务（未指定的要求字段一律留空）。"""
    fields = dict(
        hash="a" * 40,
        downloader="test-qb",
        title="probe",
        size=0,
        hit_and_run=True,
        hr_status=hr.models.HrStatus.PENDING,
        hr_duration=None,
        additional_seed_time=0,
        hr_deadline_days=None,
        hr_ratio=None,
        hr_upload_multiplier=None,
        hr_upload_gte_download=None,
        ratio=0,
        downloaded=0,
        uploaded=0,
        seeding_time=0,
        deleted=False,
    )
    fields.update(overrides)
    return hr.models.HrTask(**fields)


NOW = 1_700_000_000.0


class TestEvaluateGate:
    """判定入口的门控与幂等。"""

    def test_non_hr_task_is_ignored(self, hr):
        task = _task(hr, hit_and_run=False, hr_duration=1)
        assert hr.evaluator.evaluate_task(task, hr.models.HrSiteRule(), NOW) is None
        assert task.hr_status is hr.models.HrStatus.PENDING

    @pytest.mark.parametrize("status", ["COMPLIANT", "OVERDUE"])
    def test_terminal_status_is_not_reevaluated(self, hr, status):
        task = _task(hr, hr_status=getattr(hr.models.HrStatus, status), hr_duration=1)
        assert hr.evaluator.evaluate_task(task, hr.models.HrSiteRule(), NOW) is None
        assert task.hr_status is getattr(hr.models.HrStatus, status)

    def test_no_transition_returns_none(self, hr):
        """已在 IN_PROGRESS 且仍不达标 → 无跃迁，返回 None。"""
        task = _task(hr, hr_status=hr.models.HrStatus.IN_PROGRESS, hr_duration=10)
        assert hr.evaluator.evaluate_task(task, hr.models.HrSiteRule(), NOW) is None

    def test_missing_requirement_never_meets(self, hr):
        """四类要求全为空：不因「没有要求」被判达标。"""
        task = _task(hr)
        assert task.meets_hr() is False
        assert hr.evaluator.evaluate_task(task, hr.models.HrSiteRule(), NOW) is hr.models.HrStatus.IN_PROGRESS


class TestEvaluateTransitions:
    """状态跃迁。"""

    def test_seeding_met_marks_compliant_and_stamps_time(self, hr):
        task = _task(hr, hr_duration=1, seeding_time=3600)
        assert hr.evaluator.evaluate_task(task, hr.models.HrSiteRule(), NOW) is hr.models.HrStatus.COMPLIANT
        assert task.hr_met_time == NOW

    def test_partial_seeding_stays_in_progress(self, hr):
        task = _task(hr, hr_duration=10, seeding_time=3600)
        assert hr.evaluator.evaluate_task(task, hr.models.HrSiteRule(), NOW) is hr.models.HrStatus.IN_PROGRESS
        assert task.hr_met_time is None

    def test_overdue_when_deadline_passed(self, hr):
        task = _task(hr, hr_duration=100, added_on=NOW - 3 * 86400, hr_deadline_days=1)
        assert hr.evaluator.evaluate_task(task, hr.models.HrSiteRule(), NOW) is hr.models.HrStatus.OVERDUE

    def test_deadline_not_passed_stays_in_progress(self, hr):
        task = _task(hr, hr_duration=100, added_on=NOW, hr_deadline_days=1)
        assert hr.evaluator.evaluate_task(task, hr.models.HrSiteRule(), NOW) is hr.models.HrStatus.IN_PROGRESS

    def test_compliant_beats_overdue(self, hr):
        """已达标但已过期：达标优先（先判 meets_hr）。"""
        task = _task(hr, hr_duration=1, seeding_time=7200, added_on=NOW - 30 * 86400, hr_deadline_days=1)
        assert task.deadline_time < NOW
        assert hr.evaluator.evaluate_task(task, hr.models.HrSiteRule(), NOW) is hr.models.HrStatus.COMPLIANT

    def test_deleted_without_meeting_needs_seeding(self, hr):
        task = _task(hr, hr_duration=10, deleted=True)
        assert hr.evaluator.evaluate_task(task, hr.models.HrSiteRule(), NOW) is hr.models.HrStatus.NEEDS_SEEDING

    def test_zero_deadline_days_never_overdue(self, hr):
        """hr_deadline_days=0 视为未设考核期，不判过期。"""
        task = _task(hr, hr_duration=10, added_on=NOW - 999 * 86400, hr_deadline_days=0)
        assert task.formatted_deadline() == "-"
        assert hr.evaluator.evaluate_task(task, hr.models.HrSiteRule(), NOW) is hr.models.HrStatus.IN_PROGRESS


class TestRequirementLayering:
    """要求字段的来源分层：分档 > 站点规则 > 任务既有值。"""

    def test_rule_overrides_task_requirements(self, hr):
        task = _task(hr, hr_duration=None, additional_seed_time=0, seeding_time=8 * 3600)
        rule = hr.models.HrSiteRule(hr_duration=5, additional_seed_time=3, hr_deadline_days=7)
        assert task.meets_hr() is False
        status = hr.evaluator.evaluate_task(task, rule, NOW)
        assert status is hr.models.HrStatus.COMPLIANT
        assert task.required_hours() == 8
        assert task.hr_deadline_days == 7

    def test_rule_none_keeps_task_value(self, hr):
        task = _task(hr, hr_duration=2, additional_seed_time=1)
        hr.evaluator.evaluate_task(task, hr.models.HrSiteRule(), NOW)
        assert task.required_hours() == 3

    def test_size_tier_wins_over_rule(self, hr):
        task = _task(hr, size=GIB // 2, hr_duration=100, seeding_time=3600)
        tier = hr.models.HrSizeTier(max_size_gib=1, hr_duration=1, hr_deadline_days=5)
        rule = hr.models.HrSiteRule(hr_duration=100, hr_deadline_days=99, hr_size_tiers=[tier])
        assert hr.evaluator.evaluate_task(task, rule, NOW) is hr.models.HrStatus.COMPLIANT
        assert (task.hr_duration, task.hr_deadline_days) == (1, 5)
        assert task.required_hours() == 1

    def test_size_tier_boundary_is_inclusive(self, hr):
        tier = hr.models.HrSizeTier(max_size_gib=1, hr_duration=1, hr_deadline_days=0)
        rule = hr.models.HrSiteRule(hr_size_tiers=[tier])
        assert hr.rules.match_size_tier(rule, GIB) is tier
        assert hr.rules.match_size_tier(rule, GIB + 1) is None

    def test_size_tier_zero_limit_is_last(self, hr):
        """max_size_gib=0 表示无上限，排序后置于末位，能兜住超大种子。"""
        small = hr.models.HrSizeTier(max_size_gib=1, hr_duration=1)
        big = hr.models.HrSizeTier(max_size_gib=0, hr_duration=99)
        rule = hr.models.HrSiteRule(hr_size_tiers=[big, small])
        assert hr.rules.match_size_tier(rule, 10 * GIB) is big
        assert hr.rules.match_size_tier(rule, GIB // 2) is small


class TestMeetsHrAlternatives:
    """meets_hr 四条件 OR 及各条件的边界。"""

    def test_ratio_alternative_satisfies(self, hr):
        task = _task(hr, hr_duration=999, hr_ratio=2.0, ratio=2.5)
        assert task.meets_hr() is True
        assert hr.evaluator.evaluate_task(task, hr.models.HrSiteRule(), NOW) is hr.models.HrStatus.COMPLIANT

    def test_ratio_below_threshold_does_not_satisfy(self, hr):
        task = _task(hr, hr_duration=999, hr_ratio=2.0, ratio=1.99)
        assert task.meets_hr() is False

    def test_upload_multiplier_requires_positive_size(self, hr):
        """size=0 时上传倍数条件不生效（避免除零语义下的误判）。"""
        task = _task(hr, hr_duration=999, hr_upload_multiplier=1.0, uploaded=10 * GIB)
        assert task.meets_hr() is False
        task.size = GIB
        assert task.meets_hr() is True

    def test_upload_gte_download_requires_download(self, hr):
        task = _task(hr, hr_duration=999, hr_upload_gte_download=True, downloaded=0, uploaded=5 * GIB)
        assert task.meets_hr() is False
        task.downloaded = GIB
        task.uploaded = GIB
        assert task.meets_hr() is True

    def test_zero_thresholds_are_treated_as_unset(self, hr):
        """hr_ratio=0 / 上传倍数=0 不算「要求」，不能据此判达标。"""
        task = _task(hr, hr_duration=None, hr_ratio=0, hr_upload_multiplier=0, ratio=99, uploaded=99 * GIB)
        assert task.meets_hr() is False


class TestSeedingProgress:
    """做种进度（0~1）。"""

    def test_progress_is_ratio_of_required_hours(self, hr):
        task = _task(hr, hr_duration=2, seeding_time=3600)
        assert hr.evaluator.seeding_progress(task) == pytest.approx(0.5)

    def test_progress_is_capped_at_one(self, hr):
        task = _task(hr, hr_duration=2, seeding_time=10 * 3600)
        assert hr.evaluator.seeding_progress(task) == pytest.approx(1.0)

    def test_no_requirement_follows_status(self, hr):
        task = _task(hr)
        assert hr.evaluator.seeding_progress(task) == 0.0
        task.hr_status = hr.models.HrStatus.COMPLIANT
        assert hr.evaluator.seeding_progress(task) == 1.0

    def test_remain_hours_never_negative(self, hr):
        task = _task(hr, hr_duration=1, seeding_time=5 * 3600)
        assert task.remain_hours() == 0
