from typing import Dict, List, Optional

from .base import FarmSiteConfig
from .baozi import BaoziConfig
from .haoxue import HaoxueConfig
from .novahd import NovaHDConfig
from .playlet import PlayLetConfig
from .siqi import SiqiConfig
from .skit import SkitConfig

SITE_CONFIGS: Dict[str, FarmSiteConfig] = {
    "playlet": PlayLetConfig(),
    "novahd": NovaHDConfig(),
    "haoxue": HaoxueConfig(),
    "baozi": BaoziConfig(),
    "skit": SkitConfig(),
    "siqi": SiqiConfig(),
}

SITE_OPTIONS = [
    {"title": config.site_name, "value": site_id}
    for site_id, config in SITE_CONFIGS.items()
]


def get_site_config(site_id: str) -> Optional[FarmSiteConfig]:
    return SITE_CONFIGS.get(site_id)


def get_all_site_configs() -> List[FarmSiteConfig]:
    return list(SITE_CONFIGS.values())


__all__ = [
    "FarmSiteConfig",
    "SITE_CONFIGS",
    "SITE_OPTIONS",
    "get_site_config",
    "get_all_site_configs",
]
