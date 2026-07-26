import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from core.strategy import effective_site_policy, should_sell


def test_should_sell_with_profit_range():
    crop = {"cost": 500}

    assert should_sell(crop, 600, {"min_profit_rate": 0.1, "max_profit_rate": 0.5})
    assert not should_sell(crop, 1000, {"min_profit_rate": 0.1, "max_profit_rate": 0.5})
    assert should_sell(crop, 510, {"min_profit_rate": 0, "max_profit_rate": 0})


def test_max_profit_rate_site_override():
    policy = effective_site_policy(
        {"min_profit_rate": 0.1, "max_profit_rate": 0},
        {"playlet": {"max_profit_rate": 0.5}},
        "playlet",
    )

    assert policy["max_profit_rate"] == 0.5
