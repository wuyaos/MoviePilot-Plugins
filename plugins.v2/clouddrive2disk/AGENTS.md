# clouddrive2disk CloudDrive2 存储

## 一句话职责
通过基于 clouddrivedisk/cd2disk 修改而成的 CloudDrive2 proto 1.0.7 / gRPC 直连与 API 令牌把 CloudDrive2 注册为 MoviePilot V2 存储。

## Input / Output / Pos
- **Input**：MoviePilot 插件配置、CloudDrive2 gRPC 地址、API 令牌、存储模块文件操作调用
- **Output**：`CloudDrive2Disk` 插件类与 `Cd2Api` 存储操作适配器
- **Pos**：`plugins.v2/clouddrive2disk/`，独立 MoviePilot V2 存储扩展插件目录

## Files
- `__init__.py` — 插件入口，注册存储、处理配置、暴露 get_module 覆盖方法与 StorageOperSelection 事件。
- `cd2.proto` — CloudDrive2 gRPC 协议定义参考文件（proto 1.0.7，package cd2，仅供参考）。
- `requirements.txt` — 插件运行依赖。
- `core/cd2_helpers.py` — 纯静态工具函数：路径规范化、FileItem 转换、gRPC 错误文本、human_size 等；无 I/O，无副作用。
- `core/cd2_client.py` — gRPC 连接与鉴权层（Cd2Client）：建立 channel、Bearer token 元数据、基础 RPC 调用、下载 URL 解析。
- `core/cd2_upload.py` — 上传策略层：DirectUploader（CreateFile/WriteToFile/CloseFile + 等待云端上传）、RemoteUploadManager（协议骨架，当前回退到直接上传）。
- `core/cd2_api.py` — MoviePilot 存储适配器（Cd2Api）：薄层，委托给 Cd2Client 与 DirectUploader，实现 list/iter_files/create_folder/get_item/delete/rename/move/copy/download/upload/usage。
- `proto/cd2_pb2.py` — 由 cd2.proto（package cd2）生成的消息类型代码，descriptor pool key 为 `cd2.proto`，不与其他插件冲突。
- `proto/cd2_pb2_grpc.py` — 由 cd2.proto 生成的 gRPC stub 代码，方法路径已修正为 `/clouddrive.CloudDriveFileSrv/…`。
