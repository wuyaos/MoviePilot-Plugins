# 论坛签到

论坛站点签到插件，单插件支持蜂巢 pting.club 与药丸 invites.fun 双站调度，含 Cookie/账号登录、失败重试和历史记录。

## Input / Output / Pos
- Input: 双站启用开关、Cookie 或账号密码、定时 cron、代理开关和通知开关。
- Input: 签到重试次数/间隔、定时用户信息更新开关、PT 人生推送配置。
- Input: 配置页立即运行、立即更新用户信息和定时任务触发。
- Output: 蜂巢/药丸签到状态、用户信息、PT 人生数据推送结果。
- Output: 双站概览卡、签到日历、历史记录、通知消息和持久化 Cookie。
- Pos: 非 PT 站论坛签到入口；双站认证、签到、信息刷新与通知统一在一个 V2 插件中。
- Pos: 蜂巢与药丸逻辑拆分到服务模块，运行时异常需互相隔离。

## Files
- `__init__.py`: 插件入口、配置读写、调度服务、通知与历史合并。
- `http_client.py`: curl-cffi Chrome 指纹 HTTP 客户端，唯一网络出口。
- `fengchao.py`: 蜂巢登录/签到/用户信息/PT人生推送业务。
- `invites.py`: 药丸登录/Cookie 刷新/签到/退避业务。
- `ui.py`: 配置页与详情页渲染。

## Key Constraints
- `plugin_version` 必须与 `package.v2.json` 中 `ForumSignin.version` 同步。
- 蜂巢和药丸异常隔离；任一站点失败不能影响另一站点执行与历史落库。
- Cookie 优先，账号登录只作为 Cookie 缺失或失效时的回退；刷新后的 Cookie 要持久化。
- 站点拥塞状态码 429/502/503/504 走退避重试，不要密集请求整点接口。
- 药丸首页 session 校验、签到 429 和用户信息接口要分别处理拥塞与失败原因。
- 历史记录按 site + 日期维度合并，详情页需兼容旧状态码数据。
- curl-cffi 请求失败时保留 ERROR traceback/响应片段，便于定位宿主线程池内问题。
- 新增字段时同步 `get_form()` 默认模型、配置读取、保存配置和详情页展示。
- 不要把某个论坛的硬编码状态影响到另一站点分支。
- 提交前用 ast 语法检查 `__init__.py`。
