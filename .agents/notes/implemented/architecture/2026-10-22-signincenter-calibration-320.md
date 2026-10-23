# Agent Note: 3.20.0 签到证据校准

Status: implemented

## Problem

通用“唯一 POST 表单”和默认消息链不能区分标题、签到结果与非签到表单：海棠日历重复签到表单，RetroToon 额外提交时区表单，多个已签站点根本不再显示签到表单。未确认不表示签到失败。

## Decision

- 用户明确裁决 BTSchool 的每日签到入口消失即已签；仅在带用户导航及退出入口的已认证首页采用反向语义，挑战页/错误页缺入口不能证明已签。存在唯一入口才执行一次 addbonus GET，提交后仍新 GET 回读。该站恢复专属模块，不推广到其他站。
- PTTime 首页没有状态消息，动作页只有 `p` 中“拒绝访问：已签到，无需再签”。使用个人 `/attendance.php?type=list` 的当天“签到日：YYYYMMDD”span 确证，业务日按 Asia/Shanghai；不把总签到天数、历史某日或动作页 body 当今日证据。恢复专属模块。
- 海棠只选包含“立即签到”的主表单；RetroToon 只选 csrf_token + claim 表单。多个候选仍拒绝提交，不随意选择第一个。
- 普通站使用实测消息节点或已签导航 marker。只有观察到已签结构的站，未签/未知夹具保持未确认，不编造生产失败文案。
- yema 按用户裁决 `signin_capable=False`，保留模拟登录；M-Team 的 `login_check_not_available` 是认证协议尚未接入的预期结果，本轮不修改协议。
- 不变更 verified、全局消息链、UI/dist 或生产宿主。真实校准只在授权本地 17430 执行，部署前核验 onlyonce=false，保留原 unlock_all_sites=true。

## Alternatives considered

- 放宽全局唯一表单限制可少写专属模块，但会提交时区/日历表单，且影响未采样站，拒绝。
- BTSchool 继续恒未确认符合旧保守策略，但与本轮用户明确认可的站点反向语义冲突；以认证首页约束范围，替代该站旧例外。
- PTTime 重复请求动作页可得到结果 p，但会再次触发业务入口；使用只读详情页，不把动作响应替代新页回读。

## Consequences

2026-10-22 本地验收：海棠与 RetroToon 实际提交后 success；audiences、baozi、discfan、lpbits、ptfans、ptzone、tu88、btschool、pttime 为 already。憨憨执行被本日已签缓存跳过，再用只读 verify_site 得 already，不清缓存重复签到。

待恢复：cspt HTTP 200 内为 403 Forbidden；pt_0ff 为滑动认证页；phoenixpt 明示 Attendance has been temporarily disabled。hdvideo/shaobaoyuan 不在管理站点与 custom 候选采样列表，插件执行仍能拿其他来源凭据但无唯一表单，不能据此宣称宕机，待补可采样凭据/认证页面。没有绕盾或自动开启 Browserless。

离线回归包含结构摘录、缺 marker、旧日期、双表单、入口持续存在、挑战页、提交异常及回读；真实样本和 API 记录留本地 `D:/tmp/calibration/`，不提交带账号或令牌的完整 HTML。

## Related decisions / audit

- [消息证据与安全回读](2026-10-22-signincenter-response-evidence.md)：部分重叠；仅 BTSchool 恒未确认例外由本篇用户裁决替代，其他证据边界仍有效。
- [原生双轨](2026-10-21-signincenter-native-dual-track.md)：部分重叠；不改变门控和旧桥生命周期。
- proposed/rejected 目录不存在，没有本轮校准的重复决定；不归档仍有效的原生架构笔记。
