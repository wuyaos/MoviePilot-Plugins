"""任务声明装饰器。

通过 task_type 声明任务语义，执行引擎不再依赖任务 label 文本判断。
新增任务类型只需使用新的字符串标识，不需要修改基类。
"""


class TaskType:
    """内置任务类型常量。第三方站点可直接使用自定义字符串扩展。"""

    GENERIC = "generic"
    CHAT = "chat"              # 喊话，执行后收集反馈
    CHECKIN = "checkin"        # 签到
    CLAIM = "claim"            # 任务申领
    EXCHANGE = "exchange"      # 兑换/购买
    MEDAL = "medal"            # 勋章
    LOTTERY = "lottery"        # 抽奖


def task_info(label: str = None, hint: str = None, task_type: str = TaskType.GENERIC):
    """声明任务元数据。

    :param label: 配置页/通知显示名称，支持 ``{client_name}``
    :param hint: 配置页提示，支持 ``{client_name}``
    :param task_type: 任务类型，内置类型见 TaskType，也可使用自定义字符串。
    """
    def decorator(func):
        func._task_meta = {
            "label_template": label or func.__name__,
            "hint_template": hint or f"执行 {func.__name__} 任务",
            "task_type": task_type or TaskType.GENERIC,
        }
        return func
    return decorator
