# clouddrive2disk

CloudDrive2 存储插件，基于 baranwang/cd2disk，通过 gRPC 直连 CloudDrive2 并提供 MoviePilot V2 存储模块能力。

## Input / Output / Pos
- input: CloudDrive2 gRPC 地址（`http(s)://host:port`）、API 令牌（Bearer token）
- output: 注册 `CloudDrive2` 存储类型；实现 `get_module()` 存储接口；响应 `StorageOperSelection` 事件
- pos: MoviePilot V2 插件层，存储适配器；不含调度逻辑

## Files

| 文件 | 职责 |
|------|------|
| `__init__.py` | 插件入口：shim 安装、`_PluginBase` 实现、`get_module()` 包装层 |
| `cd2_api.py` | `Cd2Api` gRPC 操作类：鉴权、文件浏览/增删改、上传/下载、空间统计 |
| `clouddrive_pb2.py` | 由官方 `clouddrive.proto` 生成的 protobuf 消息类（勿手动修改） |
| `clouddrive_pb2_grpc.py` | 由官方 `clouddrive.proto` 生成的 gRPC stub（勿手动修改） |
| `clouddrive.proto` | CloudDrive2 官方 proto 源文件，来源：`https://www.clouddrive2.com/api/clouddrive.proto` |
| `requirements.txt` | 依赖：`grpcio>=1.50.0`、`protobuf>=4.21.0` |

## 关键设计

- **bare-name shim**：`_install_clouddrive_shim()` 在模块加载时将 `clouddrive_pb2` / `clouddrive_pb2_grpc` 注册到 `sys.modules` 裸键，使其在 MoviePilot 热重载（仅清除 `app.plugins.*`）后仍可复用，避免 `AddSerializedFile` 重复执行导致的 descriptor pool 冲突。
- **plugin_config_prefix**：`clouddrive2disk_`，与插件目录名一致，兼容旧版用户配置。
- **snapshot_storage**：返回 `Dict[str, Dict]`（含 size / modify_time / type），支持 MP 增量快照对比。

## Proto 更新方法

```bash
# 下载最新 proto（始终与 CloudDrive2 服务器版本一致）
curl -fsSL https://www.clouddrive2.com/api/clouddrive.proto -o clouddrive.proto

# 重新生成 pb2 文件
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. clouddrive.proto

# 生成后将 clouddrive_pb2.py / clouddrive_pb2_grpc.py 复制到本目录
```

服务器版本可通过 `GetRuntimeInfo` RPC 查询。
