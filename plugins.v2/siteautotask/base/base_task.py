import inspect
from pathlib import Path
from typing import List


class BaseTask:
    """任务基类：只负责收集任务声明，不承载站点业务逻辑。"""

    def __init__(self, client=None):
        self.client = client

    def _find_task_meta(self, name: str):
        for base in self.__class__.__mro__:
            func = base.__dict__.get(name)
            if func and hasattr(func, "_task_meta"):
                return getattr(func, "_task_meta")
        return None

    def get_registered_tasks(self) -> List[dict]:
        tasks = []
        for name, method in inspect.getmembers(self.__class__, predicate=inspect.isfunction):
            if name not in self.__class__.__dict__:
                continue
            meta = getattr(method, "_task_meta", None) or self._find_task_meta(name)
            if not meta:
                continue
            try:
                prefix = Path(inspect.getfile(self.__class__)).stem.lower()
            except (TypeError, OSError):
                prefix = getattr(self.__class__, "__module__", "").split(".")[-1].lower()
            client_name = (
                getattr(self.client, "name_cn", None)
                or getattr(self.client, "site_name", None)
                or "未知"
            )
            tasks.append({
                "id": f"{prefix}_{name}",
                "name": name,
                "label": meta["label_template"].format(client_name=client_name),
                "hint": meta["hint_template"].format(client_name=client_name),
                "task_type": meta.get("task_type", "generic"),
                "func": getattr(self, name),
            })
        return tasks
