# 论坛签到 V3

## 边界与宿主契约
- V3 插件只用 `app.sdk.*` 宿主接口；所有自有 API 显式 `auth: bear`、使用相对路径和 `success/message/data` envelope。
- Vue 联邦入口 `remoteEntry.js` 暴露 `./Config` 与 `./Page`，共享宿主 Vue；配置由宿主 `save(model)` 保存。
- 站点凭据只经鉴权配置 API 读写；不得进入统计、历史或日志。历史保留 90 天，清运行缓存不得清历史。
- 药丸为 Flarum API 驱动：GET `/api/users/{uid}` 判 canCheckIn，POST `/api/checkin` 后回读 api_state 复核；服务器轮换的 `flarum_session` 经 `_sync_session` 吸收进凭据（csrf 配对），提交失败的响应原文透出为 failed message。SSDForum 以本人签到行为基础、已签文案确认状态，无行但表单可交互按未签提交并回读复核。蜂巢 API 提交不自动重试可能已落地的请求。只读核验不得 POST。
- 离线测试只使用合成数据，不代表真实 DOM 或站点验证；不得在测试或发布验证中触发真实签到。

## core/ 子包与运行时结构
- `core/models.py`：`SignResult`/`Evidence`（frozen dataclass）。`Evidence.note` 存站点原文口径（如"已累计签到22天"）；`SignResult.metadata["trigger"]` 记录 scheduled/verify/manual。
- `core/history.py`：`HistoryStore` 内存缓存 + `save_data("signin_history")` 持久化；`latest` 按 site id 取最近一条。
- `core/registry.py`：pkgutil 自动发现 `integrations/*.py`（`SITE` 声明 + `ADAPTER`）；`site_names()` 供通知文案取站点中文名，新增站点无需改通知代码。
- `core/runner.py`：页面型站点统一签到流（身份绑定、保守预检、提交后无条件回读）；站点分支禁止写入 runner。
- 远程命令：`EventType.PluginAction` action=`signin_once`（cmd `/forum_signin`），轮内用 `_round_lock` 去重并发。
- PT 人生快照：`integrations/pt_life.py` 在蜂巢确认后向 `/pt-life/snapshot` 推送全站列表；一次失败退避重试至多 3 次。
- `already` 与 `signed` 在统计口径归一为已签；SKIPPED 不进入通知缓冲。
- 失败/网络错误按 retry_count/retry_interval 分钟退避重试，重试链只在终态落一次历史与通知（中途失败不出多条记录）；成功/已签/未确认/认证失败不重试。
- 前端操作按钮的成败反馈走 Toast 轻提示（新宿主），旧宿主无 Toast 时静默降级。

## 新增论坛站点
1. 在 `integrations/` 添加模块，声明 `SITE`（唯一 `id`、`name`、`domain`、能力、`fields`）并导出 `ADAPTER`。
2. `ADAPTER` 提供 `credential_spec`、`base`、页面站点提供 `fetch_page`/`submit`/`verifier`；站点凭据字段需使用 flat config key，Cookie/Token 字段标为 `type: password`。
3. 在 `verifiers/` 实现该站的身份、提交前/后状态和奖励证据解析。页面型站点优先复用 `core/runner.py`：身份绑定、保守预检、提交后无条件回读由核心统一控制。
4. 只在确有不同认证协议时加专属 adapter；Cookie 型 Discuz 页面实现应复用通用页面签到协议，不能把站点判定分支写入核心 runner。
5. 给 adapter/verifier 添加无真实凭据的离线合成测试；为 `SITE.fields` 补 UI/API 契约断言。确认 registry 自动发现后再构建 `frontend.v3/forumsignin/`。

## 前端与验证
- 配置页为单页滚动布局（基础设置 → 执行调度 → 论坛站点区），站点少不拆 Tab；站点卡与凭据输入由 `/stats` 返回的注册表和 `credential.fields` 驱动；新增站点不得在 Vue 中增加站点 ID 分支。
- 复用 `frontend.v3/forumsignin/src/preview.css` 的 `--ptc-*` 变量、深浅色和玻璃主题观察器，不添加另一套样式/渲染路径。
- 构建：在 `frontend.v3/forumsignin/` 执行 `npm ci --ignore-scripts && npm run build`，直接输出到 `plugins.v3/forumsignin/dist/`；`distbak/` 保留迁移前备份。
- 离线测试：`PYTHONIOENCODING=utf-8 micromamba run -n base python -m pytest tests/v3/forumsignin`。
