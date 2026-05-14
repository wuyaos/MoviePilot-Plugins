# strmmanage 云盘 Strm 管理

## 一句话职责
生成 strm 并按配置联动 CloudDrive2 处理非视频文件。

## Input / Output / Pos
- **Input**：MoviePilot 插件配置、目录映射、CloudDrive2 地址/账号、插件事件/API 调用
- **Output**：`StrmManage` 插件类，提供全量扫描、单文件处理、API 与远程命令
- **Pos**：`plugins.v2/strmmanage/`，独立 MoviePilot V2 插件目录

## Files
- `__init__.py` — 插件入口，解析配置、扫描目录、生成 strm、处理非视频文件与事件/API。
- `requirements.txt` — 插件运行依赖。
