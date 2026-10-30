# PT 签到中心 V3

## 边界
- 站点启用且选择动作即可执行，仍检查真实能力、凭据、站点互斥与已签去重；不再使用 verified/unlock_all_sites 审批或手动旁路。
- 站点由 `sites/native/` 原生声明、generic 声明与 integrations 组成；不接管 `plugins.v2` 入口，默认不激活自动调度。
- 站点语义（2026-10-28 修订）：zhuque 的 fireGenshinCharacterMagic 是技能动作回执而非每日签到，已转 `signin_capable=False` 仅保留登录；52pt 签到入口整体下线（`signin_capable=False`，去仿真）仅保留登录；vclib 人工验证走 CloakBrowser 页面动作签到。
- 站点规则（2026-10-24）：HDDolby 公告「API 访问不计有效登录；严禁 Cookies/伪造 UA 模拟登录，违者警告或封号」——hddolby 声明 `login_notice`，配置/数据卡显示 ⚠ 徽标（title 全文）提醒用户定期浏览器人工登录，登录轨不强行关闭（用户裁决）。同类站点规则按此先例加 notice 徽标。
- Registry 仅发现 `sites/native/`；generic 声明由 native 包提供，rousi/sunnypt 由 integrations 注册。旧适配器副本和旧执行桥已移除。
- 任何提交结果都必须尝试新页面回读；按钮文本只能来自页面证据。
- 对外新结果使用下方统一六值；适配器内部可保留原始协议状态，但未知证据不得猜成功或失败。提交与回读规则不因归一改变。
- 旧 verifier 链（`verifiers/`、`core/verification.py`、`SignRunner.run/run_login`）与 UID 防串号按 2026-10-28 用户裁决删除：生产回读只走 `core/nexus.py` 声明链与 `core/native.py` 的 `read_login_twice`／无条件新页回读，证据只保留消息文本与本人行日期；`Evidence.uid`/`Credential.uid` 字段保留，仅不再自动解析。

## 验证
- `PYTHONIOENCODING=utf-8 micromamba run -n base python -m pytest tests/v3/autoptcheckin`
- 不在离线测试中放置 Cookie、Token 或真实 URL 请求。

## UI 契约
以定稿 `D:/tmp/pt-signin-form-preview.html` 为视觉与交互依据；示例站点、数量、日期、奖励和勾选值不作为生产数据或默认配置。

### 配置页
- 只设「设置 / 站点」两 Tab，默认显示「设置」；使用 Vue 响应式 model 与原生 Tab，不拆出调度或凭证 Tab。
- 「设置」按基础设置、执行调度、Browserless 分组：基础设置的「启用插件 / 发送通知」同行。
- 执行调度填写框按字段数量和可用宽度多列自适应（auto-fit，最小宽约 180px），不固定两列；时间窗口保持文本输入。凭据区同样自适应，窄屏自动降列。
- Browserless 全局服务配置为 browserless_url/browserless_token；默认公共服务需 Token，自建非默认地址允许免 Token。仅显式 cloudsign_capable 的站点显示云签开关，site_cloudsign 独立选择；缺配置明确提示且不回退。立即运行/清缓存只放数据页。
- 「站点」依次呈现启用数量、可按名称筛选的多选站点清单、可移除的已选 chips、启用站点卡片；启用数量行末提供「编辑自定义站点」按钮；无启用项时显示空态。选择器使用带搜索框的多选下拉及可移除 chips；多选后「确认选择」一次性更新 enabled_sites 并插入平铺列表，下拉顶部「全选/全不选」仅切换当前筛选结果集合（无筛选为全部站点），不影响草稿中的其他项；取消不改变启用清单，保存配置前不持久化。已选 chips 回显在选择框内（/sites 加载后按 enabled_sites 映射）；打开时回显 pendingSites 草稿，勾选/移除即时更新草稿，关闭未确认则恢复已启用 chips；关闭态移除 chip 直接更新 enabled_sites。弹层使用原生 popover top layer 避免宿主裁切，按视口剩余空间上下翻转、水平约束，最大高度 min(400px,60vh) 并内部滚动；滚动/resize 重新定位。
- 「编辑自定义站点」打开 dialog 列表（站点名 / 地址 / 仿真 / 保存、删除），直接行内编辑，提供新增行；不提供启用勾选。名称必填、地址限 HTTP(S)；行内保存仅更新 custom_sites_data，新站不自动启用；删除同步清理 enabled_sites 与动作集合。关闭丢弃未保存编辑，保留已保存行。自定义站点与 MP 站点共用主选择器、来源固定「自定义站点」；仍需主表单保存才持久化。
- 窄屏（预览断点 640px）字段与站点数据卡改为单列；统计卡、证据字段改为两列，避免强制保留桌面同行布局。

### 配置站点卡片
- 收起态使用约 36px 的紧凑行，五区域列轨（×移除/站名/徽标/开关组/▸）：`.row-left` 小号移除按钮（×，二次确认后为 danger「确认移除」+subtle「取消」）→ 站名（图标+名称）；`.badges` 来源/凭据/CF盾/云签|仿真/云签未配置/⚠notice 徽标；`.row-right` 双开关组——左组「代理/仿真/云签」（仿真全站渲染：无适配站关闭态灰、有适配站 `adapt` 橙变体，开启仍 success；云签仅 capable 站显示，缺位 placeholder 对齐），右组「签到（canSign 才显示）/登录」；`.btn.ghost.mini.expand-icon` ▸ 仅 hasExtraSettings（凭据字段）站显示，缺位 placeholder 保列轨。⏻ 暂停/恢复（`.pwr`，30px 圆形）在站名前。整行不触发展开，仅 ▸ 切换；开关可直接交互不折叠详情；仿真不由 CF 推断。开关统一 38×22、18px 圆点：关闭浅灰 inset 描边、开启 success 绿、adapt 关闭 warning 橙。
- 已启用列表为单一平铺紧凑行，不显示分组；提供独立名称筛选、8 枚状态筛选 chips、全部展开/收起。「全部展开」仅打开所有已启用且有额外配置的站点详情（不受名称筛选限制），「全部收起」关闭所有详情。列表最大高度 68vh 并内部滚动，桌面以一屏至少 15 行为验收。
- 徽标枚举：来源「MP 站点 / 插件适配 / 自定义站点」；能力「可签到」，支持模拟登录时才显示「模拟登录」徽标与选项；凭证方式 `cookie / api / password`，允许组合，API 可标注 JWT；CF 状态「CF 有盾 / CF 无盾 / CF 未检测」，未知不得当成无盾；`shield=cloud` 云签徽标 / `emulate` 仿真徽标 / `null` 无徽标。
- 收起态即可勾选「签到」；支持模拟登录时才显示「模拟登录」勾选（同行），直接同步 sign_sites/login_sites，不改变 enabled_sites；勾选不触发详情展开，展开态显示来源、凭证方式、CF 状态、模拟登录能力的只读站点类型行，以及凭据、自定义地址/仿真等额外配置，不重复动作勾选或移除按钮。自定义站点同时展示地址与仿真状态；收起态站点名前的 × 经行内二次确认移出启用，同步 chips 与启用数量。
- 凭据区按站点所需字段生成：肉丝为「账号 / 密码」，SunnyPT 为「账号 / 密码」，列数按可用宽度自适应；纯 Cookie 示例站点不额外生成账号密码区。账号用普通文本，密码、JWT、令牌用 `type: password`。
- 仅在站点启用且至少勾选签到或模拟登录、并且该站有专属凭据字段时显示凭据区；取消两个动作即隐藏，不能因选择了站点就无条件显示凭据。

### Vue 模式与宿主契约
- `get_render_mode()` 返回 `("vue", "dist/assets")`；宿主无条件解包 get_form：`get_form()` 返回 `(None, defaults)`，`get_page()` 返回 None，不再生成 Vuetify JSON。
- Vite originjs ESM 联邦名为 `AutoPtCheckin`，入口 `remoteEntry.js` 暴露 `./Config` 与 `./Page`；共享宿主 Vue 3.5.13，不打包第二份 Vue 或 Vuetify。
- 宿主 Config 传入 `initial-config / api / plugin-id`；`save(model)` 事件由宿主 PUT `plugin/{id}` 保存。`close / switch / layout({maxWidth})` 事件由宿主处理。Page 接收 `api / plugin-id / show_switch`。
- API 相对插件 ID：GET/PUT `/config`、GET/PUT `/site_config`；GET `/stats`、`/history`、`/status`；POST `/run_once`、`/clean_today`、`/signin_by_domain?domain=...` 单站执行、`/verify_site?domain=...` 只读核验、`/login_by_domain?domain=...` 模拟登录；`/manual_signin` 与 `/notify_preview` 已删除；所有端点显式设置 `auth: bear`（默认 apikey 不适用于宿主前端）；配置与凭据只在宿主鉴权边界内读写，不进入统计/日志。
- `/site_config` 使用既有 flat keys（enabled_sites/sign_sites/login_sites/custom_sites_data 及专属凭据）；与完整 config 同源，get_data/save_data 保存站点子集。
- 配置页动作框按真实能力显隐；数据页动作按钮按启用、动作选择与相同能力判定，不另设审批。
- 代理、仿真与云签选择遵循下方执行通道契约；M-Team 为独立真实浏览器账密登录例外。
- 在 `frontend.v3/autoptcheckin/` 执行 `npm ci --ignore-scripts && npm run build`，构建直接输出到 `plugins.v3/autoptcheckin/dist/`；`distbak/` 保留迁移前备份，node_modules 不入库。
- 用宿主页面核验 Tab、条件字段、选移站点、卡片折叠、凭据显隐、证据展开；离线测试不能代替渲染验收。

### 数据页
- 站点名优先采用适配器 match 命中的 MP 登记名，未匹配保留适配器名；/sites 和 /stats 使用相同映射。图标仅读取 SiteOper.get_icon_by_domain 的 data:image 缓存，不加载远程 URL；配置卡及数据卡显示图标，缺失/加载失败用首字母占位。关闭按钮用 ghost 描边，×/移除 chip 用 danger 描边。
- 今日总览保留下次调度与运行操作；签到、登录各三卡（桌面三列等宽，窄屏自适应）：成功/失败为当前启用且勾选轨道的今日结论，待处理为有效队列中的 pending（含尚未执行），不是本轮执行次数。
- 站点小卡三行紧凑布局（`.site-r1`/`.site-caps`/`.site-msg`）：第一行 ⏻ 暂停/恢复（`.pwr` 30px 圆形）+ 图标/首字母占位 + 站名（外链）+ `.head-right` 内「签到」「登录」状态 chip 按钮（文字固定签到/登录、颜色表状态：绿=成功、红=失败、橙=结果待确认、灰=待执行；pending 按 reason 选色；消息全文放 title），chip 即执行按钮，点击直接执行对应动作，显隐只跟随站点配置开关，置灰由暂停/忙态决定；第二行能力 chips（云签/仿真/代理，仅生效时显示）；第三行消息摘要（30px 两行截断，title 全文）。不展示结果文字行、UID、时间、凭证来源或奖励明细；总览行保留「立即运行/清理缓存/⟳刷新」。可见文案统一用「登录」，不再出现「模拟登录」。数据页底部不放图例。卡片排序为非成功优先：轨道判定只计入已启用且非暂停、状态非 disabled 的轨道（避免「只签到不登录」的站点被永久顶到最前），失败/待确认/待执行同属第一档并按下发顺序稳定排列。签到/登录 chip 按钮是 24px 紧凑变体，不继承全局按钮 36px 最小高度。
- 卡片区筛选 chips 与站点徽标同款样式：签到（绿/红=成功/失败）、结果待确认（橙）、登录（绿/红）、不可达、维护中、待验证、待执行（均 off 色），再点选中态恢复全部；认证失败归失败，skipped 沿用停用色归停用；维护、网络及协议状态虽共用 off 中性色，筛选按状态与 reason 独立匹配，不按颜色混入停用。切换筛选重置为筛选后前 8 张，空匹配显示独立空态。另有「已暂停」筛选 chips，按 `site_paused` 直接筛出启停按钮关闭的站点。
- 桌面三列等宽等高小卡，中屏两列、640px 以下单列；末张不跨列。默认前 8 张，非成功优先（轨道判定见上，失败/待确认/待执行同档）且同优先级保持原顺序；其余用「展开其余 X 个站点」/「收起其余站点」切换，空态单独展示。
- 历史通过现有 page/size API 每页 100 条加载全部保留记录，按浏览器本地日期前端聚合；分组头为「YYYY-MM-DD · N 条记录」，默认仅当天展开，其余收起。列顺序为「时间 / 站点 / 状态 / 最近消息」四列；不提供证据展开行，失败与异常说明（403/503/维护等）由最近消息列承载；API 与存储不变。历史表容器 max-height:60vh、内部横纵滚动，不提供证据展开行，不撑破宿主页面。
- 历史不展示回读按钮文本/记录日期/记录状态等证据字段（回读证据仍按存储契约保留在 history.records，仅不在 UI 展开）。历史消息使用真实 item.message，奖励如有拼在消息末尾，不借回读按钮文本替代执行结论；历史结果时间按浏览器本地时间显示 YYYY/MM/DD HH:mm:ss，存储 ISO 不变。
- 配置自定义站点 dialog 使用草稿模式：打开时复制已保存数据，取消/关闭丢弃未保存编辑，行内保存仅更新草稿与已保存项；主配置保存前不持久化。
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
- 主题跟随宿主 `html.v-theme--dark` / `html.v-theme--light`（MutationObserver 实时监听）；无宿主主题 class 时回退 `prefers-color-scheme`。颜色变量集中定义于 `frontend.v3/autoptcheckin/src/preview.css` 的 `--ptc-*` 清单，组件样式不得使用主题硬编码色。

### 结果与兼容边界
- 新执行/API/历史结果只输出 signed/login_ok/failed/pending/skipped/cancelled。signed 无 reason 为本次成功，already_signed 表示此前已签；failed 可带 auth_failed；pending 的 reason 为 result_unknown/network_error/maintenance/protocol_pending。
- 原始适配器枚举仅在统一边界转换，消息、奖励与回读证据保留。归一必须幂等；未知原值归 pending 并保留 raw_status 诊断，不能猜失败。
- 旧历史只兼容读取，不批量改写。旧 track.state v1 的 signed 是旧 already；v2 新 signed 不再重解释。新历史显式保存 reason 字段区分新旧记录。
- 兼容层的删除条件（四条全满足才可动手，涉及 `core/state_store.py` 的 `_compat_legacy_entries`、`core/models.py` 的旧 already 解释、`core/history.py` 旧值读取、`core/native.py` 的 `cookies.refreshed` 迁移）：① `track.state` 已无 `version == 1` 数据；② history 14 天保留窗口内所有记录都带 reason 字段；③ `cookies.refreshed.migrated` 已置位且旧键为空；④ `track.state` 不再出现旧审批 reason。删除是不可逆的数据语义变更，动手前先导出 `track.state` 与 history 备份。
- 轨道仍为 success/failed/pending/disabled；pending 下轮重入队、不当场重试。锁忙 skipped/取消只写流水，不覆盖结论。
- 憨憨的 register-now-info 声明必须使用 XPath class-token 匹配，不能把 CSS 选择器交给 lxml.xpath；attendance 前读/动作/回读使用相同 URL，测试必须按调用顺序提供响应。
- 站点每日重置小时用 `reset_hour` 声明（u2/retrotoon=9，generic 声明同样支持该键）：重置小时前 read_before 读到的 ALREADY 只改消息归属（「昨日已签，站点 9 点后刷新」），状态仍是 already（跳过本轮、不提交），未签照常提交——不做时间门控、不降级 unconfirmed（2026-10-28 用户裁决，旧 U2 9 点守卫已删）。U2 9 点后表单提交「一切随缘」随机选项。

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
- 不以静态 verified 属性表示运行许可，也不为放行伪造已验证证据。
- 原生站点实现 `SiteModule`，通过类属性声明 `id/name/url/credential/login_capable/cf/record_spec`，仅实现 `signin(ctx)`；`sites/native/` 逐模块发现，导入失败隔离为 `skipped`，不阻断其他站点。generic 声明（`generic_sites.json`）必须显式给出 `protocol`（nexus/form/api/get/page_action/login_only），由协议决定执行基类与必填键（api/get/form 必须给 `safe_read_path`），不再按键存在性推断流程。`signin_capable` 只在 False 时声明（缺省=True，registry/native 均以 `getattr(..., True)` 兜底，读取方不得直接属性访问）；`hook_implemented` 元键已删除。
- `RecordSpec` 默认 page_message，每个 XPath 必须选中唯一消息元素；多选择器遇空值、歧义或无效表达式继续扫描，首个非空文本停止，再按 status_map 声明顺序映射 signed/unsigned（无匹配仍 unconfirmed，不继续找成功词）。NexusSignin 的空 message 声明（仅 source=page_message）默认回退消息链，站点可关闭 use_default_message；response_json 仍按 response_field 的精确类型和值匹配。signed_marker 可确认安全前读 already 和提交后新页 success；日期只作本人行匹配，UID 不再解析，不以缺失字段或整页文本补造结论。校准记录见 sites/native/AGENTS.md。
- `NexusSignin` 提供 attendance 页面 GET、唯一 POST 表单发现、验证码钩子和提交后的无条件新页面 GET 回读；提交响应不能替代回读，超时或异常不得自动重试。
- 验证码站每轮最多 `captcha_attempts`（默认 3）次「识别+提交」：仅当回读 unconfirmed、新页面仍是未签到的验证码表单（含 imagehash+imagestring 且能发现唯一 POST 表单）时重新取图再试一次；提交异常/取消/已签页面/页面动作站(cloak_steps)/回读明确 failed 都不得重试（failed 的当场重试由 runner 的 retry_count 负责）。尝试次数写入 `metadata.signin_attempts`；失败现场写入 `metadata.captcha`（识别到的 `code`/`engine`/`length`，或失败原因 `imagehash_missing`/`post_form_not_found`/`captcha_image_not_found`/`captcha_image_cross_origin`/`ocr_error`/`ocr_no_match`/`ocr_unavailable`/`cancelled`）与 `metadata.submit`（POST 响应 `status`、`still_captcha`、`snippet` 关键文案片段，由 `NativeHttpClient.post` 记录）；仍无证据时消息追加「（验证码已重试 N 次仍无成功证据；<现场>）」，单次尝试追加「（<现场>）」。HTTP 通道 UA 经 `browser_ua()` 兜底：站点未配 UA、配成插件 UA（`Plugin/...`）或库默认 UA 时统一换固定浏览器 UA（验证码图下载与会话校验要求浏览器指纹）。
- `SignContext` 由执行边界注入已认证的 HTTP client、站点锁、取消事件及可选 `page/ocr`；`SiteModule` 不查凭据、不创建或关闭资源，资源生命周期由 `core.native`/runner 管理。
- native、custom、integrations 使用各自执行器；DarkLand/DigitalCore 签到不适用，M-Team 仅登录。能力声明与用户选择共同约束手动/自动入口。

### 仿真通道（CloakBrowser）
- site_proxy/site_emulate 为站点ID到布尔的覆盖表：缺键继承 MP proxy / (MP render 或内置 emulate)，显式 false 优先；自定义仿真默认按条目填写。site_cloudsign 为独立选择数组，仅签到走云签，登录不受云签影响仍走原路径（勾选仿真走仿真，不勾选走 HTTP）。旧 site_browserless 仅一次性迁移读取，随后删除，不复活已清空的新选择。
- 复用 Nexus 前读→动作→无条件回读，结论一律来自回读证据。Cookie 双向同步仅限本次执行；不得重放动作。页面动作后的落点页 stash 即为回读证据；站点每次进入可能发放新的滑块门页，不能用二次 GET 替代动作回读。
- **页面动作站（`cloak_steps`）**：声明侧为 `protocol: page_action` + `cloak_steps`，执行基类 `PageActionSignin` 统一承担动作链、落点页回读与验证钩子存根；pt_0ff=[slider,sign_button]（滑块有时不出现，出现才拖动）、yema=[altcha,sign_button]（ALTCHA 方框勾选→PoW 验证通过（文案「已验证/Verified」）→点「立即签到」，# /user/growth，slow 90s）、vclib=[human_verify,sign_button]（Cloudflare Turnstile，headful CloakBrowser 等待 token 最多 60 秒）、piggo/kamept=[sign_button]。`run_page_action` 步骤缺失不阻断（absent 继续下一步），点击后等 5s，最终以回读消息链判定成功/已签/未确认，不猜测按钮结果。 pt_0ff 拖到底松开后门页先显示「验证通过」，约 8 秒自动跳转真实签到页；回读出现「签到已得N」才是成功证据，默认消息链已覆盖。slider 拖动后轮询等待标题/正文离开「滑动认证/拖动滑块验证」门页（每 1.5s，最多 25s），离开后再稳定等待 2s，超时如实保留未确认。
- 每站独立 actor 创建、操作、关闭 CloakBrowser，禁止跨线程共享 Playwright 对象。多站逐个启动增加开销，换取线程、代理和有头模式隔离；保留严格线程归属反例测试。
- 单站与批量执行沿用同一能力/启用/动作选择语义；手动调用不绕过未启用或未选动作。
- 默认 solve 与页面稳定等待各 15 秒；单次导航上限 30 秒。滑块拖动为 humanize 步进鼠标（24 步），真实过盾效果需生产验证。

## 阶段2数据契约
- `core/registry.py` 使用 `pkgutil` 遍历 `sites/native/`，逐模块导入并收集 `SiteModule` 子类；导入异常只进入 `skipped` 日志，不阻断其他站点。注册项包含 `id/name/login_capable/credential/cf`，并追加 `rousi/sunnypt` 两个 integrations 注册项；`/sites` 返回 `sources.adapters` 与 `sources.integrations` 计数。
- native 站点凭证默认 `kind=cookie`、来源 `cookiecloud/managed_site/local_cookie`；集成凭证从 integrations 的 `CredentialSpec` 获取。注册表只缓存元数据，不实例化适配器或请求站点。模拟登录表示访问页面，不要求专属登录动作；native 站点默认 login_capable=true（含 HDSky），仅显式 false 的特殊站关闭。
- 本地 SQLite（4.0.20）：`PLUGIN_DATA_PATH/AutoPtCheckin/autoptcheckin.db`（WAL，`core/history.py:open_local_db` 建 records/kv 两表）。`HistoryStore` 存 `{time,site,action,status,message,reward,evidence}` 单行 JSON 到 records 表，`list(page,size)` SQL 分页（默认 20、上限 100），追加时顺手清理超过 14 天的行；无 db_path（测试 stub 无 get_data_path）退化为内存后端。`IconCacheDB` 以 `icon:<site_id>` 存 kv 表。`_migrate_local_store`（init_plugin 一次，kv 标记 `migrated:localstore` 幂等）：宿主 plugindata 的 history.records/icon.cache 导入后 del 源 key，并探删 V2 遗留 `^\\d+月\\d+日$` 按日 key。track.state/cookies.table/site_config/schedule_* 仍走宿主 save_data。历史只保存回读证据，不保存凭据。
- 轨道状态表（3.35.0）：`save_data("track.state")` 持久化每站×轨道（sign/login）的规范化状态，`core/state_store.py` 唯一实现。四值：success/failed/pending/disabled；映射唯一入口 `normalize(track,status,reason)`——sign 成功族={success,signed}（already 已在 `_record_result` 入口归一为 signed，状态表不出现）、login 成功={login_ok}；门控类 skip（reason ∈ 登记清单）→ disabled(reason)；其余失败族与无记录 → failed/pending；maintenance/network_error/protocol_pending 与未知/空状态 → pending；锁忙 skipped 与 cancelled 只写历史不改表。写入点：`_record_result`（read_only 结果跳过）；`init_plugin`/每轮 `_execute_all` 前全量重算 pending/disabled（`_recompute_track_states`，success/failed 结论保留）；日切（state.time 非今日的 success → pending）；清理缓存联动 `clear_transient`（非禁用→pending）。
- 双队列先签到后登录；实际队列取启用∧勾选∧真实能力∧状态∈{failed,pending}。保留历史结果不代表仍允许入队；能力关闭、站点移除后不得因旧 failed 重试。单站 failed 当场重试至 retry_count，锁忙/取消不算实际执行。
- `/stats.latest` 按当前启用、勾选轨道展示 success/failed/pending；成功/失败只取今日结论，pending 取有能力的有效队列（含未执行）。历史与通知的本轮计数不得反推此统计。
- 配置页站点来自 /sites，无静态 sites.json 兜底；不得把演示清单当生产数据。

## 执行边界
- 账号锁忙立即 skipped；站点锁在身份解析前获取，避免首次绑定与后续执行交错。Cookie 按 cookiecloud → managed_site → local_cookie 选择，并按请求 host 与 Cookie domain 边界匹配。
- 无 Cookie 返回 auth_failed，不请求签到页面。原生轨道日期只作本人行匹配（不解析 UID）；提交状态依声明消息或 signed_marker 确认，证据不足为 unconfirmed。每次尝试独立写 history。
- 原生签到与只读核验走 `run_native`；custom 走 `run_custom`；rousi/sunnypt 走 integrations；M-Team 登录走独立 CloakBrowser。ourbits 为账密兜底 hook（`integrations/ourbits.py`）：Cookie 全源失效（auth_failed）后表单登录 takelogin.php 换取新 Cookie 并经 persist_cookie_result 回写统一 Cookie 表；2FA TOTP 可选——配置 ourbits_totp 才填 2fa_code（pyotp），未配置不填直接提交；登录页出现 imagestring 验证码明确放弃。其它无执行实现的旧站点返回 `skipped(site_removed)`。

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
- `scheduler_enabled` 默认 false，是生产切换门控，不随 S6 的 enabled 迁移；false 时不注册常规定时服务，并打一条 warning 日志。未激活时 `/stats.next_schedule=null`，`schedule_status` 解释阶段限制。立即运行是独立线程执行，不写配置、不注册一次性服务。4.0.18 起插件自有配置保存（`_save_config`）做键级合并，partial PUT 不再静默重置未提交键；`init_plugin` 路径仍全量替换（迁移恢复要求精确回滚）。
- 定时只注册 cron/interval，由宿主管理；配置初始化/保存调用 _sync_jobs 同步。立即运行不得改调度配置或注册 DateTrigger；旧 onlyonce 剥除不触发执行。非法调度配置拒绝应用并保留现有运行配置，宿主已保存的非法值由用户改正。
- interval 对齐 V2 `__generate_schedule_crons` + TimerUtils.random_scheduler：次数 max(1, int((end-begin)/interval))，从 begin:00 累加 [max(30,interval*30),interval*60] 随机分钟，最小 interval=0.5，0<=begin<end<=23。schedule_crons/schedule_signature 用 get_data/save_data 保存，signature 相同复用，变化重排；不采用重载重新随机，以免调度漂移。
- 数据页「立即运行一次」直接调用 run_once API，在独立线程执行一轮，不写配置、不注册一次性服务；不受 scheduler_enabled/常规运行门控限制，但仍遵守站点选择、账号锁、轮次互斥和停止取消。
- 调度与立即运行共用全量 runner 路径、站点选择与账号锁，history 增加 trigger=scheduler/manual；调度不绕过站点门控。next_schedule 从已声明的真实 Trigger 计算，不从展示配置猜测。
- 生产激活衔接 S6：备份并停旧插件任务 → preview/execute 配置迁移 → 核对站点 Cookie/UA 和只读回读 → 用户授权手动验证 → 显式保存 scheduler_enabled=true → 核对宿主服务及 next_schedule。回退先关闭门控并确认旧服务移除，再恢复旧插件，禁止两边同时运行。

## 模拟登录契约
- native 登录调用 parse_login，不执行 signin；只访问登录探测页面，不访问签到或保活动作。
- 非 native 集成之外的已配置域名登录使用通用页面解析；已有 registry ID 按 matcher 找宿主条目，未登记域名必须已在 enabled_sites/login_sites 配置，并由宿主或 custom 条目提供同 host 地址。不得直接请求任意 API 入参 URL。27域排除清单仅表示没有 native 签到声明，不再表示依赖登录旧桥。
- GET 站点页面后无条件再次 GET 回读，无签到提交、无业务日期；页面可达即 login_ok，不解析 UID（防串号已按用户裁决移除），不因身份冲突降级。重定向到登录页为 auth_failed，不可达为 unconfirmed。
- 批量执行按签到、登录两个独立队列处理，分别遵守对应选择与能力；两项都未勾保留 skipped 记录。单站登录 API 为 POST /login_by_domain（auth: bear），复用站点锁。
- history 保存 action=sign/login；旧记录无 action 视为 sign。登录结果写入登录轨道状态并进入对应今日统计，历史同时保留；历史 login_ok 显示「登录成功」。
- rousi/sunnypt 使用专属集成协议并在启用与动作选择后可执行。PeerGo 登录先 GET `/api/v1/session`，Cookie 无效时使用账密 POST 刷新；签到读取 session/attendance，已有 claimed_today 不重复提交，提交带 Origin、Referer、X-CSRF-Token 与唯一 Idempotency-Key。SunnyPT 优先配置 JWT，否则账密换 token；Bearer 签到按 code=0/400001/400000 分类，token 失效时重新登录并最多重试一次。M-Team 仍仅由独立 CloakBrowser 真实登录实现，不经通用 password 集成协议。

## 通知契约
- 通知为纯文本（4.0.9 起）：无 notify_format 配置项、无标签富文本；post_message 不传 parse_mode。分轨两条消息（签到/模拟登录），标题「【PT 签到中心】」。Telegram 等按 HTML 解析的渠道不再因 `<div>` 等标签 400。
- 通知三行：全部签到/登录；本次签到/登录（成功 · 失败 · 待处理）；下轮待执行。前两项分类仅取本轮最终结果，下一轮直接取实际队列快照，不等于失败数。明细分已完成/失败/待处理，空组隐藏；当日旧待办只补明细，不补本轮计数。本轮零执行、无明细行且下轮待执行为 0 的轨道整条不发——「全部 X」是启用站点数、恒大于 0，不能当作该轨是否有话说的判据。
- POST /notify_test（auth: bear）绕过「发送通知」开关直接推送当前轮数据，用于渠道连通验证；封套与其余端点一致（success/message/data），无数据或发送异常返回 success=false 并附错误消息。


## Custom 签到契约（3.13.0）
- custom 条目按启用、动作选择与能力执行，不自动启用新增站；代理/仿真按统一覆盖表解析。
- custom Cookie 使用本条目的 local_cookie；GET attendance → 唯一同源 POST 表单 → 单次提交 → 无条件新页回读默认消息链。前读已签为 already，新页确证为 success，缺证据为 unconfirmed；history action=sign。无唯一表单返回 protocol_pending，不猜非 NexusPHP 协议；已识别验证码不自动作答。
- 有效 emulate=true 时启用 CloakBrowser 前读/回读与 HTTP 提交混合路径；HTTP 与浏览器均接收同一有效 proxy。不得因浏览器错误静默降级或重放动作。
- verify 保留只读 login_ok 语义，不视为签到；custom 模拟登录复用同一可达性语义并无条件二次 GET 回读，仍检查 enabled/login 选择；模拟登录按站点有效仿真配置执行。真实站点未实测，另行授权验证；设计取舍见 .agents/notes/implemented/feature/2026-10-22-custom-attendance.md。

### 3.36.0 后端数据与端点契约
- `/manual_signin` 与 `/notify_preview` 已移除；保留 `/verify_site` 只读核验入口及 `/run_once`。数据页按钮、错误消息行、统计合并卡、历史按天、配置 switch 与 per-site 仿真的渲染由前端契约负责；接口不另增前端字段。
- /sites 与 /stats 返回同源有效 proxy/emulate、cloudsign_capable/cloudsign_selected；shield 仅在实际选中云签时为 cloud，否则按有效仿真显示。
- 集成凭据分类：rousi/sunnypt 为 password（账密登录；SunnyPT JWT 是登录产物）；mteam 凭据 password（账密登录；登录态 Cookie/storage_state 内置存储，失效自动重新账密登录），CloakBrowser 保活（`login_capable=true`）；ourbits 为 password（ourbits_username/ourbits_password/ourbits_totp 可选，作为 Cookie 全源失效后的兜底换取通道，不是常规登录轨）。
