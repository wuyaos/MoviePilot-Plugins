# RousiCheckin

rousi.pro（PeerGo）独立签到插件。

## 结构

- `__init__.py`：MoviePilot 插件入口、调度、签到编排、Cookie 回写、历史和通知。
- `client.py`：PeerGo API 客户端，负责 Session Cookie、账号密码登录、CSRF 签到及只读数据接口。
- `ui.py`：配置页与详情页 Vuetify 结构。
- `tests/`：客户端认证、签到请求与 UI 契约的离线测试。

## 关键约束

- 认证顺序固定为：配置 Cookie → `GET /api/v1/session` 验证 → 失效时账号密码登录 → 回写新 Cookie。
- Cookie 使用 `__Host-peergo_session`，不得写入日志、通知、测试夹具或提交记录。
- 登录仅在 Cookie 失效时执行；登录请求使用 `remember_me=true` 获取约30天 Session。
- 签到前必须先读取 `/api/v1/me/attendance`；`claimed_today=true` 时禁止重复 POST。
- 签到 POST 必须同时携带 `X-CSRF-Token` 和唯一 `Idempotency-Key`。
- 站内消息只通过 GET 读取，不自动标记已读；去重键为字符串类型通知 ID。
- 版本变更同步更新 `plugin_version` 与 `package.v2.json` 的 version/history。
- 真实签到属于有副作用操作，只有用户明确授权后才能执行。
