# PTNewsWatch

MoviePilot V2 的 PT 论坛/RSS/Atom 动态汇总插件。

## 职责
- 汇总 PTerClub、TJUPT NexusPHP 主题页与蜂巢 RSS、药丸 Atom 新消息。
- 每个来源模板支持一行一个 URL；URL 实例独立去重、水位、错误和最近消息，同站实例只共享认证。
- 首次成功运行固定推送最近消息并建立 seen 基线；后续只通知未见 entry ID，通知条数受单来源上限控制。
- 数据页使用紧凑资讯列表，标题链接原帖，所有时间按 `settings.TZ` 展示。

## 目录
- `__init__.py`：MoviePilot 生命周期、调度/API/UI 委托。
- `core/config.py`：平铺配置模型与完整序列化。
- `core/models.py`：来源、消息、抓取结果和运行结果模型。
- `core/source_registry.py`：内置来源模板注册表。
- `core/source_instances.py`：多行 URL 校验、去重和稳定运行实例 ID。
- `core/url_utils.py`：HTTPS、域名、同源跳转和内容链接安全校验。
- `core/auth/`：MP 站点 Cookie、CookieCloud、药丸 Cookie 解析。
- `core/fetchers/`：RSS/Atom/NexusPHP 网络抓取。
- `core/parsers/`：Feed 与 NexusPHP 页面纯解析。
- `core/state.py`：PluginData 水位、seen、时间轴和最近运行摘要。
- `core/engine.py`：多来源隔离编排和首次基线。
- `ui/`：配置页和数据页。

## 约束
- Cookie 不进入日志、通知、历史、页面或 API。
- PTerClub/TJUPT 只使用 MoviePilot 站点 Cookie+UA；不保存手工 Cookie。
- 药丸 Atom 手工 Cookie 优先；为空时 CookieCloud 精确匹配 `invites.fun` 并完整回写配置。
- 来源失败不得推进该 URL 实例的 seen/watermark，也不得阻断同组或其他来源。
- 携带 Cookie 的来源和分页/重定向必须保持 HTTPS、受信域名与同源边界。
- 配置控件使用平铺 model key，禁止点号嵌套。
- 真实调试只 GET，不发帖、不回帖、不修改论坛。
- 版本变更同步 `plugin_version` 与根 `package.v2.json`。
