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
- `tanglottery/`: 不可躺自动抽奖助手，本地修正版增强定时服务注册稳定性。
- `strmmanage/`: 云盘 STRM 管理插件。

## 图标规范
- 图标资源统一使用根目录 `icons/` 下的 PNG 文件，并通过 `plugin_icon` 与 `package.v2.json` 的 `icon` 引用。
- 画布固定为 `200×200`，使用 RGBA 透明背景；主体建议控制在约 `160×160`，四周保留约 `20px` 安全边距。
- 主体必须水平、垂直居中；保留业务图形原始比例，不得通过拉伸填满画布。窄图形通过透明留白保持视觉居中。
- 新增或修改后，检查尺寸、RGBA 模式和透明边距。
