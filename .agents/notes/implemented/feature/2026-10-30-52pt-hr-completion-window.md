# Agent Note: 52pt 完成时间起算的 H&R 内置规则

Status: implemented

## Problem

52pt 站点需对下载完成的种子自动建立 H&R 条目，并在完成后 5 天内满足“累计做种 24 小时”或“该种分享率 ≥1”之一。既有 H&R 通用截止期从任务加入时间 `added_on` 起算，不能代表完成时间；未完成任务的分享率也不能提前使其通过此规则。

## Decision

52pt 预设以 `hr_active: true` 自动启用规则，并设置 `hr_duration: 24`、`hr_ratio: 1`、`hr_deadline_days: 5`、`hr_deadline_from_completion: true`。两个达标条件沿用 `HrTask.meets_hr()` 的 OR 语义。

H&R 扫描快照采集 qBittorrent `completion_on` 与 Transmission `done_date`/兼容字段，写入可空的 `HrTask.completed_on`；旧任务数据无需迁移，缺字段默认为空。仅 52pt 通过规则字段选择从完成时间起算；未完成且没有 `completed_on` 的任务保持进行中，即便 ratio 已达到 1 也不提前通过。完成后截止时间为 `completed_on + 5 days`；过期优先于首次达标判定，避免扫描到时已超过期限的任务仍被新标为达标。其他站点与全局规则仍从 `added_on` 起算。

## Alternatives considered

- 把所有 H&R 截止期改为完成时间：与其他站点既有口径不兼容，故仅通过可选站点规则字段启用。
- 用 `added_on` 近似完成时间：种子可能先下载、后完成，最多会把五天窗口提前耗尽，故不推断；缺少客户端完成时间时不启动该站点的期限。

## Consequences

新字段向后兼容；扫描周期继续使用现有调度，不新增存储迁移。测试覆盖预设解析、未完成时 ratio≥1 不达标、完成时间起算、5日内任一条件达标、期限已过判为超期，以及 qBittorrent 完成时间快照。若客户端无法提供完成时间，52pt 任务保持进行中且不产生伪造的期限；当前实现覆盖 qBittorrent 与 Transmission 快照字段。相关配置页视觉取舍见 [转移配置分组与窄容器适配](../architecture/2026-10-30-dml-transfer-form-sections.md)。

本次仅改源码和离线测试，未部署到会接触真实下载任务的 MP 实例，未推送、未部署 QNAP。真实下载器的完成事件、52pt tracker 匹配和宿主中的实际纳管需在单独授权的运行时验收中确认。
