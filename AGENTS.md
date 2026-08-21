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
- `RousiCheckin`: 肉丝 PeerGo 独立签到，优先复用 Session Cookie，失效后使用账号密码登录并自动回写新 Cookie。
- `SiteRefresh`: 站点自动更新，接收 Cookie 失效事件并刷新站点 Cookie/UA。
- `TangLottery`: 不可躺自动抽奖助手，按每日目标次数自动拆解并执行抽奖。
- `CloudDrive2Disk`: CloudDrive2 存储模块，通过 gRPC/API 接入 CloudDrive2。
- `PtHitAndRun`: H&R 助手 Pro，管理 PT 站 H&R 种子标签、状态和清理。
- `ForumSignin`: 论坛签到，支持蜂巢 pting.club 与药丸 invites.fun 双站签到。
- `PtTaskFlow`: 声明式 PT 站点任务流，使用 Task/Control/Unit/Site 分层组合签到、喊话、申领、勋章和抽奖。
- `PTNewsWatch`: PT 资讯动态监控，汇总 PTerClub/TJUPT 主题页与蜂巢 RSS、药丸 Atom 新消息。

## 开发规范
- 每个插件目录必须有 `__init__.py`（插件入口）和 `AGENTS.md`（结构说明）
- `package.v2.json` 必须登记插件元数据：name/description/labels/version/icon/author/level/history
- 插件版本变更时同步更新 `__init__.py` 的 `plugin_version` 和 `package.v2.json` 的 version + history
- 插件间协作通过 `EventType.PluginAction` 事件，避免硬依赖其他插件模块
- 插件图标统一放在根目录 `icons/`，使用 PNG + RGBA 透明背景，画布固定为 `200×200`
- 图标主体应在画布内保持水平、垂直居中，建议有效内容控制在约 `160×160`，四周预留约 `20px` 安全边距，避免宿主按 `48×48` 容器显示时过度放大
- 图标主体比例可按业务图形保留，不强制裁成正方形；窄图形应通过画布留白保持视觉居中，不得通过拉伸填满画布
- 修改或新增图标后检查：文件尺寸为 `200×200`、模式为 `RGBA`、存在透明边距
- 提交前 `python3 -c "import ast; ast.parse(open('<file>').read())"` 校验语法
- MP 本地调试：`moviepilot` CLI，后端 http://127.0.0.1:7300

### `package.v2.json` 编辑规范
- 向 history 插入新版本条目时，禁止用 `edit` 的 `oldText`/`newText` 做相邻行替换（如把 `"history": {\n  "v1.5.6":` 整体作为 oldText 替换），会吞掉旧行键名导致两个字符串相邻、JSON 破坏。
- 必须二选一：
  - 优先用 `replace`：先 `read` 拿到目标行 3 字 HASH 锚点，对该单行整行替换，旧行完整保留为新行下方一行；
  - 或用 `write` 全量重写整个 `package.v2.json`（适合多处改动）。
- 每次 `package.v2.json` 改动后立即 `python3 -m json.tool package.v2.json >/dev/null` 校验，失败则当场修复并补提交，不得带病继续。
- 版本字段三处同步：`__init__.py` 的 `plugin_version`、`package.v2.json` 的 `version`、`history` 顶部新版本条目。

### Todo 管理
Todo 必须与实际进度同步，避免滞后或遗漏：
- 开始有产出的任务前：`create` + 立即 `update(in_progress)`，`activeForm` 用进行时描述（如“迁移站点适配”）
- 产出落地后立即 `update(completed)`：以提交、推送、测试通过或验证结果为完成标志，不留尾巴
- 遇到阻塞：新建阻塞 todo，原 todo 保持 `in_progress`，不批量标记完成
- 每轮对话结束前检查：不应有 `in_progress` 超出当前实际工作范围
- 禁止把预期当结论：`completed` 必须有实际文件、提交、测试或工具结果支撑
- 简单单步任务可不建 todo；3 步以上或多目标的复杂工作必须建 todo 跟踪

## 常用命令
- 启动 MP: `moviepilot start`
- 重载插件: `curl -sS http://127.0.0.1:7300/api/v1/plugin/reload/<PluginId> -H "X-API-KEY: <key>"`
- 触发签到: `moviepilot scheduler run <service_id>`
