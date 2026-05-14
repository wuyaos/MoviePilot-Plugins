# clouddrive2disk CloudDrive2 存储

## 一句话职责
通过基于 clouddrivedisk/cd2disk 修改而成的 CloudDrive2 proto 1.0.7 / gRPC 直连与 API 令牌把 CloudDrive2 注册为 MoviePilot V2 存储。

## Input / Output / Pos
- **Input**：MoviePilot 插件配置、CloudDrive2 gRPC 地址、API 令牌、存储模块文件操作调用
- **Output**：`CloudDrive2Disk` 插件类与 `Cd2Api` 存储操作适配器
- **Pos**：`plugins.v2/clouddrive2disk/`，独立 MoviePilot V2 存储扩展插件目录

## Files
- `__init__.py` — 插件入口，注册存储、处理配置、暴露 get_module 覆盖方法与 StorageOperSelection 事件。
- `clouddrive.proto` — CloudDrive2 gRPC 协议定义参考文件（proto 1.0.7）。
- `requirements.txt` — 插件运行依赖。
- `core/cd2_api.py` — CloudDrive2 gRPC API 适配器，实现浏览、上传、下载、删除、重命名、移动、复制与空间统计。
- `proto/clouddrive2disk_pb2.py` — 由 proto 1.0.7 生成的消息类型代码（插件专属命名，避免全局 descriptor pool 冲突）。
- `proto/clouddrive2disk_pb2_grpc.py` — 由 proto 1.0.7 生成的 gRPC stub 代码（插件专属命名）。
