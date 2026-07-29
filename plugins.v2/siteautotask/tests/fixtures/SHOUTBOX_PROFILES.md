# 喊话区 Profile 浏览器证据

采集时间：2026-07-30。来源为已登录 Chrome 的 **只读** `shoutbox.php` DOM；不包含 Cookie、令牌或用户私密数据。`tests/fixtures/shoutbox_profiles.json` 是可由测试读取的等价结构化数据。

| 站点 | 读取入口 | 行结构 | 消息与反馈关系 | 解析规则 |
|---|---|---|---|---|
| 青蛙 | `/shoutbox.php?type=shoutbox` | `li` | 奖励“发了！”在消息上方 | 相邻上方反馈 |
| 织梦 | `/shoutbox.php?type=shoutbox` | `td.shoutrow` | `zmpt @用户名`在消息上方 | 识别上传/下载/电力/魔力关键词 |
| 藏宝阁 | `/shoutbox.php?type=shoutbox` | `td.shoutrow` | `系统: 感谢 @用户名`在消息上方 | 允许时间前缀；按上传/魔力区分 |
| LongPT | `/shoutbox.php?type=shoutbox` | `td.shoutrow` | admin 奖励在消息上方 | API 响应仅辅助，仍必须确认喊话行 |
| 13City | `/shoutbox.php?type=shoutbox` | `td.shoutrow` | 神明 `@用户名`在消息上方 | 啤酒瓶反馈 |
| PTS | `/shoutbox.php?type=shoutbox` | `td.shoutrow` + 顶部 `div.magic-reward-top.system-msg` | 奖励不与消息行相邻 | 独立顶部奖励 extractor，精确匹配 `用户「用户名」` |
| PTLGS | `/shoutbox.php?type=shoutbox` | `td.shoutrow` | 黑丝娘 `@用户名`在消息上方 | 不可 `startswith`，行含时间前缀 |
| 好学 | `/shoutbox.php?ajax_chat=1&type=` | `td.shoutrow` | “系统提示”在消息上方 | 仅此入口为有效确认快照；入口无效不得重发 |
| LuckPT | `/shoutbox.php?type=shoutbox` | `div.chat-message-container`、`div.wish-bubble-system` | 祈愿系统消息独立于普通聊天 | 精确匹配 `@用户名` 的幸运星/已祈愿结果 |
| RailgunPT | `/shoutbox.php?type=shoutbox` | `td.shoutrow` | 炮姐 `@用户名`在消息上方 | 上传/魔力/VIP 文本反馈 |
| Moment | `/shoutbox.php` | `td.shoutrow` | 女友反馈可位于消息上方或下方 | 双向窗口；女友行含用户名但绝不是本人喊话边界 |
| 天枢 | `/shoutbox.php?type=shoutbox` | `td.shoutrow` | 奖励随机存在于消息上方 | 无反馈正常，不能使确认失败 |
| 大青虫 | `/shoutbox.php?type=shoutbox` | `td.shoutrow` | 青虫娘 `@用户名`在消息上方 | 上传/魔力反馈；双消息间隔 60 秒 |

## 通用安全约束

1. 快照必须能解析出 Profile 指定的至少一个行选择器，否则 `snapshot_valid=false`，不可重发。
2. 确认当前消息只匹配“当前用户名 + 当前完整消息”；反馈行包含用户名不构成下一条本人消息边界。
3. Profile 指定的边界只能是另一条实际包含已配置喊话内容的本人消息。
4. 每次发送后的同一有效快照同时用于确认与反馈关联，避免二次读取错配。
