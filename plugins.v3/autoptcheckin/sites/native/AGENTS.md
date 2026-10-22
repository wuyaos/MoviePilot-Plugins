# Native declarations and evidence audit

## 边界
- 旧 `sites/` 副本是迁移依据；B1 声明一律 `native=True, verified=False`；下表保留各历史批次的 hook/verified 状态，不代表当前生产授权；当前默认门控及显式 unlock_all_sites 例外见插件主 AGENTS.md。
- 凭证与证据来源是两个维度：凭证术语为 cookie/password/api_key，证据来源为 page_message/response_json。OpenCD 使用 cookie + response_json；蜂巢对照为 api_key + response_json，不在本插件添加论坛站。旧凭证枚举 api 的统一改名不在本批范围。
- `RecordSpec.source=page_message` 只匹配唯一消息元素；`response_json` 按 `response_field` 取顶层标量并以类型和值精确匹配 `status_map`，不把任意非空值当成功。
- `pre_read_spec` 用于安全页面前读及只读核验；`signed_marker` 同时用于安全新页回读；页面 JSON 不冒充动作回执。response_json 声明不继承通用 POST；六站真实动作、回执接线与无条件安全回读已在 C4 实现。
- `batch2-message-pending-calibration` 是历史合成占位，当前 NexusSignin 默认回退消息链（可由 use_default_message 关闭），不是生产选择器；`未签到` 为合成回归输入。没有证据保持 unconfirmed，不从整个页面、表单消失或未知 JSON 值推断成功。
- 本表的 standard-declared 说明证据声明可表达，不表示提交协议已实现；special-hook 说明提交动作需站点钩子。两者与 verified 是独立维度。

## B1-6 六站对照（3.6.6）

| site | V2 判定依据与流程 | 本轮声明 / 状态 | 待实现或校准 |
| --- | --- | --- | --- |
| opencd | 首页 show-log 链接；frmSignin/imagehash/img；六位 OCR；POST plugin_sign-in.php?cmd=signin 的 state=success | cookie + response_json(state)；standard-declared(response_json)；安全前读 / + show-log；hook_implemented=True | 已实现，待生产校准：六位 OCR、state=success 与 show-log 回读 |
| phoenixpt | attendance.php CAPTCHA；通用简繁成功/重复文案 | page_message；special-hook；hook_implemented=True | 已实现，待生产校准：imagehash/imagestring OCR、消息节点 |
| pterclub | GET attendance-ajax.php 即签到；JSON status="1"；旧版其余状态全部当已签 | cookie + response_json(status)；standard-declared(response_json)；安全前读 /；hook_implemented=True | status="0" 单独不证明已签，保留 unconfirmed；已实现，待生产回执校准 |
| pttime | GET attendance.php 即签到；签到成功/已签到/无需再签；响应示例仅 body 文本 | page_message；special-hook；安全前读 /；hook_implemented=True | 已实现，待生产校准：安全首页 scoped 消息；不以 body 全页替代消息选择器 |
| retrotoon | csrf_token+claim POST；今日 calendar claimed class 或 Daily Reward 卡片完成文案 | page_message；standard-declared；唯一 rt-form-card Daily Reward 节点；检查 CSRF/claim | 日历 class、大小写与真实页面校准；无条件 GET 回读已保留 |
| siqi | imagehash/imagestring OCR；“这是您的第…次签到，已连续签到…天”/“您今天已经签到过了”/attend-success-effect | page_message；special-hook；hook_implemented=True | OCR 与 class 钩子已实现，待生产校准；完整奖励正则尚未用于消息判定 |

## 全量重审（3.6.5 基线实际 27 站，非最初口径 22）

逐站核对 `sites/<id>.py` 及继承的 attendance helper；“原声明”指修正前。安全路径 attendance 指 GET 展示表单，/ 或 index 指安全首页；全部结论仅为源码重审，未请求真实站点。

| site | V2 原版判定依据 | 原声明 / 是否需修正 | 本轮修正或保留理由；安全前读 |
| --- | --- | --- | --- |
| 52pt | 今天已经签过到了；数字+点魔力值正则；随机问答 | page_message 含虚构今日已签到/签到成功；需修正 | 删除虚构成功词，只保留确证重复词；奖励解析与随机问答已实现，待生产消息校准；现 hook_implemented=True；bakatest |
| agsvpt | 签到成功/簽到成功；已经签到/已經簽到/今天已经签到/今日已签到/請勿重複刷新 | standard-declared；无需修正 | 文案一致；消息节点仍待校准；attendance |
| baozi | 通用 CAPTCHA helper 四个简繁成功词、十一重复词 | special-hook，缺变体与 hook 标志；需修正 | 补全 helper 文案；现 hook_implemented=True；attendance |
| btschool | 首页每日签到入口消失；GET index.php?action=addbonus | 错把动作 URL 当前读，虚构成功词；需修正 | 前读改 /；清空无依据成功映射，不以缺失入口推断；现 hook_implemented=True |
| chdbits | 同 52pt：重复词、数字奖励、随机问答 | page_message 含虚构成功词；需修正 | 删除虚构词；奖励解析与随机问答已实现，待生产消息校准；现 hook_implemented=True；bakatest |
| dongying | 通用 CAPTCHA helper 简繁成功/重复文案 | special-hook，缺变体；需修正 | 补齐全部 helper 文案；attendance |
| dstudio | POST 后表单消失且签到成功/签到已得；重复词 | standard-declared 缺签到已得；需修正 | 补签到已得；不新增旧宽泛获得/连续签到作为回读判据；attendance |
| haidan | GET signin.php 后 index.php 的 value="已经打卡" | 仅占位消息；需修正 | 使用 input[value="已经打卡"]；special-hook；index.php |
| haitang | action=sign POST，回读成功/本次签到获得/今日已签到等 | 既有试点 page_message；无需修正 | 映射覆盖原版；保持试点与无条件回读，不宣称真实选择器已核验；attendance |
| hares | GET attendance.php?action=sign；JSON code=0 成功，code=1 示例重复 | 误用 page_message 占位；需修正 | response_json code 精确数值0；未知非0不猜已签；hook_implemented=True；/ |
| hdarea | POST sign_in.php action=sign_in；此次签到您获得/请不要重复签到哦 | special-hook；无需修正 | 文案一致；/ |
| hdbao | POST；签到成功/签到已得/获得/连续签到及重复词 | standard-declared；无需修正 | 文案一致，宽泛词限合成指定消息节点，生产仍待校准；attendance |
| hdchina | 首页确切已签到 anchor；Cookie刷新+x-csrf POST；JSON state 示例 success | 只有首页 page_message，漏 JSON；需修正 | response_json state 精确success；独立 pre_read_spec 保留 anchor；hook_implemented=True；index.php |
| hdcity | GET /sign 即签到；本次签到获得魅力/Got extra/已签到/Already checked in today | special-hook；无需修正 | 中英文一致；前读 / 避免动作 |
| hdsky | 首页已签到；image_code_ajax 验证码；showup JSON success | 已实现试点 OCR；回读 page_message | 无需修改执行语义：JSON 是动作响应，当前试点特意以新首页已签到确认，不拿提交回执代替回读；index.php |
| hdupt | span#yiqiandao 存在；动作 GET added.php?action=qiandao 任意数字响应 | 错将未使用文本常量当消息，漏 marker；需修正 | 补已签 marker，清空伪消息映射；GET hook 已实现，数字响应不作证据；/ |
| hhanclub | GET attendance 即签到，需 Referer；签到成功/本次签到获得/已连续签到与重复词 | special-hook；无需修正 | 文案一致，前读 / 避免动作 |
| kelu | 通用 CAPTCHA helper 简繁文案 | special-hook；无需修正 | 全部变体一致；attendance |
| lajidui | 独立 OCR；签到成功/签到已得/获得/连续签到与重复词 | special-hook；无需修正 | 文案一致，消息节点合成且 gate 关闭；attendance |
| luckpt | 普通 POST；四个成功词与四个重复词 | standard-declared；无需修正 | 文案一致，不套 M-Team 协议；attendance |
| mteam | Authorization Token POST updateLastBrowse；HTTP 200，仅保活 | 自定义 SiteModule，空签到映射；无需修正 | 不虚构签到；无请求返回 skipped；api_key 为凭证术语，旧枚举 api 留收尾统一 |
| muxuege | POST 后表单消失+签到成功/签到已得/连续签到/本次签到获得 | standard-declared；无需修正 | 文案覆盖；不以表单消失单独判成功；attendance |
| naturept | 通用 CAPTCHA helper 简繁文案 | special-hook；无需修正 | 全部变体一致；attendance |
| nexushd | 直接 POST signin.php action=post/content；本次签到获得/你今天已经签到过了 | special-hook；无需修正 | 文案一致；前读 / 不访问动作页 |
| novahd | 通用 CAPTCHA helper 简繁文案 | special-hook；无需修正 | 全部变体一致；attendance |
| opencd | show-log 已签标记 + JSON state + frmSignin OCR | 错写无消息即无判定依据；需修正 | 见本批六站表；standard-declared(response_json)，OCR hook_implemented=True；/ |
| oshen | 通用 CAPTCHA helper 简繁文案 | special-hook；无需修正 | 全部变体一致；attendance |

## 验证边界
- 合成夹具覆盖 JSON 精确类型/值（false 不得匹配0）、已签 marker、无证据、CSRF POST 及异常后回读、所有特殊站双 gate；不把离线通过当生产签到验收。
- 52PT/CHDBits/BTSchool/HDUpt 不再用虚构成功文本凑三态。未实现协议应保持 unconfirmed；PTerClub/Hares 的旧宽泛 else 不迁移。
- 设计取舍见 `.agents/notes/implemented/architecture/2026-10-22-signincenter-response-evidence.md`；本批不改 dist、不发送真实站点请求。

## B1-7 十四站对照（3.7.0）

来源徽标口径：插件适配 = 插件内部有适配、但 MP 的 PT 站点数据（站点管理/SiteOper）没有登记的站点；MP 站点 = 站点管理已登记（站点名取 MP 登记名）；自定义站点 = 用户页面手工添加。分类与 native/verified/hook 门控独立，不改变既有 registry 逻辑。

全部从 `plugins.v2/autoptcheckin/sites/` 原版及其 helper 核对；native=True、verified=False。当前 hook 状态已按 C1–C7 更新，不因 hook 完成开放执行。下表的未签到合成文本只用于回归，非生产证据。

| site | V2 判定依据与流程 | 分类 / 声明 | 安全前读与待办 |
| --- | --- | --- | --- |
| darkland | Cffi 浏览器指纹首页；登录标记、Cloudflare/登录表单 | special-hook(login-only)；空签到映射；signin_not_applicable | C6 hook_implemented=True（签到不适用）；任何签到入口 skipped；login_capable=True，登录使用原生 parse_login |
| digitalcore | status API 的 user.id 或 user.username | special-hook(login-only)；空签到映射；signin_not_applicable | C6 hook_implemented=True（签到不适用）；不把用户信息当签到；login_capable=True，登录使用原生 parse_login |
| playlet | 通用 CAPTCHA helper 简繁成功/重复词 | special-hook；page_message 合成节点 | attendance；imagehash/imagestring OCR 已实现，待生产消息/表单校准 |
| ptzone | 无验证码 POST；四个简繁成功词、七个重复词 | standard-declared；page_message 合成节点 | attendance；通用表单及无条件新页回读，待校准消息节点 |
| shaobaoyuan | 通用 CAPTCHA helper 简繁成功/重复词 | special-hook；page_message 合成节点 | attendance；imagehash/imagestring OCR 已实现，待生产消息/表单校准 |
| soulvoice | 通用 CAPTCHA helper 简繁成功/重复词 | special-hook；page_message 合成节点 | attendance；imagehash/imagestring OCR 已实现，待生产消息/表单校准 |
| tjupt | attendance anchor 今日已签到；首次/连续/重新签到数字奖励正则；豆瓣图片比对 | special-hook；只保留已签 anchor，不把正则裁成宽泛词 | attendance；C5 hook_implemented=True；图片 aHash、answer 文本缓存、豆瓣比对、数字奖励及新 anchor 回读；verified=False |
| ttg | 首页绿色 b 已签到；提交后“您已连续签到”/“亲，您今天已签到过，不要太贪哦” | special-hook；独立 pre_read_spec + 消息占位 | /；signed_timestamp/signed_token POST signed.php 已实现，待生产参数/消息校准 |
| tu88 | 通用 CAPTCHA helper 简繁成功/重复词 | special-hook；page_message 合成节点 | attendance；imagehash/imagestring OCR 已实现，待生产消息/表单校准 |
| u2 | showup anchor 四种语言；POST 回执 JS 跳转 | special-hook；只保留 anchor；不以 JS 跳转冒充新页成功 | showup.php；9点时段、签到表单 _csrf/req/hash/form、图片选项与提交已实现，待生产校准 |
| vclib | 通用 CAPTCHA helper 简繁成功/重复词 | special-hook；page_message 合成节点 | attendance；imagehash/imagestring OCR 已实现，待生产消息/表单校准 |
| yema | GET api/consumer/checkIn；JSON success 布尔 | special-hook；response_json(success)，精确布尔 | /；动作 GET 与布尔比较已实现，待生产校准；bool 不转成数字1 |
| yzyy | .signbtn 今日已打卡/点击打卡；本人行；同 Session 动态 sign token | special-hook；限定唯一 .signbtn 消息 | plugin.php?id=zqlj_sign；同 Session/Cookie 同步、动态链接、无条件按钮/本人行回读已实现，待生产校准；不移植响应兜底 |
| zhuque | CSRF + fireGenshinCharacterMagic；JSON status=200、data.bonus | api-evidence；response_json(status)，精确数值200 | /；这是技能动作回执而非独立每日签到；动作与安全回读已实现，待生产校准 |

三态例外：tjupt/u2 的状态只有已签标记，未签/未知输入均 unconfirmed；Yema success 按精确布尔 true→signed、false→unsigned，未知类型保持 unconfirmed；登录站任何内容均不生成签到结果；朱雀非200无充分未签证据，保留 unconfirmed。不编造 unsigned 生产判据。

## B1-8：批次 2 输入（特殊钩子盘点）

本表保留 B1-8 的全部输入，按 C7 实际源码更新状态。旧“24站”口径不准确：25 个分组行、37 个站点 ID；34 个签到 hook + DarkLand/DigitalCore/M-Team 三个签到不适用项。C1–C6 漏分配的 52pt/chdbits/yzyy 已在 C7 补齐。hook 完成不等于生产校准完成。

| 站名 / ID | hook 类型 | 实现要点 | hook 状态 | 待实现或校准 |
| --- | --- | --- | --- | --- |
| 52PT / 52pt、CHDBits / chdbits | 随机问答 | bakatest 参数、数字奖励正则、保留明确重复文本 | hook_implemented=True（C7） | 已实现，待生产校准（见分组校准清单） |
| 包子 / baozi、冬樱 / dongying、可乐 / kelu、NaturePT / naturept、NovaHD / novahd、OshenPT / oshen、凤凰PT / phoenixpt | attendance CAPTCHA | imagehash/imagestring、OCR、消息节点校准；提交后不自动重试 | hook_implemented=True（C1） | 已实现，待生产校准（见分组校准清单） |
| PlayLet / playlet、烧包乐园 / shaobaoyuan、聆音Club / soulvoice、TU88 / tu88、VC-Lib / vclib | attendance CAPTCHA | 同通用 CAPTCHA 协议，但逐站核对生产页面 | hook_implemented=True（C1） | 已实现，待生产校准（见分组校准清单） |
| 垃圾堆 / lajidui、思齐 / siqi | 独立 OCR | 独立验证码参数；siqi 完整奖励正则及 attend-success-effect class | hook_implemented=True（C2） | 已实现，待生产校准（见分组校准清单） |
| BTSchool / btschool | 副作用 GET | index.php?action=addbonus；入口消失不足以证明成功，需回读确证 | hook_implemented=True（C2） | 已实现，待生产校准（见分组校准清单） |
| 海胆 / haidan | 副作用 GET | signin.php；回读 index.php 的已经打卡 input | hook_implemented=True（C2） | 已实现，待生产校准（见分组校准清单） |
| HDArea / hdarea | 专属 POST | sign_in.php action=sign_in；奖励/重复文案 | hook_implemented=True（C3） | 已实现，待生产校准（见分组校准清单） |
| HDCity / hdcity | 副作用 GET | /sign；安全首页回读，中英文确证消息 | hook_implemented=True（C2） | 已实现，待生产校准（见分组校准清单） |
| HDUpt / hdupt | 副作用 GET + 数字回执 | added.php?action=qiandao；回读 yiqiandao marker，不猜任意数字含义 | hook_implemented=True（C2） | 已实现，待生产校准（见分组校准清单） |
| 憨憨 / hhanclub | 副作用 GET + Referer | attendance.php；安全首页、Referer、消息校准 | hook_implemented=True（C2） | 已实现，待生产校准（见分组校准清单） |
| NexusHD / nexushd | 专属 POST | signin.php action=post/content；安全首页回读 | hook_implemented=True（C3） | 已实现，待生产校准（见分组校准清单） |
| PTTime / pttime | 副作用 GET | attendance.php；动作 body 文本不能冒充 scoped 新页面证据 | hook_implemented=True（C2） | 已实现，待生产校准（见分组校准清单） |
| TJUPT / tjupt | 豆瓣图片问答 | 图片 hash、answer 选项、外部查询与缓存、数字奖励正则 | hook_implemented=True（C5） | 已实现，待生产校准（见分组校准清单） |
| TTG / ttg | 动态参数 POST | signed_timestamp/signed_token，signed.php；绿色 b 回读 | hook_implemented=True（C3） | 已实现，待生产校准（见分组校准清单） |
| U2 / u2 | 特殊表单/图片选项 | 9点限制、作用域 _csrf、req/hash/form、提交选项；JS 回执不代替回读 | hook_implemented=True（C3） | 已实现，待生产校准（见分组校准清单） |
| yzyy | Discuz 动态链接 | 同 Session、Cookie 同步、sign token、本人记录与按钮回读 | hook_implemented=True（C7） | 已实现，待生产校准（见分组校准清单） |
| DarkLand / darkland | 仅登录指纹 | 浏览器指纹客户端、登录标记、CF/限流；签到不适用 | hook_implemented=True；signin_capable=False（C6） | 签到不适用；模拟登录使用原生 parse_login |
| DigitalCore / digitalcore | 仅登录 API | status API user.id/username；签到不适用 | hook_implemented=True；signin_capable=False（C6） | 签到不适用；模拟登录使用原生 parse_login |
| M-Team / mteam | API 保活 | Token updateLastBrowse，仅保活，不能生成签到证据 | hook_implemented=False；保活不适用（非遗漏） | 仅保活；signin 保持 skipped，不开放保活动作 |
| 夜猫 / yema | 布尔 API 回执 | 精确 bool 比较、checkIn 动作与安全回读 | hook_implemented=True（C4） | 已实现，待生产校准（见分组校准清单） |
| Hares / hares | API证据/动作 GET | code 数值0；未知非0不当已签；安全首页前读 | hook_implemented=True（C4） | 已实现，待生产校准（见分组校准清单） |
| HDChina / hdchina | API证据/CSRF POST | Cookie 刷新、x-csrf、state=success；首页已签 anchor 回读 | hook_implemented=True（C4） | 已实现，待生产校准（见分组校准清单） |
| OpenCD / opencd | API证据/OCR POST | frmSignin/imagehash/img、六位 OCR、state=success、show-log 安全回读 | hook_implemented=True（C4） | 已实现，待生产校准（见分组校准清单） |
| PTerClub / pterclub | API证据/动作 GET | attendance-ajax.php status 字符串1；0 不单独证明重复 | hook_implemented=True（C4） | 已实现，待生产校准（见分组校准清单） |
| 朱雀 / zhuque | API证据/技能动作 | x-csrf-token、JSON POST、status 数值200/data.bonus；保留技能语义 | hook_implemented=True（C4） | 已实现，待生产校准（见分组校准清单） |

已实现 HDSky OCR 试点不列为待实现 hook；海棠试点不变。普通声明站仍需真实消息节点校准，不在特殊钩子清单重复列出。所有真实请求和生产启用另需授权。

## C1：attendance CAPTCHA hook（3.8.1）

12 站 V2 副本均仅覆盖域名，无字段、Referer 或成功文案差异；共用 helper 的 4–6 位 alnum，ddddocr 未识别才降级 ocrhelper。图片下载由 ctx.ocr 执行；OCR 和提交均使用 attendance 页 Referer。提交后不重试，始终新 GET 回读。

| site | hook 状态 | verified | 遗留校准 |
| --- | --- | --- | --- |
| baozi | hook_implemented=True（solve_captcha） | False | 生产消息节点；实际表单/验证码图与回读页面 |
| dongying | hook_implemented=True（solve_captcha） | False | 生产消息节点；实际表单/验证码图与回读页面 |
| kelu | hook_implemented=True（solve_captcha） | False | 生产消息节点；实际表单/验证码图与回读页面 |
| naturept | hook_implemented=True（solve_captcha） | False | 生产消息节点；实际表单/验证码图与回读页面 |
| novahd | hook_implemented=True（solve_captcha） | False | 生产消息节点；实际表单/验证码图与回读页面 |
| oshen | hook_implemented=True（solve_captcha） | False | 生产消息节点；实际表单/验证码图与回读页面 |
| phoenixpt | hook_implemented=True（solve_captcha） | False | 生产消息节点；实际表单/验证码图与回读页面 |
| playlet | hook_implemented=True（solve_captcha） | False | 生产消息节点；实际表单/验证码图与回读页面 |
| shaobaoyuan | hook_implemented=True（solve_captcha） | False | 生产消息节点；实际表单/验证码图与回读页面 |
| soulvoice | hook_implemented=True（solve_captcha） | False | 生产消息节点；实际表单/验证码图与回读页面 |
| tu88 | hook_implemented=True（solve_captcha） | False | 生产消息节点；实际表单/验证码图与回读页面 |
| vclib | hook_implemented=True（solve_captcha） | False | 生产消息节点；实际表单/验证码图与回读页面 |

## C2：副作用 GET 与独立 OCR（3.8.2）

以下 8 站 hook_implemented=True，verified 全部保持 False；上方对照表已同步当前 hook 状态。动作只尝试一次，异常仍无条件安全回读，动作响应不作新页面证据。

| site | 已实现协议 / 安全前读及回读 | 遗留校准 |
| --- | --- | --- |
| btschool | GET index.php?action=addbonus；/ | 2026-10-23 用户裁决：登录态首页入口消失即已签，成功文本二选一即可——既有 read_before/read_after（ALREADY→SUCCESS）已符合；待采样补成功文本映射 |
| haidan | GET signin.php；index.php | input[value="已经打卡"] 的生产结构 |
| hdcity | GET /sign；/ | 中英文映射保留，安全首页消息节点仍为合成占位 |
| hdupt | GET added.php?action=qiandao；/ | span#yiqiandao 生产回读；数字回执不作证据 |
| hhanclub | GET attendance.php + 首页 Referer；/ | 安全首页消息节点仍为合成占位 |
| pttime | GET attendance.php；/ | scoped 新页消息节点仍为占位，body 文本不作证据 |
| lajidui | attendance GET → imagehash/imagestring POST → attendance GET；4–6 位 OCR | 实际表单、验证码图、生产消息节点 |
| siqi | attendance GET → imagehash/imagestring POST → attendance GET；至少4位 OCR | 实际表单及 class；完整奖励正则保留声明，尚未用于消息判定 |

SiQi 的 attend-success-effect 按完整 class token 判定前读和回读，不匹配整页文字或 class 子串。BTSchool 三态/重复输入均未确认；海胆/HDUpt 无未签生产判据，缺 marker 仍未确认。OCR 两站沿用 V2 POST，不误改为动作 GET。未发送真实请求，不改 dist。

## C3/C4：专属 POST 与 API 动作（3.8.3）

以下十站 hook_implemented=True，verified 均保持 False；上方 B1 表保留原版依据，hook 状态已同步。所有动作仅一次，异常/取消发生在动作中也无条件安全回读，不重放动作。

| site | 已实现动作 / 安全回读 | 遗留生产校准 |
| --- | --- | --- |
| hdarea | POST sign_in.php action=sign_in；/ | 奖励/重复消息的生产节点仍为占位 |
| nexushd | POST signin.php action=post/content=''；/ | 首页消息的生产节点仍为占位 |
| ttg | 首页唯一 signed_timestamp/signed_token → POST signed.php；/ 绿色 b | 动态参数实际脚本、绿色 b；消息节点仍为占位 |
| u2 | 9点后 scoped _csrf/req/hash/form + 随机图片选项 POST；showup.php | 表单与四语言 anchor；随机选项沿用 V2，不声称能识图；JS 不作证据 |
| hares | GET attendance.php?action=sign；/ | code 数值0的真实回执；非0未确认 |
| hdchina | 执行级 Cookie 仅保留 hdchina 前读并接收刷新 Cookie；x-csrf → POST csrf；index.php | Cookie 刷新、CSRF、state=success、已签 anchor |
| opencd | frmSignin/imagehash/img 六位 OCR（ddddocr→ocrhelper）POST cmd=signin；/ | 表单/验证码、state=success、show-log anchor |
| pterclub | GET attendance-ajax.php；/ | status 字符串1的回执；0不猜重复 |
| zhuque | x-csrf-token + JSON POST fireGenshinCharacterMagic；/ | status 数值200与 data.bonus；仍为技能动作语义 |
| yema | GET api/consumer/checkIn；/ | success 精确布尔；false→unsigned（V2 无重复分支） |

API 站优先采用新安全页已签证据，否则采用动作 JSON 的精确字段；安全回读失败不丢弃明确 JSON 回执。前读/只读页即使是 JSON 也不当动作回执。RecordSpec 布尔键不与数值0/1互换；缺失、错误类型、未知值为 unconfirmed。合成三态只验证执行契约，不表示十站生产校准完成；TJUPT 由 C5、52pt/chdbits/yzyy 由 C7 补齐。dist 未改，无真实请求。

## 批次 2 完成（C7，3.8.5；仅离线实现闭环）

- C1：12 站通用 CAPTCHA；C2：6 站副作用 GET + 2 站独立 OCR（不是8站GET）；C3：4站专属 POST；C4：6站 API；C5：TJUPT 图片问答；C6：2站登录专用不适用；C7：52pt/chdbits 随机问答、yzyy Discuz 动态链接。M-Team 保活例外保持 hook_implemented=False、signin skipped。B1-8 所有37个ID均已核对，无未归类遗漏。
- 52pt/chdbits 共用 BakatestSignin：唯一问答表单、questionid、随机 choice[]、V2 usercomment/wantskip，单次 POST 后无条件回读；数字点魔力值仅作奖励展示，状态仍依赖新页 scoped 消息。生产消息节点仍占位，不把整页奖励正则冒充状态。
- yzyy：只接受唯一 .signbtn 下同源 plugin.php 的动态 sign token；执行边界在站点锁内创建 Session，finally 关闭，刷新 Cookie 同步到执行级字典；动作异常仍回读按钮文本与 tb_my 本人行，UID 来自 um 导航，冲突保持未确认，不使用动作响应兜底。
- 本批已实现但 record_spec 仍含合成节点的24站：baozi、dongying、kelu、naturept、novahd、oshen、phoenixpt、playlet、shaobaoyuan、soulvoice、tu88、vclib、btschool、hdcity、hdupt、hhanclub、pttime、lajidui、siqi、hdarea、nexushd、ttg、52pt、chdbits。其中 hdupt/siqi/ttg 另有已签 marker；BTSchool 空映射不能确认成功。其余消息节点、表单及 CAPTCHA 仍待真实采样校准。
- 非占位的 haidan、u2、tjupt、yzyy 仍需生产页面/本人行/时段/图片问答核验；hdchina、opencd、pterclub、zhuque、yema（hares 站点已关闭，2026-10-22 移除） 仍需真实 JSON 类型/值、CSRF/OCR/Cookie 与安全页核验。无合成节点不代表生产 verified。
- 非本批普通声明站 agsvpt、dstudio、hdbao、luckpt、muxuege、ptzone 也仍有合成 record_spec；不适用站 darkland/digitalcore/mteam 的空占位不属于签到校准任务。全部非试点 verified 保持 False；未发送真实请求，未改 dist，版本收尾不开放执行。

## 批次 2 校准实测（2026-10-21，本地 MP + qnap Cookie）

以下为本轮收尾接收的既有实测汇总；收尾仅归档，不重发真实站点请求，不以汇总代替逐站提交验收。历史 C1–C7 的“未发送真实请求”仅描述当时离线实现阶段。

| 结果 | 数量 | 语义 |
| --- | --- | --- |
| already | 22 | 只读页面已有确证已签消息/标记；不是本轮新提交成功，也不自动提升 verified |
| unconfirmed | 13 | 证据不足，不能解释为签到失败或确实未签；需后续授权采样/校准 |
| auth_failed | 4 | 凭据/认证未通过，不证明签到动作失败 |
| 合计 | 39 | 本次回读样本口径，不等于37个特殊站ID或27站全量重审清单 |

- 规则放宽：默认链标题选择器采用 contains(.) 而非仅直接 text()，覆盖内嵌标签；纳入打卡及简繁变体。多选择器空、歧义或无效时续扫，仍要求唯一非空消息；首个非空消息无状态匹配时保持 unconfirmed，不遍历整页寻找成功词。具体判定契约以插件主 AGENTS.md 为准。
- 四站 signed_marker 校准：hdsky 的 td 含“[已签到]”；haitang 的 span/b“今日已签到”或 faqlink“签到已得”；hdarea 的 span#sign_in_done；hdcity 的 href="sign" anchor 含“已签到”。安全前读及提交后的新页均可使用；不把动作响应当新页。
- 52pt/chdbits/tjupt/pttime 本阶段运维决策为仅模拟登录，不执行签到；已实现 hook 不因此删除，也不宣称它们已完成生产提交验证。该选择是操作范围，不是源码强制禁签能力。
- ptzone/vclib 当时维护中，保留待恢复后校准；不以维护页或未确认结果判定签到失败。
- unlock_all_sites 与 signin_applicable 的当前契约统一见插件主 AGENTS.md；unlock 仅供显式校准放行，既有回读结果不等于批量真实签到授权。
- local_cookie 候选：插件适配站无宿主 Cookie 时，可按规范化域名（小写、去 www.）从 custom_sites_data 的 cookie 取值；managed_site 优先。不得将 Cookie 写入本表或测试，cookiecloud 独立候选接线留批次3。

## 通用声明站（3.10.0）

- generic.py 从 generic_sites.json 生成模块级 NexusSignin 子类，复用现有 registry 发现；60站均未生产校准，verified=False，沿用标准 attendance 与默认消息链。
- 输入导出实际 sign_sites=88、login_sites=133，并集133；Vc-Lib 管理站与 custom 为同域，去重后132域。按浏览器 Cookie dump 中 c_secure_pass 域名证据筛选；无该证据不等于已证明非 NexusPHP，保守排除。
- 生成器 scripts/build_generic_sites.py 只输出 id/name/url/attendance_path；域名去 www、去最后一段 TLD、点和连字符转下划线；ID冲突加 _g。
- 明确别名 pterclub.net→pterclub、kp.m-team.cc→mteam，禁止生成重复通用类；darkland/digitalcore/mteam 排除。custom 数字 ID 的 name/url/id 已由 registry 原样输出。
- 排除清单（27域，缺 c_secure_pass 证据，无 native 签到声明；登录走通用页面链，边界见插件主 AGENTS.md）：FileList (`https://filelist.io/`)、海豚 (`https://dicmusic.com/`)、Anthelion (`https://anthelion.me/`)、JPopsuki (`https://jpopsuki.eu/`)、Nebulance (`https://nebulance.io/`)、青蛙 (`https://www.qingwapt.com/`)、星空 (`https://star-space.net/`)、Aither (`https://aither.cc/`)、猪猪 (`https://piggo.me/`)、我堡 (`https://ourbits.club/`)、春天 (`https://springsunday.net/`)、BeyondHD (`https://beyond-hd.me/`)、龟站 (`https://kamept.com/`)、海豹 (`https://greatposterwall.com/`)、天雪 (`https://skyeysnow.com/`)、AnimeZ (`https://animez.to/`)、梓喵 (`https://azusa.wiki/`)、莫妮卡 (`https://monikadesign.uk/`)、IPT (`https://iptorrents.com/`)、HD-Space (`https://hd-space.org`)、AsianCinema (`https://eiga.moi`)、bitporn (`https://bitporn.eu`)、NordicQuality (`https://nordicq.org`)、bakabt (`https://bakabt.me`)、seedpool (`https://seedpool.org`)、clearjav (`https://clearjav.com`)、dreadvault (`https://dreadvault.org`)。
- 遗留：通用站逐站核验实际表单/消息与验证码差异；不以 Cookie 名存在替代生产签到验证，不自动开启 verified。

## 答题类站点说明（2026-10-22）
- chdbits/tjupt 为答题类签到（随机问答/豆瓣图片），误答有账号风险，**不建议启用答题功能**；52pt 已改为滑块签到（HTTP 无法完成，须 Browserless/Playwright 实现，暂缓）；registry signin_applicable=False，均仅保留模拟登录。
- u2 为随机图片选项（非知识问答），保留签到能力。BakatestSignin 为 52pt/chdbits 共用的 bakatest.php 随机问答实现。
- hares 站点已关闭，native 模块与声明移除（旧桥副本保留）。

## D1 声明下沉（3.11.0）

- 将只有协议参数差异的20个专属模块并入 generic_sites.json，复用 C1/C2/C3/C4 执行器而不另造提交链；verified、动作至多一次、异常后安全回读和未确认语义不变。不迁移 Cookie/CSRF/动态问答等专属流程。
- CAPTCHA：baozi/dongying/kelu/naturept/novahd/oshen/phoenixpt/playlet/shaobaoyuan/soulvoice/tu88/vclib；GET：hdupt/hhanclub/hdcity/haidan/pttime/btschool；静态 POST：hdarea/nexushd。kelu 的简繁 status_map 顺序原样保留，海胆安全路径仍为 /index.php，既有 signed_marker 保留。
- 可选字段：captcha 委托 attendance_captcha；action_get + 必填 safe_read_path 选择 GetSignin，referer=true 使用站点首页；form_data + form_path 生成独立表单数据副本；response_json + action_path + 必填 safe_read_path 选择 ApiSignin（本轮没有真实站采用此新声明）；use_default_message=false 关闭默认链；signin_capable=false 返回 skipped 且 registry 展示不适用。message/status_map/success_texts/signed_marker 保留站点证据覆盖。
- response_json.status_map 的 object 仅表示字符串键；typed pairs 如 [[0,"signed"]] 或 [[true,"signed"],[false,"unsigned"]] 保留数值/布尔类型，禁止数字与布尔相等键共存导致 Python dict 覆盖，不从字符串键猜测类型。
- 原65条通用声明中 nexushd/shaobaoyuan/vclib 与专属ID重复，按原 registry 最终专属行为覆盖（NexusHD 保留 v6.nexushd.org）；合并后82条通用声明。native 总数108守恒，专属 .py 从47减至27（含既有同ID声明，不等于唯一站点数）。不要运行只输出基础字段的旧导出脚本覆盖此行为表。
- darkland/digitalcore/mteam 保留专属，新增仅登录字段不迁移其协议；btschool 明确下沉。hdsky/haitang/tjupt/chdbits/yzyy/u2/hdchina/opencd 及其余未列入下沉的专属模块不动，rousi/sunnypt 集成不动；hdchina URL 本轮不改。
- 离线回归迁移 C1/C2/C3 三态至 generic 参数化，并保留原协议异常/取消/不重试测试；本轮不发送真实请求、不改 dist。生产消息/表单/CAPTCHA 与 hdchina 域名修正留后续授权，离线通过不提升 verified。
