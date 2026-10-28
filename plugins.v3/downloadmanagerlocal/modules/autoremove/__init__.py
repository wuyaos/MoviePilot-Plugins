"""自动删种模块：移植 TorrentRemover 的规则删种，并在删除前接入 H&R 保护闸门。

- `constants.py`：配置键与表单/QNAP 默认值、持久化 key、调度注册与服务 ID 常量。
- `models.py`：RemoverConfig / RemoveSnapshot / RemoveCandidate。
- `rules.py`：插件配置解析（remover_* 键）。
- `criteria.py`：条件校验、编译与 AND 匹配（非法配置整轮停止）。
- `scanner.py`：下载器任务读取与 qBittorrent / Transmission 字段归一。
- `service.py`：AutoRemoveService，候选收集、动作执行、H&R 保护与运行状态汇总。
"""
