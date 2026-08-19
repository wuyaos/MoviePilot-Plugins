# PTNewsWatch

MoviePilot V2 的 PT 论坛/RSS/Atom 动态汇总插件。

## 职责
- 汇总 PTerClub、TJUPT NexusPHP 主题页与蜂巢 RSS、药丸 Atom 新消息。
- 每来源独立认证、去重、水位、错误和最近消息；同站多来源只共享认证。
- 首次成功运行默认静默建立基线；后续只通知未见 entry ID。
- 数据页使用资讯时间轴，所有时间按 `settings.TZ` 展示。

## 目录
- `__init__.py`：MoviePilot 生命周期、调度/API/UI 委托。
- `core/config.py`：平铺配置模型与完整序列化。
- `core/models.py`：来源、消息、抓取结果和运行结果模型。
- `core/source_registry.py`：固定来源注册表；新增来源优先只增加 `SourceSpec`。
- `core/auth/`：MP 站点 Cookie、CookieCloud、药丸 Cookie 解析。
- `core/fetchers/`：RSS/Atom/NexusPHP 网络抓取。
- `core/parsers/`：Feed 与 NexusPHP 页面纯解析。
- `core/state.py`：PluginData 水位、seen、时间轴和历史。
- `core/engine.py`：多来源隔离编排和首次基线。
- `ui/`：配置页和数据页。

## 约束
- Cookie 不进入日志、通知、历史、页面或 API。
- PTerClub/TJUPT 只使用 MoviePilot 站点 Cookie+UA；不保存手工 Cookie。
- 药丸 Atom 手工 Cookie 优先；为空时 CookieCloud 精确匹配 `invites.fun` 并完整回写配置。
- 来源失败不得推进该来源 seen/watermark，也不得阻断其他来源。
- 配置控件使用平铺 model key，禁止点号嵌套。
- 真实调试只 GET，不发帖、不回帖、不修改论坛。
- 版本变更同步 `plugin_version` 与根 `package.v2.json`。
