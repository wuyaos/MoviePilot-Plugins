# SiteAutoTask 单体插件设计文档

> 合并 ptautotask（bfjy）+ groupchatzone（KoWming）为单体插件。
> 目标：少装一个插件；groupchatzone 反馈解析 + ptautotask 多任务；数据页（任务状态+反馈奖励一体）；配置页按站点分组+任务各自开关。

## 一、插件元数据

| 字段 | 值 |
|---|---|
| plugin_id | SiteAutoTask |
| plugin_name | 站点自动任务 |
| plugin_desc | 站点周期任务合集：签到、喊话、领勋章、抽奖、兑换、任务申领，并解析喊话反馈奖励 |
| plugin_version | 1.0.0 |
| plugin_author | wuyaos（合并自 liuyunfz/bfjy 与 KoWming/madrays） |
| plugin_config_prefix | siteautotask_ |
| plugin_order | 24 |
| auth_level | 2 |
| plugin_icon | 自选 |

## 二、目录结构

```
plugins.v2/siteautotask/
├── __init__.py              # 主类 SiteAutoTask(_PluginBase)：init/get_form/get_service/get_page/get_command/get_api/stop_service + 执行引擎
├── base/
│   ├── __init__.py
│   ├── nexusphp.py          # 统一的 NexusPHP 请求层（吸收 groupchatzone 的 session+重试+browser 兜底，修掉 ptautotask 的 5 秒超时/json 不容错）
│   ├── site_handler.py      # ISiteHandler 基类：match/get_feedback/get_rewards/get_user_privileges + 喊话/签到/领勋章/兑换/抽奖 钩子
│   ├── base_task.py         # BaseTask：任务元数据收集（吸收 ptautotask 的 @task_info 反射机制）
│   └── decorator.py         # @task_info(label, hint) 装饰器
├── sites/
│   ├── __init__.py          # 站点加载（pkgutil 扫描，统一 Handler+Tasks 契约）
│   ├── qingwa.py            # 青蛙：Handler(QingwaHandler) + Tasks(daily_shotbox/daily_checkin/daily_exchange)
│   ├── zm.py                # 织梦：Handler(ZmHandler，含邮件时间调度/反馈) + Tasks(daily_shotbox/daily_checkin/medal_bonus)
│   ├── cangbao.py           # 藏宝阁
│   ├── longpt.py            # LongPT
│   ├── city13.py            # 13City
│   ├── ptskit.py            # Ptskit
│   ├── ptlgs.py             # PTLGS
│   ├── vicomo.py            # （已移除：象站关站）
│   ├── nexusphp.py          # 通用 NexusPHP 兜底 Handler
│   ├── ...                  # 其余站点（car/crabpt/cspt/cyanbug/freefarm/lajidui/lgs/novahd/vclib/tangpt 等）
│   ├── hxpt.py              # 好学（groupchatzone 独有）
│   ├── dubhe.py             # 天枢（groupchatzone 独有）
│   ├── moment.py            # Moment
│   ├── luckpt.py            # LuckPT
│   ├── railgunpt.py         # RailgunPT
│   └── dqc.py               # 大青虫（含 get_user_privileges）
├── utils/
│   ├── __init__.py
│   ├── request.py           # 统一请求工具（session 单例 + 重试 + 代理 + browser 兜底 + json 容错）
│   ├── content_filter.py    # lxml/re 解析工具
│   ├── feedback.py          # 反馈奖励解析（NotificationIcons + 奖励类型识别）
│   └── schedule.py          # 织梦邮件时间调度计算
├── form.py                  # 配置页表单构造（站点分组卡片 + 任务开关 + 全局设置）
└── AGENTS.md                # 结构说明
```

## 三、统一站点契约（核心设计）

### 设计原则
两个插件的抽象合并为**单文件双类**：每个站点文件含 `Handler(ISiteHandler)` + `Tasks(BaseTask)`。
- `Handler` 负责 HTTP 请求 + match 路由 + 反馈解析（来自 groupchatzone）
- `Tasks` 负责任务定义 + @task_info 元数据（来自 ptautotask），任务方法调用 `self.client.xxx()`

### 3.1 ISiteHandler 基类（base/site_handler.py）

```python
class ISiteHandler(metaclass=ABCMeta):
    def __init__(self, site_info: dict):
        self.site_info = site_info
        self.site_url = site_info["url"].strip()
        self.site_name = site_info["name"].strip()
        self.site_cookie = site_info["cookie"].strip()
        self.ua = site_info.get("ua", "").strip()
        self.render = site_info.get("render", False)
        self.use_proxy = site_info.get("use_proxy", True)
        self.session = build_session(self.site_cookie, self.ua, self.use_proxy)
        # URL 常量
        self.url_shoutbox = self.site_url + "/shoutbox.php"
        self.url_ajax = self.site_url + "/ajax.php"
        self.attendance_url = self.site_url + "/attendance.php"
        self.messages_url = self.site_url + "/messages.php"
        self._last_message_result = None  # 反馈缓存

    @abstractmethod
    def match(self) -> bool: ...           # 路由判断

    def get_feedback(self, message=None) -> Optional[Dict]:
        """返回 {site, message, rewards:[{type,description,amount,unit,is_negative}]}"""
        return None

    # —— 可选业务方法（站点按需实现/重写）——
    def send_messagebox(self, message, callback=None) -> Tuple[bool, str]: ...
    def attendance(self) -> str: ...
    def claim_task(self, task_id, callback=None) -> str: ...
    def get_message_list(self, callback=None): ...
    def buy_daily_bonus(self) -> Tuple[bool, str]: ...      # 青蛙每日福利
    def daily_lottery(self) -> Tuple[bool, str]: ...         # LongPT 每日抽奖
    def buy_blessing(self) -> Tuple[bool, str]: ...          # 13City 勋章
    def medal_bonus(self) -> str: ...                        # 织梦勋章奖励
    def get_user_privileges(self) -> Dict: ...               # 大青虫 VIP/彩虹ID
    def get_latest_message_time(self) -> Optional[str]: ... # 织梦邮件时间
```

### 3.2 BaseTask + @task_info（base/base_task.py + base/decorator.py）

吸收 ptautotask 机制，绑定到 client（Handler 实例）：

```python
@task_info(label="{client_name}喊话", hint="执行{client_name}站点的喊话任务")
def daily_shotbox(self): ...

class BaseTask:
    def __init__(self, client): self.client = client
    def get_registered_tasks(self) -> List[Dict]:
        # 反射收集子类中带 _task_meta 的方法，返回 [{id, label, hint, func}]
```

任务 id = `站点文件名_方法名`（如 `qingwa_daily_exchange`），作为配置开关 key。

### 3.3 站点文件标准结构

```python
class QingwaHandler(ISiteHandler):
    def match(self) -> bool: return "青蛙" in self.site_name
    def send_messagebox(self, message, callback=None): ...   # 青蛙特化
    def buy_daily_bonus(self) -> Tuple[bool, str]: ...       # 青蛙每日福利

class Tasks(BaseTask):
    def __init__(self, cookie): super().__init__(QingwaHandler(cookie))  # 注意：Tasks 绑定 Handler
    @task_info(label="青蛙喊话")
    def daily_shotbox(self): ...
    def daily_checkin(self): return self.client.attendance()
    @task_info(label="每日1k蝌蚪")
    def daily_exchange(self): return self.client.buy_daily_bonus()
```

> **契约统一要点**：Tasks 的 client 是 Handler 实例（不是旧的 NexusPHP 子类）。
> 旧 ptautotask 站点迁移时，把 `class Xxx(NexusPHP)` 改为 `class XxxHandler(ISiteHandler)`，业务方法签名对齐。

## 四、配置数据结构

### 4.1 持久化配置（update_config）

```python
{
  "enabled": bool,            # 启用
  "cron": "30 9,21 * * *",    # 定时表达式（支持 cron / 小时间隔 / "2.3/9-23"）
  "onlyonce": bool,
  "notify": bool,              # 通知开关
  "history_days": 30,          # 历史保留天数
  "use_proxy": bool,           # 代理
  "get_feedback": bool,        # 获取喊话反馈
  "feedback_timeout": 5,
  "retry_count": 2,            # 失败重试次数
  "retry_interval": 10,        # 重试间隔(分钟)
  "retry_notify": bool,
  "chat_sites": ["站点id"],    # 启用的站点（来自 MP 站点库 + 自定义站点）
  "task_switches": {           # 每站点每任务开关（key=task_id）
     "qingwa_daily_shotbox": true,
     "qingwa_daily_exchange": true,
     "zm_medal_bonus": false,
     ...
  },
  # 织梦独立调度状态
  "zm_mail_time": "...",
  "last_zm_execution_time": "...",
  "zm_execution_cooldown": 600,
  # 精细重试状态
  "failed_messages": [...],
  "current_retry_count": 0,
  "next_retry_time": "...",
}
```

### 4.2 配置页结构（form.py）

```
VForm
├── VCard「全局设置」
│   ├── 启用 / 通知 / 仅一次 / 获取反馈 / 代理
│   ├── cron 表达式
│   ├── 重试次数 / 重试间隔 / 历史天数
│   └── 反馈超时
├── VCard「站点选择」（VSelect multiple，选 MP 站点库中的站点）
└── VCard「站点任务设置」  ← 动态生成
    └── 每个选中站点一个 VCard 子卡片
        ├── 标题：站点名 + 图标
        └── VRow × N：该站点所有任务，每任务一个 VSwitch(model=task_id)
```

> 配置页用 `get_form` 动态读取 `chat_sites` + 站点任务列表生成卡片，
> 未选中的站点不展示任务卡片（减少干扰）。

## 五、执行引擎（__init__.py）

### 5.1 主执行流程 `__do_tasks`

```
1. 获取选中站点列表（chat_sites → MP site_info，带 cookie/ua/render）
2. 对每个站点：
   a. get_site_handler(site_info)  # match 路由
   b. 获取该站点的 Tasks 实例（用 handler 作为 client）
   c. handler.get_registered_tasks()  # 拿到任务列表
   d. 对每个任务：
      - 检查 task_switches[task_id] 开关
      - 执行 task.func()
      - 收集 status + feedback（若 get_feedback 开启）
3. 织梦特殊处理：若选中织梦，走独立 send_zm 路径（邮件时间调度+冷却）
4. 失败任务进入 _failed_messages，安排精细重试
5. 记录 history run（含任务状态+反馈奖励）
6. 合并发送通知（按站点分组，含反馈奖励图标）
```

### 5.2 织梦独立调度

- `send_zm_site_messages`：基于 `get_latest_message_time` 计算下次执行时间（24h 后）
- 冷却机制 `zm_execution_cooldown`
- `get_service` 注册独立 date 触发器

### 5.3 精细重试

- `_failed_messages` 存储失败任务详情
- `_execute_retry` 按间隔重跑失败任务
- `_prune_failed_messages` 防内存增长

## 六、数据页（get_page）

### 6.1 数据结构（save_data）

```python
"history": [
  {
    "date": "2026-07-24 18:00:00",
    "records": [
      {
        "site": "青蛙", "domain": "qingwapt.com",
        "task_id": "qingwa_daily_exchange", "task_label": "每日1k蝌蚪",
        "status": "购买成功。",  # ✅
        "feedback": {            # 可选，喊话任务才有
          "message": "蛙总，求上传",
          "rewards": [{"type":"上传量","description":"获得10G上传","amount":"10","unit":"GB"}]
        }
      },
      ...
    ],
    "retry": {"current":1,"max":2}  # 可选
  }
]
```

### 6.2 数据页展示

```
VCard「最近运行」
├── 运行时间 + 成功/失败统计
└── VTable（按站点分组）
    ├── 站点 | 任务 | 状态 | 反馈奖励
    └── 反馈奖励列：图标+描述（上传量⬆️/魔力✨/电力⚡...）
```

最近 10 条运行记录分页展示，超 history_days 自动清理。

## 七、迁移清单

### 7.1 重叠站点统一（8 个）
| 站点 | Handler 来源 | Tasks 来源 | 备注 |
|---|---|---|---|
| 青蛙 | groupchatzone（带 buy_daily_bonus） | ptautotask（daily_exchange） | buy_daily_bonus 改用动态 getItems |
| 织梦 | groupchatzone（邮件时间+反馈） | ptautotask（medal_bonus） | 保留独立调度 |
| 藏宝阁/LongPT/13City/Ptskit/Ptlgs | groupchatzone 的反馈 + ptautotask 的任务 | 合并 |

### 7.2 ptautotask 独有站点迁移（按新契约重写）
蟹黄堡/自由农场/垃圾堆/躺平/财神/Car/Crabpt/Cspt/Cyanbug/Lgs/NovaHD/Vclib/Tangpt/City13

### 7.3 groupchatzone 独有站点迁移
天枢/好学/Moment/LuckPT/Dubhe/大青虫（含 get_user_privileges）

## 八、关键改进（合并时修复）

1. **统一请求层健壮性**（修 ptautotask 短板）：
   - session + Retry 适配器 + 15 秒超时
   - `response.json()` 容错：非 JSON / 302 跳登录 → 返回明确错误"cookie 失效"
   - browser 渲染兜底（render 站点）

2. **青蛙福利购买动态化**：
   - 从 `GET /api/bonus-shop/getItems` 按名称匹配"每日福利"取 id
   - 不再硬编码 id=28（虽然当前仍有效，防未来变化）

3. **配置页按站点分组**：用户选站点后动态展开该站点任务卡片

4. **数据页一体展示**：任务状态 + 反馈奖励同表

## 九、版本规划

- v1.0.0：合并骨架 + 重叠 8 站点 + ptautotask 全部站点迁移 + 数据页
- v1.0.1+：groupchatzone 独有站点补齐 + bug 修复
```
