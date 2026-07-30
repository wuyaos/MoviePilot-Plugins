import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class CropDef:
    key: str
    name: str
    cost: int
    type: str
    id: int
    action: str = "plant"


@dataclass
class LandState:
    """统一土地状态模型，通用农场与思齐共用。

    通用农场无地块概念，按 crop_key 合成虚拟 land_id；思齐按真实 land_id/plot_index。
    策略层基于此统一模型决策，不再关心站点差异。
    """
    # 标识
    land_id: str                    # 统一地块标识；通用农场合成 f"{site_id}:{crop_key}"
    site_id: str = ""
    crop_key: Optional[str] = None   # 作物 key（如 "crop_1"），空地为 None
    plot_index: Optional[int] = None

    # 状态
    state: str = "empty"             # "empty" | "growing" | "ripe"
    can_harvest: bool = False

    # 作物信息
    seed_id: Optional[int] = None
    seed_name: Optional[str] = None

    # 时间信息
    harvest_time: Optional[float] = None    # 收获时间戳（秒）
    remaining_minutes: Optional[int] = None
    grow_time: Optional[int] = None        # 总成长时间（秒）

    # 经济信息
    cost: Optional[int] = None       # 购入价
    sellable: bool = False           # 是否可出售


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
    skipped: bool = False
    reason: str = ""
    crop_name: str = ""
    crop_icon: str = ""
    land_name: str = ""
    plot_index: Optional[int] = None
    quantity: int = 0
    # 操作实际产生的展示数值；与计入魔力净收益的 profit 分离。
    value: Optional[int] = None
    value_unit: str = ""
    # 执行时刻的时间戳(浮点秒)，前端直接解析展示
    time: float = field(default_factory=time.time)
    # 操作后的账户余额(魔力/金币)，保证执行记录「魔力」列有值
    balance_after: Optional[int] = None


@dataclass
class SiteRunReport:
    site_id: str
    site_name: str
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
