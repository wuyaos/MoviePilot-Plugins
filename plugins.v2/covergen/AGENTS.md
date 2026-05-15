# CoverGen 媒体库封面生成插件

## 一句话职责
自动生成 Emby/Jellyfin 媒体库封面：抓取库内项目图片 → 按风格模板渲染 → 上传为库 Primary 封面。

## Input / Output / Pos
- **Input**：MoviePilot `_PluginBase` 配置 dict、`MediaServerHelper` 提供的 ServiceInfo
- **Output**：媒体服务器 Library/Images/Primary 上传 + 本地历史封面
- **Pos**：`plugins.v2/covergen/`，对应 `package.v2.json` 中的 `CoverGen` 条目

## 设计动因
重构原 `mediacovergeneratorcustom`（单文件 5200 行、88 方法），按职责拆分为 9 个模块。

## Files
- `__init__.py` — 插件入口，装配子模块；`CoverGen(_PluginBase)` 类
- `requirements.txt` — pillow / numpy / pytz / pyyaml
- `core/` — 核心业务模块（config, font, server, image_io, render, engine, scheduler）
- `api/` — REST API 路由统一构建（消除 40 处重复 dict）
- `ui/` — Vuetify JSON 表单与页面构建
- `style/` — 8 个封面风格模板（4 static + 4 animated），从原插件直接复用
- `utils/` — 颜色/图像/网络/性能工具，从原插件直接复用
- `static/` — 风格预览图 base64 数据，从原插件直接复用


## 更新条件
新增/删除/重命名子目录或顶级文件、调整模块边界时同步更新本文件。
