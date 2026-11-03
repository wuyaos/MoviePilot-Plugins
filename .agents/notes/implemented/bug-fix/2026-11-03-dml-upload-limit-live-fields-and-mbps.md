# Agent Note: DML 上传限速实时字段与 MB/s 展示

Status: implemented

## Problem

上传限速模块的下载器卡片长期显示「状态：当前接口未提供 / 全局限速 — / 更新时间 当前接口未提供」。前端模板期望 `status/connected/global_limit_kib/updated_at` 字段，但 `run_upload_limit_cycle` 的 downloaders 条目从未生成它们；界面同时把速度与限速一律写死为 KiB/s，与用户阅读习惯不符。

## Decision

- `run_upload_limit_cycle` 在两个 summary 构建路径（downloader-only 与完整 summary）注入 `_downloader_live_fields(context, error)`：`connected` 以扫描 context 存在与否为准；`status` 区分 正常/异常/未轮询；`global_limit_kib` 仅在 `upload_enabled` 且拿到 `upload_limit_bps` 时换算给出，否则 `None`；`updated_at` 只在真实轮询过（context 存在且 `polled_at > 0`）时给本地时间字符串。数据不可用一律 `None/空串`，不回退周期时间伪造“更新时间”。
- MB/s 仅是展示层换算：Page.vue `formatUploadRate` 统一 `(rate/1024/1024).toFixed(2) MB/s`，卡片全局限速、已分配额度、配置摘要（controller/config_summary.py）按 KiB→MB 换算显示；Config.vue 上传限速输入经 `uploadDownloaderLimit`/`setUploadDownloaderLimit`/站点规则读写函数做 MB↔KiB 双向换算（×1024，写回 floor）。存储契约（`*_kib` 字段、qB bps 接口）完全不变。
- 未轮询下载器（配置选择但无服务实例或本轮未扫描）显示「未轮询」而不是「未连接」，避免与连接失败混淆。

## Alternatives considered

1. 后端直接输出 MB 单位字段：需要迁移存储与 qB 接口口径，破坏 `*_kib` 契约与历史记录，收益仅是展示单位，放弃。
2. 前端各模板自行除 1024：换算逻辑散落、四舍五入口径不一，集中在既有格式化函数与读写函数中处理。

## Consequences

升级后卡片首次渲染仍可能是「未轮询」，待下一轮限速周期或手动执行后出现实时字段；扫描失败的下载器状态为「异常」并保留 error 文本。KiB 输入值经 MB 换算写回会有 ±1023 bps 以内的整除误差，对限速控制无实质影响。

## Testing

仓库根目录 `PYTHONIOENCODING=utf-8 C:/app/scoop/apps/micromamba/2.9.0-0/base/envs/mp3/python.exe -m pytest tests/v3/downloadmanagerlocal/ -q`：1008 passed（含实时字段三态/换算/未轮询新用例）。`cd frontend.v3/downloadmanagerlocal && node --test tests/*.test.mjs && npm run build`：160 passed、构建通过。Config.vue 保持纯 CRLF；config-density directives 契约在提取处统一归一 `\r\n`→`\n` 后比对 fixture（内容契约不受行尾影响）；H&R 业务脚本字节锁更新为授权展示改动后的新 SHA。

## Related notes

检索 implemented 未发现同主题笔记；[空标签清理与执行反馈](2026-11-02-dml-empty-tags-and-execution-feedback.md) 讨论标签清理契约，互不替代。
