# DownloadManagerLocal：最终规格与后续实施

## 当前状态

- 唯一实施入口：[`docs/downloadmanagerlocal-final-implementation-spec.md`](../docs/downloadmanagerlocal-final-implementation-spec.md)。
- 本轮只审核/更新文档、清理过时文档与整理Todos；未按最终规格修改插件源码，未部署。
- 代码实施等待用户明确开始。旧循环仍记录iteration24，不因循环活跃而越过当前规划范围；不自动排下一轮业务实施。
- 旧阶段一至七的完整记录、测试数量、先前提交与未验项保留在[历史任务记录](../docs/history/downloadmanagerlocal/pre-final-v2/dml-seven-optimizations.md)。它们不是本版完成证据。

## 已完成的本轮产物

- [x] 汇总数据页与七模块配置页逐项定稿。
- [x] 统一文字层级：同级字号/字重/行高/颜色一致，Tab不改；字段名/按钮名精简；帮助/风险/错误统一。
- [x] 规定配置左下角查看数据、保存不关闭配置窗口；宿主契约实施前核实。
- [x] 更新最终实施规格，包含目标/文件定位/工作包/验收/失败停止/配置兼容。
- [x] 旧七项方案、转移草案、UI报告、页面草案改为短链接；原文移至docs/history/downloadmanagerlocal/pre-final-v2/。
- [x] 收录模型分工及开发前baseline、逐阶段本地Git提交要求。

## 未完成：不得勾选成实现完成

- [ ] P0：开工基线、配置/API/宿主契约核对与Git基线提交。
- [ ] P1：公共视觉、级内统一文字和短文案实现。
- [ ] P2：逐模块配置布局与兼容实现。
- [ ] P3：保存/关闭/查看数据真实宿主接线。
- [ ] P4：后端契约、H&R安全联动、错误适配与只读标签扫描。
- [ ] P5：真实结果/统计/历史与已请求归档上限。
- [ ] P6：统一表格、空态、各业务数据页。
- [ ] P7：总览与诊断最后接线。
- [ ] P8：独立复核、全部门禁、本地MP与隔离下载器/视觉验收。
- [ ] 全绿后另行申请推送和QNAP完整包部署；无当前授权不得自动操作。

## 执行纪律

- 复杂前端骨架由pa-responses/GPT-6.1-Sol；细节Luna；机械项DeepSeek/GLM；后端DeepSeek/GLM。连续两次定向修复同阻塞仍失败升级Sol，再交回，禁止无限重试。
- 同一文件一个写入者；模型provider/id按运行时清单解析；主线整合验收与提交。
- 开发前先审阅并提交现有DML基线，之后每个验证通过阶段独立提交，显式路径暂存，不推送。
- HTML基线用户已暂停；旧失真存档不可作视觉依据，不自行恢复存档任务。
- 标签前缀新配置默认🏠，已有显式空串保留；观察新装/恢复默认开，旧配置普通保存不覆盖。
- 模块关闭不干扰其他模块；H&R唯一状态源，授权解除限已确认转移删源与错误删除来源。
- QNAP监控旧计划需核对是否仍运行，不把历史todo in_progress当实时监控证据，不擅自取消真实计划。

## Verification / Preservation

工作目录：`D:/work/project/person/MoviePilot-Plugins`。

精确可重跑门禁（开发阶段执行，本轮文档整理未跑业务测试）：

```bash
cd /d/work/project/person/MoviePilot-Plugins && micromamba run -n base python -X utf8 -m json.tool package.v3.json > /dev/null && micromamba run -n base python -X utf8 -m pytest tests/v3/downloadmanagerlocal -q --tb=short && (cd frontend.v3/downloadmanagerlocal && node --test tests/*.test.mjs && npm run build)
```

保留测试源码、dist、既有场景脚本、日志、失败截图及复核报告，不将它们当过时方案删除；真实验收按docs/mp-local-debug.md。禁止宣称旧295/39数量是本轮新结果。

新提交需在交接记录写工作包、commit、前置commit、测试/退出码与回滚范围；有未完成工作不输出COMPLETE。
