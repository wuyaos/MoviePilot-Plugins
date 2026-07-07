# PT站点自动签到

自动签到/登录站点，支持自定义站点、CookieCloud 同步、Cookie 失效补取重试和部分站点验证码签到适配。

## Input / Output / Pos
- Input: MoviePilot 站点配置、自定义站点文本、CookieCloud 数据、`EventType.PluginAction` 命令与调度器触发。
- Input: `sign_sites` 与 `login_sites` 分别控制签到和模拟登录站点集合。
- Input: `retry_keyword` 控制本日后续任务只重试命中关键词的站点。
- Output: 站点签到/模拟登录结果、每日历史数据、通知消息和详情页记录。
- Output: Cookie 失效时触发 `site_refresh` 事件，并在 CookieCloud 补取成功时回写 Cookie。
- Pos: PT 站点日常签到编排层；发现 Cookie 失效后对接 SiteRefresh。
- Pos: 通用签到/登录逻辑在入口，站点特殊逻辑下沉到 `sites/`。

## Files
- `__init__.py`: 插件入口、配置页、调度注册、签到/登录主流程、CookieCloud 补取和事件处理。
- `requirements.txt`: 验证码识别和 HTTP 回退依赖声明。
- `helper/attendance_captcha_helper.py`: NexusPHP attendance.php 验证码签到通用流程。
- `helper/http_helper.py`: curl-cffi HTTP 客户端与 SSL 回退处理。
- `helper/ocr_helper.py`: OCRHelper / ddddocr 识别封装。
- `helper/__init__.py`: helper 包标记。
- `sites/`: 各 PT 站点的 match/signin/login 特化适配。
- `sites/AGENTS.md`: 站点适配子目录约束说明。
- `sites/__init__.py`: sites 包标记，供 `ModuleHelper.load()` 扫描。

## Key Constraints
- `plugin_version` 必须与 `package.v2.json` 中 `AutoPtCheckin.version` 同步。
- CookieCloud 仅作为补取/同步来源；空 Cookie 或 Cookie 失效重试后要更新当前 `site_info["cookie"]`。
- MoviePilot 站点 Cookie 回写使用 `self.siteoper.update(site_id, {"cookie": cookie})`，自定义站点不写 SiteOper。
- 同一轮签到和登录共享 `refresh_triggered_site_ids`，避免同站点重复触发 SiteRefresh。
- 特定站点适配放入 `sites/`，通过 `match(url)` 加载，不在主流程堆叠站点判断。
- 服务器繁忙、维护、403、网关错误等站点异常不应误报 Cookie 失效。
- `checkin_force` 要同时覆盖签到和登录，注意 `_clean` 在两次 `__do()` 前的恢复。
- 提交前至少执行 `python3 -c "import ast; ast.parse(open('plugins.v2/autoptcheckin/__init__.py').read())"`。
