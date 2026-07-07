# MoviePilot-Plugins

MoviePilot V2 自用插件仓库。

## 仓库结构
- `plugins.v2/`: V2 插件目录，每个子目录一个插件
- `package.v2.json`: 插件元数据登记（name/version/history/level/icon）
- 每个插件目录应有 `AGENTS.md` 描述结构

## 插件列表
- `LLMRecognizer`: AI 识别增强，复用 MoviePilot 当前 LLM 配置做原生识别失败后的结构化兜底。
- `CoverGen`: 媒体库封面生成，支持库白名单、合集黑名单过滤、动画风格和 Emby/Jellyfin。
- `StrmManage`: 云盘 Strm 助手，生成 strm 并通过 CloudDrive2 处理非视频文件。
- `AzKeepAlive`: AnimeZ 保活，定时访问站点并提交候选种子到下载器。
- `AutoPtCheckin`: PT 站点自动签到，支持自定义站点、CookieCloud 同步和验证码签到适配。
- `SiteRefresh`: 站点自动更新，接收 Cookie 失效事件并刷新站点 Cookie/UA。
- `TangLottery`: 不可躺自动抽奖助手，按每日目标次数自动拆解并执行抽奖。
- `CloudDrive2Disk`: CloudDrive2 存储模块，通过 gRPC/API 接入 CloudDrive2。
- `PtHitAndRun`: H&R 助手 Pro，管理 PT 站 H&R 种子标签、状态和清理。
- `ForumSignin`: 论坛签到，支持蜂巢 pting.club 与药丸 invites.fun 双站签到。

## 开发规范
- 每个插件目录必须有 `__init__.py`（插件入口）和 `AGENTS.md`（结构说明）
- `package.v2.json` 必须登记插件元数据：name/description/labels/version/icon/author/level/history
- 插件版本变更时同步更新 `__init__.py` 的 `plugin_version` 和 `package.v2.json` 的 version + history
- 插件间协作通过 `EventType.PluginAction` 事件，避免硬依赖其他插件模块
- 提交前 `python3 -c "import ast; ast.parse(open('<file>').read())"` 校验语法
- MP 本地调试：`moviepilot` CLI，后端 http://127.0.0.1:7300

## 常用命令
- 启动 MP: `moviepilot start`
- 重载插件: `curl -sS http://127.0.0.1:7300/api/v1/plugin/reload/<PluginId> -H "X-API-KEY: <key>"`
- 触发签到: `moviepilot scheduler run <service_id>`
