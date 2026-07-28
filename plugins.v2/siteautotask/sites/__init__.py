"""站点加载器。

统一 ptautotask（pkgutil 扫描 Client+Tasks）与 groupchatzone（ModuleHelper 加载 Handler）
两套站点发现机制。

约定：每个站点文件含
  - Handler 类：继承 ISiteHandler，实现 match() 路由 + 业务方法 + get_feedback
  - Tasks 类：继承 BaseTask，用 @task_info 标注任务方法，__init__ 绑定 Handler
"""
import importlib
import inspect
import pkgutil
from pathlib import Path
from typing import List

from app.log import logger

from ..base.site_handler import ISiteHandler
from ..base.base_task import BaseTask


def load_site_classes() -> List[dict]:
    """扫描 sites/ 目录，加载所有站点的 Handler 与 Tasks 类。

    返回 [{handler_cls, tasks_cls, site_name, domain, tasks_meta}]
    其中 tasks_meta 为 [{id, label, hint}]（用 cookie=None 实例化 Tasks 反射得到）。
    """
    sites_info = []
    sites_path = Path(__file__).parent
    pkg_prefix = __package__ or "sites"

    module_infos = list(pkgutil.iter_modules([str(sites_path)]))
    # NexusPHP 只提供能力基类，不作为可配置/可执行的通用站点。
    # 所有任务必须归属于明确的站点适配器，避免误把未知站点当作可执行目标。
    for module_info in sorted(module_infos, key=lambda item: item.name):
        if module_info.name == "nexusphp":
            continue
        module_name = f"{pkg_prefix}.{module_info.name}"
        try:
            module = importlib.import_module(module_name)
        except Exception as e:
            logger.error(f"加载站点模块 {module_name} 失败：{e}")
            continue

        handler_cls = None
        tasks_cls = None

        for name, obj in inspect.getmembers(module, inspect.isclass):
            # 仅取当前模块定义的类，排除导入的基类
            if getattr(obj, "__module__", "") != getattr(module, "__name__", ""):
                continue
            if issubclass(obj, ISiteHandler) and obj is not ISiteHandler:
                handler_cls = obj
            elif issubclass(obj, BaseTask) and obj is not BaseTask:
                tasks_cls = obj

        if not handler_cls or not hasattr(handler_cls, "match") or inspect.isabstract(handler_cls):
            continue

        site_name = ""
        domain = ""
        # 静态方法获取站点名/域名（不需要实例化）
        if hasattr(handler_cls, "get_site_name"):
            try:
                site_name = handler_cls.get_site_name()
            except Exception:
                pass
        if hasattr(handler_cls, "get_site_domain"):
            try:
                domain = handler_cls.get_site_domain()
            except Exception:
                pass

        # 反射任务元数据（实例化 Tasks，cookie 传空）
        tasks_meta = []
        if tasks_cls:
            try:
                # Tasks.__init__(cookie) 内部会构造 Handler(cookie)，
                # 但 Handler 需要 site_info。这里只为拿任务元数据，
                # 用占位 site_info 实例化。
                placeholder = {"url": "", "name": site_name, "cookie": "", "ua": "", "render": False}
                try:
                    handler_inst = handler_cls(placeholder)
                except Exception:
                    handler_inst = None
                try:
                    tasks_inst = tasks_cls(cookie=None) if "cookie" in inspect.signature(
                        tasks_cls.__init__).parameters else tasks_cls()
                except Exception:
                    tasks_inst = None
                if tasks_inst is not None and handler_inst is not None:
                    tasks_inst.client = handler_inst
                    tasks_meta = tasks_inst.get_registered_tasks()
            except Exception as e:
                logger.error(f"解析站点 {site_name} 任务失败：{e}")

        # 为 CLAIM/MEDAL/可选 CHAT 附加下拉选项（静态从 Handler 类获取）。
        claim_options = []
        if hasattr(handler_cls, "get_claim_options"):
            try:
                claim_options = handler_cls.get_claim_options()
            except Exception as e:
                logger.error(f"获取站点 {site_name} claim 选项失败：{e}")
        chat_options = []
        if hasattr(handler_cls, "get_chat_options"):
            try:
                chat_options = handler_cls.get_chat_options()
            except Exception as e:
                logger.error(f"获取站点 {site_name} chat 选项失败：{e}")
        for task in tasks_meta:
            task_type = task.get("task_type")
            if task_type in ("claim", "medal") and claim_options:
                task["claim_options"] = claim_options
                if task_type == "medal":
                    task["claim_multiple"] = bool(getattr(handler_cls, "CLAIM_MULTIPLE", False))
            elif task_type == "chat" and chat_options:
                task["claim_options"] = chat_options
                task["chat_selection"] = True

        sites_info.append({
            "handler_cls": handler_cls,
            "tasks_cls": tasks_cls,
            "site_name": site_name,
            "domain": domain,
            "tasks_meta": tasks_meta,
        })
        logger.info(f"成功加载站点：{site_name or module_info.name}，任务数：{len(tasks_meta)}")

    return sites_info


def get_site_handler(site_info: dict, handler_classes: List[type]) -> ISiteHandler:
    """根据 site_info 路由到匹配的 Handler 实例。

    遍历 handler_classes，第一个 match() 成功的返回。
    """
    for handler_cls in handler_classes:
        try:
            if not (inspect.isclass(handler_cls) and issubclass(handler_cls, ISiteHandler)
                    and handler_cls is not ISiteHandler):
                continue
            handler = handler_cls(site_info)
            if handler.match():
                return handler
        except Exception as e:
            logger.error(f"实例化/匹配处理器 {handler_cls.__name__} 失败：{e}")
    return None
