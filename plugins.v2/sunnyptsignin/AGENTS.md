# SunnyPTSignin

SunnyPT 自动签到插件（独立于 autoptcheckin）。

## 背景
SunnyPT 是 Next.js + NextAuth + REST API（api.sunnypt.top）站点，非 NexusPHP。
鉴权用 Bearer JWT（accessToken），token 24h 过期，且 cookie（AuthSession）无法用 c_secure_* 刷新，
因此不走 autoptcheckin 的 cookie 体系，改用用户名密码登录换 token。

## 结构
- `__init__.py`: 插件入口
  - `SunnyPTSignin` 类继承 `_PluginBase`
  - 登录 `POST /login` {username, password} → data.token
  - 签到 `POST /api/v1/attendance/check-in` (Bearer)
  - 状态 `GET /api/v1/attendance/status` (Bearer) 丰富历史记录
  - token 缓存（save_data "token_cache"），解码 JWT exp，提前 1h 刷新
  - token 失效（code=400000）自动重新登录重试一次
  - 签到成功 code=0，已签到 code=400001，未登录 code=400000

## 配置项
- enabled / username / password / cron / notify / run_once

## 接口常量
- LOGIN_URL = https://api.sunnypt.top/login
- SIGNIN_URL = https://api.sunnypt.top/api/v1/attendance/check-in
- STATUS_URL = https://api.sunnypt.top/api/v1/attendance/status
- REFERER = https://sunnypt.top/user/attendance

## 历史存储
- save_data "records" 最近 30 条
- save_data "token_cache" {token, exp, username}
