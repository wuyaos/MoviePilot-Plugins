# 聚影签到 V3（JyingCheckin）

jying.top 聚影单站每日签到保活，**仅账密模式（B 路径）**——用户裁决不实现 API Key 通道（docs/jyingcheckin-plan.md 修订 2）。

## 结构

- `__init__.py`：插件入口（`app.sdk.plugin._PluginBase`）。`run_once()` 状态机编排 + 调度注册 + API。
- `client.py`：`/api/app/*` 纯协议封装（login/stats/do/luck-draw），不抛网络异常、不做编排。
- `store.py`：`Store` 适配宿主 get_data/save_data；session/latest/history 三键。
- `config_defaults.json`：flat 配置模型（enabled/username/password/lucky_mode/notify/cron/onlyonce/retry_count/retry_interval）。
- `config_form.py`：声明式 Vuetify JSON 表单拼装（`build_form()`），`get_form()` 代理；`get_page()` 用同风格 JSON 渲染 KPI 与记录表。**不使用 vue 联邦**（`get_render_mode()` 覆写已删，回落基类 `vuetify` 声明式渲染）。

## 运行时关键约束

- **必须 `super().__init__()`**：宿主端口（plugindata/_plugininstance/systemmessage）在基类构造器绑定，
  缺失 = save_data/update_config 全部 AttributeError 且被适配层吞掉，签到「成功」但零落盘。
  详见 `.agents/notes/2026-11-08-jyingcheckin-super-init-persistence.md`。
- **onlyonce 用后即关**：宿主保存配置不复位 onlyonce；`run_once` 开跑即 `_consume_onlyonce()` 回写 false。
- **单次任务 +5s 缓冲**：`DateTrigger(run_date=now+5s)`，date=now 曾出现到点未跑。
- **手动触发验证**：`GET /api/v1/system/runscheduler?jobid=JyingCheckin_JyingCheckinScheduled`。
- 真实签到协议已校准（2026-11-08 实测）：login/stats/do 无额外前置调用与守卫头；
  已签时 do/stats 返回文案「今日已签到，明天再来吧~」→ status=already。

## 站点协议要点（浏览器取证）

- 登录 `POST /api/app/login/`（username/password）→ Bearer token，**7 天绝对过期无 refresh**；多端登录互不踢线（已实测），token 失效即整段重登。
- 统计 `GET /api/app/checkin/stats/` → `{status:"success", checked_today, can_checkin, my_total_days, reward_points,...}`（**status 风格 envelope**，不是 code 风格）。
- 每日一签；幸运签缺 user_id 时降级普通签并在文案注明。

## 状态机与重试语义

- 五态：`success` / `already` / `auth_failed`（账密错或重登仍失败）/ `pending`（网络类，请求可能已落地）/ `unknown`（无法归类的站点响应）。
- 单轮最多整段重登 1 次；`token_refreshed` 记录本轮是否发生过续登。
- pending 重试链：retry_interval 分钟退避、retry_count 次上限；**只有终态落一次历史与通知**，中间态只注册重试调度。
- 已签（checked_today 或文案含"已签"）不重试。

## 安全边界

- 密码只存宿主配置；token 只存插件数据（session 键），不进日志/历史/通知/状态 API。
- history 落盘走 `HISTORY_FIELDS` 白名单，保留 90 天、上限 200 条。
- 离线测试用合成数据；不得在测试中触发真实登录/签到。
