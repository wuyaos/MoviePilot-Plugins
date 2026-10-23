# Agent Note: 签到证据来源与凭证分离

Status: implemented

## Problem

仅允许消息文本会丢失旧适配器已确证的 JSON 回执与已签标记，OpenCD 因此被错误标成无判据。源码重审另发现 BTSchool 把副作用 GET 放在前读，以及早期特殊站缺少独立 hook 门控。

## Decision

RecordSpec 分为 page_message 与 response_json；后者通过 response_field 选择顶层字段，以 status_map 精确类型和值映射，不使用 truthiness。凭证 cookie/password/api_key 与证据来源独立；本批不迁移旧 api 凭证枚举。

NexusSignin 的 read_before 支持独立 pre_read_spec 和显式 signed_marker，签到前读与只读执行共享此入口。首页上的 JSON 不作为动作回执；JSON 站点不使用通用表单提交。OpenCD、Hares、HDChina、PTerClub 的动作由 ApiSignin 接线；hook_implemented=True 不替代 verified 门控。动作后无条件安全回读，优先采用页面已签证据，否则采用明确 JSON 回执；回读不可达也保留有效动作回执，不重试动作。

此决定部分取代[原生双轨笔记](2026-10-21-signincenter-native-dual-track.md)中“OpenCD 只能等待消息文本校准”的决定。其双轨、资源注入与门控理由仍有效。活跃笔记审计：原生双轨属于部分重叠并互链；论坛 F1/F2 属不同插件，不改其凭证执行器。

## Alternatives considered

- 保留纯消息模型：无需改框架且便于统一回读，但会误判确证的 JSON/链接标记为没有判据，因此保留默认消息模型并增加最小证据来源字段。
- 沿用旧版任意非零/非空值或 else 即已签到：兼容旧结果，但未知错误也可能被报告成功；PTerClub status=0 与 Hares 非0不单独映射，未确认不等于失败。
- 本批实现全部 OCR/GET 动作：可以让声明立即执行，但超出离线迁移范围；保留双 gate，真实页面和回执接线交批次2。

C3/C4 经授权扩展 RecordSpec 接受 bool 键，仍按 type 与值同时匹配；Yema true→signed、false→unsigned。V2 yema 的 false 进入失败分支，无“已经签到”例外；不把 true 转成数字1。Python Mapping 无法同时表示相等的 bool/int 键，因此每个站声明应使用其协议实际类型；读取仍精确检查类型。DarkLand/DigitalCore 只声明登录能力，signin 返回不适用；朱雀保留技能动作 status=200 回执语义，不虚构每日签到。yzyy 是既有 V2 成员，迁移范围不因 Discuz 技术栈而移至论坛插件。

## Consequences

B1-6、基线27站重审、B1-7十四站与批次2钩子输入表位于 sites/native/AGENTS.md。页面占位选择器仍不能证明生产结构，52PT/CHDBits 数字奖励、RetroToon 日历 class、SiQi 完整正则等留在明确的特殊协议边界内。HDSky 已实现试点继续依赖无条件首页回读，不因其动作返回 JSON 就更改成功优先级。

离线测试验证精确 JSON 类型、未知输入、前读标记、特殊站双 gate、RetroToon CSRF POST 及异常后回读。不得将解析测试通过描述为真实站点成功；不接触站点凭证或网络。B1-7 追加授权仅调整调度/凭据区自适应列宽并重建 dist，不改变站点执行门控。

C2 实现六站单次动作 GET 和两站独立 OCR POST；复用 Nexus 的无条件安全回读，显式 marker 也可用于新页面确认。SiQi class 使用完整 token，完整奖励正则仅保留声明。OCR 共用字段/图片解析，但 SiQi 无最大长度、垃圾堆最多六位，POST 只发送 V2 两字段。不迁移旧版动作响应/body/数字成功推断：BTSchool 缺正向证据时历史恒为 unconfirmed，无法用重复签到夹具制造 ALREADY。此例外与 OCR 原版 POST 已经范围裁决确认，生产校准前 verified 保持关闭。

C3/C4 的 Cookie 刷新留在 NativeHttpClient 的执行级内存字典，不回写凭证存储；HDChina 前读前只保留 hdchina 项，随后吸收服务端 Cookie，避免旧临时 Cookie 破坏 CSRF。扩展 headers/JSON POST 服务朱雀真实协议，不创建新客户端或引入旧桥。U2 在9点前仍可只读确认已签，但禁止动作；图片选项沿用 V2 随机一次，JS 跳转从不当证据。TTG 缺失/重复动态参数不提交。

拒绝仅靠安全页才能确认 API 成功的方案：安全页可能没有独立签到记录，强制其确证会丢弃 V2 的有效回执；因此将来源标为 response_json，回读失败与明确 API 回执可并存。相反，HDArea/NexusHD/TTG 的 POST 文案与 U2 JS 回执仍不能冒充新页面。合成测试覆盖十站三态、异常回读、时段/参数边界、OCR 降级和 Cookie/JSON 请求；真实页面结构及宿主网络行为仍需单独授权校准。

C5/C6 使用 ctx 注入 get_data/save_data 与无凭据 public_get；TJUPT 的 tjupt.answer 保存 aHash→选项文本。原版文件缓存读文本却写 value，且空字典不落首条答案；不照搬这两个缺陷，确认数字奖励后写非空答案字典（包括首次建库）。缓存未命中才查豆瓣，沿用10×10平均hash和严格大于0.9阈值；无匹配不猜。奖励回执用于确认答案与奖励，签到状态仍以新 attendance anchor 为准，不把整页奖励正则当消息证据。采用独立无凭据请求而非复用站点客户端，避免向豆瓣传 Cookie。DarkLand/DigitalCore 的 hook=True 仅表示不适用声明闭环；签到/只读核验在凭据解析之前 skipped(signin_not_applicable)，不开放旧桥模拟登录。三站 verified 保持 False，离线验证不替代生产校准。


C7 查漏发现 B1-8 为25行/37个ID，原24站口径漏掉随机问答与 Discuz 分配。经授权补齐52pt/chdbits/yzyy；前两站共用 BakatestSignin，随机单选沿用V2，不引入LLM；数字奖励仅展示，不覆盖新页消息状态。yzyy 必须同 Session 传递临时 sign token，故仅该站在 run_native 站点锁内创建 caller-owned Session 并 finally 释放；RequestUtils 注入该 Session，响应/Session Cookie 同步到执行级字典。拒绝每次新客户端仅带最初 Cookie 的方案（sid 刷新使 token 失效），拒绝旧响应成功词兜底（不是新页证据）。回读 .signbtn 与 tb_my 本人行，身份取 um 导航，不取排行榜首人；身份/消息冲突未确认。测试 test_bakatest_yzyy_c7.py 覆盖三态、重复、动作异常、回读失败、同源 token、Cookie 更新和锁内 Session 异常释放；生产结构仍待授权校准。M-Team 不因清单收尾变成签到站。

## 3.20.0 站点校准例外

[BTSchool 入口反向语义与 PTTime 详情回读](2026-10-22-signincenter-calibration-320.md) 记录用户新裁决；仅 BTSchool 恒未确认例外被替代，不改变其他站的安全回读原则。
