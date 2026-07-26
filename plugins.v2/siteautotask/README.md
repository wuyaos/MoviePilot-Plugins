# 站点自动任务（SiteAutoTask）

MoviePilot V2 站点日常任务合集，统一执行签到、喊话、任务申领、抽奖、兑换与勋章续购，并记录任务状态和喊话反馈。

## 功能

- 按站点独立启用签到、喊话、兑换、抽奖、勋章及任务申领。
- CLAIM 任务通过下拉选择具体任务，通知与历史显示实际选中的任务名称。
- 支持喊话反馈解析；多条喊话按消息间隔顺序发送，并分别展示反馈。
- 主定时、失败重试、勋章定时、织梦独立调度与当天手动补跑相互隔离。
- `立即运行一次` 是一次性表单触发，消费后不持久化，不会因插件重载再次执行。
- 支持内置 Vc-Lib：MoviePilot 未配置该站点时自动提供站点选项，实际执行时从 CookieCloud 获取 `vclib.online` Cookie。
- 支持梓喵（`azusa.wiki`）任务申领，下拉选择页面公开的每日、七日或月度任务。

## 手动入口

- 配置页：`立即运行一次`，执行当天未成功的已配置任务。
- 命令：`/siteautotask_manual_run`。
- API：`POST /api/v1/plugin/SiteAutoTask/manual-run`。
- 调试 API：`POST /api/v1/plugin/SiteAutoTask/run`，可附加 `site_id`、`task_name`。

## 参考来源

本插件从零开始进行模块化合并与重构，站点接口、任务逻辑和反馈解析参考了以下开源项目：

- [bfjy2024/MoviePilot-Plugins](https://github.com/bfjy2024/MoviePilot-Plugins) 的 `ptautotask`：多站点任务定义、任务申领、抽奖、兑换与部分站点接口。
- [KoWming/MoviePilot-Plugins](https://github.com/KoWming/MoviePilot-Plugins) 的 `groupchatzone`：喊话发送、奖励反馈解析、Cookie/请求处理及织梦调度思路。
- [jiangbkvir/MoviePilot-Plugins](https://github.com/jiangbkvir/MoviePilot-Plugins) 的 `ggptmedalbuyer`：GGPT 疯狂星期四勋章续购接口与过期判断逻辑（原作者 `jiangbkvir`，本仓库的 `ggptmedalbuyer` 为移植维护版本）。
- 本仓库原有的 `myptmedalbuyer`：myPT 勋章续购的站点接口和过期判断逻辑。

感谢上述项目作者的开源贡献。请遵守相应上游项目的许可证与使用约束。
