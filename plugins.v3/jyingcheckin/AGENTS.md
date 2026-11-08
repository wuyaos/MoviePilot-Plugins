# 聚影签到 V3（JyingCheckin）

jying.top 聚影单站每日签到保活，**仅账密模式（B 路径）**——用户裁决不实现 API Key 通道（docs/jyingcheckin-plan.md 修订 2）。

## 结构

- `__init__.py`：插件入口（`app.sdk.plugin._PluginBase`）。`run_once()` 状态机编排 + 调度注册 + API。
- `client.py`：`/api/app/*` 纯协议封装（login/stats/do/luck-draw），不抛网络异常、不做编排。
- `store.py`：`Store` 适配宿主 get_data/save_data；session/latest/history 三键。
- `config_defaults.json`：flat 配置模型（enabled/username/password/lucky_mode/notify/cron/onlyonce/retry_count/retry_interval）。
- `config_form.py`：声明式 Vuetify JSON 表单拼装（`build_form()`），`get_form()` 代理；`get_page()` 用同风格 JSON 渲染 KPI 与记录表。**不使用 vue 联邦**（`get_render_mode()` 覆写已删，回落基类 `vuetify` 声明式渲染）。

## 站点协议要点（浏览器取证）

- 登录 `POST /api/app/login/`（username/password）→ Bearer token，**7 天绝对过期无 refresh**；多端登录互不踢线（已实测），token 失效即整段重登。
- 统计 `GET /api/app/checkin/stats/` → `{status:"success", checked_today, can_checkin, my_total_days, reward_points,...}`（**status 风格 envelope**，不是 code 风格）。
- 每日一签；提交类请求可能有 `await e()` 前置调用与 accountMutation 守卫头（X-Expected-App-User-Id/X-App-User-Token），**待真实运行校准**（修订 2 第 4 条）。

## 状态机与重试语义

- 五态：`success` / `already` / `auth_failed`（账密错或重登仍失败）/ `pending`（网络类，请求可能已落地）/ `unknown`（无法归类的站点响应）。
- 单轮最多整段重登 1 次；`token_refreshed` 记录本轮是否发生过续登。
- pending 重试链：retry_interval 分钟退避、retry_count 次上限；**只有终态落一次历史与通知**，中间态只注册重试调度。
- 已签（checked_today 或文案含"已签"）不重试；幸运签缺 user_id 时降级普通签并在文案注明。

## 安全边界

- 密码只存宿主配置；token 只存插件数据（session 键），不进日志/历史/通知/状态 API。
- history 落盘走 `HISTORY_FIELDS` 白名单，保留 90 天、上限 200 条。
- 离线测试用合成数据；不得在测试中触发真实登录/签到。
