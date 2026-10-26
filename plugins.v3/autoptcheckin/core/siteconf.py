# -*- coding: utf-8 -*-
"""每站执行配置解析：有效 proxy/emulate 与云签能力/选择的唯一入口。

数据键（config / site_config 共用同一存储语义）：
- ``site_proxy``: ``{站点id: bool}``，缺键继承 MP 站点 proxy，显式 bool（含 false）最高优先。
- ``site_emulate``: ``{站点id: bool}``，缺键继承 MP render OR 站点声明 emulate。
- ``site_cloudsign``: ``[站点id]``，仅声明云签能力的站生效；显式 ``[]`` 表示用户关闭云签。

本模块只做纯解析，不读宿主对象、不发送请求；/sites、/stats 与执行入口共用。
"""
from __future__ import annotations

from . import cloudsign

__all__ = ["resolve", "cloak_proxy"]


def resolve(site_id, config, *, declared_emulate: bool = False,
            mp_proxy: bool = False, mp_render: bool = False,
            cloudsign_capable: bool | None = None) -> dict:
    """解析站点有效执行配置。

    :param site_id: 站点 ID（数字 ID 统一转 str 匹配）
    :param config: 插件配置（含 site_proxy/site_emulate/site_cloudsign）
    :param declared_emulate: 站点声明的内置仿真（custom 条目为用户填写值）
    :param mp_proxy: MP 站点管理 proxy 布尔（proxy 缺键时的继承来源）
    :param mp_render: MP 站点管理 render 布尔（emulate 缺键时的继承来源）
    :param cloudsign_capable: 显式能力声明；None 时按 cloudsign.CLOUD_SITES 判定
    :return: ``{'proxy': bool, 'emulate': bool, 'cloudsign_capable': bool, 'cloudsign_selected': bool}``
    """
    config = config or {}
    sid = str(site_id)
    proxy_overrides = config.get('site_proxy') or {}
    emulate_overrides = config.get('site_emulate') or {}
    # 覆盖表读取必须用键存在性判断：显式 false 终结继承，绝不能经 `or` 被默认值重新开启。
    proxy = bool(proxy_overrides[sid]) if sid in proxy_overrides else bool(mp_proxy)
    emulate = (bool(emulate_overrides[sid]) if sid in emulate_overrides
               else bool(mp_render) or bool(declared_emulate))
    capable = cloudsign.enabled(sid) if cloudsign_capable is None else bool(cloudsign_capable)
    selected = capable and sid in {str(v) for v in (config.get('site_cloudsign') or [])}
    return {'proxy': proxy, 'emulate': emulate,
            'cloudsign_capable': capable, 'cloudsign_selected': selected}


def cloak_proxy(proxy_enabled: bool, config=None):
    """Cloak 会话出口代理；与本地 HTTP（settings.PROXY）同源保持一致。

    旧 ``cloak_proxy`` 全局配置兼容：非空值优先（'off'=强制直连）。
    ``proxy_enabled`` 为 False 时直接返回 None——显式/继承关闭的站点
    绝不能被 PROXY_HOST 兜底重新开启。
    """
    if not proxy_enabled:
        return None
    legacy = str((config or {}).get('cloak_proxy') or '').strip()
    if legacy:
        return None if legacy.lower() == 'off' else legacy
    try:
        from app.sdk.config import settings
        proxy = settings.PROXY
    except Exception:
        return None
    if isinstance(proxy, dict):
        return proxy.get('https') or proxy.get('http') or None
    return proxy or None
