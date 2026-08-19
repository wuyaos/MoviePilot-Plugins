from __future__ import annotations

import pytest

from core.config import BrushConfig, ConfigError


def test_defaults_use_ten_minute_cron_and_expected_qb_tags():
    config = BrushConfig.from_mapping({})

    assert config.cron == "*/10 * * * *"
    assert config.qb_category == "刷流"
    assert config.qb_tags == ("bakabt", "刷流")
    assert config.max_bakabt_downloading == 2


def test_zero_means_no_filter_constraint():
    config = BrushConfig.from_mapping({
        "min_publish_age_minutes": 0,
        "max_publish_age_minutes": 0,
        "min_size_mb": 0,
        "max_size_mb": 0,
        "max_bakabt_downloading": 0,
    })

    assert config.min_publish_age_minutes == 0
    assert config.max_publish_age_minutes == 0
    assert config.min_size_mb == 0
    assert config.max_size_mb == 0
    assert config.max_bakabt_downloading == 0


def test_invalid_enabled_ranges_are_rejected():
    with pytest.raises(ConfigError, match="发种时间"):
        BrushConfig.from_mapping({
            "min_publish_age_minutes": 120,
            "max_publish_age_minutes": 60,
        })

    with pytest.raises(ConfigError, match="体积"):
        BrushConfig.from_mapping({"min_size_mb": 500, "max_size_mb": 100})


def test_bakabt_tag_is_required_for_qb_scope_accounting():
    with pytest.raises(ConfigError, match="bakabt"):
        BrushConfig.from_mapping({"qb_tags": "刷流"})


def test_cookie_is_preserved_in_complete_config_mapping():
    config = BrushConfig.from_mapping({"cookie": "bbtid=example", "qb_tags": "bakabt,刷流,bakabt"})

    mapping = config.to_mapping()
    assert mapping["cookie"] == "bbtid=example"
    assert mapping["qb_tags"] == "bakabt,刷流"
