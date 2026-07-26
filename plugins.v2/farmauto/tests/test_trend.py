import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from core.trend import PriceTrendStore


def test_record_get_and_limit_to_latest_twenty_samples():
    store = PriceTrendStore()

    for price in range(25):
        store.record("playlet", {"crop_1": 500 + price}, ts=float(price))

    store.prune()
    samples = store.get("playlet", "crop_1")
    assert len(samples) == 20
    assert samples[0] == (5.0, 505)
    assert samples[-1] == (24.0, 524)
    assert store.get("playlet", "missing") == []


def test_to_dict_from_dict_and_prune_invalid_or_excess_samples():
    source = {
        "skit": {
            "crop_1": [[index, 900 + index] for index in range(23)],
            "invalid": [["bad", "price"], [1]],
        },
        "broken": "not-an-object",
    }

    store = PriceTrendStore.from_dict(source)
    serialized = store.to_dict()

    assert serialized["skit"]["crop_1"] == [
        [float(index), 900 + index] for index in range(3, 23)
    ]
    assert "invalid" not in serialized["skit"]
    assert "broken" not in serialized

    restored = PriceTrendStore.from_dict(serialized)
    assert restored.get("skit", "crop_1") == store.get("skit", "crop_1")
