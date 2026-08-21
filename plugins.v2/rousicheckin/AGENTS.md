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
- 登录 POST 必须携带 `Origin: https://rousi.pro` 与 `Referer: https://rousi.pro/login`，否则 PeerGo 在认证前返回 HTTP 403 同源校验错误。
- 签到前必须先读取 `/api/v1/me/attendance`；`claimed_today=true` 时禁止重复 POST。
- 签到 POST 必须携带 `Origin: https://rousi.pro`、站内同源 `Referer`、`X-CSRF-Token` 和唯一 `Idempotency-Key`。
- 自动登录取得新 Cookie 后必须用完整配置回写，保留账号、密码、cron、通知和启用状态，并将 `onlyonce` 重置为 `false`，避免配置重载重复执行。
- 站内消息只通过 GET 读取，不自动标记已读；去重键为字符串类型通知 ID。
- AutoPtCheckin 不再保留 rousi.pro 适配，肉丝签到只由本插件负责，避免重复执行。
- 版本变更同步更新 `plugin_version` 与 `package.v2.json` 的 version/history。
- 真实签到属于有副作用操作，只有用户明确授权后才能执行；登录验证可只获取 Session 和读取签到状态，不调用签到 POST。

## 远程验证

- qnap 运行目录为容器内 `/app/app/plugins/rousicheckin/`；同步后通过插件 reload API 重载。
- 部署验证至少确认：插件版本、配置页账号/密码/Cookie 字段、Cookie Session GET、调度注册与 `onlyonce=false`。
- 禁止在命令输出、插件日志、测试夹具或提交中暴露账号密码及 Cookie 值。
