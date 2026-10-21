# 论坛签到 V3

## 边界
- 本轮只交付 F1 后端骨架与 F2 协议；Vue frontend/dist 在 F3 交付前不得安装或发布为可用 UI。
- 仅蜂巢、药丸、SSDForum；不引入 PT 站点、CookieCloud、账密续期、消息中心或 PT 快照推送。
- 不提供签到定时任务；唯一服务 ForumSigninInfoUpdate 是只读蜂巢信息同步。
- 运行 `PYTHONIOENCODING=utf-8 micromamba run -n base python -m pytest tests/v3/forumsignin`；夹具是合成数据，不代表真实页面验证。

## Vue 模式与宿主契约（沿用 PT 签到中心）
- `get_render_mode()` 返回 `("vue", "dist/assets")`；宿主无条件解包 `get_form()`，返回 `(None, defaults)`；`get_page()` 返回 None。
- F3 使用 Vite originjs ESM 联邦，名为 `ForumSignin`，入口 `remoteEntry.js` 暴露 `./Config` 与 `./Page`；共享宿主 Vue 3.5.13，不打包第二份 Vue/Vuetify。
- Config 接收 `initial-config / api / plugin-id`，通过 `save(model)` 由宿主 PUT `plugin/{id}` 保存；`close / switch / layout({maxWidth})` 交由宿主处理。Page 接收 `api / plugin-id / show_switch`。
- 所有自有 API 显式 `auth: bear`；绑定实例方法，`methods` 为复数。配置凭据只在鉴权配置端点读写，不进入统计、历史或日志。
- 配置与 site_config 使用同一 flat model；本站点注册表为三站静态插件适配，模拟登录能力为 false。
- F3 复用「设置 / 站点」两 Tab、紧凑站点卡、五态颜色与宿主玻璃主题规范；差异是无签到调度/Browserless/迁移 UI，保留蜂巢同步设置与手动更新。
- Cookie/API Key 使用 password 控件；根容器不绘制额外卡片边框，沿用宿主主题变量。前端验收不能用离线测试替代。

## F3 前端差异
- `Config.vue` 仅使用「设置 / 站点」两 Tab；三站以插件适配徽标和紧凑行呈现，详情必须通过显式「展开配置」按钮打开，凭据字段按 `CredentialSpec` 显示。
- `Page.vue` 展示四项统计、三列站点小卡、五态筛选、按浏览器本地日期分组的历史证据，以及独立蜂巢个人信息卡；图标缺失使用首字母占位。
- 蜂巢同步信息属于独立信息区，不并入签到统计；本插件无批量迁移语义。

## 协议与证据
- 蜂巢使用专用 Bearer API `/api/integrations/moviepilot/v1/`：POST check-in，GET me/status。沿用持久化 `fengchao_instance_id`，不在签到前调用 me，避免既有实例绑定冲突。
- 本轮任务明确允许蜂巢 API 响应为证据；仍在提交后无条件 GET status。API 证据 source=api，不伪造按钮、UID 或业务日期。空响应不是成功；不重试可能已落地的提交。
- 药丸首页解析 userId/csrfToken，Cookie + x-csrf-token POST `/api/checkin`；不保留旧自动登录或 remember 续期流程。
- SSDForum GET `/dsu_paulsign-sign.html?mobile=no`，解析本人空间 UID/formhash，POST Discuz dsu_paulsign 表单；本地签到文本满足 6–50 字，不请求一言。
- 药丸/SSDForum 每次提交（含异常）后重新 GET 页面；本人身份、按钮文本、本人行 UID/日期/明确状态缺一即 unconfirmed。只在本人当日未签到证据完整时提交；只读核验绝不 POST。
- SSDForum “已经签到或者时间未开始”不算已签；大洋及累计天数只能读取本人记录，不加一、不从余额推算奖励。
- 当前 DOM 选择器未经生产采样确认；未知结构禁止猜测成功。真实接管须用户授权后只读核验，必要时补脱敏夹具。
- 缺凭证标 auth_failed（尚未提交）；多宿主同域候选须显式 managed_site_id；UID 绑定冲突停止，不自动切号。
- history.records 保留 90 天，already 映射 signed；reward 保存完整 RewardSummary，证据保留 source 以区分 API 与页面。

## 蜂巢同步
- 同步仅 GET me/status，与签到共用站点锁；缓存 fengchao_user_info、fengchao_user_info_updated_at 与独立 fengchao_sync_status。
- me 失败可使用既有身份缓存；status 失败不覆盖上次用户信息或成功更新时间。零积分/零连签不当作缺值。
- 未读数只并入用户信息，不创建消息队列、去重水位或消息中心；同步不写签到历史、不改变签到统计。
- enabled 与 timed_update_enabled 同时开启才声明同步 cron；stop_service 清理宿主服务。不在 init 直接请求站点。
- notify 字段为后续统一通知层保留，本轮不发送通知。F3 接入数据展示时同时核对通知交付范围。
