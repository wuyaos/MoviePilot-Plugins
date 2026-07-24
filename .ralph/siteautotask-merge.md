# SiteAutoTask 合并开发循环

目标：在 `/mnt/d/work/project/person/MoviePilot-Plugins/plugins.v2/siteautotask/` 完成可扩展、模块化的单体插件，合并 ptautotask 与 groupchatzone：
- groupchatzone 的喊话反馈与奖励解析
- ptautotask 的多任务模型
- 按站点分组、每个任务独立开关的配置页
- 任务状态+反馈奖励一体的数据页
- 插件目录、插件 ID、配置前缀全部使用小写 `siteautotask`
- 避免单一大文件：入口、核心执行、调度、历史、UI、基础能力、站点适配分离

必须遵守的交付节奏：
1. 先修正/冻结架构，不继续堆站点代码直到架构可测试。
2. 分阶段实现，每阶段完成后必须：
   - 多个 mock 测试（请求、cookie失效、任务结果、反馈解析、配置/历史）
   - 少量真实情况测试（优先只读 GET；涉及真实购买/喊话必须明确说明并避免重复副作用）
   - 本地 MoviePilot 调试（插件加载、表单/数据页/服务注册；若服务未运行要记录阻塞）
   - 阶段性 code review；可用多个 subagent 并行审查，主代理统一修复
3. 只在验证通过后进入下一阶段；失败则先修复，不得标记阶段完成。
4. 每轮保持一个清晰的小范围变更，避免一次生成巨型文件。注意本地提交，避免无法回溯

阶段规划：
A. 现状盘点与架构收敛：检查当前半成品，确保 `__init__.py` 瘦身，拆出 core/engine.py、scheduler.py、history.py、config.py、ui/form.py、ui/page.py；定义 TaskResult/task_type、能力模块、站点注册契约；清理设计文档与路径命名。
B. 基础层测试：完成 request/session/json容错、TaskResult、task_info、站点加载器、能力 mixin；建立 tests/ 或可运行的 mock 测试脚本；运行 ast/pytest。
C. 第一批站点：先完成青蛙、织梦、通用 NexusPHP；站点适配独立小文件；青蛙福利动态获取商品ID但禁止测试重复购买；mock API 响应和 cookie失效响应。
D. 第二批站点：迁移双方重叠站点（藏宝阁、LongPT、13City、Ptskit、PTLGS、Vicomo），每批少量；保留反馈解析与特殊任务。
E. 独有站点迁移：按小批次迁移 ptautotask/groupchatzone 独有站点；每批验证加载与任务元数据。
F. UI：完成按站点分组、任务独立开关的配置页；完成任务状态+反馈奖励的数据页；mock 组件结构并尝试 MP 本地页面接口。
G. 集成：主入口委托、服务/调度、通知、历史、重试、配置持久化；运行完整 mock 测试。
H. 多 subagent code review：至少并行审查架构/安全与请求、MoviePilot V2 契约/UI、站点迁移/测试覆盖；主代理修复发现的问题。
I. 最终验证：所有 Python 文件 ast.parse；pytest；插件加载/表单/数据页/服务接口；本地 MP 调试；更新 package.v2.json、插件 AGENTS.md、版本历史；检查 git diff 与残余风险。

当前已存在半成品，必须先审计再改，不要假设已有代码正确。所有对用户的进展使用简体中文。