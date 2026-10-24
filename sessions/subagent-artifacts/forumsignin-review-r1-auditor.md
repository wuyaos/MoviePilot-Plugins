# ForumSignin V3 独立审查报告（Ralph 第 1 轮 · risk-auditor）

范围：plugins.v3/forumsignin/（__init__.py, core/*, http_client.py, integrations/*, verifiers/*）+ tests 只读参考。
结论：NEEDS FIX

## P0
1. __init__.py run_once 站点循环无 per-site try/except；`_history.append`（两处）在保护区外。HistoryStore._load 遇损坏时间或 save_data 失败 → 异常逃逸 → 其余站点漏签、通知丢失、api_run_once 500。

## P1
1. core/credentials.py:35 `if binding is not None:` 空串 managed_site_id 触发绑定校验 raise → 站点永远 UNCONFIRMED。改 `if binding:`。
2. __init__.py _handle_remote_command：无来源过滤；_stopped/未启用时应直接 return；无整轮并发去重。
3. __init__.py _save_config→init_plugin→stop_service 置 _stopped=True → 运行中保存配置腰斩本轮（轮内判定不应依赖 _stopped）。
4. integrations/yaowan.py fetch_page readonly 路径仍会 _login() POST —— 违反"只读核验不得 POST"。

## P2（合并主 agent 发现）
- skipped 进 notify 且 labels 默认"签到完成"误导
- time.sleep 阻塞线程池（V2 语义，保留不修）
- api_stats：currentStreak int() 无保护；favicon 串行；icon.cache 无锁
- pt_life 补推 job 被 stop_service 清除无重建
- trigger 恒标 manual
- today_counts 不计 network_error/skipped；重试膨胀
- api_update_info domain=pting.club 误导；signin_by_domain 任意 site_id 落历史
- `blocks = []` 重复行
- history._load 全量 deepcopy 性能（不修）
- app.core.event → app.sdk.events 正规路径替换（compat hook 两版宿主均存在，非紧急）

## 确认无问题
状态机完整性（无 unconfirmed→success 吞并；不重试 UNCONFIRMED）、HistoryStore 进程内并发原子、敏感信息脱敏链、pt_life 推送隔离、命令与 API 同路径、配置白名单、API envelope、锁语义。

## 待证
- 宿主 save_data 多 worker 原子性（单进程部署无影响）
- managed_site_id 空串仅经 API 可达
- curl_cffi yaowan /login 非 200 行为
