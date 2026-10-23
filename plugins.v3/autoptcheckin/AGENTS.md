# PT 签到中心 V3

## 边界
- 站点由 `sites/native/` 原生声明、generic 声明与 integrations 组成；不接管 `plugins.v2` 入口，默认不激活自动调度。
- 站点语义（2026-10-23 用户裁决）：zhuque 的 fireGenshinCharacterMagic「释放技能」动作即其签到能力（signin_capable=True，按技能动作回执判定）；vclib 人工验证、52pt 内联滑块均走 CloakBrowser 页面动作签到。
- 站点规则（2026-10-24）：HDDolby 公告「API 访问不计有效登录；严禁 Cookies/伪造 UA 模拟登录，违者警告或封号」——hddolby 声明 `login_notice`，配置/数据卡显示 ⚠ 徽标（title 全文）提醒用户定期浏览器人工登录，登录轨不强行关闭（用户裁决）。同类站点规则按此先例加 notice 徽标。
- Registry 仅发现 `sites/native/`；generic 声明由 native 包提供，rousi/sunnypt 由 integrations 注册。旧适配器副本和旧执行桥已移除。
- hares（白兔）由被删副本转正为 generic 声明：`signin_capable=false` 仅登录；与旧基线的差异（name=白兔、url=club.hares.top）为明确接受的变更。
- 任何提交结果都必须尝试新页面回读；按钮文本和 UID 只能来自页面证据。
- `unconfirmed` 独立于 `failed`，提交后回读不可达、证据不足或身份冲突不得猜测成功/失败；签到前读维护/关闭用 `maintenance`，其他不可达用 `network_error`，未适配表单/参数、验证码未解决或提交前解析异常用 `protocol_pending`。模拟登录状态契约不变。

## 验证
- `PYTHONIOENCODING=utf-8 micromamba run -n base python -m pytest tests/v3/autoptcheckin`
- 不在离线测试中放置 Cookie、Token 或真实 URL 请求。

## UI 契约
以定稿 `D:/tmp/pt-signin-form-preview.html` 为视觉与交互依据；示例站点、数量、UID、日期、奖励和勾选值不作为生产数据或默认配置。

### 配置页
- 只设「设置 / 站点」两 Tab，默认显示「设置」；使用 Vue 响应式 model 与原生 Tab，不拆出调度或凭证 Tab。
- 「设置」按基础设置、执行调度、Browserless 分组：基础设置的「启用插件 / 发送通知」同行。
- 执行调度填写框按字段数量和可用宽度多列自适应（auto-fit，最小宽约 180px），不固定两列；时间窗口保持文本输入。凭据区同样自适应，窄屏自动降列。
- 仿真开关仅按站点逐项配置，不提供全局仿真服务地址或令牌。一次性操作不在配置页显示；「立即运行一次 / 清理本日缓存」位于数据页今日总览，与立即签到、只读核验并列；配置页底部保留保存操作。
- 「站点」依次呈现启用数量、可按名称筛选的多选站点清单、可移除的已选 chips、启用站点卡片；启用数量行末提供「编辑自定义站点」按钮；无启用项时显示空态。选择器使用带搜索框的多选下拉及可移除 chips；多选后「确认选择」一次性更新 enabled_sites 并插入平铺列表，下拉顶部「全选/全不选」仅切换当前筛选结果集合（无筛选为全部站点），不影响草稿中的其他项；取消不改变启用清单，保存配置前不持久化。已选 chips 回显在选择框内（/sites 加载后按 enabled_sites 映射）；打开时回显 pendingSites 草稿，勾选/移除即时更新草稿，关闭未确认则恢复已启用 chips；关闭态移除 chip 直接更新 enabled_sites。弹层使用原生 popover top layer 避免宿主裁切，按视口剩余空间上下翻转、水平约束，最大高度 min(400px,60vh) 并内部滚动；滚动/resize 重新定位。
- 「编辑自定义站点」打开 dialog 列表（站点名 / 地址 / 仿真 / 保存、删除），直接行内编辑，提供新增行；不提供启用勾选。名称必填、地址限 HTTP(S)；行内保存仅更新 custom_sites_data，新站不自动启用；删除同步清理 enabled_sites 与动作集合。关闭丢弃未保存编辑，保留已保存行。自定义站点与 MP 站点共用主选择器、来源固定「自定义站点」；仍需主表单保存才持久化。
- 窄屏（预览断点 640px）字段与站点数据卡改为单列；统计卡、证据字段改为两列，避免强制保留桌面同行布局。

### 配置站点卡片
- 收起态使用约 36px 的紧凑行：小号移除按钮 → 站点名 → 来源徽标 → 签到勾选框 → 模拟登录勾选框（支持时）→ 仿真（仅 site.emulate=true）→「展开配置/收起配置」按钮。整行不触发展开，仅显式按钮切换；全部展开/收起语义不变。动作勾选可直接交互，不触发详情折叠；仿真不由 CF 推断。详情默认收起；行内使用 flex align-items:center，站点名固定列宽，徽标紧随且垂直居中。
- 已启用列表为单一平铺紧凑行，不显示分组；提供独立名称筛选、全部展开/收起。「全部展开」打开所有已启用站点详情（不受筛选限制），「全部收起」关闭所有详情。列表最大高度 68vh 并内部滚动，桌面以一屏至少 15 行为验收。
- 徽标枚举：来源「MP 站点 / 插件适配 / 自定义站点」；能力「可签到」，支持模拟登录时才显示「模拟登录」徽标与选项；凭证方式 `cookie / api / password`，允许组合，API 可标注 JWT；CF 状态「CF 有盾 / CF 无盾 / CF 未检测」，未知不得当成无盾。
- 收起态即可勾选「签到」；支持模拟登录时才显示「模拟登录」勾选（同行），直接同步 sign_sites/login_sites，不改变 enabled_sites；勾选不触发详情展开，展开态显示来源、凭证方式、CF 状态、模拟登录能力的只读站点类型行，以及凭据、自定义地址/仿真等额外配置，不重复动作勾选或移除按钮。自定义站点同时展示地址与仿真状态；收起态站点名前的 × 经行内二次确认移出启用，同步 chips 与启用数量。
- 凭据区按站点所需字段生成：肉丝为「账号 / 密码」，SunnyPT 为「账号 / 密码」，列数按可用宽度自适应；纯 Cookie 示例站点不额外生成账号密码区。账号用普通文本，密码、JWT、令牌用 `type: password`。
- 仅在站点启用且至少勾选签到或模拟登录、并且该站有专属凭据字段时显示凭据区；取消两个动作即隐藏，不能因选择了站点就无条件显示凭据。

### Vue 模式与宿主契约
- `get_render_mode()` 返回 `("vue", "dist/assets")`；宿主无条件解包 get_form：`get_form()` 返回 `(None, defaults)`，`get_page()` 返回 None，不再生成 Vuetify JSON。
- Vite originjs ESM 联邦名为 `AutoPtCheckin`，入口 `remoteEntry.js` 暴露 `./Config` 与 `./Page`；共享宿主 Vue 3.5.13，不打包第二份 Vue 或 Vuetify。
- 宿主 Config 传入 `initial-config / api / plugin-id`；`save(model)` 事件由宿主 PUT `plugin/{id}` 保存。`close / switch / layout({maxWidth})` 事件由宿主处理。Page 接收 `api / plugin-id / show_switch`。
- API 相对插件 ID：GET/PUT `/config`、GET/PUT `/site_config`；GET `/stats`、`/history`、`/status`；POST `/run_once`、`/clean_today`、`/signin_by_domain?domain=...` 单站执行、`/verify_site?domain=...` 只读核验、`/login_by_domain?domain=...` 模拟登录；`/manual_signin` 与 `/notify_preview` 已删除；所有端点显式设置 `auth: bear`（默认 apikey 不适用于宿主前端）；配置与凭据只在宿主鉴权边界内读写，不进入统计/日志。
- `/site_config` 使用既有 flat keys（enabled_sites/sign_sites/login_sites/custom_sites_data 及专属凭据）；与完整 config 同源，get_data/save_data 保存站点子集。
- UI 执行按钮按站点启用状态、动作选择与能力门控；后端 unlock_all_sites 不自动修改 verified。
- 仿真由站点声明与 `site_browserless` 名单共同门控，无全局开关；M-Team 保活登录是独立的真实浏览器登录，不属于仿真签到。
- 在 `frontend/` 执行 `npm ci --ignore-scripts && npm run build`；同步提交 dist，node_modules 不入库。
- 用宿主页面核验 Tab、条件字段、选移站点、卡片折叠、凭据显隐、证据展开；离线测试不能代替渲染验收。

### 数据页
- 站点名优先采用适配器 match 命中的 MP 登记名，未匹配保留适配器名；/sites 和 /stats 使用相同映射。图标仅读取 SiteOper.get_icon_by_domain 的 data:image 缓存，不加载远程 URL；配置卡及数据卡显示图标，缺失/加载失败用首字母占位。关闭按钮用 ghost 描边，×/移除 chip 用 danger 描边。
- 今日总览显示下次调度时间、调度模式/间隔与时段，提供「立即签到 / 只读核验 / 立即运行 / 清理缓存」；下次调度时间格式 `YYYY/MM/DD HH:mm`（本地时区），间隔模式时段显示 `HH:00~HH:00`；其下统计区为「签到 · 今日」「登录 · 今日」两组并排同一行（窄屏 640px 以下纵向堆叠），每组 3 张统计卡按「成功 / 失败 / 未确认」统计当日有执行的站点（每轨最新记录聚合，success/signed/failed+auth_failed/unconfirmed），不再按今日执行计数；标题为「站点状态总览」。
- 站点小卡两行紧凑布局：第一行图标+站点名+站点名后方无文字「测试连接」图标按钮（原只读核验，ghost pico，title/aria-label=测试连接）+「签到」「登录」两枚徽标，徽标文字固定为签到/登录、颜色表状态（绿=成功、红=失败、橙=未确认、灰=未进行），仅站点不可达/维护中/协议待适配以状态文字入徽标（不可达/维护/待适配，沿用 off 色），消息全文放徽标 title；第二行「签到」「登录」pico 小按钮与第一行同名徽标的显隐只跟随站点配置开关（开启即显示，未开启完全不出现），按钮置灰才由执行能力（disabled/门控）决定；不展示结果文字行、UID、时间、凭证来源或奖励明细。总览保留只读核验入口；停用或不支持对应能力的站点禁用执行按钮。可见文案统一用「登录」，不再出现「模拟登录」。数据页底部不放图例。
- 卡片区筛选 chips 与站点徽标同款样式：签到（绿/红/橙=成功/失败/未确认）、登录（绿/红）、不可达、维护、待适配、停用/未尝试（均 off 色），再点选中态恢复全部；认证失败归失败，skipped 沿用停用色归停用；维护、网络及协议状态虽共用 off 中性色，筛选按状态值独立匹配，不按颜色混入停用。切换筛选重置为筛选后前 8 张，空匹配显示独立空态。
- 桌面三列等宽等高小卡，中屏两列、640px 以下单列；末张不跨列。默认前 8 张，failed/unconfirmed/auth_failed 优先且同优先级保持原顺序；其余用「展开其余 X 个站点」/「收起其余站点」切换，空态单独展示。
- 历史通过现有 page/size API 每页 100 条加载全部保留记录，按浏览器本地日期前端聚合；分组头为「YYYY-MM-DD · N 条记录」，默认仅当天展开，其余收起。列顺序为「时间 / 站点 / 状态 / 最近消息」四列；不提供证据展开行，失败与异常说明（403/503/维护等）由最近消息列承载；API 与存储不变。历史表容器 max-height:60vh、内部横纵滚动，证据展开行在同一容器内，不撑破宿主页面。
- 历史不展示回读按钮文本/UID/记录日期/记录状态等证据字段（回读证据仍按存储契约保留在 history.records，仅不在 UI 展开）。历史消息使用真实 item.message，奖励如有拼在消息末尾，不借回读按钮文本替代执行结论；历史结果时间按浏览器本地时间显示 YYYY/MM/DD HH:mm:ss，存储 ISO 不变。
- 不提供迁移预览区；不要把静态预览的演示按钮、示例快照提示或刷新恢复示例文案带入正式页面。

### 状态色映射
| 状态 | 预览 class | 背景色 | 文字色 |
| --- | --- | --- | --- |
| 成功（今日成功） | `success` | `#eaf5ed` | `#247337` |
| 已签 | `signed` | `#edf3f8` | `#476a82` |
| 失败 | `failure` | `#fef0ee` | `#b42318` |
| 未确认 | `unknown` | `#fff2e1` | `#a85400` |
| 停用 | `off` | `#eef0f3` | `#626b78` |
- 统计卡、结果徽标、历史状态和图例共用上表，不将未确认合并为失败；能力「可签到」沿用 success，CF 有盾沿用 unknown。
- 配置和数据视图都不绘制根 card 边框、圆角或阴影，外框交给宿主弹窗。
- 主题跟随宿主 `html.v-theme--dark` / `html.v-theme--light`（MutationObserver 实时监听）；无宿主主题 class 时回退 `prefers-color-scheme`。颜色变量集中定义于 `frontend/src/preview.css` 的 `--ptc-*` 清单，组件样式不得使用主题硬编码色。

### 结果枚举（3.21.0）
| 值 | 中文 | 产生条件 | 今日四卡归类 |
| --- | --- | --- | --- |
| success | 成功 | 提交后有确证 | success |
| already → signed（历史） | 已签 | 前读已有已签证据 | signed |
| failed | 失败 | 明确未签证据 | failed |
| auth_failed | 认证失败 | 缺凭据或认证页 | failed（仅 sign） |
| unconfirmed | 未确认 | 提交后证据不足或身份冲突；旧轨道/登录未知结果保留兼容 | unconfirmed（仅 sign） |
| maintenance | 维护中/已关闭 | 签到前读及 native 核验 仅响应体前 2 KiB（UTF-8）含维护/关闭文案（英文不区分大小写）；HTTP 状态码一律归站点不可达（2026-10-23 用户裁决）；提交后回读与模拟登录语义不变 | 不计入 |
| network_error | 站点不可达 | 签到前读空响应、排除维护状态后的非认证 HTTP 错误或请求异常（含 native 核验） | 不计入 |
| protocol_pending | 协议待适配 | 签到无唯一表单、参数/验证码未解决或提交前解析异常 | 不计入 |
| skipped | 已跳过 | 门控、未选动作或锁忙 | 不计入 |
| cancelled | 已取消 | 执行取消 | 不计入 |
| login_ok | 登录成功 | 页面可达的模拟登录/自定义核验 | 不计入 |
| disabled（展示值） | 停用 | 未启用的站点卡 | 不计入 |

- 保留既有存储值，不批量重写历史 unconfirmed；新增状态只影响新的对应产生点。GetSignin 继承 Nexus 流程，无需复制分类逻辑；API 动作回执及提交后无条件回读不变。
- 憨憨的 register-now-info 声明必须使用 XPath class-token 匹配，不能把 CSS 选择器交给 lxml.xpath；attendance 前读/动作/回读使用相同 URL，测试必须按调用顺序提供响应。
- U2 按每日 9 点重置：9 点前 read_before 的 ALREADY 一律降级 unconfirmed（昨日状态不作为今日证据，修复 01:00 误判已签）；9 点后表单提交「一切随缘」随机选项。

### 徽标色映射
- 徽标用 `--ptc-badge-*` 半透明背景和同系文字，深浅主题各一套；配置下拉、chips、收起行与数据页使用同一来源映射。
| 类别 | 配色 |
| --- | --- |
| MP 站点 / 插件适配 / 自定义站点 | 蓝 / 紫 / 橙 |
| cookie / api(JWT) / password | 青 teal / 紫红 / 棕 |
| 可签到 / 模拟登录 | success 绿 / signed 蓝 |
| CF 有盾 / CF 无盾 / 未检测 | unknown 橙 / 灰绿 / 灰 |

### 禁止事项
- 不添加解释性长文案；只保留必要的短字段提示、状态与操作标签。
- 不加入蜂巢、药丸等已由论坛签到插件承接的站点；yzyy 为本插件 V2 原有成员，保留迁移范围。

## 原生站点契约
- 原生站点实现 `SiteModule`，通过类属性声明 `id/name/url/credential/login_capable/cf/record_spec`，仅实现 `signin(ctx)`；`sites/native/` 逐模块发现，导入失败隔离为 `skipped`，不阻断其他站点。
- `RecordSpec` 默认 page_message，每个 XPath 必须选中唯一消息元素；多选择器遇空值、歧义或无效表达式继续扫描，首个非空文本停止，再按 status_map 声明顺序映射 signed/unsigned（无匹配仍 unconfirmed，不继续找成功词）。NexusSignin 的合成占位声明默认回退消息链，站点可关闭 use_default_message；response_json 仍按 response_field 的精确类型和值匹配。signed_marker 可确认安全前读 already 和提交后新页 success；UID/日期仅展示，不以缺失字段或整页文本补造结论。校准记录见 sites/native/AGENTS.md。
- `NexusSignin` 提供 attendance 页面 GET、唯一 POST 表单发现、验证码钩子和提交后的无条件新页面 GET 回读；提交响应不能替代回读，超时或异常不得自动重试。
- `SignContext` 由执行边界注入已认证的 HTTP client、站点锁、取消事件及可选 `page/ocr`；`SiteModule` 不查凭据、不创建或关闭资源，资源生命周期由 `core.native`/runner 管理。
- native 站点签到/只读核验走原生模块，登录使用独立登录路径；custom 与 integrations 各走专属执行器。unlock_all_sites 默认 false，仅影响 native verified/hook 门控；不绕过启用、动作选择、凭据与站点锁。DarkLand/DigitalCore 签到不适用；M-Team 不提供签到。signin_applicable 是 registry 展示适用性，后端仍执行对应能力检查。

### 仿真通道（CloakBrowser）
- 仿真名单（`site_browserless`）：ourbits、audiences、hdkyl、mua_xloli、pt_0ff、vclib、yema、52pt、piggo、kamept；生效条件为站点声明且 ID 在名单中，无全局开关。native 与 custom 仿真使用 CloakBrowser，结果 `transport=cloak`。一般模拟登录不走仿真；M-Team 保活登录是专门的真实浏览器账密登录例外，不执行签到。
- 复用 Nexus 前读→动作→无条件回读，结论一律来自回读证据。Cookie 双向同步仅限本次执行；不得重放动作。页面动作后的落点页 stash 即为回读证据；站点每次进入可能发放新的滑块门页，不能用二次 GET 替代动作回读。
- **页面动作站（`cloak_steps`）**：pt_0ff=[slider,sign_button]（滑块有时不出现，出现才拖动）、52pt=[slider,sign_button]、yema=[human_verify,sign_button]、vclib=[human_verify,sign_button]（Cloudflare Turnstile，headful CloakBrowser 等待 token 最多 60 秒）、piggo/kamept=[sign_button]。`run_page_action` 步骤缺失不阻断（absent 继续下一步），点击后等 5s，最终以回读消息链判定成功/已签/未确认，不猜测按钮结果。 pt_0ff 拖到底松开后门页先显示「验证通过」，约 8 秒自动跳转真实签到页；回读出现「签到已得N」才是成功证据，默认消息链已覆盖。slider 拖动后轮询等待标题/正文离开「滑动认证/拖动滑块验证」门页（每 1.5s，最多 25s），离开后再稳定等待 2s，超时如实保留未确认。
- **轮内共享会话**：一轮 ≥2 个仿真站到期时共用一个 CloakSession（`_runner.shared_cloak`），按站注入 Cookie，不重复开关浏览器；会话生命周期归轮次，异常降级为逐站独立会话。
- **手动门控旁路**：`signin_by_domain`/`login_by_domain`（trigger=manual）绕过 native_unverified/hook_not_implemented 及 legacy 未启用门控（手动单站即显式人工授权）；调度轮仍受门控。darkland/digitalcore（signin_not_applicable）与 login_not_supported 不受旁路影响。
- 默认 solve 与页面稳定等待各 15 秒；单次导航上限 30 秒。滑块拖动为 humanize 步进鼠标（24 步），真实过盾效果需生产验证。

## 阶段2数据契约
- `core/registry.py` 使用 `pkgutil` 遍历 `sites/native/`，逐模块导入并收集 `SiteModule` 子类；导入异常只进入 `skipped` 日志，不阻断其他站点。注册项包含 `id/name/login_capable/credential/cf`，并追加 `rousi/sunnypt` 两个 integrations 注册项；`/sites` 返回 `sources.adapters` 与 `sources.integrations` 计数。
- native 站点凭证默认 `kind=cookie`、来源 `cookiecloud/managed_site/local_cookie`；集成凭证从 integrations 的 `CredentialSpec` 获取。注册表只缓存元数据，不实例化适配器或请求站点。模拟登录表示访问页面，不要求专属登录动作；native 站点默认 login_capable=true（含 HDSky），仅显式 false 的特殊站关闭。
- `core/history.py` 使用 `get_data/save_data` 的 key `history.records` 保存 `{time,site,action,status,message,reward,evidence}`；`list(page,size)` 按时间倒序分页，默认每页 20、上限 100；追加和读取均清理超过 90 天的记录。历史只保存回读证据，不保存凭据。
- 轨道状态表（3.35.0）：`save_data("track.state")` 持久化每站×轨道（sign/login）的规范化状态，`core/state_store.py` 唯一实现。四值：success/failed/pending/disabled；映射唯一入口 `normalize(track,status,reason)`——sign 成功族={success,signed}（already 已在 `_record_result` 入口归一为 signed，状态表不出现）、login 成功={login_ok}；门控类 skip（reason ∈ 登记清单）→ disabled(reason)；其余失败族与无记录 → failed/pending；maintenance/network_error/protocol_pending 与未知/空状态 → pending；锁忙 skipped 与 cancelled 只写历史不改表。写入点：`_record_result`（read_only 结果跳过）；`init_plugin`/每轮 `_execute_all` 前全量重算 pending/disabled（`_recompute_track_states`，success/failed 结论保留）；日切（state.time 非今日的 success → pending）；清理缓存联动 `clear_transient`（非禁用→pending）。
- 双队列执行（3.35.0）：`_execute_all` 先签到后登录串行；队列=启用∧勾选∧状态∈{failed,pending}；单站结果 failed 当场重试 ≤ `retry_count`；收尾把 failed/pending 清单写日志留给下一轮。`skip_signed_today`/`_signed_today`/`_site_tracks`/`_counts`/`_bucket`/`_site_results` 退役：`/stats` 的站点行与三卡统计直接读状态表（字段 sign_state/sign_status/sign_time/sign_message、login_*；latest 按 success/failed/unconfirmed 当日计数）。
- `/stats` 返回 `latest:{sign:{success,failed,unconfirmed}, login:{...}}` 与 `next_schedule`；`/history` 返回 `{total,items}`。签到 action 的 auth_failed 计入失败卡；maintenance/network_error/protocol_pending 仅保留历史及站点卡，不计入四张统计卡，也不增统计键，避免把未执行当签到失败；保留原始历史状态；空态仅表示实际存储为空。
- 配置页以 `/sites` 为主数据源；仅在 registry 整包导入失败时使用 `frontend/src/sites.json` 作为静态兜底，不把静态清单当生产主数据源。

## 执行边界
- 账号锁忙立即 skipped；站点锁在身份解析前获取，避免首次绑定与后续执行交错。Cookie 按 cookiecloud → managed_site → local_cookie 选择，并按请求 host 与 Cookie domain 边界匹配。
- 无 Cookie 返回 auth_failed，不请求签到页面。原生轨道 UID/日期仅展示；提交状态依声明消息或 signed_marker 确认，证据不足为 unconfirmed。每次尝试独立写 history。
- 原生签到与只读核验走 `run_native`；custom 走 `run_custom`；rousi/sunnypt 走 integrations；M-Team 登录走独立 CloakBrowser。其它无执行实现的旧站点返回 `skipped(site_removed)`。

## 组件与宿主玻璃主题
- Config/Page 共用 preview.css 的 .btn/.input/.switch/.chip/table；常规控件统一 36px 最小高度、6px 圆角、同一焦点框，紧凑列表 chip 是明确的小号变体。
- 按钮语义：保存/立即签到用主色蓝；移出启用与移除 chip 用 --ptc-danger 红色描边；查看数据/只读核验用 ghost；确认类用 --ptc-confirm 绿；禁用用灰并降低透明度。开关 on=主色、off=灰。
- 消费宿主 RGB 变量 --v-theme-surface / surface-variant / on-surface / primary / on-primary，以及 --v-border-color / --v-border-opacity；通过 --ptc-surface*、--ptc-text*、--ptc-line* 和 --ptc-blue 收口。
- 从 .v-application 的 v-theme--glass 与 surface RGB 明度识别玻璃深浅色；玻璃主题面板/输入/表格使用半透明底，局部卡片与弹层 blur(12px)，不绘制实心根面板。五态沿用 --ptc-*，深浅玻璃使用各自高覆盖率半透明底确保文字对比。
- 筛选下拉只保留弹层单框；弹层内搜索框用底线而非再套一圈描边。

## S6 迁移契约
- 迁移仅走运维 API：先 GET `/migrate/preview`，审核后 POST `/migrate/execute`，JSON body 必须含 `confirm: true`，`overwrite_conflicts` 默认 false；均为 `auth: bear`，不加 UI、不启动调度或站点请求。
- 来源配置走同宿主 GET `/api/v1/plugin/{id}`（内部 loopback + 宿主 API key），先查已安装清单和版本；AutoPtCheckin 的本地版本 >=3 标 `source_missing(reason=self_v3)`，不得迁移自己。未安装标 source_missing；鉴权/网络/版本异常标 source_error，不伪装成缺失。
- 映射：AutoPtCheckin 的 enabled/cron/cron_mode/interval_hours/begin_hour/end_hour/notify/queue_cnt 同名写入；sign_sites/login_sites 按 registry ID 或域名匹配，合并生成 enabled_sites，未识别项列 unmapped。custom_site_urls（名称|URL|Y/N）与 custom_sites_data 合并到自定义站点源，旧数字 ID 转稳定 custom ID，render 转 emulate；不复制 Cookie 或一次性动作。
- RousiCheckin 的 username/password → rousi_username/rousi_password；SunnyPTSignin 的 username/password/token → sunnypt_username/sunnypt_password/sunnypt_token，空 token 不填。预览不回显专属凭据值。
- 配置端点不含 V2 get_data：Rousi history、Sunny records/token_cache 在就绪来源预览中标 data_unavailable；本轮不写 history.records 或站点附属数据。生产切换阶段由运维另行从宿主数据文件读取迁移，不假装已完成。
- 已有非空目标值不同即 conflict（false、0 也算已有值）；默认跳过，只有 overwrite_conflicts=true 才覆盖。自定义源冲突跳过时，同时跳过引用未导入 custom ID 的动作集合，返回 skipped_dependencies。
- 预览不落盘；执行重新读取来源并比较预览及当前配置，变化或重载后须重新预览。执行前停旧插件调度并暂停其他配置保存；只在同一宿主单进程执行，不能跨进程并发迁移。
- 写入前 save_data `migration.v2.backup` 保存完整 config、site_config 和时间，再写 `migration.v2.state=applying`；成功标 completed，重复执行返回 already_executed。中途异常保留快照和 applying，拒绝自动重试，交运维处理；空迁移不封存执行标记。
- 回滚不是公开 API：运维在维护窗口读取备份，将完整 config 用 update_config 恢复，将 site_config 用 save_data 恢复，重新 init_plugin；核对恢复成功后清理 migration.v2.state，再重新预览。快照包含原凭据，只保留于宿主插件数据，不输出日志；回滚前另备份迁移后新配置，避免覆盖后续人工修改。

## S7 调度契约
- `scheduler_enabled` 默认 false，是生产切换门控，不随 S6 的 enabled 迁移；false 时包括 onlyonce 在内均不注册。常规服务另需 enabled=true；未激活时 `/stats.next_schedule=null`，`schedule_status` 解释阶段限制。
- cron 注册 `AutoSignIn / PT 签到中心`；interval 注册 `AutoSignIn.{index} / PT 签到中心 HH:mm`。服务由宿主拥有，不创建插件后台调度器；stop_service 经 SDK remove_plugin_job 清理，配置 API 保存后 update_plugin_job 重建，宿主保存走宿主重建流程。
- interval 对齐 V2 `__generate_schedule_crons` + TimerUtils.random_scheduler：次数 max(1, int((end-begin)/interval))，从 begin:00 累加 [max(30,interval*30),interval*60] 随机分钟，最小 interval=0.5，0<=begin<end<=23。schedule_crons/schedule_signature 用 get_data/save_data 保存，signature 相同复用，变化重排；不采用重载重新随机，以免调度漂移。
- 数据页「立即运行一次」设置 onlyonce 并触发一次性操作；onlyonce 优先只返回 `AutoSignIn.once` DateTrigger（即使 scheduler_enabled=false），且 `_scheduled_once` 消费后直接全量执行，不受 scheduler_enabled/常规运行门控限制；回调先持久化 onlyonce=false 再执行，重载不重复消费。进程在消费写盘后崩溃不自动重试，避免重复签到；失败由人工核验后再决定。
- 调度与立即运行共用全量 runner 路径、站点选择与账号锁，history 增加 trigger=scheduler/manual；调度不绕过站点门控。next_schedule 从已声明的真实 Trigger 计算，不从展示配置猜测。
- 生产激活衔接 S6：备份并停旧插件任务 → preview/execute 配置迁移 → 核对站点 Cookie/UA/UID 和只读回读 → 用户授权手动验证 → 显式保存 scheduler_enabled=true → 核对宿主服务及 next_schedule。回退先关闭门控并确认旧服务移除，再恢复旧插件，禁止两边同时运行。

## 模拟登录契约
- native 登录直接调用 SiteModule.parse_login（含 DarkLand/DigitalCore），不要求 verified/hook_implemented，不执行 signin；页面 GET 仅访问首页，不访问 attendance 或保活动作。站点 registry 不发现旧适配器。
- 非 native 集成之外的已配置域名登录使用通用页面解析；已有 registry ID 按 matcher 找宿主条目，未登记域名必须已在 enabled_sites/login_sites 配置，并由宿主或 custom 条目提供同 host 地址。不得直接请求任意 API 入参 URL。27域排除清单仅表示没有 native 签到声明，不再表示依赖登录旧桥。
- GET 站点页面后无条件再次 GET 回读，无签到提交、无业务日期；页面可达即 login_ok，UID 尽力解析，缺失不阻断，显式冲突为 unconfirmed。重定向到登录页为 auth_failed，不可达为 unconfirmed。
- 批量执行勾签到的站点走签到链，仅勾模拟登录的站点走登录链；两项都未勾保留 skipped 记录。单站登录 API 为 POST /login_by_domain（auth: bear），复用站点锁和身份绑定。
- history 保存 action=sign/login；旧记录无 action 视为 sign。登录结果仅入历史，不覆盖签到小卡或四态统计；历史 login_ok 显示「登录成功」。
- rousi/sunnypt 使用专属集成协议并在启用与动作选择后可执行。PeerGo 登录先 GET `/api/v1/session`，Cookie 无效时使用账密 POST 刷新；签到读取 session/attendance，已有 claimed_today 不重复提交，提交带 Origin、Referer、X-CSRF-Token 与唯一 Idempotency-Key。SunnyPT 优先配置 JWT，否则账密换 token；Bearer 签到按 code=0/400001/400000 分类，token 失效时重新登录并最多重试一次。M-Team 仍仅由独立 CloakBrowser 真实登录实现，不经通用 password 集成协议。

## 批次 3 完成（3.15.0，2026-10-22）
- D1 下沉：20 专属模块（CAPTCHA 12/GET 6/POST 2）并入 generic_sites.json 行为字段（captcha/action_get/safe_read_path/referer/form_data/form_path/response_json/action_path/use_default_message/signin_capable；typed status_map pairs），native 守恒 108。
- D3：CookieCloud 为独立数据源，候选链第一环（本地文件优先/远端单次 20s/严格域边界/CF-only 子集拒绝/静默降级），不回写。
- D4：custom 站标准 NexusPHP 签到+emulate 混合路径（未启用 Browserless 不降级）；verify 保持 login_ok。
- D5：模拟登录全原生（native parse_login/custom/已配置域名通用双 GET），已移除旧桥回退。
- D6：凭证枚举 api→api_key（credentials/integrations/registry/前端徽标/测试）。
- D7：移除旧适配器副本与旧桥代码。
- D9：Luna 审查 8 项 6 过，P2 CF-only 过滤补全（_CF_ONLY_COOKIES）、P3 文档过期描述修正。
- 52pt 已滑块化并接入页面动作签到，yema 恢复 signin_capable=True；答题类 chdbits/tjupt 仅模拟登录。

## 批次 3 计划（已实施，见上；保留原文备查）
- 统一凭证枚举 api → api_key，连同配置、registry、UI 与测试同步迁移；当前版本不改名。
- cookiecloud 原生候选已于 3.12.0 接入；原生模拟登录同样按 cookiecloud → managed_site → local_cookie 选择；custom 保持本条目 Cookie。本轮仅离线 mock 验证，真实服务器与站点验证仍需授权。

## Custom 签到契约（3.13.0）
- custom_sites_data 的已启用且勾选签到条目（含数字 ID）直接使用 NexusSignin 默认 attendance 表单流程，不要求 native verified；unlock_all_sites 不能绕过启用与动作选择。registry 将 custom 注册为可执行站点；signin_applicable=True，仿真能力由站点声明与 `site_browserless` 名单决定。
- custom Cookie 使用本条目的 local_cookie；GET attendance → 唯一同源 POST 表单 → 单次提交 → 无条件新页回读默认消息链。前读已签为 already，新页确证为 success，缺证据为 unconfirmed；history action=sign。无唯一表单返回 protocol_pending，不猜非 NexusPHP 协议；已识别验证码不自动作答。
- emulate=true 且自定义站点 ID 位于 `site_browserless` 时启用 CloakBrowser 前读/回读 + HTTP 提交混合路径（`metadata.transport=cloak`），执行级 Cookie 双向同步；连接/页面错误不降级 HTTP-only、不重试动作。
- verify 保留只读 login_ok 语义，不视为签到；custom 模拟登录复用同一可达性语义并无条件二次 GET 回读，仍检查 enabled/login 选择；模拟登录不走仿真。真实站点未实测，另行授权验证；设计取舍见 .agents/notes/implemented/feature/2026-10-22-custom-attendance.md。

### 3.36.0 后端数据与端点契约
- `/manual_signin` 与 `/notify_preview` 已移除；保留 `/verify_site` 只读核验入口及 `/run_once`。数据页按钮、错误消息行、统计合并卡、历史按天、配置 switch 与 per-site 仿真的渲染由前端契约负责；接口不另增前端字段。
- `/stats.sites[]` 提供 `cf`（未知为 `unknown`）、`emulate`（`site_browserless` 名单或自定义站点 emulate）及声明值 `emulate`。
- 集成凭据分类：rousi/sunnypt 为 password（账密登录；SunnyPT JWT 是登录产物）；mteam 凭据 password（账密登录；登录态 Cookie/storage_state 内置存储，失效自动重新账密登录），CloakBrowser 保活（`login_capable=true`）。
