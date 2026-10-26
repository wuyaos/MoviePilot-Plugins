"""整理失败清理模块：整理失败即时删源与重复下载残留巡检。

- `constants.py`：配置键与默认值（含 qnap 基线）、持久化 key、调度注册常量。
- `config.py`：插件配置解析与运行时配置（FailCleanConfig）。
- `hostapi.py`：宿主能力边界（存储链、整理/下载历史、下载目录、媒体扩展名）。
- `notify.py`：源文件删除结果与巡检汇总通知。
- `service.py`：FailCleanService，插件生命周期、事件与调度的对外入口。
- `events.py`：TransferFailed 事件处理入口，供插件入口层注册。
"""
