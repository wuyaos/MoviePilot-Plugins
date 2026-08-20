from __future__ import annotations

import pytest

from core.config import BrushConfig, ConfigError, parse_range


def test_defaults_use_ten_minute_cron_and_expected_qb_tags():
    config = BrushConfig.from_mapping({})

    assert config.cron == "*/10 * * * *"
    assert config.qb_category == "刷流"
    assert config.qb_tags == ("bakabt", "刷流")
    assert config.max_bakabt_downloading == 2
    assert config.publish_age_range_minutes == "0"
    assert config.size_range_mb == "0"
    assert config.auto_delete is False
    assert config.delete_files is False
    assert config.page_max_height == 520
    assert config.page_visible_items == 8


def test_dry_run_is_persisted_as_a_one_shot_config_flag():
    config = BrushConfig.from_mapping({"dry_run": True})

    assert config.dry_run is True
    assert config.to_mapping()["dry_run"] is True


def test_strict_range_semantics_single_full_and_unlimited():
    assert parse_range("100", "测试") == ("100", 0, 100)
    assert parse_range("100-10240", "测试") == ("100-10240", 100, 10240)
    assert parse_range("0", "测试") == ("0", 0, 0)
    assert parse_range("", "测试") == ("0", 0, 0)

    config = BrushConfig.from_mapping({
        "publish_age_range_minutes": "5-120",
        "size_range_mb": "10240",
        "max_bakabt_downloading": 0,
    })
    assert config.publish_age_minimum == 5
    assert config.publish_age_maximum == 120
    assert config.size_minimum_mb == 0
    assert config.size_maximum_mb == 10240
    assert config.max_bakabt_downloading == 0


@pytest.mark.parametrize("value", ["100-", "-10240", "100-0", "0-10240", "1-2-3", "abc"])
def test_invalid_or_open_range_is_rejected(value):
    with pytest.raises(ConfigError):
        BrushConfig.from_mapping({"size_range_mb": value})


def test_minimum_greater_than_maximum_is_rejected():
    with pytest.raises(ConfigError, match="最小值"):
        BrushConfig.from_mapping({"publish_age_range_minutes": "120-60"})


def test_page_window_settings_are_bounded():
    low = BrushConfig.from_mapping({"page_max_height": 1, "page_visible_items": 0})
    high = BrushConfig.from_mapping({"page_max_height": 9999, "page_visible_items": 999})

    assert (low.page_max_height, low.page_visible_items) == (240, 1)
    assert (high.page_max_height, high.page_visible_items) == (1600, 30)


def test_bakabt_tag_is_required_for_qb_scope_accounting():
    with pytest.raises(ConfigError, match="bakabt"):
        BrushConfig.from_mapping({"qb_tags": "刷流"})


def test_cookie_and_cleanup_settings_are_preserved_in_complete_mapping():
    config = BrushConfig.from_mapping({
        "cookie": "bbtid=example",
        "qb_tags": "bakabt,刷流,bakabt",
        "auto_delete": True,
        "delete_seed_hours": 24,
        "delete_exclude_tags": "H&R,保留,H&R",
    })

    mapping = config.to_mapping()
    assert mapping["cookie"] == "bbtid=example"
    assert mapping["qb_tags"] == "bakabt,刷流"
    assert mapping["auto_delete"] is True
    assert mapping["delete_seed_hours"] == 24
    assert mapping["delete_exclude_tags"] == "H&R,保留"
    assert BrushConfig.from_mapping({"delete_exclude_tags": ""}).delete_exclude_tags == ()
