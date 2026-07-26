# api/ REST API 路由

## 一句话职责
为 `_PluginBase.get_api()` 构建路由表，统一响应格式，消除原插件 40 处带/不带前导斜杠的 dict 重复。

## Input / Output / Pos
- **Input**：CoverGen 插件实例（提供 `api_*` 方法引用）
- **Output**：`List[Dict]` 路由清单（含 `path`/`endpoint`/`auth`/`methods`/`summary`）
- **Pos**：`plugins.v2/covergen/api/`，被 `__init__.py` 的 `get_api()` 调用

## Files
- `endpoints.py` — `build_api_routes(plugin)` 列表驱动循环；`ok()` / `err()` 统一响应辅助

## 更新条件
新增/删除 API 端点时更新 `endpoints.py` 中的 `specs` 列表，无需手动维护带斜杠/不带斜杠的两份。
