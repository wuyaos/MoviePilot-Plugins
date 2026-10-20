# RuntimePatchGuard (V3)

## Structure

- `__init__.py`: V3 插件入口（`app.sdk.plugin._PluginBase`）；`init_plugin` 时对宿主 `SiteParserBase._get_page_content` 做内存 monkey-patch，加总时长守卫。

## 设计要点（不可从代码推断的部分）

- 背景：MP V3 宿主站点解析请求只有 per-request `timeout=60`，缺总时长守卫；慢站/黑洞会挂起调用线程并拖垮调度批次（2026-10-19 事故）。旧方案是手工改容器内文件，MP 升级即丢失。
- 方案：不改宿主文件，只在插件初始化时内存包装原方法。每次调用在独立 daemon 线程执行原实现，`join(timeout)` 超时后调用方返回空串。不用共享线程池——池会被黑洞请求占满导致全体站点解析瘫痪。
- 泄漏取舍：超时后 worker 线程仍阻塞在原请求上，直到底层 socket 失败才退出；因官方已有 `timeout=60`，泄漏是有界的且仅在病态站点出现。
- 幂等与升级：以函数属性 `_runtimepatchguard_wrapped` 为标记，重复 init 不会二次包装；MP 升级后原方法重新加载，插件 init 自动重新应用；官方若内置总时长守卫，本插件仍会包装（无冲突，可手动禁用）。
- `stop_service`/禁用时会恢复原始方法。

## Constraints

- 不要把补丁改成写宿主文件；不要改用共享 executor。
- `from app.modules.indexer.parser import ...` 是宿主模块的延迟导入，属预期（补丁目标本身），不违反 V3 `app.sdk` 导入约定。
