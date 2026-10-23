# 论坛签到 V3

## 边界与宿主契约
- V3 插件只用 `app.sdk.*` 宿主接口；所有自有 API 显式 `auth: bear`、使用相对路径和 `success/message/data` envelope。
- Vue 联邦入口 `remoteEntry.js` 暴露 `./Config` 与 `./Page`，共享宿主 Vue；配置由宿主 `save(model)` 保存。
- 站点凭据只经鉴权配置 API 读写；不得进入统计、历史或日志。历史保留 90 天，清运行缓存不得清历史。
- 药丸和 SSDForum 每次提交后无条件重新 GET 页面；身份、按钮文本、本人行 UID/日期/明确状态缺一即 `unconfirmed`。只读核验不得 POST。
- 蜂巢 API 提交不自动重试可能已落地的请求；提交后仍 GET status。API 与页面证据保持区分。
- 离线测试只使用合成数据，不代表真实 DOM 或站点验证；不得在测试或发布验证中触发真实签到。

## 新增论坛站点
1. 在 `integrations/` 添加模块，声明 `SITE`（唯一 `id`、`name`、`domain`、能力、`fields`）并导出 `ADAPTER`。
2. `ADAPTER` 提供 `credential_spec`、`base`、页面站点提供 `fetch_page`/`submit`/`verifier`；站点凭据字段需使用 flat config key，Cookie/Token 字段标为 `type: password`。
3. 在 `verifiers/` 实现该站的身份、提交前/后状态和奖励证据解析。页面型站点优先复用 `core/runner.py`：身份绑定、保守预检、提交后无条件回读由核心统一控制。
4. 只在确有不同认证协议时加专属 adapter；Cookie 型 Discuz 页面实现应复用通用页面签到协议，不能把站点判定分支写入核心 runner。
5. 给 adapter/verifier 添加无真实凭据的离线合成测试；为 `SITE.fields` 补 UI/API 契约断言。确认 registry 自动发现后再构建 `frontend`。

## 前端与验证
- 配置页为单页滚动布局（基础设置 → 执行调度 → 论坛站点区），站点少不拆 Tab；站点卡与凭据输入由 `/stats` 返回的注册表和 `credential.fields` 驱动；新增站点不得在 Vue 中增加站点 ID 分支。
- 复用 `frontend/src/preview.css` 的 `--ptc-*` 变量、深浅色和玻璃主题观察器，不添加另一套样式/渲染路径。
- 构建：`cd plugins.v3/forumsignin/frontend && npm run build`。
- 离线测试：`PYTHONIOENCODING=utf-8 micromamba run -n base python -m pytest tests/v3/forumsignin`。
