# 云盘Strm助手（CD2增强）

生成云盘媒体 strm 文件，并支持通过 CloudDrive2 下载 nfo、字幕、图片等非视频文件。

## Input / Output / Pos
- Input: 监控目录映射、strm 输出目录、云盘路径、命名格式和扩展名配置。
- Input: CloudDrive2 地址、账号密码、超时、非媒体处理方式和立即扫描开关。
- Input: `EventType.PluginAction` 远程命令、扫描 API 和配置页触发。
- Output: strm 文件、非视频附属文件下载/复制结果、扫描统计和最近运行状态。
- Output: API/命令响应、插件日志和详情页扫描摘要。
- Pos: MoviePilot 云盘媒体库 strm 生成辅助层。
- Pos: 可联动 CloudDrive2 增强非视频文件处理，但不替代宿主媒体整理链路。

## Files
- `__init__.py`: 插件入口、配置解析、目录扫描、strm 生成、CloudDrive2 登录/下载、API 和远程命令。
- `requirements.txt`: CloudDrive2 HTTP 调用依赖声明。

## Key Constraints
- `plugin_version` 必须与 `package.v2.json` 中 `StrmManage.version` 同步。
- 目录配置每行必须为 `本地目录#strm目录#云盘目录#格式`，字段缺失时只跳过该行并记录错误。
- 扫描任务通过 `_lock` 和后台线程执行，避免多次立即运行并发写同一目录。
- `cd2_handle_mode` 是当前非媒体处理方式来源，旧 `cd2_use_grpc_lookup` 仅作兼容。
- 生成 strm 时遵守覆盖、URI 编码和扩展名配置，不要硬编码媒体扩展名。
- CloudDrive2 请求需使用配置的超时，认证失败或下载失败要落入统计并继续处理其他文件。
- 文件路径映射要保持本地目录、strm 目录和云盘目录的相对路径一致。
- 非媒体文件处理失败不应影响同目录其他媒体 strm 生成。
- API 返回要包含成功状态和可读消息，便于前端按钮展示。
- 删除或重命名配置项时保持旧配置兼容读取。
