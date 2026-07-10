# MoviePilot-Plugins
MoviePilot官方插件市场：https://github.com/jxxghp/MoviePilot-Plugins

本仓库收录 MoviePilot V2 插件，共 13 个，涵盖媒体库封面、识别增强、云盘存储、PT 站点运营与做种保活等场景。

> 说明：本仓库插件均为自用，基于参考项目进行部分场景增强；部分代码由 AI 辅助生成（vibe coding），可能存在未覆盖的边界情况，使用前请自行评估。

## 目录

| 插件 ID | 插件 | 版本 | 简述 |
|---|---|---|---|
| covergen | [媒体库封面生成](#covergen) | 1.4.7 | 为 Emby / Jellyfin 自动生成统一风格媒体库封面 |
| autoptcheckin | [PT站点自动签到](#autoptcheckin) | 1.3.1 | 自动签到 / 登录站点，支持自定义站点与 CookieCloud 同步 |
| siterefresh | [站点自动更新](#siterefresh) | 1.3.1 | 接收 Cookie 失效事件，刷新站点 Cookie 和 UA |
| llmrecognizer | [AI识别增强](#llmrecognizer) | 1.2.12 | 复用当前 LLM 配置，原生识别失败后本地结构化识别兜底 |
| pthitandrun | [H&R助手Pro](#pthitandrun) | 1.2.4 | PT 站 H&R 种子自动标签管理 |
| azkeepalive | [AnimeZ保活](#azkeepalive) | 2.5.9 | 定时访问 AnimeZ 并选种提交下载器，满足保活要求 |
| torrenttransfer | [自动转移做种](#torrenttransfer) | 2.0.1 | 定期转移下载器中的做种任务到另一个下载器 |
| forumsignin | [论坛签到](#forumsignin) | 1.0.5 | 论坛站点签到，单插件双站调度 |
| strmmanage | [云盘Strm助手](#strmmanage) | 0.1.1 | 联动生成 strm，支持 CloudDrive2 下载非视频文件 |
| clouddrive2disk | [CloudDrive2 存储](#clouddrive2disk) | 1.0.3 | CloudDrive2 gRPC 直连接入，注册为 MoviePilot 存储 |
| myptmedalbuyer | [myPT勋章续购](#myptmedalbuyer) | 1.0.0 | 自动续购 myPT 勋章，避免到期忘记购买 |
| tanglottery | [不可躺自动抽奖助手](#tanglottery) | 3.0.2 | 按每日目标次数自动拆解并执行不可躺抽奖 |
| tangredpacket | [不可躺自动领红包](#tangredpacket) | 1.0.0 | 自动发现并串行领取不可躺红包 |

---

<a id="covergen"></a>
### [媒体库封面生成 CoverGen](https://github.com/wuyaos/MoviePilot-Plugins/tree/main/plugins.v2/covergen)
> 版本 1.4.7 · 作者 wuyaos
> 参考项目：[jellyfin-library-poster](https://github.com/HappyQuQu/jellyfin-library-poster)

CoverGen 用于为 Emby / Jellyfin 媒体库自动生成统一风格的媒体库封面。插件会按已选择的媒体服务器与媒体库抓取海报素材，生成静态或动态封面，并可自动上传回媒体服务器。

主要用途：
- 统一电影、电视剧、合集、歌单等媒体库封面风格
- 支持库白名单、合集来源黑名单、用户黑名单过滤，避免不希望展示的内容参与封面生成
- 支持多种静态 / 动态封面风格、字体配置、标题缩放、Dry Run 与手动单库重生成
- 保留历史封面与最近执行记录，便于回看生成结果和排查失败原因

<a id="autoptcheckin"></a>
### [PT站点自动签到](https://github.com/wuyaos/MoviePilot-Plugins/tree/main/plugins.v2/autoptcheckin)
> 版本 1.3.1 · 作者 wuyaos
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
> 版本 1.2.12 · 作者 wuyaos
> 参考项目：[airecognizerenhancer](https://github.com/jxxghp/MoviePilot-Plugins/tree/main/plugins.v2/airecognizerenhancer)

直接复用 MoviePilot 当前 LLM 配置，在原生识别失败后做本地结构化识别兜底，并交回原生链路继续二次识别。

- 复用 MoviePilot 当前 LLM 配置，无需额外接入
- 原生识别失败后触发本地结构化识别兜底
- 识别结果交回原生链路继续二次识别

<a id="pthitandrun"></a>
### [H&R助手Pro](https://github.com/wuyaos/MoviePilot-Plugins/tree/main/plugins.v2/pthitandrun)
> 版本 1.2.4 · 作者 wuyaos
> 参考项目：[hitandrun](https://github.com/InfinityPacer/MoviePilot-Plugins/tree/main/plugins.v2/hitandrun)

PT 站 H&R 种子自动标签管理，支持多条件 OR 判定、按大小分级、自动发现。

- 多条件 OR 判定与按大小分级，灵活适配不同站点规则
- 自动发现 H&R 种子并打标签管理

<a id="azkeepalive"></a>
### [AnimeZ保活](https://github.com/wuyaos/MoviePilot-Plugins/tree/main/plugins.v2/azkeepalive)
> 版本 2.5.9 · 作者 wuyaos

定时访问 AnimeZ 站点并从种子页选种提交下载器，满足登录和下载保活要求。

- 定时访问站点保持登录活跃
- 从种子页选种提交下载器，满足下载保活

<a id="torrenttransfer"></a>
### [自动转移做种(自用)](https://github.com/wuyaos/MoviePilot-Plugins/tree/main/plugins.v2/torrenttransfer)
> 版本 2.0.1 · 作者 wuyaos
> 参考项目：[torrenttransfer](https://github.com/jxxghp/MoviePilot-Plugins/tree/main/plugins.v2/torrenttransfer)

定期转移下载器中的做种任务到另一个下载器。

- 定时调度，按周期迁移做种任务
- 支持活跃做种状态判定，避免误转移

<a id="forumsignin"></a>
### [论坛签到](https://github.com/wuyaos/MoviePilot-Plugins/tree/main/plugins.v2/forumsignin)
> 版本 1.0.5 · 作者 wuyaos
> 参考项目：[fengchaosignin](https://github.com/madrays/MoviePilot-Plugins/tree/main/plugins/fengchaosignin)、[invitesssignin](https://github.com/jxxghp/MoviePilot-Plugins/tree/main/plugins.v2/invitesssignin)

论坛站点签到（蜂巢 pting.club + 药丸 invites.fun），单插件双站调度，支持 Cookie/账号登录、失败重试与历史记录。

- 单插件双站调度，覆盖蜂巢与药丸
- 支持 Cookie / 账号登录、失败重试与历史记录

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
> 版本 1.0.0 · 作者 wuyaos

自动续购 myPT(cc.mypt.cc) 勋章，避免到期后忘记手动购买。

<a id="tanglottery"></a>
### [不可躺自动抽奖助手](https://github.com/wuyaos/MoviePilot-Plugins/tree/main/plugins.v2/tanglottery)
> 版本 3.0.2 · 作者 jiangbkvir, bfjy, wuyaos
> 参考项目：[tanglottery](https://github.com/jiangbkvir/MoviePilot-Plugins/tree/main/plugins.v2/tanglottery)

按每日目标次数自动拆解并执行不可躺抽奖。

<a id="tangredpacket"></a>
### [不可躺自动领红包](https://github.com/wuyaos/MoviePilot-Plugins/tree/main/plugins.v2/tangredpacket)
> 版本 1.0.0 · 作者 wuyaos

自动发现并串行领取不可躺红包，支持限流感知和历史统计。
