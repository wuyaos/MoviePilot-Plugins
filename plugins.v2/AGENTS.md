# plugins.v2

MoviePilot V2 专用插件目录；每个子目录是独立插件实现，元数据统一写入根目录 `package.v2.json`。

## Input / Output / Pos
- Input: MoviePilot V2 `_PluginBase` 宿主能力、插件配置、事件、API 和调度器。
- Output: 可由 MoviePilot V2 插件市场加载的插件源码。
- Pos: 本仓库 V2 插件实现层；不承载 V1 兼容插件。

## Files
- `autoptcheckin/`: PT 站点自动签到/登录插件。
- `azkeepalive/`: AnimeZ 保活插件。
- `clouddrive2disk/`: CloudDrive2 存储接入插件。
- `covergen/`: 媒体库封面生成插件。
- `llmrecognizer/`: AI 识别增强插件。
- `pthitandrun/`: PT H&R 助手插件。
- `siterefresh/`: 站点 Cookie/UA 自动刷新插件。
- `strmmanage/`: 云盘 STRM 管理插件。
