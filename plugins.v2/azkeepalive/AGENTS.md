# AnimeZ保活

定时访问 AnimeZ 站点，并从种子页筛选候选种子提交下载器，以满足站点访问和下载保活要求。

## Input / Output / Pos
- Input: AnimeZ 站点地址、Cookie、下载器选择、qB/TR 分类标签和任务标签。
- Input: 保活间隔、候选种子筛选条件、Free 限制、超时、代理和自动删除开关。
- Input: `/az_run`、`/az_force` 远程命令，以及配置页立即运行/强制保活开关。
- Output: 访问保活状态、下载保活状态、候选种子提交结果和 H&R 标签清理结果。
- Output: 详情页状态卡、历史记录、通知消息和插件日志。
- Pos: MoviePilot 插件层的 AnimeZ 保活执行器。
- Pos: 入口负责配置和调度，下载器操作、页面解析和页面渲染拆分到 `core/`。

## Files
- `__init__.py`: 插件入口、配置解析、调度注册、远程命令和运行锁控制。
- `requirements.txt`: 插件运行依赖声明。
- `core/downloader.py`: 下载器适配、种子提交、标签清理和已有任务检查。
- `core/form_utils.py`: Vuetify JSON 表单组件辅助函数。
- `core/keepalive.py`: 保活流程编排、访问/下载状态计算和结果落库。
- `core/models.py`: 保活配置、候选种子和状态数据结构。
- `core/page.py`: 详情页状态卡片、历史表格和运行结果渲染。
- `core/scraper.py`: AnimeZ 页面请求、用户信息解析和种子候选提取。
- `core/__init__.py`: core 包标记。

## Key Constraints
- `plugin_version` 必须与 `package.v2.json` 中 `AzKeepAlive.version` 同步。
- 运行入口必须持有 `_run_lock`，避免定时任务、按钮和命令并发提交重复种子。
- 无用户 cron 时生成的随机 cron 写入 `random_cron`，不要在每次重载时漂移。
- 保活访问和下载状态分开记录；HTTP 成功但用户信息解析失败也要谨慎处理访问时间。
- qB H&R 标签查询不要依赖服务端特殊字符过滤，优先本地过滤避免 `&` 编码漏扫。
- 下载器、站点请求失败应记录原因并保持插件可用，不能让整轮任务无保护中断。
- `auto_delete` 只控制删种和数据；达标摘标签是默认行为。
- Cron 无效时跳过定时注册但保留手动服务能力。
