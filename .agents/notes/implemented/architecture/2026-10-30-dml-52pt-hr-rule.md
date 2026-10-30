# Agent Note: 52pt H&R 内置规则

Status: implemented

## Problem

52pt 规则要求：每个纳管的已完成种子以下载完成时间为起点，5 天内满足“累计做种 24 小时”或“该种分享率 ≥1”任一条件。H&R 原有 `seeding_time` 通过 `now - completion_on/done_date` 计算，是经过时长，会把暂停或离线时间误算为实际做种时间。

## Decision

52pt 预设新增 `hr_use_downloader_seeding_time`，只对该站使用下载器报告的累计做种秒数：qBittorrent `seeding_time`，Transmission `secondsSeeding`（兼容 `seconds_seeding` 字段命名）。其他站继续沿用既有经过时长口径，避免静默改变现有规则。

该字段缺失时 24 小时条件不累加、不回退到完成后的经过时间；分享率条件仍独立可达标。截止期由下载器完成时间 `completion_on` / `done_date` 计算；未观测到完成时间前不开始五日倒计时。

## Alternatives considered

- 沿用 H&R 当前的 `now - completed_at`：改动小，但暂停/离线时间会被当做实际累计做种时间，与“累计做种”不符，因此拒绝。
- 将所有站点改为下载器累计字段：会改变其他内置及用户规则的既有时长语义，因此只为52pt加规则级选项。
- 下载器字段缺失时用经过时长兜底：能让旧接口看似正常，但会制造错误达标，因此缺失时按无可用做种累计处理。

## Consequences

修改仅影响52pt 内置预设。H&R/站点规则配置门控仍沿原规则；已有种子的自动补录仍受 `hr_auto_discover` 控制。qB/TR 的累计时间由下载器采样提供，轮询和下载器持久化机制仍决定可见更新节奏。

回归覆盖 qBittorrent 与 Transmission 快照字段、24h达标、ratio达标、完成后5日过期和字段缺失不误判；`tests/v3/downloadmanagerlocal/` 全套 665 passed。JSON解析与限定文件 `git diff --check` 通过。此工作尚未部署到本地 MP 或 QNAP，也未推送。
