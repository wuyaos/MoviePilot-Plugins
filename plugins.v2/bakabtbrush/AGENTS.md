# BakaBTBrush

MoviePilot V2 的 BakaBT Freeleech 刷流插件。

## 插件标识

- 目录：`plugins.v2/bakabtbrush/`
- 入口类：`BakaBTBrush`
- 配置前缀：`bakabtbrush_`
- 元数据：根目录 `package.v2.json` 的 `BakaBTBrush`

## 结构

- `__init__.py`：MoviePilot 生命周期、调度、运行锁和 UI/通知接线。
- `core/config.py`：严格范围语义与自动删种配置模型。
- `core/form.py`：分区式 Vuetify 配置页。
- `core/cookie.py`：手动 Cookie 与 CookieCloud 获取、配置回写。
- `core/models.py`：BakaBT 种子、账户和 qB 快照模型。
- `core/scraper.py`：BakaBT 浏览页、详情页、账户页和 `.torrent` 解析。
- `core/filtering.py`：Today、Freeleech、体积与发布时间筛选。
- `core/downloader.py`：MoviePilot qB 下载器查询、槽位、添加、确认与删除。
- `core/cleanup.py`：自动删种条件评估及安全执行。
- `core/state.py`：MoviePilot 状态、详情缓存、运行与删除历史。
- `core/runner.py`：单轮执行流程，支持不增删 qB 的一次性试运行。
- `core/notification.py`：本地时区通知和详情链接。
- `core/presentation.py`：通知与数据页共用时间格式。
- `core/page.py`：总览、当前下载流程、链接化运行历史和删除历史。
- `tests/`：脱离真实 Cookie、qB 和 MoviePilot 宿主的离线测试。

## 业务边界

- 只处理 BakaBT 页面明确标记为 `.icon.freeleech` 的种子。
- 仅按发种时间与体积（MB）筛选；单值表示最大值、完整双值表示区间、`0`/空表示不限制，不接受省略范围端点。
- qB 连接只使用 MoviePilot 已配置下载器，分类固定默认 `刷流`，标签默认 `bakabt,刷流`。
- BakaBT 下载流程默认最多两个；自动删种默认关闭，且只处理分类匹配、含 `bakabt` 标签并存在插件添加记录的任务。
- “试运行一次”是独立一次性开关：执行同样的槽位、Freeleech、时间和体积复核，但不下载 `.torrent`、不调用 qB 添加或删除，运行后自动关闭。
- Cookie 手填优先，空值时从 CookieCloud 获取并回写本插件配置；不得写入日志、状态、通知或数据页。
- 自动删种满足任一启用条件即触发；排除标签优先；促销过期只有实时详情明确确认后才能删除；默认保留文件。
- 不做伪造流量、绕过下载器队列或外部 Webhook 通知。

## 状态与页面

- 使用 `_PluginBase.get_data/save_data` 保存状态，不引入 SQLite。
- 顶部四卡：BakaBT 流量、qB 刷流流量、历史下载种子数、上次运行。
- 数据页区分当前未完成下载、最近 20 条运行历史和最近 100 条自动删除历史；新记录种子名链接至详情页；窗口高度与可见条目数可配置，超出后内部滚动。
- 所有时间以 UTC 存储，通知和页面按 MoviePilot `settings.TZ` 显示。

## 校验

```bash
python3 -m py_compile plugins.v2/bakabtbrush/__init__.py
python3 -m compileall plugins.v2/bakabtbrush
python3 -m pytest plugins.v2/bakabtbrush/tests -q
python3 -m json.tool package.v2.json >/dev/null
git diff --check
```
