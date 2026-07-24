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

## 迭代 2 进度
- 已新增 LongPT 明确站点适配器及 4 个任务：签到、月度任务领取、喊话反馈、每日抽奖；全部请求测试使用 mock，未执行真实副作用。
- 已新增藏宝阁适配器（此前 checkpoint 已提交），当前加载 3 个任务。
- 已按需求移除 NexusPHP 通用站点暴露：加载器跳过 `sites/nexusphp.py`，配置页不再给未迁移站点回退通用任务；NexusPHP 仅保留能力组合代码。
- 验证：19/19 mock 测试通过；全部 Python AST 解析通过；`git diff --check` 通过。
- 本地 MoviePilot 强制重载成功，日志仅加载藏宝阁、LongPT、青蛙、织梦四个明确站点；配置页和数据页接口均返回 200。
- 当前 checkpoint 待提交；下一步迁移 13City/Ptskit 等明确站点，并先补对应 mock 测试。

## 迭代 3 反思
- 已完成：入口与核心模块已拆分；青蛙、织梦、藏宝阁、LongPT 已是明确站点适配器；通用 NexusPHP 已从注册和配置页移除；配置页/数据页经本地 MoviePilot 验证可用。
- 进展良好：每批站点保持独立小文件，mock 测试和 checkpoint 节奏清晰；当前 19/19 测试通过，未执行真实喊话、抽奖或购买。
- 当前风险：重试锁冲突、retry_notify 无效、反馈超时未接入等审查问题仍未修复；新站点迁移需避免复制未经验证的旧 API；独有站点尚未开始。
- 调整：继续一次只迁移两个明确站点，先覆盖任务元数据和失败/幂等响应，再进行 MP 只读加载验证；暂不执行真实副作用操作。
- 下一优先级：13City 与 Ptskit 适配、对应 mock 测试、加载器/表单回归验证，然后处理审查指出的重试锁冲突。

## 迭代 3 进度
- 已修复审查指出的最高风险：重试锁冲突。`core/engine.py` 的 `retry_failed()` 现在在 `run(retry_only=True)` 返回空列表（锁冲突）时不再清空 `retry_records`，避免 `all([])` 为真导致重试状态被静默丢弃。
- 已新增 13City 适配器（5 任务）：签到、每日/每月做种任务申领、喊话（参考 groupchatzone：勋章校验+发送校验+群聊区啤酒瓶反馈解析）、诸神赐福勋章自动购买。
- 已新增 Ptskit 适配器（3 任务）：签到、魔力值任务2申领、喊话（参考 groupchatzone：魔力值奖励解析+今日已领取幂等）。
- 已新增 7 个 mock 测试覆盖 13City/Ptskit 的匹配、反馈解析、未显示消息失败、勋章已拥有、幂等、任务元数据。
- 验证：26/26 mock 测试通过；全部 Python AST 解析通过；`git diff --check` 通过。
- 本地 MoviePilot 强制重载成功，日志加载 6 个明确站点（藏宝阁 3 / 13City 5 / LongPT 4 / Ptskit 3 / 青蛙 3 / 织梦 2）；配置页和数据页接口均返回 200。
- 未执行真实喊话、购买、抽奖或任务申领；全部请求测试使用 mock。

## 迭代 4 进度（阶段 D 完成）
- 已新增 PTLGS 适配器（2 任务）：签到、喊话（参考 groupchatzone：黑丝娘反馈轮询+损失标识）。
- 已新增 Vicomo/象站 适配器（3 任务）：签到、喊话（参考 groupchatzone：站内信象草反馈）、每日打 Boss（保留 ptautotask 的按星期战斗逻辑）。
- 已新增 5 个 mock 测试覆盖 PTLGS/Vicomo 的匹配、奖励类型识别、损失标识、站内信反馈、任务元数据。
- 验证：31/31 mock 测试通过；全部 Python AST 解析通过；`git diff --check` 通过。
- 本地 MoviePilot 强制重载成功，日志加载 8 个明确站点（藏宝阁 3 / 13City 5 / LongPT 4 / PTLGS 2 / Ptskit 3 / 青蛙 3 / 象站 3 / 织梦 2）；配置页和数据页接口均返回 200。
- 阶段 D（重叠站点迁移）已完成；下一阶段 E 迁移 ptautotask/groupchatzone 独有站点。

当前已存在半成品，必须先审计再改，不要假设已有代码正确。所有对用户的进展使用简体中文。