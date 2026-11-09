# TangRedPacketClaim（不可躺自动领红包 V3）

V3 迁移自 `plugins.v2/tangredpacketclaim`（V2 停留在 1.0.14，索引已标 `v3: false`）。定时领取不可躺（www.tangpt.top，NexusPHP）红包。

## 结构
- `__init__.py`：插件入口 + 全部业务（从 V2 平移，V3 契约适配：`app.sdk.plugin` 基类、`plugin_id`、`get_api()` 相对路径、`success/message/data` envelope）
- `antibot.py`：站点 antibot 人机验证适配（V3 新增，详见下）

## antibot 机制（站点逆向结论）
- 流程：POST `/api/redpacket/antibot/challenge`（头 `X-RedPacket-Device`，body 需带 `nonce` 时间戳参数按站点脚本约定）→ 按 `mode` 求解 → POST `/api/redpacket/antibot/verify`（`{challenge_id, mode, nonce|turnstile_token}`）→ 返回 `{token, expires_at, max_uses, risk_level, method, token_id}`
- `mode=disabled`：无验证，直接领取（客户端缓存 1h 免重复探测）
- `mode=pow`：本地求 `sha256("{salt}:{challenge_id}:{nonce}")` 前导 `difficulty_bits` 位为 0，与站点 `redpacket-pow-worker.js` 同算法（已离线验证 8-bit 用例）
- `mode=turnstile`：用宿主 `app.sdk.browser.launch_browser_context`（CloakBrowser）打开 `{base}/index.php`，显式加载 Turnstile 脚本 render+execute 取 token；先 headless、失败降级 headful（同步 Playwright 必须在独立线程跑，参照 autoptcheckin `run_isolated`）
- 领取请求带 `X-RedPacket-Token` + `X-RedPacket-Device`；HTTP 428 表示 token 失效/耗尽：invalidate 后重新验证并重试一次；成功领取 `mark_used()` 计数（受 `max_uses` 约束）
- device id（32 位随机）与 token 状态持久化到插件数据键 `antibot_device` / `antibot_token`（invalidate 用空串占位，不用 None）

## 其他
- 领取仍是 requests 直连 JSON API（latest/detail/claim），仅 antibot 环节需要浏览器；token 绑定 device 不依赖浏览器 Cookie
- `__request_json` 支持 `extra_headers`，每次重试都会重新合并（retry 循环内）
- 测试：`tests/v3/tangredpacketclaim/`（solve_pow 算法、token 缓存生命周期，纯离线）
