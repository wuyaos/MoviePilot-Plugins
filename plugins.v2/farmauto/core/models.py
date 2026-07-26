import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class CropDef:
    key: str
    name: str
    cost: int
    type: str
    id: int
    action: str = "plant"


@dataclass(frozen=True)
class MarketPrice:
    crop_key: str
    price: int
    ts: float


@dataclass
class PriceTrend:
    crop_key: str
    samples: List[Tuple[float, int]] = field(default_factory=list)


@dataclass(frozen=True)
class CropStatus:
    crop_key: str
    can_harvest: bool
    remaining_minutes: Optional[int] = None


@dataclass(frozen=True)
class WarehouseItem:
    name: str
    quantity: int
    expire_raw: str
    expire_minutes: Optional[int] = None
    sell_key: str = ""
    crop_key: Optional[str] = None


@dataclass
class ActionResult:
    action: str
    target: str
    success: bool
    double: bool = False
    profit: int = 0
    message: str = ""


@dataclass
class SiteRunReport:
    site_id: str
    site_name: str
    mode: str
    market_prices: Dict[str, int] = field(default_factory=dict)
    crop_status: Dict[str, Dict] = field(default_factory=dict)
    warehouse: List[Dict] = field(default_factory=list)
    actions: List[ActionResult] = field(default_factory=list)
    total_profit: int = 0
    trades_count: int = 0
    status: str = "completed"
    message: str = ""
    ts: float = field(default_factory=time.time)


@dataclass
class RunReport:
    started_at: float
    finished_at: float
    site_reports: List[SiteRunReport] = field(default_factory=list)
    total_profit: int = 0
    total_trades: int = 0
    status: str = "completed"
    message: str = ""


def parse_expire_minutes(expire_str: str) -> Optional[int]:
    """将中文剩余有效期转换为分钟。"""
    if not expire_str:
        return None
    expire_str = expire_str.strip()
    if "已过期" in expire_str:
        return 0

    matches = {
        unit: re.search(rf"(\d+)\s*{unit}", expire_str)
        for unit in ("天", "小时", "分钟")
    }
    if not any(matches.values()):
        return None
    days = int(matches["天"].group(1)) if matches["天"] else 0
    hours = int(matches["小时"].group(1)) if matches["小时"] else 0
    minutes = int(matches["分钟"].group(1)) if matches["分钟"] else 0
    return days * 24 * 60 + hours * 60 + minutes
