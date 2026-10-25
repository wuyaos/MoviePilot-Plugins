# Agent Note: Yuc 季度交互订阅的名单与写入边界

Status: implemented

## Problem

季度放送表并不等于季度详细名单：按首播月份或星期栏目筛选会漏掉提前播出、网络放送和长篇。上游同名和续作识别也不能直接作为订阅授权。

## Decision

独立脚本沿用现有 scripts 目录，不接入插件生命周期。以 Yuc 本期声明后的前 N 个详细作品为主列表，放送表只补充字段；数量不一致需人工确认。Bangumi、AniList 候选始终由用户选择，MP 匹配再确认，媒体身份采用 MP 源码规定的 media_source/media_id，而不是把外站 ID 当 TMDB ID。

创建订阅同时要求 --apply 和本部作品的季列表交互确认。公开服务与 MP 分离客户端，只有 MP 客户端携带密钥且禁止重定向；提交前刷新订阅列表，不自动重试可能已生效的写入。

## Alternatives considered

放送表作为主列表更容易按星期展示，但无法保全季度人工补录；因此只作为补充数据。模糊匹配自动选择可以减少输入，但错误续作会触发真实订阅；一次性工具采用人工候选确认。已有插件体系便于定时运行，但本任务明确要求独立交互工具，故不使用插件、数据库、缓存服务或前端工程。

## Consequences

输入步骤较多，换来可核查的匹配和写入授权。解析依赖 Yuc class/文本边界；MP adapter 只保证与所读 MoviePilot-v3 源码契约一致，尚未联调真实实例。AniList native/description 不保证中文；不把日文或英文冒充译文。结构说明、接口证据和操作方法放在 scripts/README-season-subscribe.md。

历史检索：现有活跃 notes 未发现 Yuc/season_subscribe 相关决定，无需要替代的笔记。离线 fixture 与 MockTransport 验证不产生真实订阅；独立审查及真实实例只读联调仍是交付后续验收项。
