# Agent Note: 签到中心原生双轨与试点门控

Status: implemented

## Problem

旧适配器内部持有请求、验证码重试与二元结果判定；直接复用整个 signin 方法不能保证原生 NexusSignin 的单次提交和无条件回读。逐站迁移需要保留尚未迁移的路径，且不能因发现新 SiteModule 就允许请求真实站点。

## Decision

sites/native 的 SiteModule 与旧 sites 模块并存，同 ID 的原生元数据覆盖旧登记项，旧适配器文件不删除。native=true 的签到及只读核验由 verified 授权；默认 false 的站点在读取宿主凭证和创建请求能力之前返回 skipped/native_unverified。hdsky/haitang 的 true 仅表示试点授权，不是生产页面验证结论。native=false 继续旧试点桥和原有门控。模拟登录本轮仍走旧桥。特殊站的 hook_implemented=false 独立阻断执行（skipped/hook_not_implemented），不能仅靠 verified=false 恰好阻断；页面校准与提交钩子实现是两项独立就绪条件。

原生执行使用同一站点锁和 history 回调；CredentialResolver 选择宿主已同步 Cookie，SignContext 注入有超时的 HTTP 和 OCR 能力。两站不需要浏览器，page 保持 None，不创建 Playwright 生命周期。HDSky 仅在未得到有效验证码、尚未签到提交时换 OCR 引擎；已提交响应和异常都交给 NexusSignin 无条件 GET 回读，不按响应重试提交。

原生判定继承 N1/N2 的 RecordSpec 消息制，UID/date 仅展示。旧桥仍保留本人当日记录规则。这是明确的分轨语义，不能把旧规则偷偷补回原生结果，也不能宣称合成控件/消息选择器已覆盖生产 HTML。旧 AGENTS 契约改写由后续 N6 统一处理。

custom_sites_data 在 registry 每次调用时合并，不进入发现缓存，不允许覆盖内置 ID，不回传任意凭据字段。前端消费调整属于 N6，本轮不编辑 frontend/dist。

B1-4 的 API-only M-Team 声明保留空 URL：其旧协议按宿主 URL 推导 API 域名，没有可复用的 HTML 签到页面。registry 仅在原生 URL 非空时覆盖域名 matcher，空 URL 保留旧多域匹配；Token 元数据不表示原生 Cookie 执行器已经支持 API。M-Team 的空消息映射和无 IO hook 门控防止把 updateLastBrowse 保活当作签到证据；批次 2 再决定 API 接线或登录链归属。

B1-5 的 NexusHD 仅确认直接 POST 协议，安全前读使用首页，不为其修改公共 signin.php 登录识别。OpenCD 的 show-log URL 标记与 JSON state 不属于消息文本，空 status_map 保持所有输入 unconfirmed；两站特殊协议与 CAPTCHA 三站均保留独立 hook 门控，页面校准不等于提交实现。

OpenCD 纯消息限制已被[证据来源分离决定](2026-10-22-signincenter-response-evidence.md)部分取代；上文保留原取舍背景，其余双轨与门控决定仍有效。

C1 的十二站共用 core/attendance_captcha.py，但每站保留 solve_captcha 入口和独立 verified=false。V2 副本仅域名不同，均继承 4–6 位 alnum 参数；按源码保留范围，不套用 HDSky 的固定六位。共享钩子在已选表单内取唯一图片，OCR 负责带凭证 GET；提交通过可选 SigninForm.referer 保留 attendance Referer，不改变其他站请求。未迁移旧 helper 的三次提交重试；生产消息节点仍无依据，现有合成占位不作为生产校准。

## Alternatives considered

- 继续调用旧适配器 signin：改动少且兼容现有站点，但保留其内部重试和二元判定，无法落实已批准的原生回读语义；旧代码仅作为尚未迁移站点的兼容路径。
- 将旧同名文件直接替换：目录更短，但会丢失回退参照并把迁移与删除耦合；保留双目录直到批次迁移完成。
- 用固定 PILOTS 清单同时控制原生签到：已有实现容易复用，但会让 verified 字段成为无效门控；原生签到由 verified 驱动，固定清单仅保留在旧桥/登录路径。

- 给 M-Team 套固定域名和 Nexus 表单：可减少声明差异，但旧副本无此证据且动作是保活，不制造签到选择器；保留自定义 SiteModule 和未实现 gate。

- 将 OpenCD 的 show-log URL/JSON success 映射为消息：可沿用旧二元判据，但没有唯一消息元素证据，保留空映射直至页面校准。

## Consequences

原生目录导入必须不依赖宿主，因此 sites/__init__.py 的旧运行时导入延迟到方法内部；没有安装宿主也能直接导入原生类并跑离线链测试。未迁移模块的导入异常仍隔离记录。

测试通过真实插件 API 方法、registry 和注入 HTTP 的两站签到链，覆盖已签、一次提交、异常后回读、OCR 参数及回退、只读核验、三态分流、锁忙/取消/缺凭据、元数据合并与碰撞。全部页面都是合成夹具，不发真实请求。

遗留限制：N6 前前端仍会把 /sites 返回的自定义站点与本地列表再次拼接；需要在 N6 统一消费服务端列表并兼顾未保存编辑。原生登录接线及生产 HTML 采样验证仍未完成。活跃笔记检索没有已有原生双轨决定；现有论坛 F1/F2 架构笔记属于不同插件，本篇不取代它。
