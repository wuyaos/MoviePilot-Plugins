# SiteRefresh

V2 专用站点 Cookie/UA 自动刷新插件；输入 AutoPtCheckin 的 `site_refresh` 事件、站点选择、KeePass WebDAV KDBX 或手动凭据配置，输出站点 Cookie/UA 更新结果并可同步写回 CookieCloud。

## Input / Output / Pos
- Input: `EventType.PluginAction` 事件、站点 ID、KeePass WebDAV KDBX 配置、`siteconf` 兜底配置。
- Output: 调用 `SiteChain.update_cookie()` 更新 MoviePilot 站点 Cookie 和 UA，记录最近刷新结果。
- Pos: 自动签到发现 Cookie 失效后的事件消费者，浏览器登录能力委托当前 MoviePilot V2 宿主实现。

## Files
- `__init__.py`: 插件入口、配置页、事件处理、刷新结果展示。
- `credentials.py`: 凭据来源路由，优先 KeePass WebDAV，失败时使用手动配置兜底。
- `keepass.py`: WebDAV 只读下载 KDBX、内存解密、按 entry URL 域名匹配站点并读取 TOTP。
- `cookiecloud.py`: CookieCloud 密文读取、解密、合并站点 Cookie、重新加密和写回。
- `requirements.txt`: KeePass/TOTP 依赖声明（pykeepass、pyotp）。
