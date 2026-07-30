"""显式站点注册表：顺序只影响匹配优先级，不依赖包扫描/类反射。"""
from .azusa import Azusa
from .cangbao import Cangbao
from .car import CARPT
from .city13 import City13
from .crabpt import CrabPT
from .cspt import CSPT
from .cyanbug import Cyanbug
from .dubhe import Dubhe
from .freefarm import FreeFarm
from .ggpt import GGPT
from .hxpt import HxPT
from .lajidui import Lajidui
from .longpt import LongPT
from .luckpt import LuckPT
from .moment import Moment
from .mypt import MyPT
from .novahd import NovaHD
from .ptlgs import PTLGS
from .ptskit import PTSKit
from .qingwa import Qingwa
from .vclib import Vclib
from .zm import ZM
from .railgunpt import RailgunPT
from .tangpt import TangPT


SITE_CLASSES = [
    Azusa,
    Cangbao,
    CARPT,
    City13,
    CrabPT,
    CSPT,
    Cyanbug,
    Dubhe,
    FreeFarm,
    GGPT,
    HxPT,
    Lajidui,
    LongPT,
    LuckPT,
    Moment,
    MyPT,
    NovaHD,
    PTLGS,
    PTSKit,
    Qingwa,
    Vclib,
    ZM,
    RailgunPT,
    TangPT,
]


def match_site(site_info: dict):
    """返回匹配的站点类；无适配返回 None。"""
    return next((site_cls for site_cls in SITE_CLASSES if site_cls.matches(site_info)), None)
