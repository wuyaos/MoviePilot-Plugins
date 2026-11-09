"""已停用的失败清理兼容模块。

旧配置和历史导入仍可解析，但本模块不注册事件/调度，也不执行任何删除。
"""
from typing import Any
from .config import FailCleanConfig, parse_failclean_config

class FailCleanService:
    """兼容旧导入的空服务；所有执行入口均返回停用结果。"""
    def __init__(self, plugin):
        self.plugin = plugin
        self._config = FailCleanConfig()
    @property
    def config(self):
        return self._config
    def init_module(self, config=None):
        self._config = parse_failclean_config(config)
        return self
    def stop(self):
        return None
    def handle_transfer_failed(self, *args, **kwargs) -> dict[str, Any]:
        return {"disabled": True, "deleted": 0, "skipped": 1}
    def cleanup_repeat_sources(self, *args, **kwargs) -> dict[str, Any]:
        return {"disabled": True, "cleaned": 0, "skipped": 1}
    def clear_history(self) -> dict[str, Any]:
        return {"removed": 0, "disabled": True}
