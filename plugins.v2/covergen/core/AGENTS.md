# core/ 核心业务模块

## 一句话职责
封装封面生成的全部业务逻辑：配置解析、字体管理、服务器交互、图片传输、渲染调度、定时任务。

## Input / Output / Pos
- **Input**：PluginConfig dict、ServiceInfo 实例
- **Output**：CoverEngine 调度结果 + 媒体服务器封面上传
- **Pos**：`plugins.v2/covergen/core/`，被 `__init__.py` 装配，被 `api/` `ui/` 间接引用

## Files
- `config.py` — `@dataclass PluginConfig` 全字段配置、校验、迁移、派生属性
- `font.py` — `FontManager`：预设发现、URL 下载（cache-skip）、本地校验
- `server.py` — 媒体服务器元数据查询：库/用户/项目/合集/视图（统一 Emby/Jellyfin 差异）
- `image_io.py` — 图片下载（远程/HOST 通道）+ base64 上传
- `render.py` — 图片 URL 解析、标题 YAML 解析、8 风格函数分发
- `engine.py` — `CoverEngine` 主调度器 + `RunStats`（黑名单合集过滤、历史封面每库保留上限）
- `scheduler.py` — `Scheduler`：cron 注册、TransferComplete 防抖、stop_event 管理

## 关键设计
- raw HTTP 走 `service.instance.get_data/post_data`（非 `requests`），由 MP 框架注入 host/token
- `MediaServerChain` 公共 API 不暴露 SortBy/IncludeItemTypes，本层用 raw HTTP 自行控制
- `_seen_keys` 局部化、`_current_updating_items` 加锁，消除原版多线程 TOCTOU

## 更新条件
新增/删除模块、改变模块职责或公共方法签名时同步更新本文件与对应文件头注释。
