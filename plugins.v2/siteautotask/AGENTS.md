# siteautotask

合并 `ptautotask`（liuyunfz/bfjy）与 `groupchatzone`（KoWming/madrays）的站点自动任务插件。

## 插件标识

- 目录：`plugins.v2/siteautotask/`
- 入口类（MP 插件 ID）：`SiteAutoTask`
- 配置前缀：`siteautotask_`

## 模块职责

- `__init__.py`：MoviePilot V2 生命周期入口，仅做模块委托
- `base/`：任务元数据、统一结果（TaskResult）、最小站点处理器抽象（ISiteHandler）、任务类型常量
- `core/`：配置、执行引擎、历史、调度、通知、任务键
- `sites/`：每个站点一个模块；按需组合 `capabilities.py` 中的能力
- `ui/`：配置表单（按站点分组+任务独立开关）与运行数据页（任务状态+反馈奖励一体）
- `utils/`：统一请求（session+重试+代理+JSON容错+browser兜底）、反馈奖励解析、HTML 工具
- `tests/`：无真实网络副作用的 mock 测试

## 站点清单（24 个）

### 重叠站点（7，合并双方）
| 站点 | 文件 | 特性 |
|---|---|---|
| 青蛙 | qingwa.py | 签到/喊话/每日1k蝌蚪（动态商品ID） |
| 织梦 | zm.py | 签到/喊话（电力反馈） |
| 藏宝阁 | cangbao.py | 签到/喊话/做种传奇任务 |
| LongPT | longpt.py | 签到/喊话/月度任务/每日抽奖 |
| 13City | city13.py | 签到/喊话（啤酒瓶反馈）/诸神赐福勋章/做种任务 |
| Ptskit | ptskit.py | 签到/喊话（魔力值反馈）/魔力值任务 |
| PTLGS | ptlgs.py | 签到/喊话（黑丝娘反馈+损失标识） |

### 任务申领站点（1）
| 站点 | 文件 | 任务 |
|---|---|---|
| 梓喵 | azusa.py | 每日/七日/月度任务申领（下拉选择） |

### ptautotask 独有站点（10）
| 站点 | 文件 | 任务 |
|---|---|---|
| 蟹黄堡 | crabpt.py | 签到/保种魔王/力争全勤 |
| 躺平 | tangpt.py | 签到/BUG·VIP任务 |
| 财神(CARPT) | car.py | 签到/天天快乐 |
| 财神(Cspt) | cspt.py | 签到/西财神 |
| 大青虫 | cyanbug.py | 签到/喊话（青虫娘三连） |
| 自由农场 | freefarm.py | 签到/每周做种 |
| 垃圾堆 | lajidui.py | 签到/每月保种 |
| NovaHD | novahd.py | 签到/保种 |
| Vc-Lib | vclib.py | 签到/每周上传任务（状态检查+魔力兑换）/每周魔力值任务 |

### groupchatzone 独有站点（5）
| 站点 | 文件 | 特性 |
|---|---|---|
| 天枢 | dubhe.py | 签到/喊话（请求类型验证反馈） |
| 好学 | hxpt.py | 签到/喊话（火花反馈）/精进研习社等任务申领 |
| Moment | moment.py | 签到/喊话（女友反馈） |
| LuckPT | luckpt.py | 签到/喊话（许愿池反馈） |
| RailgunPT | railgunpt.py | 签到/喊话（通用 NexusPHP，无特殊反馈） |

### 勋章续购站点（2，独立 cron）
| 站点 | 文件 | 任务 |
|---|---|---|
| GGPT | ggpt.py | 签到/疯狂星期四勋章（固定 id=35，过期检测） |
| myPT | mypt.py | 签到/勋章续购（下拉选 6 种勋章，过期检测） |

## 契约约束

- `NexusPHP` 仅作为能力组合（`capabilities.py`），不暴露为可配置站点
- 每个任务必须用 `@task_info(..., task_type=TaskType.X)` 标注显式类型
- 任务结果优先返回 `TaskResult`；旧字符串/元组由引擎兼容
- `match()` 按站点 domain 精确匹配，避免同名站点误匹配

## 新增站点

1. 在 `sites/` 新增一个小模块
2. 定义 `Handler`，继承 `CapabilityHandler` 或按需组合能力，实施 `match()`
3. 定义 `Tasks(BaseTask)`，每个任务使用 `@task_info(..., task_type=...)`
4. 任务返回 `TaskResult`
5. 补充 mock 测试后再接入真实站点

## 已知限制

- 重试状态仅存内存（MP 重启会丢失待重试任务）
- `feedback_timeout` 仅在显式轮询的站点（PTLGS）生效
- 勋章续购为简化迁移：仅检测按钮状态（已过期才买），不含到期时间解析/到点定时器/历史记录

## 调度模型

- **主 cron**：执行除 MEDAL 外的所有任务（签到/喊话/申领/抽奖/兑换等）
- **勋章 cron**（`medal_cron`，留空=不启用）：仅执行 MEDAL 任务，过期检测后购买
- **重试服务**：按 `retry_interval` 间隔重试失败任务
- 主 cron 跳过 MEDAL 任务，勋章 cron 跳过非 MEDAL 任务，互不干扰

## 校验

```bash
python3 -m unittest discover -s plugins.v2/siteautotask/tests -v
find plugins.v2/siteautotask -name '*.py' -print0 | xargs -0 -n1 python3 -c 'import ast,sys; ast.parse(open(sys.argv[1]).read())'
```

真实购买、喊话、抽奖测试必须明确确认，默认只使用 mock 或只读请求。
