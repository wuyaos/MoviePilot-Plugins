# Agent Note: 签到两件证据与独立模拟登录

Status: implemented

## Problem
签到回读把按钮和导航 UID 都当作必备证据，会拒绝已能按绑定 UID 定位的本人当日记录。模拟登录配置已有入口，却仍走签到链。

## Decision
签到只以本人当日行和明确状态确认；解析内部继续按 UID 定位，显式冲突停止。按钮保留信息展示。模拟登录独立使用页面访问及无条件回读，可达即 login_ok，UID 尽力提取；跳转登录页为 auth_failed，不可达为 unconfirmed。此语义来自本轮明确裁决，并不把可达性解释成更强的真实账号认证证明。

登录历史增加 action=login，旧记录按 sign 处理；登录失败也不进入签到四态统计。批量同时勾选两动作时签到优先。

肉丝/SunnyPT 没有已实现的认证检查器。经范围裁决仅提供检查器注入点，缺失返回 login_check_not_available；非试点继续跳过，后续逐站接入认证协议需要授权。

## Alternatives considered
- 继续要求按钮和导航 UID 能保留旧四件证据约束，但与本轮两件证据裁决不符。
- 从 V2 提取真实肉丝/SunnyPT 认证能立即开放登录，但会扩大网络和认证协议范围，因此保留试点门控。

## Consequences
缺少按钮不再制造未确认；页面可达可在 UID 未解析时确认模拟登录，但不证明账号已认证。真实站点结构仍须授权验证，合成夹具不替代生产证据。

## Verification
`test_login.py` 覆盖登录三态、无条件回读、分流与历史隔离；`test_pilot_runner.py` 覆盖绑定 UID 下缺导航的本人记录确认。

## Related notes audit
[S5 试点桥](2026-10-20-pilot-readback.md) 部分重叠，保留其提交次数和回读边界；本篇补充证据简化与登录语义。论坛笔记为独立插件，不适用本次变更。
