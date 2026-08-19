# BakaBTBrush

MoviePilot V2 的 BakaBT Freeleech 刷流插件。

## 插件标识

- 目录：`plugins.v2/bakabtbrush/`
- 入口类：`BakaBTBrush`
- 配置前缀：`bakabtbrush_`
- 元数据：根目录 `package.v2.json` 的 `BakaBTBrush`

## 结构

- `__init__.py`：MoviePilot 生命周期、配置页、调度、运行锁和通知接线。
- `core/config.py`：配置模型与校验。
- `core/cookie.py`：手动 Cookie 与 CookieCloud 获取、配置回写。
- `core/models.py`：BakaBT 种子、账户、运行结果等数据模型。
- `core/scraper.py`：BakaBT 浏览页、详情页、账户页和 `.torrent` 解析。
- `core/downloader.py`：MoviePilot qB 下载器选择、槽位、流量、添加与确认。
- `core/state.py`：MoviePilot `get_data`/`save_data` 状态与历史裁剪。
- `core/runner.py`：单轮线性执行流程。
- `core/page.py`：四张总览卡片和运行日志表。
- `tests/`：脱离真实 Cookie、qB 和 MoviePilot 宿主的离线测试。

## 业务边界

- 只处理 BakaBT 页面明确标记为 `.icon.freeleech` 的种子。
- 仅按发种时间与体积（MB）筛选；`0` 代表该阈值不限制。
- qB 连接只使用 MoviePilot 已配置下载器，分类固定默认 `刷流`，标签默认 `bakabt,刷流`。
- BakaBT 下载流程默认最多两个；下载完成后继续由 qB 保种。
- Cookie 手填优先，空值时从 CookieCloud 获取并回写本插件配置；不得写入日志、状态、通知或数据页。
- 不做伪造流量、绕过下载器队列、自动删种或外部 Webhook 通知。

## 状态与页面

- 使用 `_PluginBase.get_data/save_data` 保存状态，不引入 SQLite。
- 顶部四卡：BakaBT 流量、qB 刷流流量、历史下载种子数、上次运行。
- 日志列：时间、状态、种子、推送、详情；最多显示最近 20 条。

## 校验

```bash
python3 -m py_compile plugins.v2/bakabtbrush/__init__.py
python3 -m compileall plugins.v2/bakabtbrush
python3 -m pytest plugins.v2/bakabtbrush/tests -q
python3 -m json.tool package.v2.json >/dev/null
git diff --check
```
