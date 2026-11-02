# Agent Note: DML 空标签定义清理与删种执行反馈

Status: implemented

## Problem

用户要求清理的是关联种子为零的标签，而不是从现有种子剥离标签。旧清理列表只聚合种子标签，无法发现空的 qB 全局标签定义。自动删种按钮只修改未被弹窗使用的状态，不发送执行请求；观察轮次的零候选和读取失败也没有通知，用户无法区分未执行与执行后无候选。

## Decision

- 标签扫描同时读取 qB 全局标签定义及全量种子关联，只有零关联标签进入可选候选。执行依赖扫描快照，并再次核实全局定义和关联；只调用删除标签定义接口，永不调用种子标签移除接口。关联读取失败时不把未知当作零。旧快照不能用于新执行语义，升级后应重新扫描。
- qB 的 TorrentInfoList 和 TagList 通过 Sequence 协议读取（排除字符串/字节串），不要求内置 list；这是实际客户端的 UserList 契约。扫描错误保持 downloader/message 结构，TagCleanupScanResult.errors 同步为字典列表，保证读取失败也能正常序列化。
- 保留现有观察零写入边界。自动删种在 notify 开启时，对有候选、零候选、配置错误和读取失败均推送观察摘要；未开启通知仍不发送。
- 执行按钮打开现有样式的确认弹窗，区分观察预览与删除文件风险；取消不请求，确认调用 autoremove_run，并用运行状态阻止连续确认重复请求。

## Alternatives considered

1. 沿用临时标签归属分类和种子标签剥离：能回收历史临时标签，但与用户确认的零关联清理不一致，且会改动种子业务标签，因此不再沿用。
2. 点击按钮立即执行：接线最少，但当前配置可能删除文件，必须保留可取消且说明实际动作的确认步骤。
3. 观察模式只对非空候选通知：噪声更小，但零候选和下载器读取失败仍表现为完全无反馈，不能满足本次要求；仍由 notify 开关控制通知。

## Consequences

在用标签不再可清理，空标签扫描增加一次全局定义读取，执行时再次查询关联。qB 查询与删除并不具备原子性，用户同时新增关联仍有竞态窗口，不能宣称跨系统事务。Transmission 不提供该全局标签清理。自动删种标准、阈值、H&R 门和生产配置不变；notify 开启时零候选观察轮次也会产生消息。

## Testing

仓库根目录运行 `PYTHONIOENCODING=utf-8 C:/app/scoop/apps/micromamba/2.9.0-0/base/envs/mp3/python.exe -m pytest tests/v3/downloadmanagerlocal/ -q`：990 passed。`cd frontend.v3/downloadmanagerlocal && node --test tests/*.test.mjs && npm run build`：160 passed，构建通过。真实 Vue 组件经替身 API 点击覆盖观察开关、弹窗、取消和双击确认；下载器反例覆盖扫描后新增关联、读取失败、快照失效和观察零写入。不使用生产数据试删。

标签读取契约回归使用真实 qbittorrentapi.TorrentInfoList / TagList、UserList 及异常返回；真实扫描结果经过 TagCleanupScanResult 校验和 JSON 序列化，覆盖成功、全失败及部分失败。上述后端命令当前为 1002 passed；失败时仍不生成可删除候选。此次未改前端，也不修改自动删种行为，不触发生产删种。

## Related notes

检索 proposed/implemented/rejected 未发现同主题笔记。[转移现场重判](2026-11-02-dml-transfer-reconciliation.md) 仅讨论转移协调，互不替代。
