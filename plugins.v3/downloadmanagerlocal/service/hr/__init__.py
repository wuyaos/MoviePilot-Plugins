"""H&R 模块：站点规则解析、任务扫描、达标判定、记录清理与汇总通知。

- `constants.py`：配置键与默认值（含 qnap 基线）、持久化 key、调度注册常量。
- `models.py`：HrStatus / HrTaskType / HrSiteRule / HrSizeTier / HrTask / HrConfig。
- `rules.py`：插件配置解析、站点独立 YAML 解析与全局回填、按大小分档匹配。
- `scanner.py`：下载器任务读取、种子统计归一、站点识别、排除判定与标签读写。
- `evaluator.py`：站点要求初始化与达标状态流转。
- `cleanup.py`：达标后本地记录清理（不删任务与文件）。
- `notify.py`：状态事件队列与每日汇总通知。
- `guard.py`：破坏性删除路径的 H&R 保护闸门（HrGuard）。
- `service.py`：HrService，插件生命周期与调度/API 的对外入口。
"""
