# Agent Note: 签到与登录状态判定简化

Status: implemented

## Problem

原生登录无条件读取两次，并把持久化的 UID、首尾页 UID 和认证返回 UID 视为冲突门槛。签到提交后的未知回读有时只留下空消息或站点原文，维护者无法区分“未提交”“已提交但未确认”和“回读失败”。这些分支既增加请求，也把页面身份展示误作状态判定的前提。

## Decision

登录按页面结果判断，UID 只保留为展示证据，不参与登录或签到状态判定，也不再保存 `identity.bindings`。首读明确 `login_ok` 或 `auth_failed` 时立即返回；仅首读为 `unconfirmed` 时再读取一次，并以第二次结果为准。

原生签到仍只在明确已签时跳过；未识别状态不会单独阻止一次提交。存在唯一、同源的签到入口且验证码已解决时提交一次，之后只读回读。回读明确成功或已签为成功，明确未签为失败；其余为 pending。pending 必须说明是回读失败、没有确认标记，还是提交前没有唯一入口。未知提交结果绝不自动重提。

## Alternatives considered

- 保持无条件双读和 UID 防串号：看似更保守，但明确登录成功后第二次请求没有新证据价值，且页面 UID 变化会把可用 Cookie 错判为待确认。
- 状态未知时直接 pending 且不提交：降低误提交风险，但会让缺少稳定“未签到”文案、却有唯一签到入口的站点永远不能签到。
- 将未知回读归 failed：通知看似更明确，但它把证据不足伪装成明确失败，并会错误触发失败统计和重试策略。

## Consequences

登录核验通常减少一次请求；首读临时异常仍有一次补救读取。UID 不再用作防串号边界，因此宿主配置或页面展示异常不能阻止执行；站点锁、Cookie 候选顺序和认证失败判定保持不变。

签到保留单次提交和提交后回读的安全边界。站点消息未校准时结果会是 pending 而不是成功或失败；通知将展示可维护的原因。该决定取代 [登录证据](2026-10-21-login-evidence.md) 中“无条件回读”和“显式冲突停止”的部分，不改变其中登录/签到轨道分离的决定。

## Verification

`tests/v3/autoptcheckin/test_native_login_d5.py` 覆盖明确首读短路与不确定首读重读；`tests/v3/autoptcheckin/test_login.py` 覆盖 Runner 同口径和 UID 仅展示；`tests/v3/autoptcheckin/test_nexus_default_message.py` 覆盖提交后未知回读与回读异常的消息。完整 `tests/v3/autoptcheckin` 为 1360 passed。

## Related notes audit

[登录证据](2026-10-21-login-evidence.md) 部分被本篇替代，保留其轨道分离、历史隔离和非 native 分流事实；[原生双轨](2026-10-21-signincenter-native-dual-track.md) 仅在单次提交与回读边界上重叠，继续有效；[试点回读](2026-10-20-pilot-readback.md) 的 UID 作为确认门槛已被本篇取代。