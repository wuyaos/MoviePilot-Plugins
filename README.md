# MoviePilot-Plugins
MoviePilot官方插件市场：https://github.com/jxxghp/MoviePilot-Plugins

本仓库收录 MoviePilot 插件：V2 插件 22 个、V3 插件 4 个，涵盖媒体库封面、识别增强、云盘存储、PT 站点运营与做种保活等场景。

> 说明：本仓库插件均为自用，基于参考项目进行部分场景增强；部分代码由 AI 辅助生成（vibe coding），可能存在未覆盖的边界情况，使用前请自行评估。

## 目录

### V2 插件（plugins.v2）

| 插件 ID | 插件 | 版本 | 简述 |
|---|---|---|---|
| autoptcheckin | [PT站点自动签到](#autoptcheckin) | 1.5.37 | 自动签到 / 登录站点，支持自定义站点与 CookieCloud 同步 |
| azkeepalive | [AnimeZ保活](#azkeepalive) | 2.6.1 | 定时访问 AnimeZ 并选种提交下载器，满足保活要求 |
| bakabtbrush | [BakaBT刷流](#bakabtbrush) | 0.1.7 | 定时筛选 BakaBT Freeleech 种子并提交到 qBittorrent |
| clouddrive2disk | [CloudDrive2 存储](#clouddrive2disk) | 1.0.3 | CloudDrive2 gRPC 直连接入，注册为 MoviePilot 存储 |
| covergen | [媒体库封面生成](#covergen) | 1.4.9 | 为 Emby / Jellyfin 自动生成统一风格媒体库封面 |
| farmauto | [农场自动化Pro](#farmauto) | 3.2.18 | 多站点农场自动收获、补种与出售 |
| forumsignin | [论坛签到](#forumsignin) | 1.0.14 | 论坛站点签到，单插件双站调度 |
| ggptmedalbuyer | [GGPT勋章购买](#ggptmedalbuyer) | 1.0.3 | 自动续购 GGPT 疯狂星期四勋章 |
| llmrecognizer | [AI识别增强](#llmrecognizer) | 1.2.14 | 复用当前 LLM 配置，原生识别失败后本地结构化识别兜底 |
| myptmedalbuyer | [myPT勋章续购](#myptmedalbuyer) | 1.0.2 | 自动续购 myPT 勋章，避免到期忘记购买 |
| ptermedalbuyer | [pter勋章自动领取](#ptermedalbuyer) | 1.0.12 | 自动领取 pterclub 勋章并记录历史 |
| pthitandrun | [H&R助手Pro](#pthitandrun) | 1.2.7 | PT 站 H&R 种子自动标签管理 |
| ptnewswatch | [PT资讯动态监控](#ptnewswatch) | 0.2.0 | 汇总 PT 论坛主题、RSS 与 Atom 新消息，仅推送未见动态 |
| pttaskflow | [PT任务流](#pttaskflow) | 0.4.8 | 声明式 PT 站点任务流：签到、喊话、申领、抽奖 |
| rousicheckin | [肉丝自动签到](#rousicheckin) | 1.1.1 | rousi.pro JWT Token 签到、站内信推送与过期提醒 |
| siteautotask | [站点自动任务](#siteautotask) | 1.0.21 | 自动执行站点签到、喊话、勋章和抽奖等任务 |
| siterefresh | [站点自动更新](#siterefresh) | 1.3.1 | 接收 Cookie 失效事件，刷新站点 Cookie 和 UA |
| strmmanage | [云盘Strm助手](#strmmanage) | 0.1.1 | 联动生成 strm，支持 CloudDrive2 下载非视频文件 |
| sunnyptsignin | [SunnyPT自动签到](#sunnyptsignin) | 1.1.1 | 登录 SunnyPT 并自动签到，无需 Cookie |
| tangredpacketclaim | [不可躺自动领红包](#tangredpacketclaim) | 1.0.14 | 自动发现并串行领取不可躺红包 |
| torrenttransfer | [自动转移做种](#torrenttransfer) | 2.0.2 | 定期转移下载器中的做种任务到另一个下载器 |
| yzyysignin | [yzyy论坛签到](#yzyysignin) | 1.2.12 | yzyy 论坛每日签到，自动获取签到码完成签到 |

### V3 插件（plugins.v3）

| 插件 ID | 插件 | 版本 | 简述 |
|---|---|---|---|
| AutoPtCheckin | [PT 签到中心](#v3-autoptcheckin) | 4.0.12 | PT 站点自动签到与模拟登录（V3 重构版） |
| ForumSignin | [论坛签到](#v3-forumsignin) | 3.1.21 | 蜂巢、药丸与 SSDForum 论坛签到 |
| RuntimePatchGuard | [运行时补丁守卫](#v3-runtimepatchguard) | 1.0.0 | 站点解析网络请求总时长守卫，防慢站挂起线程 |
| Hhanclubrescueseed | [憨憨保种区](#v3-hhanclubrescueseed) | 3.0.0 | 憨憨 BT 保种区自动保种（fork 自 Seed680） |

---

<a id="covergen"></a>
### [媒体库封面生成 CoverGen](https://github.com/wuyaos/MoviePilot-Plugins/tree/main/plugins.v2/covergen)
> 版本 1.4.9 · 作者 wuyaos
> 参考项目：[jellyfin-library-poster](https://github.com/HappyQuQu/jellyfin-library-poster)

CoverGen 用于为 Emby / Jellyfin 媒体库自动生成统一风格的媒体库封面。插件会按已选择的媒体服务器与媒体库抓取海报素材，生成静态或动态封面，并可自动上传回媒体服务器。

主要用途：
- 统一电影、电视剧、合集、歌单等媒体库封面风格
- 支持库白名单、合集来源黑名单、用户黑名单过滤，避免不希望展示的内容参与封面生成
- 支持多种静态 / 动态封面风格、字体配置、标题缩放、Dry Run 与手动单库重生成
- 保留历史封面与最近执行记录，便于回看生成结果和排查失败原因

<a id="autoptcheckin"></a>
### [PT站点自动签到](https://github.com/wuyaos/MoviePilot-Plugins/tree/main/plugins.v2/autoptcheckin)
> 版本 1.5.37 · 作者 wuyaos
> 参考项目：[autosignin](https://github.com/jxxghp/MoviePilot-Plugins/tree/main/plugins.v2/autosignin)、[customsites](https://github.com/jxxghp/MoviePilot-Plugins/tree/main/plugins/customsites)

自动签到 / 登录站点，支持自定义站点和验证码识别。

- 支持自定义站点配置与 CookieCloud 同步
- 支持验证码识别，适配需登录的站点

<a id="siterefresh"></a>
### [站点自动更新（自用版）](https://github.com/wuyaos/MoviePilot-Plugins/tree/main/plugins.v2/siterefresh)
> 版本 1.3.1 · 作者 wuyaos, thsrite

接收 Cookie 失效事件，使用当前 MoviePilot V2 浏览器登录流程刷新站点 Cookie 和 UA。

- 事件驱动：监听 Cookie 失效事件自动触发刷新
- 复用 MoviePilot V2 浏览器登录流程，刷新 Cookie 与 UA

<a id="llmrecognizer"></a>
### [AI识别增强](https://github.com/wuyaos/MoviePilot-Plugins/tree/main/plugins.v2/llmrecognizer)
> 版本 1.2.14 · 作者 wuyaos
> 参考项目：[airecognizerenhancer](https://github.com/jxxghp/MoviePilot-Plugins/tree/main/plugins.v2/airecognizerenhancer)

直接复用 MoviePilot 当前 LLM 配置，在原生识别失败后做本地结构化识别兜底，并交回原生链路继续二次识别。

- 复用 MoviePilot 当前 LLM 配置，无需额外接入
- 原生识别失败后触发本地结构化识别兜底
- 识别结果交回原生链路继续二次识别

<a id="pthitandrun"></a>
### [H&R助手Pro](https://github.com/wuyaos/MoviePilot-Plugins/tree/main/plugins.v2/pthitandrun)
> 版本 1.2.7 · 作者 wuyaos
> 参考项目：[hitandrun](https://github.com/InfinityPacer/MoviePilot-Plugins/tree/main/plugins.v2/hitandrun)

PT 站 H&R 种子自动标签管理，支持多条件 OR 判定、按大小分级、自动发现。

- 多条件 OR 判定与按大小分级，灵活适配不同站点规则
- 自动发现 H&R 种子并打标签管理

<a id="azkeepalive"></a>
### [AnimeZ保活](https://github.com/wuyaos/MoviePilot-Plugins/tree/main/plugins.v2/azkeepalive)
> 版本 2.6.1 · 作者 wuyaos

定时访问 AnimeZ 站点并从种子页选种提交下载器，满足登录和下载保活要求。

- 定时访问站点保持登录活跃
- 从种子页选种提交下载器，满足下载保活

<a id="torrenttransfer"></a>
### [自动转移做种(自用)](https://github.com/wuyaos/MoviePilot-Plugins/tree/main/plugins.v2/torrenttransfer)
> 版本 2.0.2 · 作者 wuyaos
> 参考项目：[torrenttransfer](https://github.com/jxxghp/MoviePilot-Plugins/tree/main/plugins.v2/torrenttransfer)

定期转移下载器中的做种任务到另一个下载器。

- 定时调度，按周期迁移做种任务
- 支持活跃做种状态判定，避免误转移

<a id="forumsignin"></a>
### [论坛签到](https://github.com/wuyaos/MoviePilot-Plugins/tree/main/plugins.v2/forumsignin)
> 版本 1.0.14 · 作者 wuyaos
> 参考项目：[fengchaosignin](https://github.com/madrays/MoviePilot-Plugins/tree/main/plugins/fengchaosignin)、[invitessignin](https://github.com/jxxghp/MoviePilot-Plugins/tree/main/plugins.v2/invitessignin)

论坛站点签到（蜂巢 pting.club + 药丸 invites.fun），单插件双站调度，支持 Cookie/账号登录、失败重试与历史记录。

- 单插件双站调度，覆盖蜂巢与药丸
- 支持 Cookie / 账号登录、失败重试与历史记录

<a id="rousicheckin"></a>
### [肉丝自动签到 RousiCheckin](https://github.com/wuyaos/MoviePilot-Plugins/tree/main/plugins.v2/rousicheckin)
> 版本 1.1.1 · 作者 wuyaos

rousi.pro JWT Token 自动签到、站内信增量推送与 Token 过期提醒。

- 手动配置 JWT Token（登录勾选30天免登录可获30天有效期），解析 exp 动态显示剩余天数
- 每日 cron 签到并随机抖动，签到前读取 attendance stats 去重
- 成功后增量拉取站内信并合并推送（首次只记录不推）
- Token 临期/失效当日通知一次，401 自动停用插件

<a id="yzyysignin"></a>
### [yzyy论坛签到 YzyySignin](https://github.com/wuyaos/MoviePilot-Plugins/tree/main/plugins.v2/yzyysignin)
> 版本 1.2.12 · 作者 bfjy, wuyaos
> 参考项目：[yzyysignin](https://github.com/bfjy2024/MoviePilot-Plugins/tree/main/plugins.v2/yzyysignin)

yzyy 论坛每日签到，自动获取签到码完成签到。

- 站点地址可配置（默认 https://yzyy.org）
- Cookie 留空时自动从 CookieCloud 按域名获取
- 签到结果只判定当前用户打卡按钮区域，避免排行榜误报成功

<a id="strmmanage"></a>
### [云盘Strm助手（CD2增强）](https://github.com/wuyaos/MoviePilot-Plugins/tree/main/plugins.v2/strmmanage)
> 版本 0.1.1 · 作者 wuyaos

联动生成 strm，并支持通过 CloudDrive2 下载非视频文件，提供 CD2 处理方式配置。

- 联动生成 strm 文件
- 支持通过 CloudDrive2 下载非视频文件，提供 CD2 处理方式配置

<a id="clouddrive2disk"></a>
### [CloudDrive2 存储](https://github.com/wuyaos/MoviePilot-Plugins/tree/main/plugins.v2/clouddrive2disk)
> 版本 1.0.3 · 作者 wuyaos
> 参考项目：[clouddrivedisk](https://github.com/DDSRem-Dev/MoviePilot-Plugins/tree/main/plugins.v2/clouddrivedisk)、[cd2disk](https://github.com/baranwang/cd2disk)

通过基于 baranwang/cd2disk 修改而成的 CloudDrive2 gRPC 直连与 API 令牌接入 CloudDrive2，注册为 MoviePilot 存储。

- 基于 CloudDrive2 proto 0.9.24 / gRPC 直连与 API 令牌接入
- 注册为 MoviePilot 存储，支持浏览、上传、下载、删除、重命名、移动、复制与空间统计

<a id="myptmedalbuyer"></a>
### [myPT勋章续购](https://github.com/wuyaos/MoviePilot-Plugins/tree/main/plugins.v2/myptmedalbuyer)
> 版本 1.0.2 · 作者 wuyaos

自动续购 myPT(cc.mypt.cc) 勋章，避免到期后忘记手动购买。

<a id="tangredpacketclaim"></a>
### [不可躺自动领红包](https://github.com/wuyaos/MoviePilot-Plugins/tree/main/plugins.v2/tangredpacketclaim)
> 版本 1.0.14 · 作者 wuyaos

自动发现并串行领取不可躺红包，支持限流感知和历史统计。

<a id="bakabtbrush"></a>
### [BakaBT刷流 BakaBTBrush](https://github.com/wuyaos/MoviePilot-Plugins/tree/main/plugins.v2/bakabtbrush)
> 版本 0.1.7 · 作者 wuyaos

定时筛选 BakaBT Freeleech 种子并提交到 qBittorrent。

<a id="farmauto"></a>
### [农场自动化Pro FarmAuto](https://github.com/wuyaos/MoviePilot-Plugins/tree/main/plugins.v2/farmauto)
> 版本 3.2.18 · 作者 wuyaos

多站点农场自动收获、补种与出售。

<a id="ggptmedalbuyer"></a>
### [GGPT勋章购买 GGPTMedalBuyer](https://github.com/wuyaos/MoviePilot-Plugins/tree/main/plugins.v2/ggptmedalbuyer)
> 版本 1.0.3 · 作者 wuyaos

自动续购 GGPT 疯狂星期四勋章。

<a id="ptermedalbuyer"></a>
### [pter勋章自动领取 PterMedalBuyer](https://github.com/wuyaos/MoviePilot-Plugins/tree/main/plugins.v2/ptermedalbuyer)
> 版本 1.0.12 · 作者 wuyaos

自动领取 pterclub 勋章并记录历史。

<a id="ptnewswatch"></a>
### [PT资讯动态监控 PTNewsWatch](https://github.com/wuyaos/MoviePilot-Plugins/tree/main/plugins.v2/ptnewswatch)
> 版本 0.2.0 · 作者 wuyaos

汇总 PT 论坛主题页与 RSS/Atom 新消息，仅推送未见过的动态，避免重复打扰。

<a id="pttaskflow"></a>
### [PT任务流 PtTaskFlow](https://github.com/wuyaos/MoviePilot-Plugins/tree/main/plugins.v2/pttaskflow)
> 版本 0.4.8 · 作者 wuyaos

声明式 PT 站点任务流，使用 Task/Control/Unit/Site 分层组合签到、喊话、申领、勋章和抽奖任务。

<a id="siteautotask"></a>
### [站点自动任务 SiteAutoTask](https://github.com/wuyaos/MoviePilot-Plugins/tree/main/plugins.v2/siteautotask)
> 版本 1.0.21 · 作者 wuyaos

自动执行站点签到、喊话、勋章和抽奖等任务。

<a id="sunnyptsignin"></a>
### [SunnyPT自动签到 SunnyPTSignin](https://github.com/wuyaos/MoviePilot-Plugins/tree/main/plugins.v2/sunnyptsignin)
> 版本 1.1.1 · 作者 wuyaos

登录 SunnyPT 并自动签到，无需手动维护 Cookie。

## V3 插件

<a id="v3-autoptcheckin"></a>
### [PT 签到中心 AutoPtCheckin (V3)](https://github.com/wuyaos/MoviePilot-Plugins/tree/main/plugins.v3/autoptcheckin)
> 版本 4.0.12 · 作者 wuyaos

PT 站点自动签到与模拟登录的 V3 重构版，面向 MoviePilot V3 插件体系。

- 站点声明式接入：generic_sites.json 统一声明 130+ 站点，native 目录提供复杂站点专属适配
- 签到 / 模拟登录双轨：每轨独立开关与调度窗口，轨道状态表记录 success/failed/pending，失败自动重入队
- 统一 Cookie 表：stored → managed → local → cookiecloud 候选链，签到结果自动回写，跨插件复用
- Browserless 云端仿真：Cloudflare Turnstile、ALTCHA、滑块等验证场景经 BrowserQL 云端处理，本地无需浏览器
- 纯文本通知：逐站明细分组推送，支持 /notify_test 测试推送与远程立即签到命令
- 支持自定义站点、CookieCloud 同步与每站重试配置

<a id="v3-forumsignin"></a>
### [论坛签到 ForumSignin (V3)](https://github.com/wuyaos/MoviePilot-Plugins/tree/main/plugins.v3/forumsignin)
> 版本 3.1.21 · 作者 wuyaos

蜂巢 pting.club、药丸 invites.fun 与 SSDForum 论坛签到的 V3 版，单插件多站调度，支持 Cookie/账号登录、失败重试与历史记录。

<a id="v3-runtimepatchguard"></a>
### [运行时补丁守卫 RuntimePatchGuard (V3)](https://github.com/wuyaos/MoviePilot-Plugins/tree/main/plugins.v3/runtimepatchguard)
> 版本 1.0.0 · 作者 wuyaos

为站点解析网络请求增加总时长守卫，防止慢站挂起工作线程。内存补丁，插件升级免重打。

<a id="v3-hhanclubrescueseed"></a>
### [憨憨保种区 Hhanclubrescueseed (V3)](https://github.com/wuyaos/MoviePilot-Plugins/tree/main/plugins.v3/hhanclubrescueseed)
> 版本 3.0.0 · 作者 Seed680, wuyaos

> Fork from [Seed680/MoviePilot-Plugins](https://github.com/Seed680/MoviePilot-Plugins/tree/main/plugins.v3/hanhanrescueseeding)，原作者 Seed680；本仓库迁移为 V3 并增强。

憨憨 BT（HhanClub）保种区自动保种插件：定时抓取站点保种区列表，按做种人数、种子大小等条件筛选，自动提交到下载器做种并打标签。

相对原版的变更：

- 修复「获取下载记录失败」：`/download_records`、`/config` 接口统一返回 V3 `success/message/data` envelope（前端按 envelope 读取，原版返回裸数组/裸 dict 导致前端恒报错）
- 抓取页数可配置：原版固定抓取 11 页，新增「抓取页数」配置项，默认 5 页
- 插件更名为 `Hhanclubrescueseed`，图标按本仓库规范重制（200×200 RGBA）
