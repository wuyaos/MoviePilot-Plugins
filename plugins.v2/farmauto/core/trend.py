import time
from typing import Any, Dict, List, Optional, Tuple


class PriceTrendStore:
    """按站点和物品保存有限长度的价格采样。"""

    MAX_SAMPLES = 20

    def __init__(self):
        self._trends: Dict[str, Dict[str, List[Tuple[float, int]]]] = {}

    def record(
        self,
        site_id: str,
        market_prices: Dict[str, int],
        ts: Optional[float] = None,
    ) -> None:
        sample_time = time.time() if ts is None else float(ts)
        site_trends = self._trends.setdefault(str(site_id), {})
        for crop_key, price in (market_prices or {}).items():
            samples = site_trends.setdefault(str(crop_key), [])
            samples.append((sample_time, int(price)))
            del samples[:-self.MAX_SAMPLES]

    def get(self, site_id: str, crop_key: str) -> List[Tuple[float, int]]:
        return list(self._trends.get(str(site_id), {}).get(str(crop_key), []))

    def to_dict(self) -> dict:
        return {
            site_id: {
                crop_key: [[sample_ts, price] for sample_ts, price in samples]
                for crop_key, samples in site_trends.items()
            }
            for site_id, site_trends in self._trends.items()
        }

    @classmethod
    def from_dict(cls, data: Any) -> "PriceTrendStore":
        store = cls()
        if not isinstance(data, dict):
            return store
        for site_id, site_trends in data.items():
            if not isinstance(site_trends, dict):
                continue
            for crop_key, raw_samples in site_trends.items():
                if not isinstance(raw_samples, list):
                    continue
                samples: List[Tuple[float, int]] = []
                for sample in raw_samples:
                    if not isinstance(sample, (list, tuple)) or len(sample) != 2:
                        continue
                    try:
                        samples.append((float(sample[0]), int(sample[1])))
                    except (TypeError, ValueError):
                        continue
                if samples:
                    store._trends.setdefault(str(site_id), {})[str(crop_key)] = samples
        store.prune()
        return store

    def prune(self) -> None:
        empty_sites = []
        for site_id, site_trends in self._trends.items():
            empty_crops = []
            for crop_key, samples in site_trends.items():
                site_trends[crop_key] = samples[-self.MAX_SAMPLES:]
                if not site_trends[crop_key]:
                    empty_crops.append(crop_key)
            for crop_key in empty_crops:
                del site_trends[crop_key]
            if not site_trends:
                empty_sites.append(site_id)
        for site_id in empty_sites:
            del self._trends[site_id]
