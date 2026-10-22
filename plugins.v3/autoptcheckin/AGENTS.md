# PT 签到中心 V3

## 边界
- 默认仅 HDSky（hdsky）和海棠（haitang）开放手动试点；显式 unlock_all_sites 的执行边界见原生站点契约；不接管 `plugins.v2` 入口，默认不激活自动调度。
- 站点采用双轨：`sites/` 的46份 V2 站点副本已标 deprecated，保留用于 registry 元数据发现与未迁移域名参照；`sites/native/` 是原生执行实现。旧桥实际仅支持 hdsky/haitang 的 pilot 回退；生产切换前不删除副本或 `core/pilot.py`。
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
- 执行调度填写框按字段数量和可用宽度多列自适应（auto-fit，最小宽约 180px），不固定两列；时间窗口保持文本输入。凭据区与 Browserless 地址/令牌同样自适应，窄屏自动降列。
- Browserless：标题「Browserless（可选）」之后放无可见文字的开关（保留 aria-label="启用 Browserless"），再放地址/令牌自适应填写框，不重复显示开关标签。一次性操作不在配置页显示；「立即运行一次 / 清理本日缓存」位于数据页今日总览，与立即签到、只读核验并列；配置页底部保留保存操作。
- 「站点」依次呈现启用数量、可按名称筛选的多选站点清单、可移除的已选 chips、启用站点卡片；启用数量行末提供「编辑自定义站点」按钮；无启用项时显示空态。选择器使用带搜索框的多选下拉及可移除 chips；多选后「确认选择」一次性更新 enabled_sites 并插入平铺列表，下拉顶部「全选/全不选」仅切换当前筛选结果集合（无筛选为全部站点），不影响草稿中的其他项；取消不改变启用清单，保存配置前不持久化。已选 chips 回显在选择框内（/sites 加载后按 enabled_sites 映射）；打开时回显 pendingSites 草稿，勾选/移除即时更新草稿，关闭未确认则恢复已启用 chips；关闭态移除 chip 直接更新 enabled_sites。弹层使用原生 popover top layer 避免宿主裁切，按视口剩余空间上下翻转、水平约束，最大高度 min(400px,60vh) 并内部滚动；滚动/resize 重新定位。
- 「编辑自定义站点」打开 dialog 列表（站点名 / 地址 / 仿真 / 保存、删除），直接行内编辑，提供新增行；不提供启用勾选。名称必填、地址限 HTTP(S)；行内保存仅更新 custom_sites_data，新站不自动启用；删除同步清理 enabled_sites 与动作集合。关闭丢弃未保存编辑，保留已保存行。自定义站点与 MP 站点共用主选择器、来源固定「自定义站点」；仍需主表单保存才持久化。
- 窄屏（预览断点 640px）字段与站点数据卡改为单列；统计卡、证据字段改为两列，避免强制保留桌面同行布局。

### 配置站点卡片
- 收起态使用约 36px 的紧凑行：小号移除按钮 → 站点名 → 来源徽标 → 签到勾选框 → 模拟登录勾选框（支持时）→ Browserless（仅 site.emulate=true）→「展开配置/收起配置」按钮。整行不触发展开，仅显式按钮切换；全部展开/收起语义不变。动作勾选可直接交互，不触发详情折叠；Browserless 不由 CF 或全局开关推断。详情默认收起；行内使用 flex align-items:center，站点名固定列宽，徽标紧随且垂直居中。
- 已启用列表为单一平铺紧凑行，不显示分组；提供独立名称筛选、全部展开/收起。「全部展开」打开所有已启用站点详情（不受筛选限制），「全部收起」关闭所有详情。列表最大高度 68vh 并内部滚动，桌面以一屏至少 15 行为验收。
- 徽标枚举：来源「MP 站点 / 插件适配 / 自定义站点」；能力「可签到」，支持模拟登录时才显示「模拟登录」徽标与选项；凭证方式 `cookie / api / password`，允许组合，API 可标注 JWT；CF 状态「CF 有盾 / CF 无盾 / CF 未检测」，未知不得当成无盾。
- 收起态即可勾选「签到」；支持模拟登录时才显示「模拟登录」勾选（同行），直接同步 sign_sites/login_sites，不改变 enabled_sites；勾选不触发详情展开，展开态显示来源、凭证方式、CF 状态、模拟登录能力的只读站点类型行，以及凭据、自定义地址/仿真等额外配置，不重复动作勾选或移除按钮。自定义站点同时展示地址与仿真状态；收起态站点名前的 × 经行内二次确认移出启用，同步 chips 与启用数量。
- 凭据区按站点所需字段生成：肉丝为「账号 / 密码」，SunnyPT 为「账号 / 密码 / JWT（可选）」，列数按可用宽度自适应；纯 Cookie 示例站点不额外生成账号密码区。账号用普通文本，密码、JWT、令牌用 `type: password`。
- 仅在站点启用且至少勾选签到或模拟登录、并且该站有专属凭据字段时显示凭据区；取消两个动作即隐藏，不能因选择了站点就无条件显示凭据。

### Vue 模式与宿主契约
- `get_render_mode()` 返回 `("vue", "dist/assets")`；宿主无条件解包 get_form：`get_form()` 返回 `(None, defaults)`，`get_page()` 返回 None，不再生成 Vuetify JSON。
- Vite originjs ESM 联邦名为 `AutoPtCheckin`，入口 `remoteEntry.js` 暴露 `./Config` 与 `./Page`；共享宿主 Vue 3.5.13，不打包第二份 Vue 或 Vuetify。
- 宿主 Config 传入 `initial-config / api / plugin-id`；`save(model)` 事件由宿主 PUT `plugin/{id}` 保存。`close / switch / layout({maxWidth})` 事件由宿主处理。Page 接收 `api / plugin-id / show_switch`。
- API 相对插件 ID：GET/PUT `/config`、GET/PUT `/site_config`；GET `/stats`、`/history`、`/status`；POST `/run_once`、`/clean_today`、`/signin_by_domain?domain=...` 单站执行、`/verify_site?domain=...` 只读回读、`/login_by_domain?domain=...` 模拟登录、`/manual_signin` 按 sign_sites/login_sites 分流已启用站点。所有端点显式设置 `auth: bear`（默认 apikey 不适用于宿主前端）；配置与凭据只在宿主鉴权边界内读写，不进入统计/日志。
- `/site_config` 使用既有 flat keys（enabled_sites/sign_sites/login_sites/custom_sites_data 及专属凭据）；与完整 config 同源，get_data/save_data 保存站点子集。
- UI 执行按钮仍按 registry.pilot_enabled 门控；后端 unlock_all_sites 是独立校准开关，不会自动修改 UI 门控或 verified。
- Browserless 为独立 `enabled / url / token` 三字段；只有 enabled 为真才参与执行，不能由地址或令牌推断启用。
- 在 `frontend/` 执行 `npm ci --ignore-scripts && npm run build`；同步提交 dist，node_modules 不入库。
- 用宿主页面核验 Tab、条件字段、选移站点、卡片折叠、凭据显隐、证据展开；离线测试不能代替渲染验收。

### 数据页
- 站点名优先采用适配器 match 命中的 MP 登记名，未匹配保留适配器名；/sites 和 /stats 使用相同映射。图标仅读取 SiteOper.get_icon_by_domain 的 data:image 缓存，不加载远程 URL；配置卡及数据卡显示图标，缺失/加载失败用首字母占位。关闭按钮用 ghost 描边，×/移除 chip 用 danger 描边。
- 今日总览显示下次调度时间、调度模式/间隔与时段，提供「立即签到 / 只读核验」；其下四张统计卡按「今日成功 / 已签 / 失败 / 未确认」顺序显示数量，颜色见下表。
- 站点小卡两行紧凑布局：第一行图标+站点名+状态徽标（消息全文放徽标 title），第二行按配置显示单站签到、模拟登录小按钮并恒显只读核验按钮；不展示结果文字行、UID、时间、凭证来源或奖励明细。总览保留只读核验入口；停用/非试点站禁用执行按钮。
- 卡片区提供成功/已签/失败/未确认/站点不可达/协议待适配/维护中/已关闭/停用筛选 chips，再点选中态恢复全部；认证失败归失败，skipped 沿用停用色归停用；维护、网络及协议状态虽共用 off 中性色，筛选按状态值独立匹配，不按颜色混入停用。切换筛选重置为筛选后前 8 张，空匹配显示独立空态。
- 桌面三列等宽等高小卡，中屏两列、640px 以下单列；末张不跨列。默认前 8 张，failed/unconfirmed/auth_failed 优先且同优先级保持原顺序；其余用「展开其余 X 个站点」/「收起其余站点」切换，空态单独展示。
- 历史通过现有 page/size API 每页 100 条加载全部保留记录，按浏览器本地日期前端聚合；分组头为「YYYY-MM-DD · N 条记录」，默认仅当天展开，其余收起。列顺序为「时间 / 站点 / 状态 / 最近消息 / 证据」；证据按钮切换展开/收起，紧随对应记录插入跨五列的证据行；API 与存储不变。历史表容器 max-height:60vh、内部横纵滚动，证据展开行在同一容器内，不撑破宿主页面。
- 证据行只呈现实际回读的「回读按钮文本 / 本人 UID / 记录日期 / 记录状态」，桌面四列；缺失证据值留空，不输出占位文案，不从按钮单独推定签到结果。底部图例同步包含站点不可达、协议待适配、维护中/已关闭，均沿用 off 主题变量。历史消息使用真实 item.message，奖励如有拼在消息末尾，不借回读按钮文本替代执行结论；历史结果时间按浏览器本地时间显示 YYYY/MM/DD HH:mm:ss，存储 ISO 不变。
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
| maintenance | 维护中/已关闭 | 签到前读及 native 核验 HTTP 403/502/503，或响应体前 2 KiB（UTF-8）含维护/关闭文案（英文不区分大小写）；提交后回读与模拟登录语义不变 | 不计入 |
| network_error | 站点不可达 | 签到前读空响应、排除维护状态后的非认证 HTTP 错误或请求异常（含 native 核验） | 不计入 |
| protocol_pending | 协议待适配 | 签到无唯一表单、参数/验证码未解决或提交前解析异常 | 不计入 |
| skipped | 已跳过 | 门控、未选动作或锁忙 | 不计入 |
| cancelled | 已取消 | 执行取消 | 不计入 |
| login_ok | 登录成功 | 页面可达的模拟登录/自定义核验 | 不计入 |
| disabled（展示值） | 停用 | 未启用的站点卡 | 不计入 |

- 保留既有存储值，不批量重写历史 unconfirmed；新增状态只影响新的对应产生点。GetSignin 继承 Nexus 流程，无需复制分类逻辑；API 动作回执及提交后无条件回读不变。
- 憨憨的 register-now-info 声明必须使用 XPath class-token 匹配，不能把 CSS 选择器交给 lxml.xpath；attendance 前读/动作/回读使用相同 URL，测试必须按调用顺序提供响应。

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
- 执行双轨分流：native 站点签到/只读核验走原生模块；模拟登录使用下方独立登录契约，不构造旧桥。旧桥仅保留非 native 签到/核验分支（实际实现限 hdsky/haitang 试点回退，不是排除清单域名的通用签到器）。unlock_all_sites 默认 false，此时 verified、hook_implemented 和旧试点门控生效；显式 true 会绕过这三门，但不改变 verified，也不绕过启用、动作选择、凭据与站点锁。DarkLand/DigitalCore 签到仍不适用；M-Team 模块仍仅返回 skipped。signin_applicable 是 registry 展示的适用性，不等于 verified 或生产授权：排除登录专用站、M-Team，并检查原生 hook/verified；后端不以该展示字段替代执行检查。

### Native Browserless（3.23.0）
- 仅 ourbits、audiences、hdkyl、mua_xloli、pt_0ff、vclib、yema 声明 browserless；必须显式启用 browserless_enabled 并提供 HTTP(S) browserless_url。native 使用 BrowserQL HTTP，不依赖 Playwright/CDP；custom 保留原 Playwright 混合路径。
- 复用 Nexus 前读→协议解析→单次提交→无条件回读，不猜浏览器按钮或新增判定规则。BQL GET 渲染并 solve，POST 在页面内 fetch 原协议；每次请求独立浏览器，Cookie 双向同步只在本次执行内，结果 transport=browserql。未启用、未配置或首次连接失败保持原 HTTP 分类；已开始 BQL 后不重放动作，响应丢失仅按既有 finally 只读回查，证据不足为 unconfirmed。
- 默认 solve 与页面稳定等待各 15 秒，HTTP 超时为两项等待预算之和加 45 秒，上限 300 秒。Cookie/UA/脚本通过 variables 传入，不记录端点认证参数、请求体或远端错误原文。
- pt_0ff 前读已签可判 already，否则 protocol_pending，禁止滑块提交；yema 保留禁止签到；模拟登录一律不走 Browserless（用户裁决），BQL 仅服务签到路径。滑块模拟、真实过盾及站点提交效果未验证，需后续授权校准。

## 阶段2数据契约
- `core/registry.py` 使用 `pkgutil` 遍历 `sites/`，逐模块导入并收集 `_ISiteSigninHandler` 子类；导入异常只进入 `skipped` 日志，不阻断其他站点。注册项包含 `id/name/login_capable/credential/cf`，并追加 `rousi/sunnypt` 两个 integrations 注册项；`/sites` 返回 `sources.adapters` 与 `sources.integrations` 计数。
- 适配器凭证默认 `kind=cookie`、来源 `cookiecloud/managed_site/local_cookie`；集成凭证从 integrations 的 `CredentialSpec` 获取。注册表只缓存元数据，不实例化适配器或请求站点。模拟登录表示访问页面，不要求专属登录动作；适配器默认 login_capable=true（含 HDSky），仅显式 false 的特殊站关闭。
- `core/history.py` 使用 `get_data/save_data` 的 key `history.records` 保存 `{time,site,action,status,message,reward,evidence}`；`list(page,size)` 按时间倒序分页，默认每页 20、上限 100；追加和读取均清理超过 90 天的记录。历史只保存回读证据，不保存凭据。
- `/stats` 返回 `today: {success,signed,failed,unconfirmed}` 与 `next_schedule`；`/history` 返回 `{total,items}`。签到 action 的 auth_failed 计入失败卡；maintenance/network_error/protocol_pending 仅保留历史及站点卡，不计入四张统计卡，也不增统计键，避免把未执行当签到失败；保留原始历史状态；空态仅表示实际存储为空。
- 配置页以 `/sites` 为主数据源；仅在 registry 整包导入失败时使用 `frontend/src/sites.json` 作为静态兜底，不把静态清单当生产主数据源。

## S5 试点执行边界
- 同站账号锁忙时立即 skipped；试点在身份尚未解析前使用站点级锁，避免首次绑定与后续执行交错。原生 Cookie 按 cookiecloud → managed_site → local_cookie 选择；CookieCloud 使用宿主配置，只读本地密文（启用本地模式时）或单次远端下载，失败静默回退，不回写、不登录续期。按请求 host 与 Cookie domain 边界匹配，不将同名站点或兄弟域 Cookie 混用。
- 无 Cookie 返回 auth_failed，不实例化适配器或请求页面。旧桥第一次前读从账号导航识别 UID 后建立 identity.bindings，后续显式冲突停止；原生消息制已移除 UID 作为成功判定门槛，UID/日期仅展示，站点专属身份核验仍保留。换号须先人工确认旧绑定。
- 前读已签标记或本人今日成功记录 → already；明确可提交按钮/表单 → 提交；其余 → unconfirmed 且不提交。原生轨道 UID 未解析但表单明确时允许提交，成功由声明消息或 signed_marker 确认，不要求定位本人当日行；旧桥仍保留身份绑定及本人行验证。
- 桥仅使用既有适配器的提交方法；HDSky 只有未识别验证码（没有提交）才换 OCR 引擎，提交后不重试。无论二元组真假或提交异常，finally 都重新 GET 回读。
- 原生判定依次经历“四件套 → 消息制（移除 UID/日期门槛）→ 默认消息链 + signed_marker”；提交后仍无条件回读，消息链得到明确记录状态或 marker 确认后才下结论。原生 UID/日期仅作展示证据；旧桥仍对显式身份冲突立即停止。按钮文本保留展示，缺失不阻断；提交后页面不可达、消息或状态缺失 → unconfirmed；前读网络/协议分类见边界。每次尝试（含只读核验、忙、缺凭证）独立写 history。
- 当前 HTML 夹具是**合成回归夹具**，不是生产页面证据；保守选择器未匹配时不补造 UID/日期/状态，不把全页成功词当提交后证据。
- 生产切换：先在 QNAP 备份旧配置并停用旧插件对应两站调度 → 安装 3.3.0 → 确认站点管理 Cookie/UA 与选择 → 单站只读 verify_site 核验真实结构/UID → 未确认时脱敏采样补齐解析 → 用户确认后手动签到。本地调试实例可能也有真实 Cookie，执行前必须核实；真实试点需用户单独授权，未核验页面结构前不得宣称真实签到成功。

- 来源按实际登记判定：registry 以适配器 match 匹配 SiteOper URL，已登记为 MP 站点，未登记为插件适配；custom_sites_data 为自定义站点。`/sites` 的 registry 是站点清单权威来源；前端仅将本次会话尚未保存的自定义草稿做去重 overlay，已保存项不再本地重复拼接，草稿按 ID 覆盖或删除；宿主保存后回传 initialConfig 时清空 overlay 并重新获取 /sites。来源动态读取，不将凭据缓存入 registry。

## 组件与宿主玻璃主题
- Config/Page 共用 preview.css 的 .btn/.input/.switch/.chip/table；常规控件统一 36px 最小高度、6px 圆角、同一焦点框，紧凑列表 chip 是明确的小号变体。
- 按钮语义：保存/立即签到用主色蓝；移出启用与移除 chip 用 --ptc-danger 红色描边；查看数据/只读核验用 ghost；确认类用 --ptc-confirm 绿；禁用用灰并降低透明度。开关 on=主色、off=灰。
- 消费宿主 RGB 变量 --v-theme-surface / surface-variant / on-surface / primary / on-primary，以及 --v-border-color / --v-border-opacity；通过 --ptc-surface*、--ptc-text*、--ptc-line* 和 --ptc-blue 收口。
- 从 .v-application 的 v-theme--glass 与 surface RGB 明度识别玻璃深浅色；玻璃主题面板/输入/表格使用半透明底，局部卡片与弹层 blur(12px)，不绘制实心根面板。五态沿用 --ptc-*，深浅玻璃使用各自高覆盖率半透明底确保文字对比。
- 筛选下拉只保留弹层单框；弹层内搜索框用底线而非再套一圈描边。

## S6 迁移契约
- 迁移仅走运维 API：先 GET `/migrate/preview`，审核后 POST `/migrate/execute`，JSON body 必须含 `confirm: true`，`overwrite_conflicts` 默认 false；均为 `auth: bear`，不加 UI、不启动调度或站点请求。
- 来源配置走同宿主 GET `/api/v1/plugin/{id}`（内部 loopback + 宿主 API key），先查已安装清单和版本；AutoPtCheckin 的本地版本 >=3 标 `source_missing(reason=self_v3)`，不得迁移自己。未安装标 source_missing；鉴权/网络/版本异常标 source_error，不伪装成缺失。
- 映射：AutoPtCheckin 的 enabled/cron/cron_mode/interval_hours/begin_hour/end_hour/notify/queue_cnt/retry_keyword 同名写入；sign_sites/login_sites 按 registry ID 或域名匹配，合并生成 enabled_sites，未识别项列 unmapped。custom_site_urls（名称|URL|Y/N）与 custom_sites_data 合并到自定义站点源，旧数字 ID 转稳定 custom ID，render 转 emulate；不复制 Cookie 或一次性动作。
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
- 数据页「立即运行一次」设置 onlyonce 并触发一次性操作；onlyonce 优先只返回 `AutoSignIn.once` DateTrigger（即使 scheduler_enabled=false）；回调先持久化 onlyonce=false 再执行，重载不重复消费。进程在消费写盘后崩溃不自动重试，避免重复签到；失败由人工核验后再决定。
- 调度与 manual_signin 共用全量 runner 路径、试点范围与账号锁，history 增加 trigger=scheduler/manual；不因为启用调度扩大试点。next_schedule 从已声明的真实 Trigger 计算，不从展示配置猜测。
- 生产激活衔接 S6：备份并停旧插件任务 → preview/execute 配置迁移 → 核对试点 Cookie/UA/UID 和只读回读 → 用户授权手动验证 → 显式保存 scheduler_enabled=true → 核对宿主服务及 next_schedule。回退先关闭门控并确认旧服务移除，再恢复旧插件，禁止两边同时运行。

## 模拟登录契约
- native 登录直接调用 SiteModule.parse_login（含 DarkLand/DigitalCore），不要求 verified/hook_implemented，不执行 signin；页面 GET 仅访问首页，不访问 attendance 或保活动作。旧适配器只参与 registry 元数据发现，不参与登录执行。
- 非 native 登录使用通用页面解析，不构造 PilotBridge；已有 registry ID 按 matcher 找宿主条目，未登记域名必须已在 enabled_sites/login_sites 配置，并由宿主或 custom 条目提供同 host 地址。不得直接请求任意 API 入参 URL。27域排除清单仅表示没有 native 签到声明，不再表示依赖登录旧桥。
- GET 站点页面后无条件再次 GET 回读，无签到提交、无业务日期；页面可达即 login_ok，UID 尽力解析，缺失不阻断，显式冲突为 unconfirmed。重定向到登录页为 auth_failed，不可达为 unconfirmed。
- 批量执行勾签到的站点走签到链，仅勾模拟登录的站点走登录链；两项都未勾保留 skipped 记录。单站登录 API 为 POST /login_by_domain（auth: bear），复用站点锁和身份绑定。
- history 保存 action=sign/login；旧记录无 action 视为 sign。登录结果仅入历史，不覆盖签到小卡或四态统计；历史 login_ok 显示「登录成功」。
- 默认仅 HDSky/海棠可执行；显式 unlock_all_sites 可绕过模拟登录试点门控，但仍检查启用与登录动作选择。M-Team（api 凭据）与肉丝/SunnyPT 只提供可注入认证检查协议；未接检查器返回 unconfirmed/login_check_not_available，不以非空凭据冒充认证检查通过。真实协议接入须后续逐站授权。

## 批次 3 完成（3.15.0，2026-10-22）
- D1 下沉：20 专属模块（CAPTCHA 12/GET 6/POST 2）并入 generic_sites.json 行为字段（captcha/action_get/safe_read_path/referer/form_data/form_path/response_json/action_path/use_default_message/signin_capable；typed status_map pairs），native 守恒 108。
- D3：CookieCloud 为独立数据源，候选链第一环（本地文件优先/远端单次 20s/严格域边界/CF-only 子集拒绝/静默降级），不回写。
- D4：custom 站标准 NexusPHP 签到+emulate 混合路径（未启用 Browserless 不降级）；verify 保持 login_ok。
- D5：模拟登录全原生（native parse_login/custom/已配置域名通用双 GET），旧桥只剩 pilot 回退。
- D6：凭证枚举 api→api_key（credentials/integrations/registry/前端徽标/测试）。
- D7：46 副本 deprecated+legacy 分支 site_removed 防护；文件删除推迟到生产切换+verified 解锁。
- D9：Luna 审查 8 项 6 过，P2 CF-only 过滤补全（_CF_ONLY_COOKIES）、P3 文档过期描述修正。
- 52pt 已滑块化（hook=False、signin_capable=False、仅模拟登录；Browserless 滑块实现暂缓）。答题类 chdbits/tjupt 仅模拟登录。

## 批次 3 计划（已实施，见上；保留原文备查）
- 删旧桥的前置条件：全量重审口径的27站完成生产校准并逐站 verified 解锁；默认链命中、只读 already 或 unlock_all_sites 都不替代该条件，模拟登录依赖需一并核对后再删除。
- 统一凭证枚举 api → api_key，连同配置、registry、UI 与测试同步迁移；当前版本不改名。
- cookiecloud 原生候选已于 3.12.0 接入；原生模拟登录同样按 cookiecloud → managed_site → local_cookie 选择；custom 保持本条目 Cookie。本轮仅离线 mock 验证，真实服务器与站点验证仍需授权。

## Custom 签到契约（3.13.0）
- custom_sites_data 的已启用且勾选签到条目（含数字 ID）直接使用 NexusSignin 默认 attendance 表单流程，不要求 native verified；unlock_all_sites 不能绕过启用与动作选择。registry 的 custom pilot_enabled=True；signin_applicable=True，唯 emulate=true 且 Browserless 未启用时为 false。
- custom Cookie 使用本条目的 local_cookie；GET attendance → 唯一同源 POST 表单 → 单次提交 → 无条件新页回读默认消息链。前读已签为 already，新页确证为 success，缺证据为 unconfirmed；history action=sign。无唯一表单返回 protocol_pending，不猜非 NexusPHP 协议；已识别验证码不自动作答。
- emulate=true 必须显式 browserless_enabled 且配置 browserless_url；browserless_token 仅用于连接认证。本版为 Browserless 前读/回读 + HTTP 提交混合路径（metadata.transport=browserless_read_http_submit），执行级 Cookie 双向同步，独立 context 及连接 finally 释放；连接/页面错误不降级 HTTP-only、不重试动作。依赖 Playwright/CDP，浏览器指纹绑定 POST 站点可能仍未确认。
- verify 保留只读 login_ok 语义，不视为签到；custom 模拟登录复用同一可达性语义并无条件二次 GET 回读，仍检查 enabled/login 选择与 Browserless 显式开关。真实站点与 Browserless 服务未实测，另行授权验证；设计取舍见 .agents/notes/implemented/feature/2026-10-22-custom-attendance.md。
