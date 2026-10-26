# DownloadManagerLocal

下载中心：MoviePilot V3 七模块整合插件（v3.5.0）。

## 模块
- **转移做种**（`service/transfer.py` + `service/transfer_pipeline.py`）：做种转移与同步删除，内置做种校验子功能，删源前经 H&R 保护边界
- **命名补刀**（`service/rename.py` + `service/rename_events.py`）：下载完成事件重命名与手动补刀，含历史/归档
- **站点标签与分类**（`service/site_tag.py`）：下载任务站点标签、TMDB 二级分类、剧名标签补全
- **H&R 助手**（`service/hr/`）：站点 YAML 规则、任务评估、每日汇总；`guard.py` 提供跨模块保护边界（SKIP_PATHS）
- **自动删种**（`service/autoremove/`）：条件规则删种（时长/标签/MP 限定），删前经 H&R guard
- **失败清理**（`service/failclean/`）：整理失败删源与重复下载残留清理
- **上传限速**（`service/upload_limit_worker.py`）：站点策略上传限速

## 结构
- `api.py` / `controller/`：API 路由与 handlers（33 个端点，前缀 `api_`）
- `service/`：各模块业务逻辑；`scheduler/` 经 facade 统一注册定时任务
- `model/`：Pydantic 响应模型（注意：响应模型必须含 `success` 字段，缺省会 500）
- `dist/`：前端联邦构建产物（源码在仓库根 `frontend.v3/downloadmanagerlocal/`，vite outDir 指向此处）
- `ai_spec/plugin_context.md`：给 AI 的插件上下文文档（与代码同步维护）
- `adapter/`、`utils/`：宿主适配与工具

## 约束
- 前端改动需在 `frontend.v3/downloadmanagerlocal/` 构建（`npm run build`），dist 随插件目录提交
- dev 实例 reload 必须用类名 id `DownloadManagerLocal`（小写 id 会假成功、路由表不刷新）
- 版本三处同步：`__init__.py` plugin_version、`plugin.json`、根 `package.v3.json`
