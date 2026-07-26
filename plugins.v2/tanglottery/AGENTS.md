# plugins.v2/tanglottery

V2 不可躺自动抽奖助手；输入 MoviePilot 站点 Cookie、插件配置和调度器，输出自动抽奖执行记录与通知。

## Input / Output / Pos
- Input: 不可躺站点 Cookie、目标抽奖次数、Cron 配置和立即运行事件。
- Output: 抽奖接口请求、历史记录、详情页统计和通知消息。
- Pos: 站点任务类插件；本地修正版重点增强定时服务注册稳定性与诊断日志。

## Files
- `__init__.py`: 插件入口、配置页、定时服务、抽奖执行、结果解析和历史展示。
